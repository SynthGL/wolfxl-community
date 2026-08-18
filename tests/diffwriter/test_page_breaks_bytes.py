"""RFC-062 (Sprint Π Pod Π-α) — byte-stable diffwriter tests.

Verifies that writing the same workbook twice produces identical
``xl/worksheets/sheetN.xml`` bytes (modulo timestamp), so future
changes that perturb the order of attributes / elements in the
new emitter slots get caught immediately.

Pin ``WOLFXL_TEST_EPOCH=0`` to neutralize the embedded timestamp.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.worksheet.dimensions import SheetFormatProperties
from wolfxl.worksheet.pagebreak import ColBreak, RowBreak


@pytest.fixture(autouse=True)
def _pin_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


def _read_sheet_xml(p: Path) -> bytes:
    with zipfile.ZipFile(p) as z:
        return z.read("xl/worksheets/sheet1.xml")


def test_row_breaks_byte_stable(tmp_path: Path) -> None:
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "hello"
        ws.row_breaks.append(RowBreak(id=5, min=0, max=16383))
        ws.row_breaks.append(RowBreak(id=10, min=0, max=16383))
        wb.save(str(p))
    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_col_breaks_byte_stable(tmp_path: Path) -> None:
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "hello"
        ws.col_breaks.append(ColBreak(id=3, min=0, max=1048575))
        wb.save(str(p))
    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_sheet_format_byte_stable(tmp_path: Path) -> None:
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "x"
        ws.sheet_format = SheetFormatProperties(
            baseColWidth=10,
            defaultColWidth=12.5,
            defaultRowHeight=22.0,
            outlineLevelRow=2,
        )
        wb.save(str(p))
    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_block_ordering_in_sheet_xml(tmp_path: Path) -> None:
    """Verify CT_Worksheet child ordering: sheetFormatPr(4),
    headerFooter(23), rowBreaks(24), colBreaks(25)."""
    p = tmp_path / "order.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "hello"
    ws.sheet_format.defaultRowHeight = 20.0
    ws.row_breaks.append(RowBreak(id=5))
    ws.col_breaks.append(ColBreak(id=3))
    ws.header_footer.odd_header.center = "Title"
    wb.save(str(p))
    sheet = _read_sheet_xml(p).decode()
    pos = {
        "sheetFormatPr": sheet.index("<sheetFormatPr"),
        "headerFooter": sheet.index("<headerFooter"),
        "rowBreaks": sheet.index("<rowBreaks"),
        "colBreaks": sheet.index("<colBreaks"),
    }
    # Strict ECMA-376 §18.3.1.99 ordering:
    assert pos["sheetFormatPr"] < pos["headerFooter"]
    assert pos["headerFooter"] < pos["rowBreaks"]
    assert pos["rowBreaks"] < pos["colBreaks"]


def test_no_emit_when_at_defaults(tmp_path: Path) -> None:
    """Workbooks that never touch page breaks / sheet format don't
    emit <rowBreaks>, <colBreaks> elements (legacy hardcoded
    sheetFormatPr remains)."""
    p = tmp_path / "default.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = "hello"
    wb.save(str(p))
    sheet = _read_sheet_xml(p).decode()
    assert "<rowBreaks" not in sheet
    assert "<colBreaks" not in sheet
    # Legacy default sheetFormatPr is still emitted (slot 4 always
    # has a value in the writer's hardcoded path).
    assert "<sheetFormatPr " in sheet


def test_break_attribute_order(tmp_path: Path) -> None:
    """Pin attribute ordering on <brk>: id, min, max, man, pt."""
    p = tmp_path / "attr.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.row_breaks.append(RowBreak(id=5, min=0, max=16383, man=True))
    wb.save(str(p))
    sheet = _read_sheet_xml(p).decode()
    assert "<brk " in sheet
    # id before min before max before man.
    s = sheet[sheet.index("<brk "):]
    assert s.index("id=") < s.index("min=")
    assert s.index("min=") < s.index("max=")
    assert s.index("max=") < s.index("man=")
