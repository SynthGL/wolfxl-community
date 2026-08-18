"""RFC-055 §2.2 — PageMargins tests (Sprint Ο Pod 1A)."""

from __future__ import annotations

from wolfxl import Workbook
from wolfxl.worksheet.page_setup import PageMargins


class TestWorksheetPageMargins:
    def test_lazy_access(self):
        wb = Workbook()
        ws = wb.active
        pm = ws.page_margins
        assert isinstance(pm, PageMargins)
        assert pm.is_default()

    def test_default_values_in_inches(self):
        pm = PageMargins()
        # openpyxl worksheet defaults from CT_PageMargins, in inches.
        assert pm.left == 0.75
        assert pm.top == 1.0
        assert pm.header == 0.5
        assert pm.footer == 0.5

    def test_mutation_via_attribute(self):
        wb = Workbook()
        ws = wb.active
        ws.page_margins.left = 1.0
        ws.page_margins.right = 1.0
        assert ws.page_margins.left == 1.0
        assert ws.page_margins.right == 1.0

    def test_replacement_assignment(self):
        wb = Workbook()
        ws = wb.active
        new_pm = PageMargins(top=2.0, bottom=2.0, left=1.5, right=1.5,
                             header=1.0, footer=1.0)
        ws.page_margins = new_pm
        assert ws.page_margins.top == 2.0
        assert ws.page_margins.left == 1.5

    def test_rust_dict_round_trips(self):
        pm = PageMargins(top=1.0, bottom=1.0, left=0.5, right=0.5)
        d = pm.to_rust_dict()
        assert d == {
            "top": 1.0, "bottom": 1.0,
            "left": 0.5, "right": 0.5,
            "header": 0.5, "footer": 0.5,
        }

    def test_is_default_post_mutation(self):
        pm = PageMargins(top=0.5)
        assert not pm.is_default()
        pm2 = PageMargins()
        assert pm2.is_default()
