"""RFC-062 §2.1 — Break / RowBreak / ColBreak / PageBreakList tests.

Sprint Π Pod Π-α. Construction, attribute access, append semantics,
counters, and the §10 ``to_rust_dict()`` contract for the Rust side.
"""

from __future__ import annotations

import pytest

from wolfxl import Workbook
from wolfxl.worksheet.pagebreak import (
    Break,
    ColBreak,
    PageBreak,
    PageBreakList,
    RowBreak,
)


# ---------------------------------------------------------------------------
# Break / RowBreak / ColBreak construction
# ---------------------------------------------------------------------------


class TestBreakConstruction:
    def test_default_break(self):
        b = Break()
        assert b.id == 0
        assert b.min == 0
        assert b.max == 16383
        assert b.man is True
        assert b.pt is None

    def test_break_with_id(self):
        b = Break(id=5)
        assert b.id == 5

    def test_break_with_all_fields(self):
        b = Break(id=12, min=0, max=16383, man=False, pt=True)
        assert b.id == 12
        assert b.min == 0
        assert b.max == 16383
        assert b.man is False
        assert b.pt is True

    def test_row_break_inherits(self):
        rb = RowBreak(id=7)
        assert isinstance(rb, Break)
        assert isinstance(rb, RowBreak)
        assert rb.id == 7

    def test_col_break_inherits(self):
        cb = ColBreak(id=3)
        assert isinstance(cb, Break)
        assert isinstance(cb, ColBreak)
        assert cb.id == 3

    def test_page_break_alias_is_row_break(self):
        # openpyxl's PageBreak alias points at RowBreak.
        assert PageBreak is RowBreak

    def test_row_and_col_break_iter_match_openpyxl_container_attrs(self):
        from openpyxl.worksheet.pagebreak import ColBreak as OpenpyxlColBreak
        from openpyxl.worksheet.pagebreak import RowBreak as OpenpyxlRowBreak

        assert list(RowBreak()) == list(OpenpyxlRowBreak())
        assert list(ColBreak()) == list(OpenpyxlColBreak())

        row_break = RowBreak()
        openpyxl_row_break = OpenpyxlRowBreak()
        row_break.append()
        openpyxl_row_break.append()
        assert list(row_break) == list(openpyxl_row_break)

    def test_break_to_rust_dict(self):
        b = Break(id=5, min=0, max=16383)
        assert b.to_rust_dict() == {
            "id": 5,
            "min": 0,
            "max": 16383,
            "man": True,
            "pt": None,
        }

    def test_break_to_rust_dict_with_none(self):
        b = Break(id=4)
        d = b.to_rust_dict()
        assert d["min"] == 0
        assert d["max"] == 16383
        assert d["man"] is True
        assert d["pt"] is None


# ---------------------------------------------------------------------------
# PageBreakList container
# ---------------------------------------------------------------------------


class TestPageBreakList:
    def test_empty_list(self):
        pl = PageBreakList()
        assert len(pl) == 0
        assert pl.count == 0
        assert pl.manualBreakCount == 0
        assert list(pl) == []
        assert not pl  # __bool__ False on empty

    def test_append_single(self):
        pl = PageBreakList()
        pl.append(RowBreak(id=5))
        assert len(pl) == 1
        assert pl.count == 1
        assert pl.manualBreakCount == 1
        assert pl  # __bool__ True

    def test_append_multiple(self):
        pl = PageBreakList()
        pl.append(RowBreak(id=2))
        pl.append(RowBreak(id=5))
        pl.append(RowBreak(id=8))
        assert len(pl) == 3
        assert pl.count == 3
        assert pl.manualBreakCount == 3

    def test_manual_count_excludes_auto(self):
        pl = PageBreakList()
        pl.append(RowBreak(id=2, man=True))
        pl.append(RowBreak(id=5, man=False))
        pl.append(RowBreak(id=8, man=True))
        assert pl.count == 3
        assert pl.manualBreakCount == 2

    def test_append_rejects_non_break(self):
        pl = PageBreakList()
        with pytest.raises(TypeError):
            pl.append("not a break")
        with pytest.raises(TypeError):
            pl.append(42)

    def test_iter_preserves_order(self):
        pl = PageBreakList()
        pl.append(RowBreak(id=10))
        pl.append(RowBreak(id=2))
        pl.append(RowBreak(id=7))
        ids = [b.id for b in pl]
        assert ids == [10, 2, 7]

    def test_construction_from_breaks_list(self):
        # Constructing with breaks=[...] refreshes counts.
        pl = PageBreakList(breaks=[RowBreak(id=1), RowBreak(id=2, man=False)])
        assert pl.count == 2
        assert pl.manualBreakCount == 1

    def test_contains(self):
        b1 = RowBreak(id=5)
        b2 = RowBreak(id=10)
        pl = PageBreakList()
        pl.append(b1)
        assert b1 in pl
        assert b2 not in pl

    def test_to_rust_dict_empty(self):
        pl = PageBreakList()
        d = pl.to_rust_dict()
        assert d == {"count": 0, "manual_break_count": 0, "breaks": []}

    def test_to_rust_dict_with_breaks(self):
        pl = PageBreakList()
        pl.append(RowBreak(id=5, min=0, max=16383, man=True))
        d = pl.to_rust_dict()
        assert d == {
            "count": 1,
            "manual_break_count": 1,
            "breaks": [
                {"id": 5, "min": 0, "max": 16383, "man": True, "pt": None}
            ],
        }


# ---------------------------------------------------------------------------
# Worksheet integration
# ---------------------------------------------------------------------------


class TestWorksheetRowBreaks:
    def test_lazy_access_creates_empty_list(self):
        wb = Workbook()
        ws = wb.active
        rb = ws.row_breaks
        assert isinstance(rb, PageBreakList)
        assert len(rb) == 0

    def test_same_instance_returned_on_second_access(self):
        wb = Workbook()
        ws = wb.active
        rb1 = ws.row_breaks
        rb2 = ws.row_breaks
        assert rb1 is rb2

    def test_append_to_row_breaks(self):
        wb = Workbook()
        ws = wb.active
        ws.row_breaks.append(RowBreak(id=5))
        ws.row_breaks.append(RowBreak(id=10))
        assert len(ws.row_breaks) == 2
        assert ws.row_breaks.count == 2

    def test_replacement_assignment(self):
        wb = Workbook()
        ws = wb.active
        new_pl = PageBreakList()
        new_pl.append(RowBreak(id=99))
        ws.row_breaks = new_pl
        assert ws.row_breaks is new_pl
        assert len(ws.row_breaks) == 1

    def test_col_breaks_same_lazy_pattern(self):
        wb = Workbook()
        ws = wb.active
        cb = ws.col_breaks
        assert isinstance(cb, PageBreakList)
        assert len(cb) == 0
        ws.col_breaks.append(ColBreak(id=4))
        assert len(ws.col_breaks) == 1

    def test_page_breaks_alias_is_row_breaks(self):
        wb = Workbook()
        ws = wb.active
        ws.page_breaks.append(RowBreak(id=3))
        # ``page_breaks`` is a row-breaks alias (openpyxl shape).
        assert ws.row_breaks is ws.page_breaks
        assert len(ws.row_breaks) == 1

    def test_zero_overhead_when_untouched(self):
        wb = Workbook()
        ws = wb.active
        # Internal sentinel must remain None until first access.
        assert ws._row_breaks is None
        assert ws._col_breaks is None


class TestWorksheetToRustPageBreaksDict:
    def test_empty_when_no_breaks_set(self):
        wb = Workbook()
        ws = wb.active
        d = ws.to_rust_page_breaks_dict()
        assert d == {"row_breaks": None, "col_breaks": None}

    def test_empty_when_lists_initialized_but_zero_breaks(self):
        wb = Workbook()
        ws = wb.active
        # Force lazy init but don't append.
        _ = ws.row_breaks
        _ = ws.col_breaks
        d = ws.to_rust_page_breaks_dict()
        assert d == {"row_breaks": None, "col_breaks": None}

    def test_with_row_breaks_only(self):
        wb = Workbook()
        ws = wb.active
        ws.row_breaks.append(RowBreak(id=5, min=0, max=16383))
        d = ws.to_rust_page_breaks_dict()
        assert d["row_breaks"]["count"] == 1
        assert d["col_breaks"] is None

    def test_with_both_row_and_col_breaks(self):
        wb = Workbook()
        ws = wb.active
        ws.row_breaks.append(RowBreak(id=5))
        ws.col_breaks.append(ColBreak(id=3))
        d = ws.to_rust_page_breaks_dict()
        assert d["row_breaks"]["count"] == 1
        assert d["col_breaks"]["count"] == 1

    def test_breaks_dict_shape_matches_section_10(self):
        wb = Workbook()
        ws = wb.active
        ws.row_breaks.append(RowBreak(id=5, min=0, max=16383, man=True))
        ws.row_breaks.append(RowBreak(id=10, min=0, max=16383, man=True))
        d = ws.to_rust_page_breaks_dict()
        rb = d["row_breaks"]
        assert rb["count"] == 2
        assert rb["manual_break_count"] == 2
        assert len(rb["breaks"]) == 2
        assert rb["breaks"][0] == {
            "id": 5,
            "min": 0,
            "max": 16383,
            "man": True,
            "pt": None,
        }


# ---------------------------------------------------------------------------
# Save round-trip — write mode
# ---------------------------------------------------------------------------


class TestSaveRoundTrip:
    def test_save_with_row_breaks_emits_xml(self, tmp_path):
        import zipfile

        p = tmp_path / "rb.xlsx"
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "hello"
        ws.row_breaks.append(RowBreak(id=5, min=0, max=16383))
        wb.save(str(p))
        with zipfile.ZipFile(p) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode()
        assert "<rowBreaks" in xml
        assert 'id="5"' in xml
        assert 'count="1"' in xml
        assert 'manualBreakCount="1"' in xml

    def test_save_with_col_breaks_emits_xml(self, tmp_path):
        import zipfile

        p = tmp_path / "cb.xlsx"
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "hello"
        ws.col_breaks.append(ColBreak(id=3, min=0, max=1048575))
        wb.save(str(p))
        with zipfile.ZipFile(p) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode()
        assert "<colBreaks" in xml
        assert 'id="3"' in xml

    def test_save_with_both_breaks(self, tmp_path):
        import zipfile

        p = tmp_path / "both.xlsx"
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "x"
        ws.row_breaks.append(RowBreak(id=5))
        ws.col_breaks.append(ColBreak(id=3))
        wb.save(str(p))
        with zipfile.ZipFile(p) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode()
        # Both elements present.
        assert "<rowBreaks" in xml
        assert "<colBreaks" in xml
        # rowBreaks (slot 24) before colBreaks (slot 25).
        assert xml.index("<rowBreaks") < xml.index("<colBreaks")

    def test_no_break_elements_when_lists_empty(self, tmp_path):
        import zipfile

        p = tmp_path / "empty.xlsx"
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "hello"
        # Force lazy init but don't append.
        _ = ws.row_breaks
        _ = ws.col_breaks
        wb.save(str(p))
        with zipfile.ZipFile(p) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode()
        assert "<rowBreaks" not in xml
        assert "<colBreaks" not in xml

    def test_multiple_breaks_preserved(self, tmp_path):
        import zipfile

        p = tmp_path / "multi.xlsx"
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "x"
        for i in (5, 10, 15):
            ws.row_breaks.append(RowBreak(id=i, min=0, max=16383))
        wb.save(str(p))
        with zipfile.ZipFile(p) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode()
        assert 'count="3"' in xml
        for i in (5, 10, 15):
            assert f'id="{i}"' in xml
