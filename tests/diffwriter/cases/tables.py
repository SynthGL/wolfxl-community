"""Table cases — full table with totals row, header-only table.

The header-only case probes the oracle's special-case post-save patch
(``rust_xlsxwriter_backend.rs:2503``). Native handles it cleanly via the
emitter; the diff harness verifies they produce equivalent output.
"""
from __future__ import annotations

from typing import Any


def _build_full_with_totals(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = "Name"
    ws["B1"] = "Amount"
    ws["A2"] = "Apple"
    ws["B2"] = 10
    ws["A3"] = "Bread"
    ws["B3"] = 25
    ws["A4"] = "Total"
    ws["B4"] = 35
    w = wb._rust_writer
    w.add_table(ws.title, {
        "name": "Sales",
        "ref": "A1:B4",
        "style": "TableStyleMedium9",
        "columns": ["Name", "Amount"],
        "header_row": True,
        "totals_row": False,
    })


def _build_header_only(wb: Any) -> None:
    """Table with only a header row — no data rows."""
    ws = wb.active
    ws["A1"] = "ColA"
    ws["B1"] = "ColB"
    ws["C1"] = "ColC"
    w = wb._rust_writer
    w.add_table(ws.title, {
        "name": "HeadersOnly",
        "ref": "A1:C1",
        "columns": ["ColA", "ColB", "ColC"],
        "header_row": True,
        "totals_row": False,
        "autofilter": False,
    })


CASES = [
    ("tables_full_with_totals_row", _build_full_with_totals),
    ("tables_header_only", _build_header_only),
]
