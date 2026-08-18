"""RFC-055 — Print/page-setup write/read parity with openpyxl.

These tests exercise the full pipeline:

  Python PageSetup / PageMargins / HeaderFooter / SheetView
  → set_sheet_setup_native PyO3 binding
  → wolfxl-writer's emit_page_setup / emit_page_margins / etc.
  → openpyxl reads it back

If openpyxl can round-trip our XML, Excel/LibreOffice will too.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

wolfxl = pytest.importorskip("wolfxl")
openpyxl = pytest.importorskip("openpyxl")

from wolfxl.worksheet.header_footer import HeaderFooter, HeaderFooterItem
from wolfxl.worksheet.page_setup import PageMargins
from wolfxl.worksheet.views import Pane, SheetView


@pytest.fixture(autouse=True)
def _force_test_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


@pytest.fixture
def tmp_xlsx(tmp_path: Path) -> Path:
    return tmp_path / "print_settings.xlsx"


def _read_sheet_xml(p: Path) -> str:
    with zipfile.ZipFile(p) as zf:
        return zf.read("xl/worksheets/sheet1.xml").decode("utf-8")


def _read_workbook_xml(p: Path) -> str:
    with zipfile.ZipFile(p) as zf:
        return zf.read("xl/workbook.xml").decode("utf-8")


def test_page_setup_orientation_round_trips(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.page_setup.orientation = "landscape"
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert 'orientation="landscape"' in text

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op.active.page_setup.orientation == "landscape"
    finally:
        op.close()


def test_page_setup_paper_and_scale(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.page_setup.paperSize = 9
    ws.page_setup.scale = 75
    wb.save(tmp_xlsx)

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert int(op.active.page_setup.paperSize) == 9
        assert int(op.active.page_setup.scale) == 75
    finally:
        op.close()


def test_page_setup_fit_to_width_height(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    wb.save(tmp_xlsx)

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert int(op.active.page_setup.fitToWidth) == 1
        assert int(op.active.page_setup.fitToHeight) == 0
    finally:
        op.close()


def test_g24_page_setup_extended_attrs_round_trip(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.page_setup.paperHeight = "297mm"
    ws.page_setup.paperWidth = "210mm"
    ws.page_setup.pageOrder = "overThenDown"
    ws.page_setup.copies = 3
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert 'paperHeight="297mm"' in text
    assert 'paperWidth="210mm"' in text
    assert 'pageOrder="overThenDown"' in text
    assert 'copies="3"' in text

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        setup = op.active.page_setup
        assert setup.paperHeight == "297mm"
        assert setup.paperWidth == "210mm"
        assert setup.pageOrder == "overThenDown"
        assert int(setup.copies) == 3
    finally:
        op.close()


def test_g24_print_options_round_trip(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.print_options.horizontalCentered = True
    ws.print_options.verticalCentered = True
    ws.print_options.headings = True
    ws.print_options.gridLines = True
    ws.print_options.gridLinesSet = False
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert "<printOptions " in text
    assert text.index("<printOptions") < text.index("<pageMargins")
    assert 'horizontalCentered="1"' in text
    assert 'verticalCentered="1"' in text
    assert 'headings="1"' in text
    assert 'gridLines="1"' in text
    assert 'gridLinesSet="0"' in text

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        opts = op.active.print_options
        assert opts.horizontalCentered is True
        assert opts.verticalCentered is True
        assert opts.headings is True
        assert opts.gridLines is True
        assert opts.gridLinesSet is False
    finally:
        op.close()


def test_g24_print_titles_emit_reserved_defined_name(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws.title = "Report"
    ws["A1"] = "x"
    ws.print_title_rows = "1:2"
    ws.print_title_cols = "A:B"
    wb.save(tmp_xlsx)

    workbook_xml = _read_workbook_xml(tmp_xlsx)
    assert 'name="_xlnm.Print_Titles"' in workbook_xml
    assert 'localSheetId="0"' in workbook_xml
    assert "Report!$1:$2,Report!$A:$B" in workbook_xml

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op["Report"].print_title_rows == "$1:$2"
        assert op["Report"].print_title_cols == "$A:$B"
    finally:
        op.close()


def test_g24_user_defined_print_titles_suppresses_auto_inject(tmp_xlsx: Path) -> None:
    from wolfxl.workbook.defined_name import DefinedName

    wb = wolfxl.Workbook()
    ws = wb.active
    ws.title = "Report"
    ws["A1"] = "x"
    ws.print_title_rows = "1:2"
    wb.defined_names["_xlnm.Print_Titles"] = DefinedName(
        name="_xlnm.Print_Titles",
        value="Report!$3:$4",
        localSheetId=0,
    )
    wb.save(tmp_xlsx)

    workbook_xml = _read_workbook_xml(tmp_xlsx)
    assert workbook_xml.count('name="_xlnm.Print_Titles"') == 1
    assert "Report!$3:$4" in workbook_xml
    assert "Report!$1:$2" not in workbook_xml


def test_g24_print_titles_modify_mode_round_trip(tmp_xlsx: Path, tmp_path: Path) -> None:
    src = tmp_path / "source.xlsx"
    op = openpyxl.Workbook()
    op.active.title = "Report"
    op.active["A1"] = "x"
    op.save(src)
    op.close()

    wb = wolfxl.load_workbook(src, modify=True)
    ws = wb["Report"]
    ws.print_title_rows = "1:2"
    ws.print_title_cols = "A:B"
    wb.save(tmp_xlsx)

    rt = wolfxl.load_workbook(tmp_xlsx)
    assert rt["Report"].print_title_rows == "$1:$2"
    assert rt["Report"].print_title_cols == "$A:$B"

    op_rt = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op_rt["Report"].print_title_rows == "$1:$2"
        assert op_rt["Report"].print_title_cols == "$A:$B"
    finally:
        op_rt.close()


def test_g24_print_titles_modify_mode_can_clear_existing_titles(
    tmp_xlsx: Path, tmp_path: Path
) -> None:
    src = tmp_path / "source-print-titles.xlsx"
    op = openpyxl.Workbook()
    op.active.title = "Report"
    op.active["A1"] = "x"
    op.active.print_title_rows = "1:2"
    op.active.print_title_cols = "A:B"
    op.save(src)
    op.close()

    wb = wolfxl.load_workbook(src, modify=True)
    ws = wb["Report"]
    ws.print_title_rows = None
    ws.print_title_cols = None
    wb.save(tmp_xlsx)

    rt = wolfxl.load_workbook(tmp_xlsx)
    assert rt["Report"].print_title_rows is None
    assert rt["Report"].print_title_cols is None

    workbook_xml = _read_workbook_xml(tmp_xlsx)
    assert 'name="_xlnm.Print_Titles"' not in workbook_xml

    op_rt = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op_rt["Report"].print_title_rows is None
        assert op_rt["Report"].print_title_cols is None
    finally:
        op_rt.close()


def test_g24_print_titles_modify_mode_clearing_rows_preserves_columns(
    tmp_xlsx: Path, tmp_path: Path
) -> None:
    src = tmp_path / "source-print-title-cols.xlsx"
    op = openpyxl.Workbook()
    op.active.title = "Report"
    op.active["A1"] = "x"
    op.active.print_title_rows = "1:2"
    op.active.print_title_cols = "A:B"
    op.save(src)
    op.close()

    wb = wolfxl.load_workbook(src, modify=True)
    ws = wb["Report"]
    ws.print_title_rows = None
    wb.save(tmp_xlsx)

    rt = wolfxl.load_workbook(tmp_xlsx)
    assert rt["Report"].print_title_rows is None
    assert rt["Report"].print_title_cols == "$A:$B"

    op_rt = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op_rt["Report"].print_title_rows is None
        assert op_rt["Report"].print_title_cols == "$A:$B"
    finally:
        op_rt.close()


def test_page_margins_round_trip(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.page_margins = PageMargins(left=1.0, right=1.5, top=2.0, bottom=2.0,
                                  header=0.5, footer=0.5)
    wb.save(tmp_xlsx)

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        m = op.active.page_margins
        assert float(m.left) == 1.0
        assert float(m.right) == 1.5
        assert float(m.top) == 2.0
        assert float(m.bottom) == 2.0
        assert float(m.header) == 0.5
        assert float(m.footer) == 0.5
    finally:
        op.close()


def test_header_footer_odd_header_round_trip(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.header_footer = HeaderFooter(
        odd_header=HeaderFooterItem(left="L", center="C", right="R"),
    )
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert "<oddHeader>" in text
    # openpyxl recognises the embedded format codes.
    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        oh = op.active.oddHeader
        # openpyxl parses the &L/&C/&R back into separate segments
        assert oh.left.text == "L"
        assert oh.center.text == "C"
        assert oh.right.text == "R"
    finally:
        op.close()


def test_header_footer_different_first(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.header_footer.different_first = True
    wb.save(tmp_xlsx)

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        # openpyxl exposes this as differentFirst=True
        assert op.active.HeaderFooter.differentFirst is True
    finally:
        op.close()


def test_sheet_view_zoom_round_trip(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.sheet_view.zoom_scale = 150
    wb.save(tmp_xlsx)

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        sv = op.active.sheet_view
        assert int(sv.zoomScale) == 150
    finally:
        op.close()


def test_sheet_view_grid_lines_off(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.sheet_view.show_grid_lines = False
    wb.save(tmp_xlsx)

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        assert op.active.sheet_view.showGridLines is False
    finally:
        op.close()


def test_sheet_view_freeze_pane_via_typed_view(tmp_xlsx: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.sheet_view = SheetView(
        pane=Pane(ySplit=1.0, topLeftCell="A2", activePane="bottomLeft", state="frozen"),
    )
    wb.save(tmp_xlsx)

    text = _read_sheet_xml(tmp_xlsx)
    assert "<pane " in text
    assert 'ySplit="1"' in text
    assert 'topLeftCell="A2"' in text
    # openpyxl reads the pane back.
    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        pane = op.active.sheet_view.pane
        assert pane is not None
        assert pane.topLeftCell == "A2"
    finally:
        op.close()


def test_combined_print_settings(tmp_xlsx: Path) -> None:
    """Set page_setup + page_margins + header_footer all together;
    verify all three round-trip via openpyxl."""
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = 9
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.75, bottom=0.75,
                                  header=0.3, footer=0.3)
    ws.header_footer.odd_header.center = "Annual Report"
    wb.save(tmp_xlsx)

    op = openpyxl.load_workbook(tmp_xlsx)
    try:
        ws_op = op.active
        assert ws_op.page_setup.orientation == "landscape"
        assert int(ws_op.page_setup.paperSize) == 9
        assert float(ws_op.page_margins.left) == 0.5
        assert ws_op.oddHeader.center.text == "Annual Report"
    finally:
        op.close()
