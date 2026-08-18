"""RFC-055 (Sprint Ο Pod 1A.5) — byte-stable diffwriter tests for the
5 sheet-setup blocks (sheetView / sheetProtection / pageMargins /
pageSetup / headerFooter).

Verifies that writing the same workbook twice produces identical
``xl/worksheets/sheetN.xml`` bytes (modulo timestamp), so future
changes that perturb the order of attributes / elements in the new
emitter slots get caught immediately.

Run with ``WOLFXL_TEST_EPOCH=0`` to pin the embedded timestamp.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.worksheet.header_footer import HeaderFooter, HeaderFooterItem
from wolfxl.worksheet.page_setup import PageMargins
from wolfxl.worksheet.protection import SheetProtection
from wolfxl.worksheet.views import Pane, SheetView


@pytest.fixture(autouse=True)
def _pin_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


def _read_sheet_xml(p: Path) -> bytes:
    with zipfile.ZipFile(p) as z:
        return z.read("xl/worksheets/sheet1.xml")


def test_page_margins_byte_stable(tmp_path: Path) -> None:
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        ws = wb.active
        ws.page_margins = PageMargins(left=1.0, right=1.0, top=1.5, bottom=1.5)
        wb.save(str(p))
    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_page_setup_byte_stable(tmp_path: Path) -> None:
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        ws = wb.active
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = 9
        ws.page_setup.scale = 75
        wb.save(str(p))
    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_header_footer_byte_stable(tmp_path: Path) -> None:
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        ws = wb.active
        ws.header_footer = HeaderFooter(
            odd_header=HeaderFooterItem(left="L", center="C", right="R"),
            odd_footer=HeaderFooterItem(center="Page &P of &N"),
        )
        wb.save(str(p))
    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_sheet_view_byte_stable(tmp_path: Path) -> None:
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        ws = wb.active
        ws.sheet_view = SheetView(
            zoomScale=150,
            showGridLines=False,
            tabSelected=True,
            pane=Pane(ySplit=1.0, topLeftCell="A2", activePane="bottomLeft", state="frozen"),
        )
        wb.save(str(p))
    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_sheet_protection_byte_stable(tmp_path: Path) -> None:
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        ws = wb.active
        sp = SheetProtection()
        sp.set_password("hunter2")
        sp.enable()
        sp.sort = False
        ws.protection = sp
        wb.save(str(p))
    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_page_setup_attribute_order(tmp_path: Path) -> None:
    """Pin ECMA-376 §18.3.1.51 attribute ordering on <pageSetup>."""
    p = tmp_path / "order.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    ws.page_setup.paperSize = 9
    ws.page_setup.scale = 75
    ws.page_setup.orientation = "portrait"
    wb.save(str(p))
    sheet = _read_sheet_xml(p).decode()
    assert "<pageSetup " in sheet
    assert 'paperSize="9"' in sheet
    assert 'scale="75"' in sheet
    assert 'orientation="portrait"' in sheet
    # Ordering: paperSize before scale before orientation.
    assert sheet.index("paperSize=") < sheet.index("scale=")
    assert sheet.index("scale=") < sheet.index("orientation=")


def test_sheet_protection_password_attr(tmp_path: Path) -> None:
    """The legacy hashed password is emitted verbatim into the
    `password=` attribute (no extra encoding)."""
    p = tmp_path / "pw.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    ws.protection.set_password("hunter2")
    ws.protection.enable()
    wb.save(str(p))
    sheet = _read_sheet_xml(p).decode()
    assert 'password="C258"' in sheet
    assert 'sheet="1"' in sheet


def test_block_ordering_in_sheet_xml(tmp_path: Path) -> None:
    """Verify CT_Worksheet child order: sheetViews(3), sheetProtection(8),
    printOptions(20), pageMargins(21), pageSetup(22), headerFooter(23)."""
    p = tmp_path / "order.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    ws.protection.enable()
    ws.page_setup.orientation = "landscape"
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = 1.0
    ws.header_footer.odd_header.center = "Title"
    ws.sheet_view.zoom_scale = 150
    wb.save(str(p))
    sheet = _read_sheet_xml(p).decode()
    pos = {
        "sheetViews": sheet.index("<sheetViews>"),
        "sheetProtection": sheet.index("<sheetProtection"),
        "printOptions": sheet.index("<printOptions"),
        "pageMargins": sheet.index("<pageMargins"),
        "pageSetup": sheet.index("<pageSetup"),
        "headerFooter": sheet.index("<headerFooter"),
    }
    # Strict ECMA-376 §18.3.1.99 ordering:
    assert pos["sheetViews"] < pos["sheetProtection"]
    assert pos["sheetProtection"] < pos["printOptions"]
    assert pos["printOptions"] < pos["pageMargins"]
    assert pos["pageMargins"] < pos["pageSetup"]
    assert pos["pageSetup"] < pos["headerFooter"]


def test_no_emit_when_at_defaults(tmp_path: Path) -> None:
    """Workbooks that never touch sheet-setup don't emit pageSetup,
    headerFooter, or sheetProtection elements (only the legacy default
    pageMargins is hardcoded)."""
    p = tmp_path / "default.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = "hello"
    wb.save(str(p))
    sheet = _read_sheet_xml(p).decode()
    assert "<pageSetup" not in sheet
    assert "<headerFooter" not in sheet
    assert "<sheetProtection" not in sheet
    # Default pageMargins still emitted.
    assert "<pageMargins " in sheet
