"""CalcEngine protocol and result dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from wolfxl._workbook import Workbook


@dataclass(frozen=True)
class CellDelta:
    """A single cell's value change from recalculation."""

    cell_ref: str  # canonical "SheetName!A1"
    old_value: float | int | str | bool | None
    new_value: float | int | str | bool | None
    formula: str | None = None  # the formula that produced new_value


@dataclass(frozen=True)
class RecalcResult:
    """Result of a perturbation-driven recalculation."""

    perturbations: dict[str, float | int]  # cell_ref -> new input value
    deltas: tuple[CellDelta, ...]  # cells that changed
    total_formula_cells: int = 0
    propagated_cells: int = 0  # formula cells whose value actually changed
    max_chain_depth: int = 0  # longest dependency chain from perturbed inputs

    @property
    def propagation_ratio(self) -> float:
        if self.total_formula_cells == 0:
            return 0.0
        return self.propagated_cells / self.total_formula_cells


@runtime_checkable
class CalcEngine(Protocol):
    """Protocol for formula evaluation engines."""

    def load(self, workbook: Workbook) -> None:
        """Scan a workbook, build dependency graph, compile formulas."""
        ...

    def calculate(self) -> dict[str, float | int | str | bool | None]:
        """Evaluate all formulas in topological order.

        Returns a dict of cell_ref -> computed value for all formula cells.
        """
        ...

    def recalculate(
        self,
        perturbations: dict[str, float | int],
        tolerance: float = 1e-10,
    ) -> RecalcResult:
        """Perturb input cells and recompute affected formulas.

        Returns a RecalcResult describing which cells changed.
        """
        ...
