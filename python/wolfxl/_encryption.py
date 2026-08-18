"""Sprint Λ Pod-α — write-side OOXML encryption (Agile / AES-256).

Mirror of :mod:`wolfxl._loader` but inverted: take a freshly written
plaintext xlsx and produce an OOXML-encrypted blob that Excel /
LibreOffice / msoffcrypto can decrypt with the supplied password.

The implementation is a thin wrapper around
``msoffcrypto.format.ooxml.OOXMLFile.encrypt`` (Agile / AES-256, the
modern Excel default). Standard (AES-128) and XOR are out of scope on
the write side because msoffcrypto-tool only implements *decrypt* for
those algorithms — see ``docs/encryption.md`` for the rationale.

``msoffcrypto-tool`` stays an **optional** dependency (it ships under
the ``[encrypted]`` extra in ``pyproject.toml`` for the read path that
Sprint Ι Pod-γ added). Importers without it pay zero cost; calling
into this module without the dep raises ``ImportError`` with the
install hint.
"""

from __future__ import annotations

import io
import os
import struct
import tempfile
from pathlib import Path

# Public API ---------------------------------------------------------------

__all__ = (
    "encrypt_xlsx_bytes",
    "encrypt_xlsx_to_path",
)


# msoffcrypto-tool's OOXML container writer routes any EncryptedPackage
# stream <= 4096 bytes through the OLE2 MiniFAT instead of the regular
# FAT (``method/container/ecma376_encrypted.py:540``), but it sets the
# StartingSectorLocation on the directory entry to the regular-FAT
# offset, so on decrypt the resulting bytes are misaligned and AES-CBC
# fails with "data length is not a multiple of block length". The
# practical workaround is to make sure the encrypted payload is large
# enough to land in the regular FAT path. The encrypted payload is
# ``8 + ceil(len(plaintext)/16) * 16``; padding the plaintext to
# ``_MIN_PLAINTEXT_FOR_REGULAR_FAT`` bytes guarantees the encrypted
# payload exceeds the 4096-byte MiniFAT cutoff with a comfortable margin.
_MIN_PLAINTEXT_FOR_REGULAR_FAT = 5120

# 0x06054b50 = "PK\x05\x06" — End Of Central Directory record signature
_EOCD_SIGNATURE = b"PK\x05\x06"


_INSTALL_HINT = (
    "write-side encryption requires msoffcrypto-tool; install with: "
    "pip install wolfxl[encrypted]"
)


def _import_msoffcrypto_ooxml():
    """Lazy-import ``msoffcrypto.format.ooxml.OOXMLFile``.

    Centralised so the same ``ImportError`` text shows up whether the
    caller takes the bytes path or the path-to-disk path.
    """
    try:
        from msoffcrypto.format.ooxml import OOXMLFile  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — exercised via mock in tests
        raise ImportError(_INSTALL_HINT) from exc
    return OOXMLFile


def _coerce_password(password: str | bytes) -> str:
    """Normalise ``password`` to ``str`` (UTF-8 for bytes inputs).

    Empty passwords are rejected up front: msoffcrypto silently produces
    an unusable blob otherwise, and openpyxl rejects empty strings as
    well, so we mirror that contract.
    """
    if isinstance(password, bytes):
        try:
            pw_str = password.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"password bytes must be valid UTF-8: {exc}"
            ) from exc
    elif isinstance(password, str):
        pw_str = password
    else:
        raise TypeError(
            "password must be str | bytes, got "
            f"{type(password).__name__}"
        )

    if pw_str == "":
        raise ValueError("empty password not allowed")
    return pw_str


def _pad_zip_via_eocd_comment(data: bytes, min_size: int) -> bytes:
    """Inflate a tiny xlsx (zip) up to ``min_size`` bytes via EOCD comment.

    Workaround for the msoffcrypto-tool MiniFAT misalignment described
    near :data:`_MIN_PLAINTEXT_FOR_REGULAR_FAT`. We rewrite the
    End-Of-Central-Directory record's ``comment_length`` field so the
    appended zero bytes are formally part of the ZIP comment — every
    standards-compliant ZIP reader (including msoffcrypto's internal
    re-read after decrypt) accepts the result without complaint.

    Returns ``data`` unchanged when already large enough, when the
    EOCD record can't be located, or when the required pad would
    exceed the 16-bit comment-length field.
    """
    if len(data) >= min_size:
        return data
    idx = data.rfind(_EOCD_SIGNATURE)
    if idx < 0:
        return data
    eocd_end_min = idx + 22  # fixed-size portion of the EOCD record
    if eocd_end_min > len(data):
        return data
    pad_needed = min_size - eocd_end_min
    if pad_needed <= 0 or pad_needed > 0xFFFF:
        return data
    return (
        data[: idx + 20]
        + struct.pack("<H", pad_needed)
        + b"\x00" * pad_needed
    )


def encrypt_xlsx_bytes(plaintext_bytes: bytes, password: str | bytes) -> bytes:
    """Encrypt a plaintext xlsx blob and return the encrypted bytes.

    Parameters
    ----------
    plaintext_bytes:
        A complete, valid xlsx blob (OOXML / ZIP). Typically the
        in-memory output of the Rust writer/patcher.
    password:
        UTF-8 ``str`` or ``bytes``. ``bytes`` is decoded as UTF-8.
        Empty passwords raise :class:`ValueError`.

    Returns
    -------
    bytes
        OOXML-encrypted (Agile / AES-256) blob suitable for writing
        directly to disk.

    Raises
    ------
    ImportError
        If ``msoffcrypto-tool`` is not installed.
    ValueError
        If the password is empty or the plaintext is rejected by
        msoffcrypto for any reason.
    """
    pw = _coerce_password(password)
    OOXMLFile = _import_msoffcrypto_ooxml()

    # Pad tiny inputs up over the OLE2 MiniFAT cutoff so msoffcrypto's
    # OOXML container writer routes us through the regular FAT (see
    # _MIN_PLAINTEXT_FOR_REGULAR_FAT). No-op for files already large
    # enough.
    inflated = _pad_zip_via_eocd_comment(
        plaintext_bytes, _MIN_PLAINTEXT_FOR_REGULAR_FAT
    )

    src = io.BytesIO(inflated)
    out = io.BytesIO()
    try:
        officefile = OOXMLFile(src)
        officefile.encrypt(pw, out)
    except (ImportError, ValueError):
        raise
    except Exception as exc:
        raise ValueError(
            f"failed to encrypt workbook: {exc}"
        ) from exc
    return out.getvalue()


def encrypt_xlsx_to_path(
    plaintext_bytes: bytes,
    password: str | bytes,
    target: str | os.PathLike[str],
) -> None:
    """Encrypt ``plaintext_bytes`` and atomically write to ``target``.

    Writes the encrypted output to a sibling tempfile in the target
    directory first, then ``os.replace``\\ s it onto the final path so
    a partial / failed encryption never overwrites a previously good
    file. The temp file is cleaned up on every error path.
    """
    target_path = Path(target)
    parent = target_path.parent if str(target_path.parent) else Path(".")
    parent.mkdir(parents=True, exist_ok=True)

    encrypted = encrypt_xlsx_bytes(plaintext_bytes, password)

    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=".wolfxl-enc-",
        suffix=".xlsx.tmp",
        dir=str(parent),
    )
    try:
        with os.fdopen(tmp_fd, "wb") as fp:
            fp.write(encrypted)
        os.replace(tmp_name, target_path)
    except Exception:
        # mkstemp returns an existing file; clean it up on failure.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
