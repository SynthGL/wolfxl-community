"""Hyperlink cases — external URL + internal sheet-local target.

Both external and internal targets exercise the rels-rId resolution that
``xml_tree.normalize`` performs. The Layer 2 diff is meaningful here only
because the rId rewrite is in place — without it, oracle and native would
allocate different rId numbers for the same logical hyperlink.
"""
from __future__ import annotations

from typing import Any


def _build_external_links(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = "Anthropic"
    ws["A2"] = "Email"
    w = wb._rust_writer  # NativeWorkbook (sole write backend after W5)
    w.add_hyperlink(ws.title, {
        "cell": "A1",
        "target": "https://anthropic.com",
        "display": "Anthropic",
    })
    w.add_hyperlink(ws.title, {
        "cell": "A2",
        "target": "mailto:hello@example.com",
        "display": "Email",
    })


def _build_internal_link(wb: Any) -> None:
    """Internal hyperlink targeting a different cell on the same workbook.

    Cell value is set to match the hyperlink display string — oracle uses
    the display attribute as the rendered cell text when both are present
    while native preserves the cell's own value. Aligning them up front
    keeps the case focused on the rels-rId resolution + internal-target
    encoding path.
    """
    ws = wb.active
    ws["A1"] = "Jump"
    ws["A50"] = "destination"
    w = wb._rust_writer
    w.add_hyperlink(ws.title, {
        "cell": "A1",
        "target": f"{ws.title}!A50",
        "internal": True,
        "display": "Jump",
    })


CASES = [
    ("hyperlinks_external_https_mailto", _build_external_links),
    ("hyperlinks_internal_sheet_local", _build_internal_link),
]
