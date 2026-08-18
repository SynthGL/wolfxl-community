"""Pivot-scoped formatting + conditional formatting.

- :class:`PivotArea` — selector identifying a region inside a pivot
  table (a field, a data subarea, a label, a button).
- :class:`Format` — pivot-area + dxfId + action ("formatting" |
  "blank"); table-scoped.
- :class:`PivotConditionalFormat` — pivot-scoped CF; references a
  workbook-scoped dxf table.
- :class:`ChartFormat` — chart-scoped re-styling for pivot-chart
  series (read-only stub; write-side construction is deferred).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


_VALID_PIVOT_AREA_TYPES = ("all", "data", "labelOnly", "button", "topRight", "origin")
_VALID_FORMAT_ACTIONS = ("formatting", "blank")


@dataclass
class PivotArea:
    """A pivot-area selector.

    Selectors that combine give Excel's "specific cells in the pivot"
    targeting model. Most common:

    - ``field=N, type='data', data_only=True`` — the data cells
      driven by the Nth field.
    - ``type='all', grand_row=True`` — the grand-total row.
    - ``type='button'`` — the field button (for hiding it).
    """

    field: Optional[int] = None
    type: str = "data"
    data_only: bool = True
    label_only: bool = False
    grand_row: bool = False
    grand_col: bool = False
    cache_index: Optional[int] = None
    axis: Optional[str] = None
    field_position: Optional[int] = None

    def __post_init__(self) -> None:
        if self.type not in _VALID_PIVOT_AREA_TYPES:
            raise ValueError(
                f"PivotArea.type must be one of {_VALID_PIVOT_AREA_TYPES}, "
                f"got {self.type!r}"
            )

    def to_rust_dict(self) -> dict:
        return {
            "field": self.field,
            "type": self.type,
            "data_only": self.data_only,
            "label_only": self.label_only,
            "grand_row": self.grand_row,
            "grand_col": self.grand_col,
            "cache_index": self.cache_index,
            "axis": self.axis,
            "field_position": self.field_position,
        }


@dataclass
class Format:
    """Table-scoped format directive."""

    pivot_area: PivotArea
    dxf_id: int
    action: str = "formatting"

    def __post_init__(self) -> None:
        if self.action not in _VALID_FORMAT_ACTIONS:
            raise ValueError(
                f"Format.action must be one of {_VALID_FORMAT_ACTIONS}, "
                f"got {self.action!r}"
            )
        # ``-1`` is a sentinel meaning "patcher will allocate a
        # workbook-scoped dxf id from the attached payload at flush
        # time". Any other negative value is an error.
        if self.dxf_id < -1:
            raise ValueError(
                f"Format.dxf_id must be ≥ -1 (sentinel), got {self.dxf_id}"
            )

    def to_rust_dict(self) -> dict:
        return {
            "action": self.action,
            "dxf_id": self.dxf_id,
            "pivot_area": self.pivot_area.to_rust_dict(),
        }


@dataclass
class PivotConditionalFormat:
    """Pivot-scoped CF. References a workbook-scoped dxf table.

    The ``rule`` is an opaque CF rule object — typically a
    :class:`wolfxl.formatting.Rule` or one of the convenience
    constructors (ColorScale / DataBar / IconSet / Rule).
    """

    rule: Any
    pivot_areas: list[PivotArea]
    priority: int = 1
    scope: str = "data"  # "selection" | "data" | "field"
    type: str = "all"  # "all" | "row" | "column" | "none"

    def __post_init__(self) -> None:
        if not self.pivot_areas:
            raise ValueError(
                "PivotConditionalFormat requires ≥ 1 pivot_area"
            )

    def to_rust_dict(self) -> dict:
        return {
            "rule": _rule_to_rust_dict(self.rule),
            "pivot_areas": [a.to_rust_dict() for a in self.pivot_areas],
            "priority": self.priority,
            "scope": self.scope,
            "type": self.type,
        }


def _rule_to_rust_dict(rule: Any) -> dict:
    """Best-effort conversion of an arbitrary CF rule object to a
    dict. If the rule has its own ``to_rust_dict()`` we call it;
    otherwise we extract a small stable subset of attributes via
    ``__dict__``."""
    if hasattr(rule, "to_rust_dict"):
        return rule.to_rust_dict()
    if hasattr(rule, "__dict__"):
        return {
            k: v
            for k, v in rule.__dict__.items()
            if not k.startswith("_")
        }
    return {"_repr": repr(rule)}


@dataclass
class ChartFormat:
    """Chart-scoped re-styling for pivot-chart series.

    Stub: chart-side styling is read-write tolerant only;
    write-side construction is deferred. Construction succeeds (so
    callers can attach existing ChartFormat instances via
    copy_worksheet); to_rust_dict returns a minimal payload.
    """

    chart_index: int
    series_index: int
    formatting: dict = field(default_factory=dict)

    def to_rust_dict(self) -> dict:
        return {
            "chart_index": self.chart_index,
            "series_index": self.series_index,
            "formatting": dict(self.formatting),
        }
