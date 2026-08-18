"""Tests for wolfxl.calc formula parser and reference extraction."""

from __future__ import annotations

import pytest
from wolfxl.calc._parser import (
    FormulaParser,
    all_references,
    expand_range,
    parse_functions,
    parse_range_references,
    parse_references,
)


class TestSingleReferences:
    def test_simple_ref(self) -> None:
        refs = parse_references("=A1+B2", "Sheet1")
        assert refs == ["Sheet1!A1", "Sheet1!B2"]

    def test_dollar_signs_stripped(self) -> None:
        refs = parse_references("=$A$1+B$2+$C3", "Sheet1")
        assert refs == ["Sheet1!A1", "Sheet1!B2", "Sheet1!C3"]

    def test_cross_sheet_ref(self) -> None:
        refs = parse_references("=Sheet2!A1+B2", "Sheet1")
        assert refs == ["Sheet2!A1", "Sheet1!B2"]

    def test_quoted_sheet_ref(self) -> None:
        refs = parse_references("='Income Statement'!B5+A1", "Sheet1")
        assert refs == ["Income Statement!B5", "Sheet1!A1"]

    def test_no_duplicates(self) -> None:
        refs = parse_references("=A1+A1+A1", "Sheet1")
        assert refs == ["Sheet1!A1"]

    def test_string_literal_ignored(self) -> None:
        refs = parse_references('=A1&"Hello A2"', "Sheet1")
        assert refs == ["Sheet1!A1"]

    def test_case_normalized(self) -> None:
        refs = parse_references("=a1+b2", "Sheet1")
        assert refs == ["Sheet1!A1", "Sheet1!B2"]


class TestRangeReferences:
    def test_simple_range(self) -> None:
        ranges = parse_range_references("=SUM(A1:A5)", "Sheet1")
        assert ranges == ["Sheet1!A1:A5"]

    def test_cross_sheet_range(self) -> None:
        ranges = parse_range_references("=SUM(TB!B2:B5)", "IS")
        assert ranges == ["TB!B2:B5"]

    def test_quoted_sheet_range(self) -> None:
        ranges = parse_range_references("=SUM('Trial Balance'!A1:A10)", "Sheet1")
        assert ranges == ["Trial Balance!A1:A10"]

    def test_dollar_in_range(self) -> None:
        ranges = parse_range_references("=SUM($A$1:$A$5)", "Sheet1")
        assert ranges == ["Sheet1!A1:A5"]

    def test_single_refs_not_in_range(self) -> None:
        """Single refs inside a range shouldn't appear in parse_references."""
        refs = parse_references("=SUM(A1:A5)+B1", "Sheet1")
        # A1 and A5 are part of the range, only B1 is standalone
        assert refs == ["Sheet1!B1"]


class TestParseRangeSingleRefExclusion:
    def test_ref_at_start_of_range_excluded(self) -> None:
        """A1 in A1:A5 should not show as a standalone ref."""
        refs = parse_references("=SUM(A1:A5)", "Sheet1")
        assert refs == []

    def test_ref_outside_range_included(self) -> None:
        refs = parse_references("=SUM(A1:A5)+C1", "Sheet1")
        assert refs == ["Sheet1!C1"]


class TestParseFunctions:
    def test_simple_function(self) -> None:
        funcs = parse_functions("=SUM(A1:A5)")
        assert funcs == ["SUM"]

    def test_nested_functions(self) -> None:
        funcs = parse_functions("=IF(SUM(A1:A5)>0,ROUND(B1,2),0)")
        assert funcs == ["IF", "SUM", "ROUND"]

    def test_no_duplicates(self) -> None:
        funcs = parse_functions("=SUM(A1:A3)+SUM(B1:B3)")
        assert funcs == ["SUM"]

    def test_function_in_string_ignored(self) -> None:
        funcs = parse_functions('=A1&"SUM(B1)"')
        assert funcs == []


class TestExpandRange:
    def test_column_range(self) -> None:
        cells = expand_range("A1:A5")
        assert cells == ["A1", "A2", "A3", "A4", "A5"]

    def test_row_range(self) -> None:
        cells = expand_range("B2:D2")
        assert cells == ["B2", "C2", "D2"]

    def test_block_range(self) -> None:
        cells = expand_range("A1:B2")
        assert cells == ["A1", "B1", "A2", "B2"]

    def test_single_cell_range(self) -> None:
        cells = expand_range("A1:A1")
        assert cells == ["A1"]

    def test_with_sheet_prefix(self) -> None:
        cells = expand_range("Sheet2!A1:A3")
        assert cells == ["Sheet2!A1", "Sheet2!A2", "Sheet2!A3"]

    def test_quoted_sheet(self) -> None:
        cells = expand_range("'Income Statement'!B1:B3")
        assert cells == [
            "Income Statement!B1",
            "Income Statement!B2",
            "Income Statement!B3",
        ]

    def test_dollar_signs_handled(self) -> None:
        cells = expand_range("$A$1:$A$3")
        assert cells == ["A1", "A2", "A3"]

    def test_reversed_range_normalized(self) -> None:
        """A5:A1 should produce same result as A1:A5."""
        cells = expand_range("A5:A1")
        assert cells == ["A1", "A2", "A3", "A4", "A5"]

    def test_invalid_range(self) -> None:
        with pytest.raises(ValueError, match="Invalid range"):
            expand_range("A1")


class TestAllReferences:
    def test_combines_singles_and_ranges(self) -> None:
        refs = all_references("=SUM(A1:A3)+B1", "Sheet1")
        # B1 is standalone, A1:A3 expands to A1, A2, A3
        assert "Sheet1!B1" in refs
        assert "Sheet1!A1" in refs
        assert "Sheet1!A2" in refs
        assert "Sheet1!A3" in refs

    def test_no_duplicates_across_types(self) -> None:
        refs = all_references("=A1+SUM(A1:A3)", "Sheet1")
        # A1 appears as both standalone and in range - should only be listed once
        assert refs.count("Sheet1!A1") == 1

    def test_multi_sheet(self) -> None:
        refs = all_references("=Sheet1!A1+Sheet2!B1", "Sheet1")
        assert "Sheet1!A1" in refs
        assert "Sheet2!B1" in refs


class TestFormulaParser:
    def test_parse_refs(self) -> None:
        p = FormulaParser()
        refs = p.parse_refs("=SUM(A1:A3)+B1", "Sheet1")
        assert "Sheet1!B1" in refs
        assert "Sheet1!A1" in refs

    def test_compile_returns_none_without_formulas_lib(self) -> None:
        """compile() should return None gracefully when formulas lib is not installed."""
        p = FormulaParser()
        result = p.compile("=SUM(A1:A5)")
        # May be None if formulas is not installed, or a callable if it is
        if result is not None:
            assert callable(result)
