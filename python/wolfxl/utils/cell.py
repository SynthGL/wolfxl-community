"""openpyxl-shape coordinate utilities.

These wrap WolfXL's existing primitives in ``wolfxl._utils`` while presenting
the openpyxl API contract - error messages, value bounds, and tuple shapes
match openpyxl 3.1.x.
"""

from __future__ import annotations

import re
from importlib import import_module
from functools import cache, lru_cache
from itertools import chain, product
from string import ascii_uppercase, digits

from wolfxl._compat import _openpyxl_name_fallback

def _cell_coordinates_exception() -> type[Exception]:
    return import_module("wolfxl.utils.exceptions").CellCoordinatesException

# Verbatim from openpyxl/utils/cell.py - keep in sync if openpyxl changes the
# pattern. The whole point of this module is bug-for-bug compatibility.
_RANGE_EXPR = r"""
[$]?(?P<min_col>[A-Za-z]{1,3})?
[$]?(?P<min_row>\d+)?
(:[$]?(?P<max_col>[A-Za-z]{1,3})?
[$]?(?P<max_row>\d+)?)?
"""
COL_RANGE = """[A-Z]{1,3}:[A-Z]{1,3}:"""
ROW_RANGE = r"""\d+:\d+:"""
SHEET_TITLE = r"""
(('(?P<quoted>([^']|'')*)')|(?P<notquoted>[^'^ ^!]*))!"""
_ABSOLUTE_RE = re.compile("^" + _RANGE_EXPR + "$", re.VERBOSE)
_COORD_RE = re.compile(r"^([A-Za-z]{1,3})(\d+)$")
SHEETRANGE_RE = re.compile(
    """{0}(?P<cells>{1})(?=,?)""".format(SHEET_TITLE, _RANGE_EXPR),
    re.VERBOSE,
)

_DECIMAL_TO_ALPHA = [""] + list(ascii_uppercase)
_ALPHA_TO_DECIMAL = {letter: pos for pos, letter in enumerate(ascii_uppercase, 1)}
_POWERS = (1, 26, 676)


@cache
def get_column_letter(col_idx: int) -> str:
    """1-based column index -> letter. Capped at 18278 (ZZZ) per openpyxl."""
    if not 1 <= col_idx <= 18278:
        raise _cell_coordinates_exception()(f"Invalid column index {col_idx}")

    if col_idx < 26:
        return _DECIMAL_TO_ALPHA[col_idx]

    result: list[str] = []
    while col_idx:
        col_idx, remainder = divmod(col_idx, 26)
        result.insert(0, _DECIMAL_TO_ALPHA[remainder])
        if not remainder:
            col_idx -= 1
            result.insert(0, "Z")
    return "".join(result)


@cache
def column_index_from_string(col: str) -> int:
    """Column letter -> 1-based index. Accepts up to 3 letters (A..ZZZ)."""
    error_msg = f"'{col}' is not a valid column name. Column names are from A to ZZZ"
    if len(col) > 3:
        raise _cell_coordinates_exception()(error_msg)
    idx = 0
    for letter, power in zip(reversed(col.upper()), _POWERS):
        try:
            pos = _ALPHA_TO_DECIMAL[letter]
        except KeyError as exc:
            raise _cell_coordinates_exception()(error_msg) from exc
        idx += pos * power
    if not 0 < idx < 18279:
        raise _cell_coordinates_exception()(error_msg)
    return idx


def range_boundaries(range_string: str) -> tuple[int | None, int | None, int | None, int | None]:
    """Parse ``'A1:D10'`` / ``'$A$1:$D$10'`` -> ``(min_col, min_row, max_col, max_row)``.

    Matches openpyxl's contract: degenerate single-cell refs return identical
    min/max; ``'A:A'`` returns ``(1, None, 1, None)``; ``'1:1'`` returns
    ``(None, 1, None, 1)``.
    """
    msg = f"{range_string} is not a valid coordinate or range"
    m = _ABSOLUTE_RE.match(range_string)
    if not m:
        raise _cell_coordinates_exception()(msg)

    min_col, min_row, sep, max_col, max_row = m.groups()

    if sep:
        cols = (min_col, max_col)
        rows = (min_row, max_row)
        # Mixed-validity check from openpyxl: either every coord is set, or
        # cols-only (whole-column ref), or rows-only (whole-row ref).
        if not (
            all(cols + rows)
            or (all(cols) and not any(rows))
            or (all(rows) and not any(cols))
        ):
            raise _cell_coordinates_exception()(msg)

    min_col_i = column_index_from_string(min_col) if min_col is not None else None
    min_row_i = int(min_row) if min_row is not None else None
    max_col_i = column_index_from_string(max_col) if max_col is not None else min_col_i
    max_row_i = int(max_row) if max_row is not None else min_row_i

    return min_col_i, min_row_i, max_col_i, max_row_i


def coordinate_to_tuple(coordinate: str) -> tuple[int, int]:
    """``'B3'`` -> ``(3, 2)``. Returns ``(row, col)``, both 1-based."""
    m = _COORD_RE.match(coordinate)
    if not m:
        raise _cell_coordinates_exception()(f"Invalid cell coordinates ({coordinate})")
    col_letter, row_str = m.groups()
    return int(row_str), column_index_from_string(col_letter)


def coordinate_from_string(coord_string: str) -> tuple[str, int]:
    """Convert a coordinate string like ``'B12'`` to ``('B', 12)``."""
    match = _COORD_RE.match(coord_string)
    if not match:
        raise _cell_coordinates_exception()(f"Invalid cell coordinates ({coord_string})")
    column, row_string = match.groups()
    row = int(row_string)
    if not row:
        raise _cell_coordinates_exception()(f"There is no row 0 ({coord_string})")
    return column, row


# Re-export the higher-level helpers that live in wolfxl.utils so that
# callers importing ``openpyxl.utils.cell`` as ``wolfxl.utils.cell`` get
# the full surface: range_to_tuple, quote_sheetname, etc.
_fallback_getattr = _openpyxl_name_fallback(globals())


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Lazy re-export from ``wolfxl.utils`` to avoid circular import at load."""
    if name in {
        "absolute_coordinate",
        "cols_from_range",
        "get_column_interval",
        "quote_sheetname",
        "range_to_tuple",
        "rows_from_range",
    }:
        import wolfxl.utils as _wu
        return getattr(_wu, name)
    return _fallback_getattr(name)


# Pod 2 (RFC-060): re-export the parser module-level constants under
# their openpyxl names so ``from openpyxl.utils.cell import COORD_RE``
# swaps cleanly. ``RANGE_EXPR`` is the regex source; ``ABSOLUTE_RE`` is
# the compiled form openpyxl exposes at module scope.
RANGE_EXPR = _RANGE_EXPR
COORD_RE = _COORD_RE
ABSOLUTE_RE = _ABSOLUTE_RE


__all__ = [
    "ABSOLUTE_RE",
    "COL_RANGE",
    "COORD_RE",
    "RANGE_EXPR",
    "ROW_RANGE",
    "SHEETRANGE_RE",
    "SHEET_TITLE",
    "column_index_from_string",
    "coordinate_from_string",
    "coordinate_to_tuple",
    "get_column_letter",
    "range_boundaries",
]
