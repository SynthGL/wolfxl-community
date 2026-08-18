"""RFC-062 — Page breaks + sheetFormatPr write/read parity with openpyxl.

These tests exercise the full pipeline:

  Python RowBreak / ColBreak / PageBreakList / SheetFormatProperties
  → set_page_breaks_native PyO3 binding
  → wolfxl-writer's emit_row_breaks / emit_col_breaks / emit_sheet_format_pr
  → openpyxl reads it back

If openpyxl can round-trip our XML, Excel/LibreOffice will too.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

wolfxl = pytest.importorskip("wolfxl")
openpyxl = pytest.importorskip("openpyxl")

from wolfxl.worksheet.dimensions import SheetFormatProperties
from wolfxl.worksheet.pagebreak import ColBreak, RowBreak


@pytest.fixture(autouse=True)
def _force_test_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


@pytest.fixture
def tmp_xlsx(tmp_path: Path) -> Path:
    return tmp_path / "page_breaks.xlsx"


def _read_sheet_xml(p: Path) -> str:
    with zipfile.ZipFile(p) as zf:
        return zf.read("xl/worksheets/sheet1.xml").decode("utf-8")


# ---------------------------------------------------------------------------
# Row breaks
# ---------------------------------------------------------------------------


def test_row_breaks_round_trip(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.row_breaks.append(RowBreak(id=5, min=0, max=16383))
    ws.row_breaks.append(RowBreak(id=10, min=0, max=16383))
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert "<rowBreaks" in text
    assert 'count="2"' in text

    # openpyxl reads back without errors.
    wb2 = openpyxl.load_workbook(str(tmp_xlsx))
    ws2 = wb2.active
    assert len(ws2.row_breaks) == 2
    ids = sorted(b.id for b in ws2.row_breaks.brk)
    assert ids == [5, 10]


def test_col_breaks_round_trip(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.col_breaks.append(ColBreak(id=3, min=0, max=1048575))
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert "<colBreaks" in text
    assert 'count="1"' in text

    wb2 = openpyxl.load_workbook(str(tmp_xlsx))
    ws2 = wb2.active
    assert len(ws2.col_breaks) == 1
    assert ws2.col_breaks.brk[0].id == 3


def test_both_breaks_preserved(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.row_breaks.append(RowBreak(id=5))
    ws.row_breaks.append(RowBreak(id=10))
    ws.col_breaks.append(ColBreak(id=3))
    wb.save(tmp_xlsx)

    wb2 = openpyxl.load_workbook(str(tmp_xlsx))
    ws2 = wb2.active
    assert len(ws2.row_breaks) == 2
    assert len(ws2.col_breaks) == 1


def test_manual_break_count_round_trips(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.row_breaks.append(RowBreak(id=5, man=True))
    ws.row_breaks.append(RowBreak(id=10, man=True))
    ws.row_breaks.append(RowBreak(id=15, man=False))
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert 'count="3"' in text
    assert 'manualBreakCount="2"' in text


# ---------------------------------------------------------------------------
# Sheet format properties
# ---------------------------------------------------------------------------


def test_sheet_format_default_row_height_round_trips(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.sheet_format.defaultRowHeight = 22.0
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert 'defaultRowHeight="22"' in text

    wb2 = openpyxl.load_workbook(str(tmp_xlsx))
    ws2 = wb2.active
    assert ws2.sheet_format.defaultRowHeight == 22.0


def test_sheet_format_outline_levels_round_trip(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.sheet_format = SheetFormatProperties(
        outlineLevelRow=2, outlineLevelCol=1
    )
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert 'outlineLevelRow="2"' in text
    assert 'outlineLevelCol="1"' in text


def test_sheet_format_custom_col_width(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.sheet_format.defaultColWidth = 12.5
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert 'defaultColWidth="12.5"' in text


# ---------------------------------------------------------------------------
# Combined (RFC-062 §6 ordering)
# ---------------------------------------------------------------------------


def test_breaks_and_format_in_same_save(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.sheet_format.defaultRowHeight = 18.0
    ws.row_breaks.append(RowBreak(id=5))
    ws.col_breaks.append(ColBreak(id=3))
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    # All three present.
    assert 'defaultRowHeight="18"' in text
    assert "<rowBreaks" in text
    assert "<colBreaks" in text
    # Ordering: sheetFormatPr (slot 4) → rowBreaks (slot 24) → colBreaks (slot 25).
    assert text.index("<sheetFormatPr") < text.index("<rowBreaks")
    assert text.index("<rowBreaks") < text.index("<colBreaks")

    # openpyxl re-reads everything.
    wb2 = openpyxl.load_workbook(str(tmp_xlsx))
    ws2 = wb2.active
    assert ws2.sheet_format.defaultRowHeight == 18.0
    assert len(ws2.row_breaks) == 1
    assert len(ws2.col_breaks) == 1
