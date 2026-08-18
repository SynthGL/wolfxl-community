"""Comment cases — single author + multi-author insertion order.

The multi-author case is the canonical regression test for the
rust_xlsxwriter BTreeMap-author bug (which is what motivated the entire
native writer rewrite). When two authors are added in insertion order
``Bob`` then ``Alice``, the emitted ``<authors>`` block must list
``Bob`` first — anything else means the IndexMap-vs-BTreeMap contract
has regressed somewhere in the pipeline.
"""
from __future__ import annotations

from typing import Any


def _build_single_author(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = "see comment"
    w = wb._rust_writer
    w.add_comment(ws.title, {
        "cell": "A1",
        "text": "first comment",
        "author": "Solo",
    })


def _build_multi_author_order(wb: Any) -> None:
    """Bob added before Alice — IndexMap insertion order must persist."""
    ws = wb.active
    ws["A1"] = "bob's"
    ws["A2"] = "alice's"
    w = wb._rust_writer
    w.add_comment(ws.title, {
        "cell": "A1",
        "text": "from Bob",
        "author": "Bob",
    })
    w.add_comment(ws.title, {
        "cell": "A2",
        "text": "from Alice",
        "author": "Alice",
    })


CASES = [
    ("comments_single_author", _build_single_author),
    ("comments_multi_author_insertion_order", _build_multi_author_order),
]
