"""Conditional-format case — cellIs rule with dxf-styled bg color."""
from __future__ import annotations

from typing import Any


def _build_cell_is_with_dxf(wb: Any) -> None:
    ws = wb.active
    for r in range(1, 11):
        ws.cell(row=r, column=1, value=r * 25)
    w = wb._rust_writer
    w.add_conditional_format(ws.title, {
        "range": "A1:A10",
        "rule_type": "cellIs",
        "operator": "greaterThan",
        "formula": "100",
        "format": {"bg_color": "#FFFF00"},
    })


CASES = [
    ("conditional_format_cellIs_with_dxf", _build_cell_is_with_dxf),
]
