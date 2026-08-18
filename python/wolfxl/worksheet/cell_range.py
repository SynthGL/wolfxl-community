"""``openpyxl.worksheet.cell_range`` — :class:`CellRange` + :class:`MultiCellRange`.

A pure-Python value type for representing an A1 range with arithmetic
operations.  Duck-typed against openpyxl's
:class:`openpyxl.worksheet.cell_range.CellRange` for the subset that
user code actually uses (``coord``, ``bounds``, ``__contains__``,
``expand``/``shift``/``shrink``, equality).

Wolfxl's existing string-based APIs (``ws.merged_cells``, ``sqref`` on
data validation / conditional formatting) accept either a string or
any object exposing a ``.coord`` attribute, so a :class:`CellRange`
plugs in alongside.

Pod 2 (RFC-060 §3).
"""

from __future__ import annotations

from copy import copy
from operator import attrgetter
from itertools import product
from typing import Iterable, Iterator, Optional, Union

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.utils import quote_sheetname
from wolfxl.utils.cell import (
    get_column_letter,
    range_boundaries,
)
from wolfxl.utils.exceptions import CellCoordinatesException


class CellRange:
    """A rectangular block of cells described in A1 notation.

    Parameters
    ----------
    range_string:
        A range like ``"A1:B10"`` or ``"A1"`` (degenerate single cell).
        Mutually exclusive with the explicit ``min_col``/``min_row``/
        ``max_col``/``max_row`` form.
    min_col, min_row, max_col, max_row:
        1-based inclusive bounds.  ``max_col``/``max_row`` default to
        ``min_col``/``min_row`` when omitted (single-cell range).
    title:
        Optional sheet-name qualifier carried purely for round-trips.
    """

    __slots__ = ("min_col", "min_row", "max_col", "max_row", "title")
    __attrs__ = ("min_col", "min_row", "max_col", "max_row", "title")

    def __init__(
        self,
        range_string: Optional[str] = None,
        *,
        min_col: Optional[int] = None,
        min_row: Optional[int] = None,
        max_col: Optional[int] = None,
        max_row: Optional[int] = None,
        title: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        if name is not None and range_string is None:
            range_string = name
        if (
            range_string is None
            and min_col is None
            and min_row is None
            and max_col is None
            and max_row is None
        ):
            raise TypeError("expected <class 'int'>")
        if range_string is not None:
            if any(v is not None for v in (min_col, min_row, max_col, max_row)):
                raise TypeError(
                    "CellRange: pass either range_string OR explicit bounds, not both"
                )
            # Allow ``"Sheet1!A1:B2"`` — strip the qualifier into ``title``.
            if "!" in range_string:
                qual, _, range_string = range_string.rpartition("!")
                if title is None:
                    title = qual.strip("'").replace("''", "'")
            mn_col, mn_row, mx_col, mx_row = range_boundaries(range_string)
            if mn_col is None or mn_row is None:
                raise CellCoordinatesException(
                    f"CellRange requires bounded coordinates, got {range_string!r}"
                )
            self.min_col = int(mn_col)
            self.min_row = int(mn_row)
            self.max_col = int(mx_col if mx_col is not None else mn_col)
            self.max_row = int(mx_row if mx_row is not None else mn_row)
        else:
            if min_col is None or min_row is None:
                raise TypeError(
                    "CellRange requires either range_string or min_col/min_row"
                )
            self.min_col = int(min_col)
            self.min_row = int(min_row)
            self.max_col = int(max_col) if max_col is not None else int(min_col)
            self.max_row = int(max_row) if max_row is not None else int(min_row)
        if self.max_col < self.min_col or self.max_row < self.min_row:
            raise ValueError(
                f"CellRange: max bound must be >= min "
                f"(got cols {self.min_col}..{self.max_col}, "
                f"rows {self.min_row}..{self.max_row})"
            )
        self.title = title

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def coord(self) -> str:
        """A1-form coordinate string: ``"A1:B10"`` or ``"A1"``."""
        if self.min_col is None or self.min_row is None:
            return ""
        top = f"{get_column_letter(self.min_col)}{self.min_row}"
        if self.min_col == self.max_col and self.min_row == self.max_row:
            return top
        bottom = f"{get_column_letter(self.max_col)}{self.max_row}"
        return f"{top}:{bottom}"

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """Tuple of ``(min_col, min_row, max_col, max_row)`` 1-based bounds."""
        if None in (self.min_col, self.min_row, self.max_col, self.max_row):
            return (None, None, None, None)  # type: ignore[return-value]
        return (self.min_col, self.min_row, self.max_col, self.max_row)

    @property
    def size(self) -> dict[str, int]:
        """``{"rows": ..., "cols": ...}`` — count of cells in each axis."""
        return {
            "rows": self.max_row - self.min_row + 1,
            "columns": self.max_col - self.min_col + 1,
        }

    @property
    def rows(self) -> Iterator[list[tuple[int, int]]]:
        """Iterate rows; each row is a tuple of ``(row, col)`` 1-based pairs."""
        for r in range(self.min_row, self.max_row + 1):
            yield [(r, c) for c in range(self.min_col, self.max_col + 1)]

    @property
    def cols(self) -> Iterator[list[tuple[int, int]]]:
        """Iterate columns; each col is a tuple of ``(row, col)`` 1-based pairs."""
        for c in range(self.min_col, self.max_col + 1):
            yield [(r, c) for r in range(self.min_row, self.max_row + 1)]

    @property
    def cells(self):
        return product(
            range(self.min_row, self.max_row + 1),
            range(self.min_col, self.max_col + 1),
        )

    # ------------------------------------------------------------------
    # Mutating operations
    # ------------------------------------------------------------------

    def expand(
        self,
        right: int = 0,
        down: int = 0,
        left: int = 0,
        up: int = 0,
    ) -> None:
        """Grow the range outward.  All four directions clamped at >= 1."""
        self.min_col = max(1, self.min_col - left)
        self.min_row = max(1, self.min_row - up)
        self.max_col += right
        self.max_row += down

    def shrink(
        self,
        right: int = 0,
        bottom: int = 0,
        left: int = 0,
        top: int = 0,
    ) -> None:
        """Shrink inward.  Raises :class:`ValueError` if the range collapses."""
        self.min_col += left
        self.min_row += top
        self.max_col -= right
        self.max_row -= bottom
        if self.max_col < self.min_col or self.max_row < self.min_row:
            raise ValueError("shrink: range would have non-positive extent")

    def shift(self, col_shift: int = 0, row_shift: int = 0) -> None:
        """Translate the range by ``col_shift`` / ``row_shift``.

        Both deltas may be negative; bounds remain 1-based.
        """
        new_min_col = self.min_col + col_shift
        new_max_col = self.max_col + col_shift
        new_min_row = self.min_row + row_shift
        new_max_row = self.max_row + row_shift
        if new_min_col < 1 or new_min_row < 1:
            raise ValueError("shift: bounds would drop below 1")
        self.min_col = new_min_col
        self.max_col = new_max_col
        self.min_row = new_min_row
        self.max_row = new_max_row

    # ------------------------------------------------------------------
    # Set algebra
    # ------------------------------------------------------------------

    def __contains__(self, item: object) -> bool:
        """Membership test for a coord string or another :class:`CellRange`."""
        if isinstance(item, str):
            try:
                other = CellRange(item)
            except (CellCoordinatesException, ValueError):
                return False
            return other.issubset(self)
        if isinstance(item, CellRange):
            return self.issuperset(item)
        return False

    def _check_title(self, other: "CellRange") -> None:
        if not isinstance(other, CellRange):
            raise TypeError(repr(type(other)))
        if other.title and self.title != other.title:
            raise ValueError("Cannot work with ranges from different worksheets")

    def issubset(self, other: "CellRange") -> bool:
        """Return True iff every cell of ``self`` is inside ``other``."""
        self._check_title(other)
        return other.__superset(self)

    __le__ = issubset

    def __lt__(self, other: "CellRange") -> bool:
        return self.__le__(other) and self.__ne__(other)

    def __superset(self, other: "CellRange") -> bool:
        return (
            self.min_col <= other.min_col
            and self.max_col >= other.max_col
            and self.min_row <= other.min_row
            and self.max_row >= other.max_row
        )

    def issuperset(self, other: "CellRange") -> bool:
        self._check_title(other)
        return self.__superset(other)

    __ge__ = issuperset

    def __gt__(self, other: "CellRange") -> bool:
        return self.__ge__(other) and self.__ne__(other)

    def isdisjoint(self, other: "CellRange") -> bool:
        """Return True iff the two ranges share no cells."""
        self._check_title(other)
        left, right = (other, self) if self.bounds > other.bounds else (self, other)
        return (
            left.max_col < right.min_col
            or left.max_row < right.min_row
            or right.max_row < left.min_row
        )

    def intersection(self, other: "CellRange") -> "CellRange":
        """Return the overlap, or ``None`` when disjoint."""
        if self.isdisjoint(other):
            raise ValueError(f"Range {self} doesn't intersect {other}")
        return CellRange(
            min_col=max(self.min_col, other.min_col),
            min_row=max(self.min_row, other.min_row),
            max_col=min(self.max_col, other.max_col),
            max_row=min(self.max_row, other.max_row),
        )

    __and__ = intersection

    def union(self, other: "CellRange") -> "CellRange":
        """Return the minimal rectangular :class:`CellRange` covering both ranges."""
        self._check_title(other)
        return CellRange(
            min_col=min(self.min_col, other.min_col),
            min_row=min(self.min_row, other.min_row),
            max_col=max(self.max_col, other.max_col),
            max_row=max(self.max_row, other.max_row),
            title=self.title,
        )

    __or__ = union

    # ------------------------------------------------------------------
    # Dunders
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        return not self.__ne__(other)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, CellRange):
            return True
        try:
            self._check_title(other)
        except ValueError:
            return True
        return self.bounds != other.bounds

    def __hash__(self) -> int:
        return hash((self.min_row, self.min_col, self.max_row, self.max_col))

    def __copy__(self):
        return self.__class__(
            min_col=self.min_col,
            min_row=self.min_row,
            max_col=self.max_col,
            max_row=self.max_row,
            title=self.title,
        )

    def __iter__(self):
        for attr in self.__attrs__:
            if attr == "title":
                continue
            yield attr, getattr(self, attr)

    @property
    def top(self) -> list[tuple[int, int]]:
        return [(self.min_row, col) for col in range(self.min_col, self.max_col + 1)]

    @property
    def bottom(self) -> list[tuple[int, int]]:
        return [(self.max_row, col) for col in range(self.min_col, self.max_col + 1)]

    @property
    def left(self) -> list[tuple[int, int]]:
        return [(row, self.min_col) for row in range(self.min_row, self.max_row + 1)]

    @property
    def right(self) -> list[tuple[int, int]]:
        return [(row, self.max_col) for row in range(self.min_row, self.max_row + 1)]

    def __repr__(self) -> str:
        if self.title:
            return f"<CellRange {self.title!r}!{self.coord}>"
        return f"<CellRange {self.coord}>"

    def __str__(self) -> str:
        if self.title:
            return f"{quote_sheetname(self.title)}!{self.coord}"
        return self.coord


class MultiCellRange:
    """Set-like collection of :class:`CellRange` objects.

    Mirrors openpyxl's ``MultiCellRange`` for the subset users actually
    construct directly: iteration, ``add``, ``remove``, and membership
    tests over coord strings.
    """

    __slots__ = ("ranges",)

    def __init__(
        self,
        ranges: Optional[Iterable[Union["CellRange", str]]] = None,
    ) -> None:
        self.ranges: set[CellRange] = set()
        if ranges is None:
            return
        if isinstance(ranges, str):
            # Allow ``MultiCellRange("A1:A4 C1:D2")`` like openpyxl.
            for token in ranges.split():
                self.ranges.add(CellRange(token))
            return
        for r in ranges:
            self.add(r)

    def add(self, other: Union["CellRange", str]) -> None:
        if isinstance(other, str):
            other = CellRange(other)
        if not isinstance(other, CellRange):
            raise ValueError("You can only add CellRanges")
        if other not in self:
            self.ranges.add(other)

    def __iadd__(self, other: Union["CellRange", str]) -> "MultiCellRange":
        self.add(other)
        return self

    def remove(self, other: Union["CellRange", str]) -> None:
        if isinstance(other, str):
            other = CellRange(other)
        if not isinstance(other, CellRange):
            raise TypeError("expected <class 'int'>")
        if other not in self.ranges:
            raise KeyError(other)
        self.ranges.remove(other)

    def __iter__(self) -> Iterator[CellRange]:
        return iter(self.ranges)

    def __len__(self) -> int:
        return len(self.ranges)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, str):
            try:
                target = CellRange(item)
            except (CellCoordinatesException, ValueError):
                return False
        elif isinstance(item, CellRange):
            target = item
        else:
            if not self.ranges:
                return False
            raise TypeError(type(item))
        return any(target.issubset(r) for r in self.ranges)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            other = self.__class__(other)
        if not isinstance(other, MultiCellRange):
            return NotImplemented
        return self.ranges == other.ranges

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __bool__(self) -> bool:
        return bool(self.ranges)

    def __hash__(self) -> int:
        return hash(str(self))

    def sorted(self) -> list[CellRange]:
        return sorted(
            self.ranges,
            key=attrgetter("min_col", "min_row", "max_col", "max_row"),
        )

    def __copy__(self):
        return self.__class__({copy(rng) for rng in self.ranges})

    def __repr__(self) -> str:
        return f"<MultiCellRange [{' '.join(str(r) for r in self.sorted())}]>"

    def __str__(self) -> str:
        return " ".join(str(r) for r in self.sorted())


__all__ = ["CellRange", "MultiCellRange"]

__getattr__ = _openpyxl_name_fallback(globals())
