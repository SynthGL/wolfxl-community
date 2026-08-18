"""Cell-value cases — strings, numbers, dates, booleans, formulas, blanks."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def _build_strings_basic(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = "Hello"
    ws["A2"] = "World"
    ws["B1"] = "Foo"
    ws["B2"] = "Bar"


def _build_strings_xml_unsafe(wb: Any) -> None:
    """Strings containing characters that need XML escaping."""
    ws = wb.active
    ws["A1"] = "<script>"
    ws["A2"] = 'quote"and&amp'
    ws["A3"] = "Tom & Jerry"
    ws["B1"] = "</close>"


def _build_numbers_int_float(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = 0
    ws["A2"] = 42
    ws["A3"] = -17
    ws["B1"] = 3.14159
    ws["B2"] = 1e-9
    ws["B3"] = 1.0e10


def _build_dates_modern(wb: Any) -> None:
    """Dates serialized via Excel 1900-system serials."""
    ws = wb.active
    ws["A1"] = datetime(2024, 1, 1)
    ws["A2"] = datetime(2026, 4, 24)
    ws["B1"] = datetime(2000, 12, 31, 23, 59, 59)


def _build_dates_1900_leap_sentinel(wb: Any) -> None:
    """Dates straddling Excel's fake 1900-02-29 leap-year sentinel (serial 60).

    Probes the 1900 epoch boundary: serial 1 (1900-01-01), serial 60 sentinel
    (1900-02-28 → next-day-after is the fake leap day), serial 61 (1900-03-01).
    Pre-1900 dates are inherently unrepresentable in the 1900 system and are
    intentionally not exercised here — both backends handle that out-of-range
    case differently and neither is "right".
    """
    ws = wb.active
    ws["A1"] = datetime(1900, 1, 1)
    ws["A2"] = datetime(1900, 2, 28)
    ws["A3"] = datetime(1900, 3, 1)


def _build_booleans(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = True
    ws["A2"] = False
    ws["B1"] = True


def _build_formulas_with_cached_result(wb: Any) -> None:
    ws = wb.active
    # Plain cells the formula references.
    ws["A1"] = 1
    ws["A2"] = 2
    ws["A3"] = 3
    # Formula as a string starting with '=' — wolfxl emits as <f>...</f>.
    ws["B1"] = "=SUM(A1:A3)"
    ws["B2"] = "=A1+A2"


def _build_blank_cells(wb: Any) -> None:
    """Cells with explicit None-valued writes followed by populated cells.

    A cell whose value is None and whose style is default should NOT emit
    a ``<c r="X" s="N"/>`` node — both emitters honor this.
    """
    ws = wb.active
    ws["A1"] = "first"
    ws["A2"] = None
    ws["A3"] = "third"
    ws["C1"] = "isolated"


CASES = [
    ("cells_strings_basic", _build_strings_basic),
    ("cells_strings_xml_unsafe", _build_strings_xml_unsafe),
    ("cells_numbers_int_float", _build_numbers_int_float),
    ("cells_dates_1900_modern", _build_dates_modern),
    ("cells_dates_1900_leap_sentinel", _build_dates_1900_leap_sentinel),
    ("cells_booleans_true_false", _build_booleans),
    ("cells_formulas_with_cached_result", _build_formulas_with_cached_result),
    ("cells_blank_no_s_attr", _build_blank_cells),
]
