"""RFC-055 §2.4 — print_title_rows / print_title_cols tests (Sprint Ο Pod 1A)."""

from __future__ import annotations

import pytest

from wolfxl import Workbook
from wolfxl.worksheet.print_settings import (
    ColRange,
    PrintTitles,
    RowRange,
)


class TestRowRange:
    def test_from_string_basic(self):
        r = RowRange.from_string("1:2")
        assert r.min_row == 1
        assert r.max_row == 2

    def test_from_string_with_dollar(self):
        r = RowRange.from_string("$1:$3")
        assert r.min_row == 1
        assert r.max_row == 3

    def test_from_string_invalid_raises(self):
        with pytest.raises(ValueError):
            RowRange.from_string("abc")
        with pytest.raises(ValueError):
            RowRange.from_string("0:1")

    def test_str_round_trips(self):
        r = RowRange.from_string("5:10")
        assert str(r) == "$5:$10"


class TestColRange:
    def test_from_string_basic(self):
        c = ColRange.from_string("A:B")
        assert c.min_col == "A"
        assert c.max_col == "B"

    def test_from_string_lowercase_normalizes(self):
        c = ColRange.from_string("a:c")
        assert c.min_col == "A"
        assert c.max_col == "C"

    def test_from_string_invalid_raises(self):
        with pytest.raises(ValueError):
            ColRange.from_string("1:2")


class TestWorksheetPrintTitles:
    def test_default_is_none(self):
        wb = Workbook()
        ws = wb.active
        assert ws.print_title_rows is None
        assert ws.print_title_cols is None

    def test_set_rows(self):
        wb = Workbook()
        ws = wb.active
        ws.print_title_rows = "1:2"
        assert ws.print_title_rows == "$1:$2"

    def test_set_cols(self):
        wb = Workbook()
        ws = wb.active
        ws.print_title_cols = "A:B"
        assert ws.print_title_cols == "$A:$B"

    def test_set_invalid_rows_raises(self):
        wb = Workbook()
        ws = wb.active
        with pytest.raises(ValueError):
            ws.print_title_rows = "garbage"

    def test_set_invalid_cols_raises(self):
        wb = Workbook()
        ws = wb.active
        with pytest.raises(ValueError):
            ws.print_title_cols = "1:2"

    def test_clear_with_none(self):
        wb = Workbook()
        ws = wb.active
        ws.print_title_rows = "1:1"
        ws.print_title_rows = None
        assert ws.print_title_rows is None

    def test_definedname_value_quotes_sheet_name_with_space(self):
        pt = PrintTitles(rows=RowRange.from_string("1:2"))
        v = pt.to_definedname_value("My Sheet")
        assert v == "'My Sheet'!$1:$2"

    def test_definedname_value_with_rows_and_cols(self):
        pt = PrintTitles(
            rows=RowRange.from_string("1:2"),
            cols=ColRange.from_string("A:B"),
        )
        v = pt.to_definedname_value("Sheet1")
        assert v == "Sheet1!$1:$2,Sheet1!$A:$B"
