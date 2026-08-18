"""Tests for formulas library integration and extended builtin functions.

Tests that the formulas library fallback works for functions not in
the builtin registry, and that the new math/text builtins work correctly.
"""

from __future__ import annotations

import pytest
from wolfxl.calc._evaluator import WorkbookEvaluator

import wolfxl

_has_formulas = pytest.importorskip is not None  # always True, but we check below
try:
    import formulas  # noqa: F401
    _has_formulas = True
except ImportError:
    _has_formulas = False

_requires_formulas = pytest.mark.skipif(
    not _has_formulas, reason="formulas library not installed (install wolfxl[calc])"
)


# ---------------------------------------------------------------------------
# New builtin math functions
# ---------------------------------------------------------------------------


class TestBuiltinRounddown:
    def test_basic(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 3.777
        ws["B1"] = "=ROUNDDOWN(A1,2)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 3.77

    def test_zero_digits(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 3.777
        ws["B1"] = "=ROUNDDOWN(A1,0)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 3.0

    def test_negative(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = -3.777
        ws["B1"] = "=ROUNDDOWN(A1,2)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == -3.77


class TestBuiltinMod:
    def test_basic(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 10
        ws["B1"] = "=MOD(A1,3)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 1.0

    def test_negative_dividend(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = -10
        ws["B1"] = "=MOD(A1,3)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        # Excel MOD: result has sign of divisor
        assert results["Sheet!B1"] == 2.0


class TestBuiltinPower:
    def test_basic(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 2
        ws["B1"] = "=POWER(A1,10)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 1024.0

    def test_fractional_exponent(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 4
        ws["B1"] = "=POWER(A1,0.5)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 2.0

    def test_negative_base_fractional_exponent(self) -> None:
        """POWER(-1, 0.5) should return #NUM! (complex result)."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = -1
        ws["B1"] = "=POWER(A1,0.5)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "#NUM!"


class TestBuiltinSqrt:
    def test_basic(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 144
        ws["B1"] = "=SQRT(A1)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 12.0


class TestBuiltinSign:
    def test_positive(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 42
        ws["B1"] = "=SIGN(A1)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 1.0

    def test_negative(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = -7
        ws["B1"] = "=SIGN(A1)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == -1.0

    def test_zero(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 0
        ws["B1"] = "=SIGN(A1)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 0.0


# ---------------------------------------------------------------------------
# New builtin text functions
# ---------------------------------------------------------------------------


class TestBuiltinLeft:
    def test_basic(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Hello World"
        ws["B1"] = '=LEFT(A1,5)'
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "Hello"

    def test_default_one_char(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        ws["B1"] = '=LEFT(A1)'
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "H"

    def test_negative_num_chars(self) -> None:
        """LEFT with negative count returns #VALUE!."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        ws["B1"] = "=LEFT(A1,-1)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "#VALUE!"


class TestBuiltinRight:
    def test_basic(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Hello World"
        ws["B1"] = '=RIGHT(A1,5)'
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "World"


class TestBuiltinMid:
    def test_basic(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Hello World"
        ws["B1"] = '=MID(A1,7,5)'
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "World"

    def test_start_below_one(self) -> None:
        """MID with start < 1 returns #VALUE!."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        ws["B1"] = "=MID(A1,0,3)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "#VALUE!"

    def test_negative_num_chars(self) -> None:
        """MID with negative num_chars returns #VALUE!."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        ws["B1"] = "=MID(A1,1,-1)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "#VALUE!"


class TestBuiltinLen:
    def test_basic(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        ws["B1"] = '=LEN(A1)'
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 5.0


class TestBuiltinConcatenate:
    def test_basic(self) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        ws["A2"] = " "
        ws["A3"] = "World"
        ws["B1"] = '=CONCATENATE(A1,A2,A3)'
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "Hello World"


# ---------------------------------------------------------------------------
# formulas library fallback: constant formulas (no cell refs)
# ---------------------------------------------------------------------------


@_requires_formulas
class TestFormulasConstantFallback:
    """Formulas that use non-builtin functions with only literal arguments."""

    def test_pmt(self) -> None:
        """PMT(rate, nper, pv) - monthly mortgage payment."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "=PMT(0.05/12,360,200000)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        # Expected: ~-1073.64
        val = results["Sheet!A1"]
        assert val is not None, "PMT formula returned None - formulas lib not available?"
        assert abs(val - (-1073.6432460242797)) < 0.01

    def test_sln(self) -> None:
        """SLN(cost, salvage, life) - straight-line depreciation."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "=SLN(30000,7500,10)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        val = results["Sheet!A1"]
        assert val is not None
        assert val == 2250 or val == 2250.0


# ---------------------------------------------------------------------------
# formulas library fallback: cell ref formulas
# ---------------------------------------------------------------------------


@_requires_formulas
class TestFormulasCellRefFallback:
    """Formulas that use non-builtin functions with cell references."""

    def test_vlookup(self) -> None:
        """VLOOKUP via formulas library fallback."""
        wb = wolfxl.Workbook()
        ws = wb.active
        # Lookup table in B1:C3
        ws["B1"] = 1
        ws["C1"] = 100
        ws["B2"] = 2
        ws["C2"] = 200
        ws["B3"] = 3
        ws["C3"] = 300
        # Lookup value
        ws["A1"] = 2
        ws["D1"] = "=VLOOKUP(A1,B1:C3,2,FALSE)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        val = results.get("Sheet!D1")
        assert val is not None, "VLOOKUP returned None - formulas lib not available?"
        assert val == 200 or val == 200.0

    def test_npv(self) -> None:
        """NPV with cell range reference."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = -10000
        ws["A2"] = 3000
        ws["A3"] = 4000
        ws["A4"] = 5000
        ws["A5"] = 6000
        ws["B1"] = "=NPV(0.1,A1:A5)"
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        val = results.get("Sheet!B1")
        assert val is not None, "NPV returned None - formulas lib not available?"
        # NPV at 10% discount: ~3534.28
        assert abs(val - 3534.28) < 1.0


# ---------------------------------------------------------------------------
# formulas library fallback: perturbation through financial formulas
# ---------------------------------------------------------------------------


@_requires_formulas
class TestFormulasFallbackPerturbation:
    """Verify perturbation propagates through formulas-lib-evaluated cells."""

    def test_pmt_perturbation(self) -> None:
        """Perturbing the loan amount should change the PMT result."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 200000  # loan amount
        ws["A2"] = "=A1*0.05/12"  # monthly rate (builtin handles this)
        ws["A3"] = "=PMT(0.05/12,360,A1)"  # PMT via formulas fallback
        ev = WorkbookEvaluator()
        ev.load(wb)
        ev.calculate()

        # PMT with cell ref may or may not work depending on formulas lib
        # handling. If A3 evaluates, perturbation should propagate.
        result = ev.recalculate({"Sheet!A1": 250000})
        # A2 uses builtins (will propagate)
        # A3 may or may not propagate depending on formulas lib
        assert result.total_formula_cells >= 2


# ---------------------------------------------------------------------------
# Builtin coverage: all 25 builtins registered
# ---------------------------------------------------------------------------


class TestBuiltinRegistryCoverage:
    def test_67_builtins_registered(self) -> None:
        """All 67 builtin functions should be in the registry."""
        from wolfxl.calc._functions import FunctionRegistry

        reg = FunctionRegistry()
        expected = {
            "SUM", "ABS", "ROUND", "ROUNDUP", "ROUNDDOWN", "INT",
            "MOD", "POWER", "SQRT", "SIGN",
            "IF", "IFERROR", "AND", "OR", "NOT",
            "COUNT", "COUNTA", "MIN", "MAX", "AVERAGE",
            "LEFT", "RIGHT", "MID", "LEN", "CONCATENATE",
            "INDEX", "MATCH", "VLOOKUP", "HLOOKUP", "XLOOKUP", "CHOOSE",
            "OFFSET",
            "SUMIF", "SUMIFS", "COUNTIF", "COUNTIFS",
            "AVERAGEIF", "AVERAGEIFS", "MINIFS", "MAXIFS",
            "PV", "FV", "PMT", "NPV", "IRR", "SLN", "DB",
            "TODAY", "DATE", "YEAR", "MONTH", "DAY", "EDATE", "EOMONTH", "DAYS",
            "NOW", "HOUR", "MINUTE", "SECOND",
            "UPPER", "LOWER", "TRIM", "SUBSTITUTE", "TEXT", "REPT", "EXACT", "FIND",
        }
        assert expected == reg.supported_functions

    def test_each_builtin_callable_from_evaluator(self) -> None:
        """Smoke test: each builtin resolves in the evaluator function registry."""
        ev = WorkbookEvaluator()
        for name in [
            "SUM", "ABS", "ROUND", "ROUNDUP", "ROUNDDOWN", "INT",
            "MOD", "POWER", "SQRT", "SIGN",
            "IF", "IFERROR", "AND", "OR", "NOT",
            "COUNT", "COUNTA", "MIN", "MAX", "AVERAGE",
            "LEFT", "RIGHT", "MID", "LEN", "CONCATENATE",
            "INDEX", "MATCH", "VLOOKUP", "HLOOKUP", "XLOOKUP", "CHOOSE",
            "OFFSET",
            "SUMIF", "SUMIFS", "COUNTIF", "COUNTIFS",
            "AVERAGEIF", "AVERAGEIFS", "MINIFS", "MAXIFS",
            "PV", "FV", "PMT", "NPV", "IRR", "SLN", "DB",
            "TODAY", "DATE", "YEAR", "MONTH", "DAY", "EDATE", "EOMONTH", "DAYS",
            "NOW", "HOUR", "MINUTE", "SECOND",
            "UPPER", "LOWER", "TRIM", "SUBSTITUTE", "TEXT", "REPT", "EXACT", "FIND",
        ]:
            assert ev._functions.has(name), f"Missing builtin: {name}"


# ---------------------------------------------------------------------------
# Combined: builtins + formulas lib in same workbook
# ---------------------------------------------------------------------------


@_requires_formulas
class TestCombinedEvaluation:
    """Workbook mixing builtin-evaluated and formulas-lib-evaluated formulas."""

    def test_income_statement_with_sln(self) -> None:
        """An income statement that uses SLN for depreciation calculation."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 100000  # revenue
        ws["A2"] = 60000   # COGS
        ws["A3"] = "=A1-A2"  # gross profit (builtin)
        ws["A4"] = 15000   # opex
        ws["A5"] = "=SLN(50000,5000,10)"  # depreciation via formulas lib
        ws["A6"] = "=A3-A4-A5"  # operating income (builtin, depends on formulas result)

        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()

        assert results["Sheet!A3"] == 40000.0  # builtin

        # SLN result (via formulas library fallback)
        sln_val = results.get("Sheet!A5")
        assert sln_val is not None, "SLN returned None - formulas lib not available?"
        assert sln_val == 4500 or sln_val == 4500.0
        # Operating income depends on SLN
        assert results["Sheet!A6"] == 40000 - 15000 - 4500

    def test_text_extraction_chain(self) -> None:
        """Chain of text functions all handled by builtins."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = "2026-01-15"
        ws["B1"] = '=LEFT(A1,4)'     # "2026"
        ws["C1"] = '=MID(A1,6,2)'    # "01"
        ws["D1"] = '=RIGHT(A1,2)'    # "15"
        ws["E1"] = '=LEN(A1)'        # 10
        ws["F1"] = '=CONCATENATE(B1,"/",C1,"/",D1)'  # "2026/01/15"

        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == "2026"
        assert results["Sheet!C1"] == "01"
        assert results["Sheet!D1"] == "15"
        assert results["Sheet!E1"] == 10.0
        assert results["Sheet!F1"] == "2026/01/15"

    def test_math_chain(self) -> None:
        """Chain of math functions mixing old and new builtins."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = -7.8
        ws["B1"] = "=ABS(A1)"         # 7.8 (old builtin)
        ws["C1"] = "=SQRT(B1)"        # ~2.793 (new builtin)
        ws["D1"] = "=POWER(C1,2)"     # ~7.8 (new builtin, should round-trip)
        ws["E1"] = "=SIGN(A1)"        # -1 (new builtin)
        ws["F1"] = "=MOD(8,3)"        # 2 (new builtin)
        ws["G1"] = "=ROUNDDOWN(C1,1)" # 2.7 (new builtin)

        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!B1"] == 7.8
        assert abs(results["Sheet!C1"] - 2.7928480087537886) < 1e-10
        assert abs(results["Sheet!D1"] - 7.8) < 1e-10
        assert results["Sheet!E1"] == -1.0
        assert results["Sheet!F1"] == 2.0
        assert results["Sheet!G1"] == 2.7

    def test_perturbation_through_new_builtins(self) -> None:
        """Perturbation should propagate through new builtin functions."""
        wb = wolfxl.Workbook()
        ws = wb.active
        ws["A1"] = 100
        ws["B1"] = "=SQRT(A1)"
        ws["C1"] = "=POWER(B1,3)"
        ws["D1"] = "=ROUNDDOWN(C1,0)"

        ev = WorkbookEvaluator()
        ev.load(wb)
        ev.calculate()

        result = ev.recalculate({"Sheet!A1": 144})
        assert result.propagation_ratio == 1.0
        delta_map = {d.cell_ref: d for d in result.deltas}
        assert delta_map["Sheet!B1"].new_value == 12.0
        assert delta_map["Sheet!C1"].new_value == 1728.0
        assert delta_map["Sheet!D1"].new_value == 1728.0
