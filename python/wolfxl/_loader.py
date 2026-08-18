"""Sprint Κ Pod-β — file-format dispatch + unified path/bytes loader.

Single entry point for ``wolfxl.load_workbook`` that accepts:

* ``str`` / :class:`os.PathLike` paths
* raw ``bytes`` / ``bytearray`` / ``memoryview`` blobs
* file-like objects exposing ``.read() -> bytes`` (e.g. :class:`io.BytesIO`)

It sniffs the file format (xlsx / xlsb / xls / ods / unknown) via magic
bytes and dispatches to the appropriate Rust backend on the
:class:`Workbook`. The format string is also stashed on
``Workbook._format`` so Python-layer guards (cell.font on .xlsb, etc.)
can produce consistent error messages without re-sniffing.

The Rust ``_rust.classify_file_format`` symbol is the preferred source
of truth — when present it overrides the Python sniffer. Until Pod-α
lands that symbol the Python sniffer carries the load.
"""
from __future__ import annotations

from io import BytesIO  # noqa: F401  (re-exported for typing parity)
from pathlib import Path
from typing import IO, Union

from wolfxl import _rust

# What Python accepts as a load source.
LoadSource = Union[
    str,
    "Path",
    bytes,
    bytearray,
    memoryview,
    IO[bytes],
]

# Magic-byte signatures.  We deliberately keep this very small — only the
# four file families wolfxl cares about — so we don't accidentally
# misidentify exotic ZIP / OLE compound files as spreadsheet inputs.
_OLE_CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # .xls + encrypted .xlsx
_ZIP_SIGNATURE = b"PK\x03\x04"  # .xlsx + .xlsb + .ods (all OOXML/ZIP-based)


def _looks_like_xlsx(data: bytes) -> bool:
    """Return True if ``data`` looks like an xlsx zip archive.

    OOXML xlsx files are zips whose `[Content_Types].xml` references the
    SpreadsheetML namespace.  We do a cheap substring scan over the
    first 4 KiB of the file rather than a real zip parse — that's enough
    to disambiguate xlsx from xlsb/ods which use different content-type
    strings.
    """
    head = data[:4096]
    return b"spreadsheetml" in head or b"workbook.xml" in head


def _looks_like_xlsb(data: bytes) -> bool:
    """Return True if ``data`` looks like an xlsb (Excel binary) file.

    xlsb is a ZIP whose content types reference the binary part names
    (workbook.bin, sheet1.bin, etc.) and the
    application/vnd.ms-excel.sheet.binary content type.
    """
    head = data[:4096]
    return b"sheet.binary" in head or b"workbook.bin" in head


def _looks_like_ods(data: bytes) -> bool:
    """Return True if ``data`` looks like an OpenDocument spreadsheet."""
    head = data[:4096]
    return b"opendocument.spreadsheet" in head or b"mimetypeapplication/vnd.oasis" in head


def _classify_bytes_python(data: bytes) -> str:
    """Pure-Python fallback for file-format sniffing.

    Returns one of ``"xlsx"``, ``"xlsb"``, ``"xls"``, ``"ods"``,
    ``"encrypted"``, ``"unknown"``. The ``"encrypted"`` return is for
    OOXML-encrypted xlsx (OLE Compound File Binary wrapping the
    ciphertext) — callers should treat that as ``"xlsx"`` when a
    password is supplied (msoffcrypto handles the actual decryption).
    """
    if len(data) < 8:
        return "unknown"

    if data.startswith(_OLE_CFB_SIGNATURE):
        # CFB envelope — used by both legacy .xls and OOXML-encrypted
        # files. The two are not distinguishable from the first 8 bytes
        # alone, so we look further into the directory entries: an
        # encrypted OOXML file embeds an "EncryptedPackage" stream,
        # while .xls embeds a "Workbook" / "Book" stream.  The CFB
        # directory uses UTF-16LE names, so we search for the wide
        # variants in the leading window.
        head_low = data[:65536]
        if (
            b"E\x00n\x00c\x00r\x00y\x00p\x00t\x00e\x00d" in head_low
            or b"EncryptedPackage" in head_low
        ):
            return "encrypted"
        return "xls"

    if data.startswith(_ZIP_SIGNATURE):
        if _looks_like_xlsb(data):
            return "xlsb"
        if _looks_like_ods(data):
            return "ods"
        if _looks_like_xlsx(data):
            return "xlsx"
        # An unknown zip is still a zip — treat as xlsx and let the
        # reader produce a meaningful error if it isn't actually OOXML.
        return "xlsx"

    return "unknown"


def _classify_path_python(path: str) -> str:
    """Pure-Python fallback that reads the head of ``path``.

    Reads up to 65 KiB so the encrypted-xlsx CFB directory (which
    follows the 512-byte sector header and lists ``EncryptedPackage``
    via UTF-16LE) is fully covered for disambiguation against legacy
    ``.xls``.
    """
    try:
        with open(path, "rb") as fp:
            head = fp.read(65536)
    except FileNotFoundError:
        # Surface to caller as a "real" file-not-found rather than
        # "unknown format" — matches openpyxl's behaviour.
        raise
    return _classify_bytes_python(head)


def _classify_via_rust(source: object) -> str | None:
    """Try to delegate to ``_rust.classify_file_format`` (Pod-α).

    Returns ``None`` when the symbol isn't yet exposed (Pod-α hasn't
    landed). Returns the format string when it is.  The Rust classifier
    cannot disambiguate legacy ``.xls`` from OOXML-encrypted ``.xlsx``
    (both wrap the same OLE2 compound-document magic), so when it
    reports ``"xls"`` we re-run the Python sniffer over the bytes /
    file head to detect the ``EncryptedPackage`` substream that
    distinguishes the two.  This preserves Rust authority for fast-path
    classification while keeping Sprint Ι Pod-γ password reads working.
    """
    fn = getattr(_rust, "classify_file_format", None)
    if fn is None:
        return None
    try:
        rust_fmt = str(fn(source))
    except Exception:
        return None

    # Encrypted-xlsx disambiguation: Rust says "xls" but the file may
    # actually be an OOXML-encrypted .xlsx wrapped in a CFB envelope.
    # The Python sniffer scans for the wide-string "EncryptedPackage"
    # directory entry and returns "encrypted" in that case.
    #
    # Synthetic-blob fallback: when Rust says "unknown" (e.g. a
    # truncated test fixture that lacks a real central directory) the
    # Python sniffer's substring scan may still recognize it.  This
    # keeps small synthetic test inputs working while real malformed
    # files still surface as "unknown".
    if rust_fmt in ("xls", "unknown"):
        if isinstance(source, (bytes, bytearray, memoryview)):
            py_fmt = _classify_bytes_python(bytes(source))
        elif isinstance(source, (str, Path)):
            try:
                py_fmt = _classify_path_python(str(source))
            except FileNotFoundError:
                return rust_fmt
        else:
            return rust_fmt
        if rust_fmt == "xls" and py_fmt == "encrypted":
            return "encrypted"
        if rust_fmt == "unknown" and py_fmt != "unknown":
            return py_fmt
    return rust_fmt


def classify_input(source: object) -> tuple[str, bytes | None, str | None]:
    """Sniff ``source`` and return ``(fmt, bytes_or_None, path_or_None)``.

    Exactly one of ``bytes_or_None`` / ``path_or_None`` will be non-None
    on a successful classification.  ``fmt`` is one of
    ``{"xlsx", "xlsb", "xls", "ods", "unknown"}``.  Bytes inputs are
    fully buffered before we classify so the caller can hand the same
    blob to a tempfile / direct-bytes reader.
    """
    if isinstance(source, (str, Path)):
        path = str(source)
        # Prefer Rust classifier when it's available; fall back to the
        # Python sniffer otherwise.
        fmt = _classify_via_rust(path)
        if fmt is None:
            fmt = _classify_path_python(path)
        return fmt, None, path

    if isinstance(source, (bytes, bytearray, memoryview)):
        data = bytes(source)
        fmt = _classify_via_rust(data)
        if fmt is None:
            fmt = _classify_bytes_python(data)
        return fmt, data, None

    if hasattr(source, "read"):
        data_obj = source.read()  # type: ignore[union-attr]
        if not isinstance(data_obj, (bytes, bytearray)):
            raise TypeError(
                f"file-like object returned {type(data_obj).__name__}; expected bytes"
            )
        data = bytes(data_obj)
        fmt = _classify_via_rust(data)
        if fmt is None:
            fmt = _classify_bytes_python(data)
        return fmt, data, None

    raise TypeError(
        "load_workbook source must be str | os.PathLike | bytes | "
        f"bytearray | memoryview | IO[bytes], got {type(source).__name__}"
    )
