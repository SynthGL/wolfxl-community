"""Print-settings classes (RFC-055 §2.4 — Pod 2 re-export targets).

Provides ``PrintArea``, ``PrintTitles``, ``ColRange``, ``RowRange``
mirroring openpyxl's ``openpyxl.worksheet.print_settings`` surface.
"""

from __future__ import annotations

import re

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.utils import absolute_coordinate, quote_sheetname
from wolfxl.utils.cell import RANGE_EXPR, SHEETRANGE_RE, SHEET_TITLE
from wolfxl.worksheet.cell_range import MultiCellRange

ROW_RANGE = r"(?P<rows>[$]?(?P<min_row>\d+):[$]?(?P<max_row>\d+))"
COL_RANGE = r"(?P<cols>[$]?(?P<min_col>[a-zA-Z]{1,3}):[$]?(?P<max_col>[a-zA-Z]{1,3}))"
ROW_RANGE_RE = re.compile(ROW_RANGE)
COL_RANGE_RE = re.compile(COL_RANGE)
PRINT_AREA_RE = re.compile(
    r"({0})?(?P<cells>{1})".format(SHEET_TITLE, RANGE_EXPR),
    re.VERBOSE,
)
TITLES_REGEX = re.compile(
    r"{0}{1}?,?{2}?,?".format(SHEET_TITLE, ROW_RANGE, COL_RANGE),
    re.VERBOSE,
)


class RowRange:
    """A row range like ``"1:2"`` (rows 1-2 inclusive, 1-based)."""

    def __init__(
        self,
        range_string: str | None = None,
        min_row: int | str | None = None,
        max_row: int | str | None = None,
    ) -> None:
        if range_string is not None:
            match = ROW_RANGE_RE.match(range_string)
            if not match:
                raise ValueError(f"{range_string} is not a valid row range")
            min_row, max_row = match.groups()[1:]
        if min_row is None or max_row is None:
            raise TypeError("__init__() missing required row bounds")
        min_row = int(min_row)
        max_row = int(max_row)
        if min_row < 1 or max_row < 1:
            raise ValueError(f"row indices must be >=1: {range_string!r}")
        self.min_row = min_row
        self.max_row = max_row

    @classmethod
    def from_string(cls, s: str) -> "RowRange":
        return cls(s.strip())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.min_row == other.min_row and self.max_row == other.max_row
        if isinstance(other, str):
            return str(self) == other or f"{self.min_row}:{self.max_row}" == other
        return False

    def __repr__(self) -> str:
        return f"Range of rows from '{self.min_row}' to '{self.max_row}'"

    def __str__(self) -> str:
        return f"${self.min_row}:${self.max_row}"


class ColRange:
    """A column range like ``"A:B"`` (columns A-B inclusive)."""

    def __init__(
        self,
        range_string: str | None = None,
        min_col: str | None = None,
        max_col: str | None = None,
    ) -> None:
        if range_string is not None:
            match = COL_RANGE_RE.match(range_string)
            if not match:
                raise ValueError(f"{range_string} is not a valid column range")
            min_col, max_col = match.groups()[1:]
        if min_col is None or max_col is None:
            raise TypeError("__init__() missing required column bounds")
        self.min_col = min_col.upper()
        self.max_col = max_col.upper()

    @classmethod
    def from_string(cls, s: str) -> "ColRange":
        return cls(s.strip())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.min_col == other.min_col and self.max_col == other.max_col
        if isinstance(other, str):
            return str(self) == other or f"{self.min_col}:{self.max_col}" == other
        return False

    def __repr__(self) -> str:
        return f"Range of columns from '{self.min_col}' to '{self.max_col}'"

    def __str__(self) -> str:
        return f"${self.min_col}:${self.max_col}"


class PrintTitles:
    """Container for repeat-rows + repeat-cols on a sheet.

    The OOXML representation is a workbook-level `<definedName
    name="_xlnm.Print_Titles" localSheetId="N">` node — the formula
    string concatenates the rows and cols ranges separated by a
    comma. This class is the typed Python view onto that string.
    """

    def __init__(
        self,
        cols: ColRange | None = None,
        rows: RowRange | None = None,
        title: str = "",
    ) -> None:
        self.cols = cols
        self.rows = rows
        self.title = title

    @classmethod
    def from_string(cls, value: str) -> "PrintTitles":
        kw = dict(
            (k, v)
            for match in TITLES_REGEX.finditer(value)
            for k, v in match.groupdict().items()
            if v
        )
        if not kw:
            raise ValueError(f"{value} is not a valid print titles definition")

        cols = ColRange(kw["cols"]) if "cols" in kw else None
        rows = RowRange(kw["rows"]) if "rows" in kw else None
        title = kw.get("quoted") or kw.get("notquoted") or ""
        return cls(cols=cols, rows=rows, title=title)

    def is_empty(self) -> bool:
        return self.rows is None and self.cols is None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return (
                self.cols == other.cols
                and self.rows == other.rows
                and self.title == other.title
            )
        if isinstance(other, str):
            return str(self) == other
        return False

    def __repr__(self) -> str:
        return f"Print titles for sheet {self.title} cols {self.rows}, rows {self.cols}"

    def __str__(self) -> str:
        title = quote_sheetname(self.title)
        return ",".join(
            f"{title}!{value}" for value in (self.rows, self.cols) if value
        )

    def to_definedname_value(self, sheet_name: str) -> str | None:
        """Compose the `_xlnm.Print_Titles` formula string for ``sheet_name``."""
        if self.is_empty():
            return None
        # Excel needs the sheet name quoted if it contains spaces or
        # punctuation — we use the same conservative rule as openpyxl:
        # quote if any non-alphanumeric/non-underscore character is
        # present.
        if any(not (c.isalnum() or c == "_") for c in sheet_name):
            quoted = "'" + sheet_name.replace("'", "''") + "'"
        else:
            quoted = sheet_name
        parts: list[str] = []
        if self.rows is not None:
            parts.append(f"{quoted}!${self.rows.min_row}:${self.rows.max_row}")
        if self.cols is not None:
            parts.append(f"{quoted}!${self.cols.min_col}:${self.cols.max_col}")
        return ",".join(parts)


class PrintArea(MultiCellRange):
    """A print area definition (range string, e.g. ``"A1:D10"``)."""

    @classmethod
    def from_string(cls, value: str) -> "PrintArea":
        ranges = []
        for match in PRINT_AREA_RE.finditer(value):
            coord = match.group("cells")
            if coord:
                ranges.append(coord)
        return cls(ranges)

    def __init__(
        self,
        sqref: str | tuple[str, ...] | list[str] | set | None = None,
        ranges: tuple[str, ...] | list[str] | set | None = None,
        title: str = "",
    ) -> None:
        if ranges is None and not isinstance(sqref, (str, type(None))):
            ranges = sqref
            sqref = None
        if ranges is None and sqref is not None:
            ranges = [sqref]
        self.sqref = sqref
        self.title = title
        super().__init__(ranges or ())

    def is_empty(self) -> bool:
        return not self.ranges

    def __str__(self) -> str:
        if self.ranges:
            return ",".join(
                f"{quote_sheetname(self.title)}!{absolute_coordinate(str(rng))}"
                for rng in sorted(self.ranges, key=str)
            )
        return ""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other
        return super().__eq__(other)


__all__ = [
    "COL_RANGE",
    "COL_RANGE_RE",
    "PRINT_AREA_RE",
    "RANGE_EXPR",
    "ROW_RANGE",
    "ROW_RANGE_RE",
    "SHEETRANGE_RE",
    "SHEET_TITLE",
    "TITLES_REGEX",
    "ColRange",
    "PrintArea",
    "PrintTitles",
    "RowRange",
]

__getattr__ = _openpyxl_name_fallback(globals())
