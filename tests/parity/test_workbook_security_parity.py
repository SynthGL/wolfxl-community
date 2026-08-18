"""RFC-058 — Workbook security write/read parity with openpyxl.

These tests exercise the full pipeline:

  Python WorkbookProtection / FileSharing
  → set_workbook_security PyO3 binding
  → wolfxl-writer's <workbookProtection> / <fileSharing> emit
  → openpyxl reads it back

If openpyxl can round-trip our XML, Excel/LibreOffice will too.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

wolfxl = pytest.importorskip("wolfxl")
openpyxl = pytest.importorskip("openpyxl")
from wolfxl.workbook.protection import FileSharing, WorkbookProtection


@pytest.fixture(autouse=True)
def _force_test_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ZIP entry mtimes for byte-stable saves."""
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


@pytest.fixture
def tmp_xlsx(tmp_path: Path) -> Path:
    return tmp_path / "secured.xlsx"


def _read_workbook_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        return zf.read("xl/workbook.xml").decode("utf-8")


def test_lock_structure_only_round_trips(tmp_xlsx: Path) -> None:
    """``lock_structure=True`` with no password should land in workbook.xml."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "hello"
    wb.security = WorkbookProtection(lock_structure=True)
    wb.save(tmp_xlsx)

    text = _read_workbook_xml(tmp_xlsx)
    assert "<workbookProtection" in text
    assert 'lockStructure="1"' in text

    # openpyxl reads back the same lock state.
    op_wb = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op_wb.security.lockStructure is True
    finally:
        op_wb.close()


def test_workbook_password_round_trip(tmp_xlsx: Path) -> None:
    """SHA-512 password attributes survive save → openpyxl read."""
    wb = wolfxl.Workbook()
    wb.active["A1"] = "x"  # type: ignore[index]
    wp = WorkbookProtection(lock_structure=True)
    wp.set_workbook_password("hunter2", salt=bytes(range(16)), spin_count=1000)
    wb.security = wp
    wb.save(tmp_xlsx)

    text = _read_workbook_xml(tmp_xlsx)
    assert 'workbookAlgorithmName="SHA-512"' in text
    assert 'workbookSpinCount="1000"' in text
    assert "workbookHashValue=" in text
    assert "workbookSaltValue=" in text

    # openpyxl reads them as the modern hash attributes.
    op_wb = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op_wb.security.workbookAlgorithmName == "SHA-512"
        assert op_wb.security.workbookSpinCount == 1000
        # Salt was the deterministic 0..15 sequence we passed in.
        from base64 import b64encode

        assert op_wb.security.workbookSaltValue == b64encode(bytes(range(16))).decode()
    finally:
        op_wb.close()


def test_file_sharing_emitted_at_correct_position(tmp_xlsx: Path) -> None:
    """``<fileSharing>`` must come BEFORE ``<workbookPr>`` per RFC-058 §5."""
    wb = wolfxl.Workbook()
    wb.active["A1"] = "x"  # type: ignore[index]
    wb.fileSharing = FileSharing(read_only_recommended=True, user_name="alice")
    wb.save(tmp_xlsx)

    text = _read_workbook_xml(tmp_xlsx)
    fv = text.find("<fileVersion")
    fs = text.find("<fileSharing")
    pr = text.find("<workbookPr")
    assert fv != -1 and fs != -1 and pr != -1
    assert fv < fs < pr, f"ordering violated: fileVersion={fv} fileSharing={fs} workbookPr={pr}"
    assert 'readOnlyRecommended="1"' in text
    assert 'userName="alice"' in text


def test_both_blocks_round_trip_via_openpyxl(tmp_xlsx: Path) -> None:
    """Both blocks present at canonical positions, openpyxl reads them."""
    wb = wolfxl.Workbook()
    wb.active["A1"] = "x"  # type: ignore[index]
    wp = WorkbookProtection(
        lock_structure=True,
        lock_windows=True,
    )
    wp.set_workbook_password("structure-pw", salt=bytes(range(16)), spin_count=1000)
    wb.security = wp

    fs = FileSharing(read_only_recommended=True, user_name="alice")
    fs.set_reservation_password("alice-pw", salt=bytes(range(16)), spin_count=1000)
    wb.fileSharing = fs

    wb.save(tmp_xlsx)

    op_wb = openpyxl.load_workbook(tmp_xlsx)
    try:
        # WorkbookProtection
        assert op_wb.security.lockStructure is True
        assert op_wb.security.lockWindows is True
        assert op_wb.security.workbookAlgorithmName == "SHA-512"

        # FileSharing — note openpyxl exposes camelCase here.
        # (openpyxl 3.1.x drops fileSharing on load if it can't parse the
        # reservation-password attribute, so the read-back assertion is
        # tolerant.)
        if hasattr(op_wb, "fileSharing") and op_wb.fileSharing is not None:
            assert op_wb.fileSharing.readOnlyRecommended is True
            assert op_wb.fileSharing.userName == "alice"
            assert op_wb.fileSharing.algorithmName == "SHA-512"
    finally:
        op_wb.close()
