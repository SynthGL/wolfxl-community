"""Tests for lookup and conditional aggregation builtins.

Covers: INDEX, MATCH, VLOOKUP, HLOOKUP, XLOOKUP, CHOOSE, SUMIF, SUMIFS,
COUNTIF, COUNTIFS, the ``&`` string concatenation operator, RangeValue
backward compatibility, and perturbation propagation through lookup/conditional
chains.
"""

from __future__ import annotations

from wolfxl.calc._evaluator import WorkbookEvaluator
from wolfxl.calc._functions import RangeValue, _match_criteria, _parse_criteria

import wolfxl

# ---------------------------------------------------------------------------
# Helper: build workbook with data + formulas
# ---------------------------------------------------------------------------


def _make_wb(data: dict[str, object], formulas: dict[str, str]) -> wolfxl.Workbook:
    wb = wolfxl.Workbook()
    ws = wb.active
    for ref, val in data.items():
        ws[ref] = val
    for ref, formula in formulas.items():
        ws[ref] = formula
    return wb


def _calc(wb: wolfxl.Workbook) -> dict[str, object]:
    ev = WorkbookEvaluator()
    ev.load(wb)
    return ev.calculate()


# ---------------------------------------------------------------------------
# RangeValue unit tests
# ---------------------------------------------------------------------------


class TestRangeValue:
    def test_get_2d(self) -> None:
        rv = RangeValue(values=[1, 2, 3, 4, 5, 6], n_rows=2, n_cols=3)
        assert rv.get(1, 1) == 1
        assert rv.get(1, 3) == 3
        assert rv.get(2, 2) == 5

    def test_get_out_of_bounds(self) -> None:
        rv = RangeValue(values=[1, 2, 3], n_rows=3, n_cols=1)
        assert rv.get(4, 1) is None
        assert rv.get(0, 1) is None

    def test_column_extraction(self) -> None:
        rv = RangeValue(values=[1, 2, 3, 4, 5, 6], n_rows=3, n_cols=2)
        assert rv.column(1) == [1, 3, 5]
        assert rv.column(2) == [2, 4, 6]

    def test_row_extraction(self) -> None:
        rv = RangeValue(values=[1, 2, 3, 4, 5, 6], n_rows=3, n_cols=2)
        assert rv.row(1) == [1, 2]
        assert rv.row(3) == [5, 6]

    def test_iterable_and_len(self) -> None:
        rv = RangeValue(values=[10, 20, 30], n_rows=3, n_cols=1)
        assert list(rv) == [10, 20, 30]
        assert len(rv) == 3


# ---------------------------------------------------------------------------
# RangeValue backward compatibility with existing builtins
# ---------------------------------------------------------------------------


class TestRangeValueBackwardCompat:
    def test_sum_with_range_value(self) -> None:
        """SUM should still work when args contain RangeValue."""
        wb = _make_wb(
            {"A1": 10, "A2": 20, "A3": 30},
            {"B1": "=SUM(A1:A3)"},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == 60.0

    def test_and_with_range_value(self) -> None:
        wb = _make_wb(
            {"A1": True, "A2": True, "A3": True},
            {"B1": "=AND(A1:A3)"},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] is True

    def test_or_with_range_value(self) -> None:
        wb = _make_wb(
            {"A1": False, "A2": True, "A3": False},
            {"B1": "=OR(A1:A3)"},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] is True

    def test_counta_with_range_value(self) -> None:
        wb = _make_wb(
            {"A1": "hello", "A2": None, "A3": 42},
            {"B1": "=COUNTA(A1:A3)"},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == 2.0


# ---------------------------------------------------------------------------
# INDEX tests
# ---------------------------------------------------------------------------


class TestBuiltinIndex:
    def test_1d_column_vector(self) -> None:
        wb = _make_wb(
            {"A1": 10, "A2": 20, "A3": 30, "A4": 40, "A5": 50},
            {"B1": "=INDEX(A1:A5,3)"},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == 30

    def test_2d_array(self) -> None:
        wb = _make_wb(
            {"A1": 1, "B1": 2, "C1": 3,
             "A2": 4, "B2": 5, "C2": 6,
             "A3": 7, "B3": 8, "C3": 9},
            {"D1": "=INDEX(A1:C3,2,2)"},
        )
        results = _calc(wb)
        assert results["Sheet!D1"] == 5

    def test_1d_horizontal(self) -> None:
        wb = _make_wb(
            {"A1": 100, "B1": 200, "C1": 300},
            {"D1": "=INDEX(A1:C1,2)"},
        )
        results = _calc(wb)
        assert results["Sheet!D1"] == 200

    def test_nested_index_match(self) -> None:
        """The critical INDEX/MATCH pattern used in financial models."""
        wb = _make_wb(
            {"A1": "Revenue", "A2": "COGS", "A3": "OpEx", "A4": "Tax", "A5": "NetInc",
             "B1": 1000, "B2": 600, "B3": 200, "B4": 50, "B5": 150,
             "C1": "COGS"},
            {"D1": "=INDEX(B1:B5,MATCH(C1,A1:A5,0))"},
        )
        results = _calc(wb)
        assert results["Sheet!D1"] == 600

    def test_out_of_bounds(self) -> None:
        wb = _make_wb(
            {"A1": 10, "A2": 20},
            {"B1": "=INDEX(A1:A2,5)"},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == "#REF!"


# ---------------------------------------------------------------------------
# MATCH tests
# ---------------------------------------------------------------------------


class TestBuiltinMatch:
    def test_exact_match_numeric(self) -> None:
        wb = _make_wb(
            {"A1": 10, "A2": 20, "A3": 30, "A4": 40, "A5": 50},
            {"B1": "=MATCH(30,A1:A5,0)"},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == 3

    def test_case_insensitive_string(self) -> None:
        wb = _make_wb(
            {"A1": "Apple", "A2": "Banana", "A3": "Cherry"},
            {"B1": '=MATCH("banana",A1:A3,0)'},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == 2

    def test_not_found(self) -> None:
        wb = _make_wb(
            {"A1": 1, "A2": 2, "A3": 3},
            {"B1": "=MATCH(99,A1:A3,0)"},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == "#N/A"

    def test_approximate_match_ascending(self) -> None:
        wb = _make_wb(
            {"A1": 10, "A2": 20, "A3": 30, "A4": 40},
            {"B1": "=MATCH(25,A1:A4,1)"},
        )
        results = _calc(wb)
        # Largest <= 25 is 20 at position 2
        assert results["Sheet!B1"] == 2


# ---------------------------------------------------------------------------
# XLOOKUP tests
# ---------------------------------------------------------------------------


class TestBuiltinXlookup:
    def test_basic_exact(self) -> None:
        wb = _make_wb(
            {"A1": 1, "A2": 2, "A3": 3,
             "B1": "Red", "B2": "Green", "B3": "Blue"},
            {"C1": "=XLOOKUP(2,A1:A3,B1:B3)"},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == "Green"

    def test_not_found_default(self) -> None:
        wb = _make_wb(
            {"A1": 1, "A2": 2, "A3": 3,
             "B1": "Red", "B2": "Green", "B3": "Blue"},
            {"C1": '=XLOOKUP(99,A1:A3,B1:B3,"Not found")'},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == "Not found"

    def test_string_lookup(self) -> None:
        wb = _make_wb(
            {"A1": "Revenue", "A2": "COGS", "A3": "OpEx",
             "B1": 1000, "B2": 600, "B3": 200},
            {"C1": '=XLOOKUP("COGS",A1:A3,B1:B3)'},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == 600


# ---------------------------------------------------------------------------
# VLOOKUP tests
# ---------------------------------------------------------------------------


class TestBuiltinVlookup:
    def test_exact_match_numeric(self) -> None:
        """VLOOKUP with FALSE (exact match) on numeric keys."""
        wb = _make_wb(
            {"A1": 1, "B1": 100,
             "A2": 2, "B2": 200,
             "A3": 3, "B3": 300},
            {"C1": "=VLOOKUP(2,A1:B3,2,FALSE)"},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == 200

    def test_exact_match_string(self) -> None:
        """VLOOKUP case-insensitive string lookup."""
        wb = _make_wb(
            {"A1": "Revenue", "B1": 1000,
             "A2": "COGS", "B2": 600,
             "A3": "OpEx", "B3": 200},
            {"C1": '=VLOOKUP("cogs",A1:B3,2,FALSE)'},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == 600

    def test_approximate_match(self) -> None:
        """VLOOKUP with TRUE (approximate match, default) on sorted data."""
        wb = _make_wb(
            {"A1": 10, "B1": "Low",
             "A2": 50, "B2": "Medium",
             "A3": 100, "B3": "High"},
            {"C1": "=VLOOKUP(75,A1:B3,2,TRUE)"},
        )
        results = _calc(wb)
        # 75 falls between 50 and 100, largest <= 75 is 50 -> "Medium"
        assert results["Sheet!C1"] == "Medium"

    def test_not_found_returns_na(self) -> None:
        wb = _make_wb(
            {"A1": 1, "B1": 100, "A2": 2, "B2": 200},
            {"C1": "=VLOOKUP(99,A1:B2,2,FALSE)"},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == "#N/A"

    def test_col_index_out_of_bounds(self) -> None:
        wb = _make_wb(
            {"A1": 1, "B1": 100},
            {"C1": "=VLOOKUP(1,A1:B1,5,FALSE)"},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == "#REF!"

    def test_nested_with_cell_ref_lookup(self) -> None:
        """VLOOKUP with lookup_value from a cell reference."""
        wb = _make_wb(
            {"A1": "4001", "B1": "Cash",
             "A2": "5001", "B2": "Revenue",
             "A3": "6001", "B3": "Rent Expense",
             "C1": "5001"},
            {"D1": "=VLOOKUP(C1,A1:B3,2,FALSE)"},
        )
        results = _calc(wb)
        assert results["Sheet!D1"] == "Revenue"

    def test_default_range_lookup_is_true(self) -> None:
        """VLOOKUP without 4th arg defaults to approximate match."""
        wb = _make_wb(
            {"A1": 0, "B1": "Zero",
             "A2": 100, "B2": "Hundred",
             "A3": 1000, "B3": "Thousand"},
            {"C1": "=VLOOKUP(500,A1:B3,2)"},
        )
        results = _calc(wb)
        # Default range_lookup=TRUE, largest <= 500 is 100 -> "Hundred"
        assert results["Sheet!C1"] == "Hundred"


# ---------------------------------------------------------------------------
# HLOOKUP tests
# ---------------------------------------------------------------------------


class TestBuiltinHlookup:
    def test_exact_match(self) -> None:
        """HLOOKUP with exact match on first row."""
        wb = _make_wb(
            {"A1": "Q1", "B1": "Q2", "C1": "Q3",
             "A2": 100, "B2": 200, "C2": 300,
             "A3": 50, "B3": 75, "C3": 90},
            {"D1": '=HLOOKUP("Q2",A1:C3,2,FALSE)'},
        )
        results = _calc(wb)
        assert results["Sheet!D1"] == 200

    def test_row_3_return(self) -> None:
        """HLOOKUP returning from row 3."""
        wb = _make_wb(
            {"A1": "Q1", "B1": "Q2", "C1": "Q3",
             "A2": 100, "B2": 200, "C2": 300,
             "A3": 50, "B3": 75, "C3": 90},
            {"D1": '=HLOOKUP("Q3",A1:C3,3,FALSE)'},
        )
        results = _calc(wb)
        assert results["Sheet!D1"] == 90

    def test_approximate_match(self) -> None:
        """HLOOKUP with approximate match on numeric first row."""
        wb = _make_wb(
            {"A1": 2020, "B1": 2021, "C1": 2022,
             "A2": 100, "B2": 200, "C2": 300},
            {"D1": "=HLOOKUP(2021.5,A1:C2,2,TRUE)"},
        )
        results = _calc(wb)
        # Largest <= 2021.5 is 2021 -> row 2 = 200
        assert results["Sheet!D1"] == 200

    def test_not_found(self) -> None:
        wb = _make_wb(
            {"A1": "X", "B1": "Y", "A2": 1, "B2": 2},
            {"C1": '=HLOOKUP("Z",A1:B2,2,FALSE)'},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == "#N/A"

    def test_row_index_out_of_bounds(self) -> None:
        wb = _make_wb(
            {"A1": "Q1", "B1": "Q2", "A2": 10, "B2": 20},
            {"C1": '=HLOOKUP("Q1",A1:B2,5,FALSE)'},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == "#REF!"


# ---------------------------------------------------------------------------
# CHOOSE tests
# ---------------------------------------------------------------------------


class TestBuiltinChoose:
    def test_basic_selection(self) -> None:
        wb = _make_wb(
            {},
            {"A1": '=CHOOSE(2,"a","b","c")'},
        )
        results = _calc(wb)
        assert results["Sheet!A1"] == "b"

    def test_with_cell_refs(self) -> None:
        wb = _make_wb(
            {"A1": 3, "B1": 100, "B2": 200, "B3": 300},
            {"C1": "=CHOOSE(A1,B1,B2,B3)"},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == 300


# ---------------------------------------------------------------------------
# SUMIF tests
# ---------------------------------------------------------------------------


class TestBuiltinSumif:
    def test_operator_criteria(self) -> None:
        wb = _make_wb(
            {"A1": 10, "A2": 60, "A3": 30, "A4": 80, "A5": 20,
             "B1": 1, "B2": 2, "B3": 3, "B4": 4, "B5": 5},
            {"C1": '=SUMIF(A1:A5,">50",B1:B5)'},
        )
        results = _calc(wb)
        # A2=60 and A4=80 match >50 -> B2+B4 = 2+4 = 6
        assert results["Sheet!C1"] == 6.0

    def test_string_exact_match(self) -> None:
        wb = _make_wb(
            {"A1": "Sales", "A2": "Marketing", "A3": "Sales", "A4": "Engineering",
             "B1": 100, "B2": 200, "B3": 300, "B4": 400},
            {"C1": '=SUMIF(A1:A4,"Sales",B1:B4)'},
        )
        results = _calc(wb)
        assert results["Sheet!C1"] == 400.0  # 100 + 300

    def test_wildcard_criteria(self) -> None:
        wb = _make_wb(
            {"A1": "apple", "A2": "apricot", "A3": "banana", "A4": "avocado",
             "B1": 10, "B2": 20, "B3": 30, "B4": 40},
            {"C1": '=SUMIF(A1:A4,"a*",B1:B4)'},
        )
        results = _calc(wb)
        # apple, apricot, avocado match "a*" -> 10+20+40 = 70
        assert results["Sheet!C1"] == 70.0

    def test_no_sum_range(self) -> None:
        wb = _make_wb(
            {"A1": 10, "A2": 60, "A3": 30, "A4": 80, "A5": 20},
            {"B1": '=SUMIF(A1:A5,">50")'},
        )
        results = _calc(wb)
        # Sums criteria range itself: 60 + 80 = 140
        assert results["Sheet!B1"] == 140.0


# ---------------------------------------------------------------------------
# SUMIFS tests
# ---------------------------------------------------------------------------


class TestBuiltinSumifs:
    def test_two_criteria(self) -> None:
        wb = _make_wb(
            {"A1": 20, "A2": 5, "A3": 30, "A4": 15, "A5": 25,
             "B1": "Sales", "B2": "Sales", "B3": "Marketing", "B4": "Sales", "B5": "Sales",
             "C1": 100, "C2": 200, "C3": 300, "C4": 400, "C5": 500},
            {"D1": '=SUMIFS(C1:C5,A1:A5,">10",B1:B5,"Sales")'},
        )
        results = _calc(wb)
        # A>10 AND B="Sales": rows 1 (20,Sales,100), 4 (15,Sales,400), 5 (25,Sales,500) = 1000
        assert results["Sheet!D1"] == 1000.0

    def test_numeric_criteria_pair(self) -> None:
        wb = _make_wb(
            {"A1": 1, "A2": 2, "A3": 1, "A4": 2,
             "B1": 10, "B2": 10, "B3": 20, "B4": 20,
             "C1": 100, "C2": 200, "C3": 300, "C4": 400},
            {"D1": "=SUMIFS(C1:C4,A1:A4,2,B1:B4,20)"},
        )
        results = _calc(wb)
        # A=2 AND B=20: row 4 -> C4=400
        assert results["Sheet!D1"] == 400.0


# ---------------------------------------------------------------------------
# COUNTIF tests
# ---------------------------------------------------------------------------


class TestBuiltinCountif:
    def test_count_gt_50(self) -> None:
        wb = _make_wb(
            {"A1": 10, "A2": 60, "A3": 30, "A4": 80, "A5": 20},
            {"B1": '=COUNTIF(A1:A5,">50")'},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == 2.0

    def test_string_match(self) -> None:
        wb = _make_wb(
            {"A1": "Yes", "A2": "No", "A3": "yes", "A4": "YES"},
            {"B1": '=COUNTIF(A1:A4,"Yes")'},
        )
        results = _calc(wb)
        # Case-insensitive: all 3 "yes" variants match
        assert results["Sheet!B1"] == 3.0

    def test_wildcard(self) -> None:
        wb = _make_wb(
            {"A1": "abc", "A2": "def", "A3": "abx", "A4": None},
            {"B1": '=COUNTIF(A1:A4,"ab*")'},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == 2.0


# ---------------------------------------------------------------------------
# COUNTIFS tests
# ---------------------------------------------------------------------------


class TestBuiltinCountifs:
    def test_dual_criteria(self) -> None:
        wb = _make_wb(
            {"A1": "Sales", "A2": "Marketing", "A3": "Sales", "A4": "Sales",
             "B1": 100, "B2": 200, "B3": 50, "B4": 150},
            {"C1": '=COUNTIFS(A1:A4,"Sales",B1:B4,">80")'},
        )
        results = _calc(wb)
        # Sales AND >80: rows 1 (Sales,100) and 4 (Sales,150) = 2
        assert results["Sheet!C1"] == 2.0


# ---------------------------------------------------------------------------
# & string concatenation operator tests
# ---------------------------------------------------------------------------


class TestAmpersandOperator:
    def test_basic_string_concat(self) -> None:
        wb = _make_wb(
            {},
            {"A1": '="Hello"&" "&"World"'},
        )
        results = _calc(wb)
        assert results["Sheet!A1"] == "Hello World"

    def test_dynamic_criteria_with_sumif(self) -> None:
        wb = _make_wb(
            {"A1": 10, "A2": 60, "A3": 30, "A4": 80,
             "B1": 1, "B2": 2, "B3": 3, "B4": 4,
             "C1": 50},
            {"D1": '=SUMIF(A1:A4,">"&C1,B1:B4)'},
        )
        results = _calc(wb)
        # ">"&50 = ">50" -> A2=60, A4=80 match -> B2+B4 = 2+4 = 6
        assert results["Sheet!D1"] == 6.0

    def test_cell_ref_concat(self) -> None:
        wb = _make_wb(
            {"A1": "Hello", "A2": " World"},
            {"B1": "=A1&A2"},
        )
        results = _calc(wb)
        assert results["Sheet!B1"] == "Hello World"


# ---------------------------------------------------------------------------
# Criteria engine unit tests
# ---------------------------------------------------------------------------


class TestCriteriaEngine:
    def test_numeric_exact(self) -> None:
        assert _match_criteria(100, 100) is True
        assert _match_criteria(100, 99) is False

    def test_operator_gt(self) -> None:
        pred = _parse_criteria(">50")
        assert pred(60) is True
        assert pred(50) is False
        assert pred(40) is False

    def test_operator_not_equal(self) -> None:
        pred = _parse_criteria("<>0")
        assert pred(1) is True
        assert pred(0) is False

    def test_wildcard(self) -> None:
        pred = _parse_criteria("app*")
        assert pred("apple") is True
        assert pred("application") is True
        assert pred("banana") is False

    def test_none_handling(self) -> None:
        pred = _parse_criteria(">0")
        assert pred(None) is False


# ---------------------------------------------------------------------------
# Perturbation propagation tests
# ---------------------------------------------------------------------------


class TestPerturbationPropagation:
    def test_perturbation_through_index_match(self) -> None:
        """Perturbing a data cell should propagate through INDEX/MATCH."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "X"
        ws["A2"] = "Y"
        ws["A3"] = "Z"
        ws["B1"] = 100
        ws["B2"] = 200
        ws["B3"] = 300
        ws["C1"] = "Y"
        ws["D1"] = "=INDEX(B1:B3,MATCH(C1,A1:A3,0))"

        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!D1"] == 200

        # Perturb B2 (the cell INDEX/MATCH resolves to)
        recalc = ev.recalculate({"Sheet!B2": 999})
        delta_map = {d.cell_ref: d for d in recalc.deltas}
        assert "Sheet!D1" in delta_map
        assert delta_map["Sheet!D1"].new_value == 999

    def test_perturbation_through_vlookup(self) -> None:
        """Perturbing a table cell should propagate through VLOOKUP."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 1
        ws["B1"] = 100
        ws["A2"] = 2
        ws["B2"] = 200
        ws["A3"] = 3
        ws["B3"] = 300
        ws["C1"] = "=VLOOKUP(2,A1:B3,2,FALSE)"

        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!C1"] == 200

        # Perturb B2 (the cell VLOOKUP resolves to)
        recalc = ev.recalculate({"Sheet!B2": 999})
        delta_map = {d.cell_ref: d for d in recalc.deltas}
        assert "Sheet!C1" in delta_map
        assert delta_map["Sheet!C1"].new_value == 999

    def test_perturbation_through_sumif(self) -> None:
        """Perturbing a sum_range cell should propagate through SUMIF."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Sales"
        ws["A2"] = "Marketing"
        ws["A3"] = "Sales"
        ws["B1"] = 100
        ws["B2"] = 200
        ws["B3"] = 300
        ws["C1"] = '=SUMIF(A1:A3,"Sales",B1:B3)'

        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!C1"] == 400.0

        # Perturb B1 -> should change SUMIF result
        recalc = ev.recalculate({"Sheet!B1": 500})
        delta_map = {d.cell_ref: d for d in recalc.deltas}
        assert "Sheet!C1" in delta_map
        assert delta_map["Sheet!C1"].new_value == 800.0  # 500 + 300
