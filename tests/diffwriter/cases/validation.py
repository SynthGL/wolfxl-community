"""Data-validation cases.

Three fixtures here:

1. ``data_validation_list_literal`` — happy path with ``allow_blank: True``
   set explicitly. Pins that both backends produce identical XML for the
   common case.

2. ``data_validation_omit_allow_blank`` — W4E.P3 regression. The original
   review flagged that native unconditionally defaulted ``allow_blank``
   to ``True`` while oracle left the OOXML default in place. This case
   builds a list-DV without the key set and asserts cross-backend
   structural parity through the harness Layer 2 + Layer 3 gates. If
   either backend changes its default, the harness flags it loudly
   instead of letting it drift silently.

3. ``data_validation_two_per_sheet`` — W4G/W4E.H5 follow-on. Earlier the
   harness suppression filter at ``xml_tree.py`` matched the literal
   ``dataValidation[1]/@showDropDown`` index only; a second DV on the
   same sheet would emit ``dataValidation[2]/@…`` divergences and noise
   the L2 diff. This case forces the multi-DV path so the regex widening
   to ``dataValidation\\[\\d+\\]/@…`` is exercised by the corpus.
"""
from __future__ import annotations

from typing import Any


def _build_dv_list(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = "pick one"
    w = wb._rust_writer
    w.add_data_validation(ws.title, {
        "range": "B1:B10",
        "validation_type": "list",
        "formula1": '"Red,Green,Blue"',
        "allow_blank": True,
    })


def _build_dv_omit_allow_blank(wb: Any) -> None:
    """W4E.P3: omit the ``allow_blank`` key entirely. Both backends must
    pick the same default — the harness reports any divergence."""
    ws = wb.active
    ws["A1"] = "pick one"
    w = wb._rust_writer
    w.add_data_validation(ws.title, {
        "range": "B1:B10",
        "validation_type": "list",
        "formula1": '"Red,Green,Blue"',
    })


def _build_dv_two_per_sheet(wb: Any) -> None:
    """W4G/W4E.H5: emit two DVs on the same sheet so the harness L2 noise
    filter is exercised against ``dataValidation[1]`` AND
    ``dataValidation[2]``. With the literal-index-1 filter, the second
    DV's ``@showDropDown`` / ``@showInputMessage`` divergence would leak
    into L2; with the widened ``dataValidation\\[\\d+\\]/@…`` regex both
    indices are suppressed.
    """
    ws = wb.active
    ws["A1"] = "pick"
    ws["A2"] = "amount"
    w = wb._rust_writer
    w.add_data_validation(ws.title, {
        "range": "B1:B10",
        "validation_type": "list",
        "formula1": '"Red,Green,Blue"',
        "allow_blank": True,
    })
    w.add_data_validation(ws.title, {
        "range": "C1:C10",
        "validation_type": "whole",
        "operator": "between",
        "formula1": "1",
        "formula2": "100",
    })


CASES = [
    ("data_validation_list_literal", _build_dv_list),
    ("data_validation_omit_allow_blank", _build_dv_omit_allow_blank),
    ("data_validation_two_per_sheet", _build_dv_two_per_sheet),
]
