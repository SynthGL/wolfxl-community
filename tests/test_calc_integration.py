"""Integration tests for wolfxl.calc: full roundtrip and Workbook convenience methods."""

from __future__ import annotations

import os
import tempfile
import time

import pytest
from wolfxl.calc import RecalcResult, WorkbookEvaluator

import wolfxl

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "calc")


def _save_and_reload(wb: wolfxl.Workbook) -> tuple[wolfxl.Workbook, str]:
    """Save workbook to temp file and reload in read mode."""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    wb.save(path)
    return wolfxl.load_workbook(path), path


# ---------------------------------------------------------------------------
# Golden workbook builders
# ---------------------------------------------------------------------------


def _build_sum_chain() -> wolfxl.Workbook:
    """A1=10, A2=20, A3=SUM(A1:A2), A4=A3*2."""
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = 10
    ws["A2"] = 20
    ws["A3"] = "=SUM(A1:A2)"
    ws["A4"] = "=A3*2"
    return wb


def _build_cross_sheet() -> wolfxl.Workbook:
    """TB sheet with values, IS sheet with formulas referencing TB."""
    wb = wolfxl.Workbook()
    tb = wb.active  # "Sheet" renamed to TB conceptually
    tb["A1"] = 1000
    tb["A2"] = 2000
    tb["A3"] = 3000
    tb["A4"] = 4000
    summary = wb.create_sheet("Summary")
    summary["A1"] = "=SUM(Sheet!A1:A4)"
    summary["A2"] = "=AVERAGE(Sheet!A1:A4)"
    summary["A3"] = "=Summary!A1-Summary!A2"
    return wb


def _build_hardcoded() -> wolfxl.Workbook:
    """Same values as sum_chain but all hardcoded (no formulas)."""
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = 10
    ws["A2"] = 20
    ws["A3"] = 30  # hardcoded
    ws["A4"] = 60  # hardcoded
    return wb


def _build_mixed() -> wolfxl.Workbook:
    """Some formulas, some hardcoded values."""
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = 100
    ws["A2"] = 200
    ws["A3"] = "=SUM(A1:A2)"  # formula
    ws["A4"] = 500  # hardcoded
    ws["A5"] = "=A3+A4"  # formula using both
    return wb


def _build_income_statement(num_rows: int = 50) -> wolfxl.Workbook:
    """Realistic income statement with many formula rows."""
    wb = wolfxl.Workbook()
    ws = wb.active

    # Revenue line items
    for i in range(1, num_rows + 1):
        ws.cell(row=i, column=1, value=f"Line {i}")
        ws.cell(row=i, column=2, value=float(i * 1000))

    # Column C: formulas referencing B
    for i in range(1, num_rows + 1):
        ws.cell(row=i, column=3, value=f"=B{i}*1.1")

    # Column D: running total
    ws.cell(row=1, column=4, value="=C1")
    for i in range(2, num_rows + 1):
        ws.cell(row=i, column=4, value=f"=D{i-1}+C{i}")

    # Summary rows
    summary_row = num_rows + 1
    ws.cell(row=summary_row, column=2, value=f"=SUM(B1:B{num_rows})")
    ws.cell(row=summary_row, column=3, value=f"=SUM(C1:C{num_rows})")
    ws.cell(row=summary_row, column=4, value=f"=D{num_rows}")

    return wb


# ---------------------------------------------------------------------------
# Fixture generation (saved to disk once)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def golden_fixtures() -> None:
    """Generate golden .xlsx fixtures for other tests."""
    os.makedirs(FIXTURE_DIR, exist_ok=True)

    builders = {
        "sum_chain.xlsx": _build_sum_chain,
        "cross_sheet.xlsx": _build_cross_sheet,
        "hardcoded.xlsx": _build_hardcoded,
        "mixed.xlsx": _build_mixed,
    }

    for name, builder in builders.items():
        path = os.path.join(FIXTURE_DIR, name)
        if not os.path.exists(path):
            wb = builder()
            wb.save(path)


# ---------------------------------------------------------------------------
# Integration tests: create -> save -> load -> calculate -> verify
# ---------------------------------------------------------------------------


class TestRoundtripCalculation:
    def test_sum_chain_roundtrip(self) -> None:
        wb = _build_sum_chain()
        wb2, path = _save_and_reload(wb)
        try:
            ev = WorkbookEvaluator()
            ev.load(wb2)
            results = ev.calculate()
            assert results["Sheet!A3"] == 30.0
            assert results["Sheet!A4"] == 60.0
        finally:
            wb2.close()
            os.unlink(path)

    def test_cross_sheet_roundtrip(self) -> None:
        wb = _build_cross_sheet()
        wb2, path = _save_and_reload(wb)
        try:
            ev = WorkbookEvaluator()
            ev.load(wb2)
            results = ev.calculate()
            assert results["Summary!A1"] == 10000.0
            assert results["Summary!A2"] == 2500.0
            assert results["Summary!A3"] == 7500.0
        finally:
            wb2.close()
            os.unlink(path)


class TestPerturbationDiscrimination:
    """The core test: formulas vs hardcoded discrimination."""

    def test_formulas_propagate(self) -> None:
        wb = _build_sum_chain()
        ev = WorkbookEvaluator()
        ev.load(wb)
        ev.calculate()
        result = ev.recalculate({"Sheet!A1": 15})
        assert result.propagation_ratio == 1.0

    def test_hardcoded_no_propagation(self) -> None:
        wb = _build_hardcoded()
        ev = WorkbookEvaluator()
        ev.load(wb)
        ev.calculate()
        result = ev.recalculate({"Sheet!A1": 15})
        assert result.propagation_ratio == 0.0

    def test_mixed_intermediate_propagation(self) -> None:
        wb = _build_mixed()
        ev = WorkbookEvaluator()
        ev.load(wb)
        ev.calculate()
        result = ev.recalculate({"Sheet!A1": 150})
        # A3 and A5 are formulas, both should propagate
        assert result.propagated_cells == 2
        assert result.propagation_ratio == 1.0


class TestGoldenFixtures:
    """Test against saved .xlsx files."""

    def test_sum_chain_fixture(self) -> None:
        path = os.path.join(FIXTURE_DIR, "sum_chain.xlsx")
        wb = wolfxl.load_workbook(path)
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results["Sheet!A3"] == 30.0
        assert results["Sheet!A4"] == 60.0
        wb.close()

    def test_hardcoded_fixture(self) -> None:
        path = os.path.join(FIXTURE_DIR, "hardcoded.xlsx")
        wb = wolfxl.load_workbook(path)
        ev = WorkbookEvaluator()
        ev.load(wb)
        results = ev.calculate()
        assert results == {}  # No formulas to evaluate
        wb.close()


class TestWorkbookConvenienceMethods:
    def test_calculate(self) -> None:
        wb = _build_sum_chain()
        results = wb.calculate()
        assert results["Sheet!A3"] == 30.0
        assert results["Sheet!A4"] == 60.0

    def test_recalculate(self) -> None:
        wb = _build_sum_chain()
        result = wb.recalculate({"Sheet!A1": 15})
        assert isinstance(result, RecalcResult)
        assert result.propagation_ratio == 1.0

    def test_cross_sheet_calculate(self) -> None:
        wb = _build_cross_sheet()
        results = wb.calculate()
        assert results["Summary!A1"] == 10000.0


class TestWorkbookCaching:
    """Verify the evaluator caching in Workbook.calculate/recalculate."""

    def test_recalculate_reuses_evaluator_after_calculate(self) -> None:
        wb = _build_sum_chain()
        wb.calculate()
        assert hasattr(wb, '_evaluator') and wb._evaluator is not None

        result = wb.recalculate({"Sheet!A1": 15})
        assert result.propagation_ratio == 1.0

    def test_recalculate_without_prior_calculate(self) -> None:
        """recalculate() still works when calculate() was never called."""
        wb = _build_sum_chain()
        result = wb.recalculate({"Sheet!A1": 15})
        assert isinstance(result, RecalcResult)
        assert result.propagation_ratio == 1.0

    def test_cached_evaluator_is_same_object(self) -> None:
        wb = _build_sum_chain()
        wb.calculate()
        ev1 = wb._evaluator
        wb.recalculate({"Sheet!A1": 15})
        assert wb._evaluator is ev1  # same object, not recreated


class TestDeterminism:
    def test_100_rounds_bit_exact(self) -> None:
        wb = _build_sum_chain()
        ev = WorkbookEvaluator()
        ev.load(wb)
        ev.calculate()

        baseline = ev.recalculate({"Sheet!A1": 11.0})
        for _ in range(99):
            ev._cell_values["Sheet!A1"] = 10
            ev._cell_values["Sheet!A2"] = 20
            ev.calculate()
            result = ev.recalculate({"Sheet!A1": 11.0})
            assert result.propagated_cells == baseline.propagated_cells
            for d1, d2 in zip(baseline.deltas, result.deltas):
                assert d1.new_value == d2.new_value


class TestPerformance:
    @pytest.mark.slow
    def test_500_formula_cells_under_2s(self) -> None:
        """calculate() on a 500-formula workbook must complete in <2s.

        Threshold is generous to avoid CI flakiness across platforms.
        Local runs typically complete in <100ms.
        """
        wb = _build_income_statement(num_rows=250)  # 250*2 + 3 = 503 formulas
        ev = WorkbookEvaluator()
        ev.load(wb)

        start = time.perf_counter()
        ev.calculate()
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"calculate() took {elapsed:.3f}s (>2s)"

    def test_recalculate_faster_than_full(self) -> None:
        """recalculate() on a subset should touch less work than full calculate()."""
        wb = _build_income_statement(num_rows=250)
        ev = WorkbookEvaluator()
        ev.load(wb)

        ev.calculate()

        start_recalc = time.perf_counter()
        result = ev.recalculate({"Sheet!B1": 2000.0})
        recalc_time = time.perf_counter() - start_recalc

        assert result.propagated_cells < result.total_formula_cells
        assert recalc_time < 2.0, f"recalculate() took {recalc_time:.3f}s (>2s)"
