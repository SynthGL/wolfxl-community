"""RFC-055 §2.5 — SheetView tests (Sprint Ο Pod 1A)."""

from __future__ import annotations

import pytest

from wolfxl import Workbook
from wolfxl.worksheet.views import Pane, Selection, SheetView, SheetViewList


class TestPane:
    def test_default(self):
        p = Pane()
        assert p.x_split == 0.0
        assert p.y_split == 0.0
        assert p.top_left_cell == "A1"
        assert p.active_pane == "topLeft"
        assert p.state == "frozen"

    def test_invalid_active_pane_raises(self):
        with pytest.raises(ValueError, match="active_pane|activePane"):
            Pane(activePane="middleLeft")

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError, match="state"):
            Pane(state="floating")

    def test_to_rust_dict(self):
        p = Pane(xSplit=2.0, ySplit=1.0, topLeftCell="C2",
                 activePane="bottomRight", state="frozen")
        assert p.to_rust_dict() == {
            "x_split": 2.0,
            "y_split": 1.0,
            "top_left_cell": "C2",
            "active_pane": "bottomRight",
            "state": "frozen",
        }


class TestSelection:
    def test_default(self):
        s = Selection()
        assert s.active_cell == "A1"
        assert s.sqref == "A1"
        assert s.pane is None

    def test_invalid_pane_raises(self):
        with pytest.raises(ValueError, match="pane"):
            Selection(pane="middleLeft")

    def test_pane_none_accepted(self):
        s = Selection(pane=None)
        assert s.pane is None


class TestSheetView:
    def test_default_is_default(self):
        sv = SheetView()
        assert sv.is_default()

    def test_zoom_scale_setter_validates(self):
        sv = SheetView()
        sv.zoom_scale = 200
        assert sv.zoomScale == 200
        with pytest.raises(ValueError):
            sv.zoom_scale = 1000

    def test_invalid_view_raises(self):
        with pytest.raises(ValueError, match="view"):
            SheetView(view="invented")

    def test_show_grid_lines_alias(self):
        sv = SheetView()
        sv.show_grid_lines = False
        assert sv.showGridLines is False
        assert sv.show_grid_lines is False

    def test_to_rust_dict_emits_pane(self):
        sv = SheetView()
        sv.pane = Pane(xSplit=1.0, ySplit=1.0, topLeftCell="B2",
                       activePane="bottomRight", state="frozen")
        d = sv.to_rust_dict()
        assert d["pane"] is not None
        assert d["pane"]["top_left_cell"] == "B2"


class TestWorksheetSheetView:
    def test_lazy_access(self):
        wb = Workbook()
        ws = wb.active
        assert isinstance(ws.sheet_view, SheetView)

    def test_freeze_panes_mirrors_into_sheet_view(self):
        wb = Workbook()
        ws = wb.active
        ws.freeze_panes = "B2"
        assert ws.sheet_view.pane is not None
        assert ws.sheet_view.pane.top_left_cell == "B2"

    def test_freeze_panes_clear_clears_pane(self):
        wb = Workbook()
        ws = wb.active
        ws.freeze_panes = "B2"
        # Materialize the view so the setter runs the mirror.
        _ = ws.sheet_view
        ws.freeze_panes = None
        assert ws.sheet_view.pane is None

    def test_openpyxl_surface_aliases(self):
        wb = Workbook()
        ws = wb.active
        assert ws.BREAK_ROW == 1
        assert ws.ORIENTATION_LANDSCAPE == "landscape"
        assert ws.PAPERSIZE_A4 == "9"
        assert ws.SHEETSTATE_VISIBLE == "visible"
        assert ws.active_cell == "A1"
        assert ws.selected_cell == "A1"
        assert ws.show_gridlines is None
        ws.show_gridlines = False
        assert ws.sheet_view.showGridLines is False
        assert len(ws.views.sheetView) == 1
        assert ws.oddHeader is ws.header_footer.odd_header
        assert ws.evenFooter is ws.header_footer.even_footer
        assert ws.print_titles == ""
        assert ws.array_formulae == {}
        assert ws.column_groups == []
        assert ws.defined_names == {}
        assert ws.legacy_drawing is None
        assert ws.encoding == "utf-8"
        assert (
            ws.mime_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
        )
        assert ws.path == "/xl/worksheets/sheet1.xml"

    def test_set_printer_settings_matches_openpyxl_helper(self):
        wb = Workbook()
        ws = wb.active
        ws.set_printer_settings(ws.PAPERSIZE_A4, ws.ORIENTATION_LANDSCAPE)
        assert ws.page_setup.paperSize == ws.PAPERSIZE_A4
        assert ws.page_setup.orientation == ws.ORIENTATION_LANDSCAPE


class TestSheetViewList:
    def test_default_creates_one_view(self):
        svl = SheetViewList()
        assert len(svl) == 1
        assert isinstance(svl[0], SheetView)

    def test_iter(self):
        svl = SheetViewList()
        seen = list(svl)
        assert len(seen) == 1
