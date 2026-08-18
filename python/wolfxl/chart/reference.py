"""`Reference` — typed cell-range descriptor used to point chart data at sheets.

Mirrors :class:`openpyxl.chart.reference.Reference`. Accepts either:

- explicit ``worksheet=, min_col=, min_row=, max_col=, max_row=``;
- a string ``range_string="Sheet1!A1:B5"`` (which we parse into the
  same fields so the rest of the codebase doesn't care which form was
  used).

The class is iterable over rows / cols (consumed by ``ChartBase.add_data``).
"""

from __future__ import annotations

import re
from typing import Any, Iterator

from wolfxl._compat import _openpyxl_name_fallback


_RANGE_RE = re.compile(
    r"^(?:'([^']+)'|([^!]+))!"  # sheet name (quoted or unquoted)
    r"\$?([A-Z]+)\$?(\d+)"  # min cell
    r"(?::\$?([A-Z]+)\$?(\d+))?$"  # optional max cell
)


def _col_to_index(col: str) -> int:
    """Convert an A1-letter column to a 1-based index ('A' -> 1, 'AA' -> 27)."""
    out = 0
    for ch in col:
        out = out * 26 + (ord(ch.upper()) - ord("A") + 1)
    return out


def _index_to_col(idx: int) -> str:
    """Inverse of :func:`_col_to_index` — 1-based index back to letters."""
    out = ""
    n = idx
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(ord("A") + r) + out
    return out


def _quote_sheetname(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


class _DummyWorksheet:
    """Carrier object for the ``title`` of a sheet referenced by name only."""

    __slots__ = ("title",)

    def __init__(self, title: str) -> None:
        self.title = title


class Reference:
    """A cell range reference — either constructed from a sheet + bounds
    or parsed from an A1-style string."""

    __slots__ = (
        "worksheet",
        "min_col",
        "min_row",
        "max_col",
        "max_row",
        "range_string",
    )

    def __init__(
        self,
        worksheet: Any | None = None,
        min_col: int | None = None,
        min_row: int | None = None,
        max_col: int | None = None,
        max_row: int | None = None,
        range_string: str | None = None,
    ) -> None:
        if range_string is not None:
            sheetname, bounds = self._parse_range_string(range_string)
            min_col, min_row, max_col, max_row = bounds
            worksheet = _DummyWorksheet(sheetname)

        if min_col is None or min_row is None:
            raise ValueError("Reference requires worksheet + min_col/min_row")

        # An explicit ``None`` worksheet is invalid: only a range_string-parsed
        # Reference may carry a synthetic _DummyWorksheet in lieu of a real
        # sheet handle.
        if worksheet is None:
            raise ValueError(
                "Reference requires a worksheet handle (got None); "
                "either pass a Workbook worksheet or supply a range_string"
            )

        self.worksheet = worksheet
        self.min_col = int(min_col)
        self.min_row = int(min_row)
        self.max_col = int(max_col) if max_col is not None else self.min_col
        self.max_row = int(max_row) if max_row is not None else self.min_row
        self.range_string = range_string

        # Validate the bounds at construction time.
        if self.min_col < 1:
            raise ValueError(
                f"Reference.min_col={self.min_col} must be >= 1 (1-based)"
            )
        if self.min_row < 1:
            raise ValueError(
                f"Reference.min_row={self.min_row} must be >= 1 (1-based)"
            )
        if self.min_col > self.max_col:
            raise ValueError(
                f"Reference.min_col={self.min_col} > max_col={self.max_col}"
            )
        if self.min_row > self.max_row:
            raise ValueError(
                f"Reference.min_row={self.min_row} > max_row={self.max_row}"
            )

    @staticmethod
    def _parse_range_string(s: str) -> tuple[str, tuple[int, int, int, int]]:
        m = _RANGE_RE.match(s)
        if not m:
            raise ValueError(f"Cannot parse range_string={s!r}")
        sheet = m.group(1) or m.group(2)
        c1 = _col_to_index(m.group(3))
        r1 = int(m.group(4))
        c2 = _col_to_index(m.group(5)) if m.group(5) else c1
        r2 = int(m.group(6)) if m.group(6) else r1
        return sheet, (c1, r1, c2, r2)

    @property
    def sheetname(self) -> str:
        return _quote_sheetname(self.worksheet.title) if self.worksheet else ""

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        if self.min_col == self.max_col and self.min_row == self.max_row:
            return f"{self.sheetname}!${_index_to_col(self.min_col)}${self.min_row}"
        return (
            f"{self.sheetname}!"
            f"${_index_to_col(self.min_col)}${self.min_row}:"
            f"${_index_to_col(self.max_col)}${self.max_row}"
        )

    def __len__(self) -> int:
        if self.min_row == self.max_row:
            return 1 + self.max_col - self.min_col
        return 1 + self.max_row - self.min_row

    def __eq__(self, other: object) -> bool:
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))

    @property
    def rows(self) -> Iterator["Reference"]:
        for row in range(self.min_row, self.max_row + 1):
            yield Reference(self.worksheet, self.min_col, row, self.max_col, row)

    @property
    def cols(self) -> Iterator["Reference"]:
        for col in range(self.min_col, self.max_col + 1):
            yield Reference(self.worksheet, col, self.min_row, col, self.max_row)

    def pop(self) -> str:
        """Return the first cell coordinate string and shrink this ref."""
        cell = f"{_index_to_col(self.min_col)}{self.min_row}"
        if self.min_row == self.max_row:
            self.min_col += 1
        else:
            self.min_row += 1
        return cell


__all__ = ["Reference"]

__getattr__ = _openpyxl_name_fallback(globals())
