"""RFC-055 §2.6 — sheet-protection write/read parity with openpyxl.

Pipeline:
  Python SheetProtection
  → set_sheet_setup_native PyO3 binding
  → wolfxl-writer's emit_sheet_protection
  → openpyxl reads it back
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

wolfxl = pytest.importorskip("wolfxl")
openpyxl = pytest.importorskip("openpyxl")

from wolfxl.worksheet.protection import SheetProtection


@pytest.fixture(autouse=True)
def _force_test_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


@pytest.fixture
def tmp_xlsx(tmp_path: Path) -> Path:
    return tmp_path / "protected.xlsx"


def _read_sheet_xml(p: Path) -> str:
    with zipfile.ZipFile(p) as zf:
        return zf.read("xl/worksheets/sheet1.xml").decode("utf-8")


def test_sheet_only_round_trips(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.protection.enable()
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert "<sheetProtection" in text
    assert 'sheet="1"' in text

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op.active.protection.sheet is True
    finally:
        op.close()


def test_password_round_trips(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.protection.set_password("hunter2")
    ws.protection.enable()
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert 'password="C258"' in text

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        # openpyxl parses the legacy password attr into the
        # password property on SheetProtection.
        assert op.active.protection.password == "C258"
    finally:
        op.close()


def test_disable_sort_locks_user_out(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.protection.enable()
    ws.protection.sort = False
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert 'sort="0"' in text

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op.active.protection.sort is False
    finally:
        op.close()


def test_select_locked_cells_emit_only_when_true(tmp_xlsx: Path) -> None:
    """selectLockedCells defaults to False (allowed). Only emit when True
    (forbidden)."""
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.protection.enable()
    ws.protection.select_locked_cells = True
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert 'selectLockedCells="1"' in text

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op.active.protection.selectLockedCells is True
    finally:
        op.close()


def test_default_no_emit(tmp_xlsx: Path) -> None:
    """A sheet whose protection is at default (sheet=False, no password)
    must NOT emit a <sheetProtection> element."""
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    # Touch the protection to force lazy init but leave at defaults:
    _ = ws.protection
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert "<sheetProtection" not in text


def test_combined_flags_round_trip(tmp_xlsx: Path) -> None:
    """Multiple toggles round-trip through openpyxl."""
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    sp = SheetProtection()
    sp.enable()
    sp.sort = False
    sp.formatCells = False
    sp.insertRows = False
    sp.set_password("secret")
    ws.protection = sp
    wb.save(tmp_xlsx)

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        prot = op.active.protection
        assert prot.sheet is True
        assert prot.sort is False
        assert prot.formatCells is False
        assert prot.insertRows is False
        assert prot.password is not None and prot.password != ""
    finally:
        op.close()
