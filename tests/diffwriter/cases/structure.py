"""Sheet-structure cases — merges, freeze panes, row heights, column widths."""
from __future__ import annotations

from typing import Any


def _build_merges(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = "Header A"
    ws["B1"] = "Header B"
    ws["A2"] = "data"
    ws.merge_cells("A1:B1")
    # Multi-cell merge
    ws.merge_cells("D1:F3")
    ws["D1"] = "big merged"


def _build_freeze(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = "Header"
    ws["B1"] = "Sub"
    for r in range(2, 6):
        ws.cell(row=r, column=1, value=r * 10)
        ws.cell(row=r, column=2, value=r * 20)
    ws.freeze_panes = "B2"  # freeze first row + first column


def _build_row_height_column_width(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = "tall"
    ws.row_dimensions[1].height = 30
    ws["A2"] = "wide"
    ws.column_dimensions["A"].width = 25.5
    ws.column_dimensions["B"].width = 8


def _build_multi_sheet_names(wb: Any) -> None:
    """W4E.H2 follow-on: exercise the ``sheet_names`` HARD dimension by
    building a workbook with three uniquely-named sheets. Default
    ``Workbook()`` ships one auto-named sheet; this case renames it and
    adds two more so a divergence on sheet ordering or naming becomes
    observable across backends.
    """
    wb.active.title = "Inputs"
    wb.active["A1"] = "raw"
    sheet2 = wb.create_sheet("Computed")
    sheet2["A1"] = "result"
    sheet3 = wb.create_sheet("Notes")
    sheet3["A1"] = "scratch"


CASES = [
    ("merges_single_and_multi", _build_merges),
    ("freeze_panes_row_col_both", _build_freeze),
    ("row_height_column_width_variable", _build_row_height_column_width),
    ("structure_multi_sheet_names", _build_multi_sheet_names),
]
