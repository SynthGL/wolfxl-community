"""Defined-name case — workbook + sheet scope, refers_to round-trip.

Print areas serialize as builtin ``_xlnm.Print_Area`` defined names, so
this case implicitly covers print-area parity through the same code path
as user-authored named ranges.
"""
from __future__ import annotations

from typing import Any


def _build_workbook_and_sheet_scope(wb: Any) -> None:
    ws = wb.active
    for r in range(1, 11):
        ws.cell(row=r, column=1, value=r)
    w = wb._rust_writer
    w.add_named_range(ws.title, {
        "name": "Workbook_Range",
        "scope": "workbook",
        "refers_to": f"{ws.title}!$A$1:$A$10",
    })
    w.add_named_range(ws.title, {
        "name": "Sheet_Range",
        "scope": "sheet",
        "refers_to": f"{ws.title}!$A$1:$A$5",
    })


CASES = [
    ("defined_names_workbook_and_sheet_scope", _build_workbook_and_sheet_scope),
]
