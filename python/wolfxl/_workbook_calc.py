"""Workbook formula evaluation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from wolfxl.calc._protocol import RecalcResult


def calculate_workbook(wb: Any) -> dict[str, Any]:
    """Evaluate all formulas and cache the evaluator for future recalcs."""
    from wolfxl.calc._evaluator import WorkbookEvaluator

    ev = WorkbookEvaluator()
    ev.load(wb)
    result = ev.calculate()
    wb._evaluator = ev  # noqa: SLF001
    return result


def cached_formula_values(wb: Any) -> dict[str, Any]:
    """Return Excel-saved cached formula results for every readable sheet."""
    if wb._rust_reader is None:  # noqa: SLF001
        return {}
    values: dict[str, Any] = {}
    for sheet_name in wb._sheet_names:  # noqa: SLF001
        sheet = wb._sheets[sheet_name]  # noqa: SLF001
        values.update(sheet.cached_formula_values(qualified=True))
    return values


def recalculate_workbook(
    wb: Any,
    perturbations: dict[str, float | int],
    tolerance: float = 1e-10,
) -> "RecalcResult":
    """Recompute affected formulas, loading and caching an evaluator if needed."""
    ev = wb._evaluator  # noqa: SLF001
    if ev is None:
        from wolfxl.calc._evaluator import WorkbookEvaluator

        ev = WorkbookEvaluator()
        ev.load(wb)
        ev.calculate()
        wb._evaluator = ev  # noqa: SLF001
    return ev.recalculate(perturbations, tolerance)
