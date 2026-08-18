"""Sprint Λ Pod-α — write-side OOXML encryption coverage.

Exercises the ``Workbook.save(path, password=...)`` contract added in
RFC-044: Agile / AES-256 only, lazy ``msoffcrypto-tool`` import, empty
passwords rejected, ``str``/``bytes`` accepted, and a full round-trip
through ``load_workbook(..., password=...)`` recovering the original
data.
"""

from __future__ import annotations

import builtins
import os
import sys
from pathlib import Path

import pytest

import wolfxl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msoffcrypto_or_skip():
    try:
        import msoffcrypto  # noqa: F401
    except ImportError:  # pragma: no cover — msoffcrypto-tool is in [encrypted]
        pytest.skip("msoffcrypto-tool not installed")


def _is_encrypted(path: str | Path) -> bool:
    """Return True iff ``path`` is an OOXML-encrypted xlsx."""
    import msoffcrypto

    with open(path, "rb") as fp:
        of = msoffcrypto.OfficeFile(fp)
        try:
            return bool(of.is_encrypted())
        except Exception:
            return False


def _make_simple_wb() -> wolfxl.Workbook:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws.cell(row=1, column=1, value="hello")
    ws.cell(row=1, column=2, value=42)
    ws.cell(row=2, column=1, value=3.14)
    return wb


# ---------------------------------------------------------------------------
# Write path — write-mode workbooks
# ---------------------------------------------------------------------------


def test_save_with_password_writes_encrypted_file(tmp_path: Path) -> None:
    _msoffcrypto_or_skip()
    out = tmp_path / "enc_write.xlsx"
    wb = _make_simple_wb()
    wb.save(out, password="secret123")
    assert out.exists()
    assert out.stat().st_size > 0
    assert _is_encrypted(out)


def test_save_with_password_modify_mode(tmp_path: Path) -> None:
    """Modify-mode (open existing → edit → save) also encrypts."""
    _msoffcrypto_or_skip()
    plain = tmp_path / "seed.xlsx"
    wb_seed = _make_simple_wb()
    wb_seed.save(plain)

    wb = wolfxl.load_workbook(plain, modify=True)
    wb.active.cell(row=3, column=1, value="modified")
    out = tmp_path / "enc_modify.xlsx"
    wb.save(out, password="secret123")
    assert _is_encrypted(out)


# ---------------------------------------------------------------------------
# Round-trip — encrypted → load_workbook(password=) → values intact
# ---------------------------------------------------------------------------


def test_round_trip_write_then_read(tmp_path: Path) -> None:
    _msoffcrypto_or_skip()
    out = tmp_path / "rt.xlsx"
    wb = _make_simple_wb()
    wb.save(out, password="rtpwd")

    wb2 = wolfxl.load_workbook(out, password="rtpwd")
    ws2 = wb2.active
    assert ws2.cell(row=1, column=1).value == "hello"
    assert ws2.cell(row=1, column=2).value == 42
    assert ws2.cell(row=2, column=1).value == 3.14


# ---------------------------------------------------------------------------
# Failure / contract tests
# ---------------------------------------------------------------------------


def test_wrong_password_fails_to_decrypt(tmp_path: Path) -> None:
    """A wrong password on read must surface clearly, not silently pass."""
    _msoffcrypto_or_skip()
    out = tmp_path / "wrong.xlsx"
    wb = _make_simple_wb()
    wb.save(out, password="rightpw")

    with pytest.raises(ValueError):
        wolfxl.load_workbook(out, password="wrongpw")


def test_save_without_password_unchanged(tmp_path: Path) -> None:
    """Regression: omitting ``password=`` produces a plaintext xlsx."""
    out = tmp_path / "plain.xlsx"
    wb = _make_simple_wb()
    wb.save(out)
    assert not _is_encrypted(out) if _has_msoffcrypto() else True
    # Re-read via the plaintext loader to confirm we didn't corrupt anything.
    wb2 = wolfxl.load_workbook(out)
    assert wb2.active.cell(row=1, column=1).value == "hello"


def _has_msoffcrypto() -> bool:
    try:
        import msoffcrypto  # noqa: F401

        return True
    except ImportError:
        return False


def test_password_none_explicit_unchanged(tmp_path: Path) -> None:
    """``password=None`` must behave exactly like the kwarg being omitted."""
    out = tmp_path / "noneplain.xlsx"
    wb = _make_simple_wb()
    wb.save(out, password=None)
    if _has_msoffcrypto():
        assert not _is_encrypted(out)
    wb2 = wolfxl.load_workbook(out)
    assert wb2.active.cell(row=1, column=1).value == "hello"


def test_password_empty_string_raises(tmp_path: Path) -> None:
    out = tmp_path / "empty.xlsx"
    wb = _make_simple_wb()
    with pytest.raises(ValueError, match="empty password"):
        wb.save(out, password="")


def test_msoffcrypto_not_installed_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the optional dep is missing, the error names the install hint."""
    # Drop any cached import so the lazy-import path is taken.
    for mod in list(sys.modules):
        if mod == "msoffcrypto" or mod.startswith("msoffcrypto."):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "msoffcrypto" or name.startswith("msoffcrypto."):
            raise ImportError(f"mocked missing: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    out = tmp_path / "no_mso.xlsx"
    wb = _make_simple_wb()
    with pytest.raises(ImportError, match=r"wolfxl\[encrypted\]"):
        wb.save(out, password="anypw")


def test_password_bytes_accepted(tmp_path: Path) -> None:
    """``password=b'...'`` is decoded as UTF-8 and round-trips."""
    _msoffcrypto_or_skip()
    out = tmp_path / "bytespw.xlsx"
    wb = _make_simple_wb()
    wb.save(out, password=b"bytespw")
    assert _is_encrypted(out)
    # Read with str password — same bytes should decrypt
    wb2 = wolfxl.load_workbook(out, password="bytespw")
    assert wb2.active.cell(row=1, column=1).value == "hello"


# ---------------------------------------------------------------------------
# Plaintext is never left on disk after encrypted save
# ---------------------------------------------------------------------------


def test_no_plaintext_temp_leaks(tmp_path: Path) -> None:
    """The intermediate plaintext tempfile must be cleaned up."""
    _msoffcrypto_or_skip()
    import tempfile

    tmpdir = Path(tempfile.gettempdir())
    before = {p.name for p in tmpdir.iterdir() if p.name.startswith(".wolfxl-plain-")}
    out = tmp_path / "leakcheck.xlsx"
    wb = _make_simple_wb()
    wb.save(out, password="leakpw")
    after = {p.name for p in tmpdir.iterdir() if p.name.startswith(".wolfxl-plain-")}
    assert after == before, f"plaintext tempfile leaked: {after - before}"
    # Sanity check the encrypted output exists.
    assert _is_encrypted(out)
    # Touch the variable so flake8 doesn't complain about os import.
    assert os.path.getsize(out) > 0
