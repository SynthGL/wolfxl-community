"""Array and data-table formula value classes for cell assignments.

RFC-057 — Dynamic-array formulas.

Provides two classes that mirror openpyxl's
``openpyxl.worksheet.formula`` surface:

* :class:`ArrayFormula` — Excel 365 spilled-range formulas
  (``=SEQUENCE(10)`` spilling to A1:A10) and pre-365 array formulas
  (``{=SUM(A1:A10*B1:B10)}``).
* :class:`DataTableFormula` — 1D and 2D Excel data tables created via
  Data > What-If Analysis > Data Table.

These shims intentionally match openpyxl's constructor / equality /
``__repr__`` semantics so user code that does
``cell.value = ArrayFormula("A1:A10", "B1:B10*2")`` Just Works
regardless of which library produced the value.

Pod 1C — Sprint Ο.
"""

from __future__ import annotations

import copy
import datetime
import numbers
import re
from decimal import Decimal
from typing import Any, Optional

from wolfxl.styles.numbers import (
    FORMAT_DATE_DATETIME,
    FORMAT_DATE_TIME6,
    FORMAT_DATE_TIMEDELTA,
    FORMAT_DATE_YYYYMMDD2,
    is_date_format,
)

TYPE_NULL = "n"
TYPE_NUMERIC = "n"
TYPE_STRING = "s"
TYPE_FORMULA = "f"
TYPE_BOOL = "b"
TYPE_ERROR = "e"
TYPE_INLINE = "inlineStr"
TYPE_FORMULA_CACHE_STRING = "str"
VALID_TYPES = (
    TYPE_STRING,
    TYPE_FORMULA,
    TYPE_NUMERIC,
    TYPE_BOOL,
    TYPE_NULL,
    TYPE_INLINE,
    TYPE_ERROR,
    TYPE_FORMULA_CACHE_STRING,
)
ERROR_CODES = ("#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#N/A")
NUMERIC_TYPES = (int, float, Decimal)
TIME_TYPES = (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)
TIME_FORMATS = {
    datetime.datetime: FORMAT_DATE_DATETIME,
    datetime.date: FORMAT_DATE_YYYYMMDD2,
    datetime.time: FORMAT_DATE_TIME6,
    datetime.timedelta: FORMAT_DATE_TIMEDELTA,
}
ILLEGAL_CHARACTERS_RE = re.compile(r"[\000-\010]|[\013-\014]|[\016-\037]")


def get_time_format(t: type) -> str:
    if t in TIME_FORMATS:
        return TIME_FORMATS[t]
    for base in t.mro()[1:]:
        if base in TIME_FORMATS:
            fmt = TIME_FORMATS[base]
            TIME_FORMATS[t] = fmt
            return fmt
    raise ValueError(f"Could not get time format for {t!r}")


def get_type(t: type, value: Any) -> str | None:  # noqa: ARG001
    if isinstance(value, NUMERIC_TYPES):
        return TYPE_NUMERIC
    if isinstance(value, STRING_TYPES):
        return TYPE_STRING
    if isinstance(value, TIME_TYPES):
        return "d"
    return None


class _FormulaAliasMeta(type):
    """Treat duplicate openpyxl/wolfxl formula class aliases as instances."""

    formula_type: str

    def __instancecheck__(cls, instance: object) -> bool:
        return (
            type(instance).__name__ == cls.__name__
            and getattr(instance, "t", None) == cls.formula_type
            and hasattr(instance, "ref")
        )


class ArrayFormula(metaclass=_FormulaAliasMeta):
    """Pre-365 array formula (CSE) or Excel 365 spilled dynamic array.

    Constructor signature mirrors openpyxl's ``ArrayFormula(ref, text)``
    so existing user code that does
    ``cell.value = ArrayFormula(ref="A1:A10", text="B1:B10*2")``
    Just Works.

    Attributes:
        ref: Spill / array range, e.g. ``"A1:A10"`` for a single-column
            spill. The cell holding the formula is the *master* of this
            range; every other cell inside ``ref`` reads back as ``None``.
        text: Formula body without the leading ``"="`` and without
            surrounding ``{}`` braces.
    """

    __slots__ = ("ref", "text")

    # ``t`` matches openpyxl's class-level discriminator used by the
    # writer's ``dict(value)`` cast when emitting ``<f t="array" ref=...>``.
    t = "array"
    formula_type = "array"

    def __init__(self, ref: str, text: str | None = None) -> None:
        """Create an array-formula value.

        Args:
            ref: Spill or array range, such as ``"A1:A10"``.
            text: Formula text, with or without a leading ``=`` or wrapping
                CSE braces. The stored value is normalized to the bare body.
        """
        self.ref = ref
        # Strip any leading "=" the caller may have passed for
        # convenience — matches openpyxl's coercion.  Also strip
        # surrounding braces so users can paste a CSE formula
        # verbatim from Excel's name box.
        if text is None:
            text = ""
        if text.startswith("{=") and text.endswith("}"):
            text = text[2:-1]
        elif text.startswith("="):
            text = text[1:]
        elif text.startswith("{") and text.endswith("}"):
            text = text[1:-1]
        self.text = text

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ArrayFormula):
            return NotImplemented
        return self.ref == other.ref and self.text == other.text

    def __hash__(self) -> int:
        return hash((self.ref, self.text))

    def __repr__(self) -> str:
        return f"ArrayFormula(ref={self.ref!r}, text={self.text!r})"

    def __iter__(self):
        """Yield ``(attr, str)`` pairs matching openpyxl's writer contract.

        ``dict(value)`` in ``write_cell`` reads back the formula's
        ``t`` discriminator and ``ref`` to populate the ``<f>`` element
        attributes. Falsy values are skipped to match upstream behavior.
        """
        from wolfxl.compat.strings import safe_string

        for key in ("t", "ref"):
            value = getattr(self, key)
            if value:
                yield key, safe_string(value)


class DataTableFormula(metaclass=_FormulaAliasMeta):
    """1D or 2D Excel data table formula.

    Constructor signature mirrors openpyxl's ``DataTableFormula``.

    Attributes:
        ref: Range that the data table fills, e.g. ``"B2:F11"``.
        ca: Always-calculate flag (``calcArray``).
        dt2D: Two-variable data-table flag.
        dtr: Row-input flag.
        r1: First input cell.
        r2: Second input cell for 2D tables.
    """

    __slots__ = ("ref", "ca", "dt2D", "dtr", "r1", "r2", "del1", "del2")

    # ``t`` matches openpyxl's class-level discriminator used by the
    # writer's ``dict(value)`` cast when emitting ``<f t="dataTable" ...>``.
    t = "dataTable"
    formula_type = "dataTable"

    def __init__(
        self,
        ref: str,
        ca: bool = False,
        dt2D: bool = False,
        dtr: bool = False,
        r1: Optional[str] = None,
        r2: Optional[str] = None,
        del1: bool = False,
        del2: bool = False,
        t: Optional[str] = None,
        **kw: Any,
    ) -> None:
        """Create a data-table formula value.

        Args:
            ref: Range that the data table fills.
            ca: Always-calculate flag.
            dt2D: Whether this is a two-variable data table.
            dtr: Whether the data-table input is a row.
            r1: First input cell reference.
            r2: Second input cell reference for two-variable tables.
            del1: Deleted first input-cell flag.
            del2: Deleted second input-cell flag.
            t: Optional OOXML formula-type discriminator. Accepted for
                openpyxl API compatibility and ignored.
            **kw: Additional openpyxl-compatible keyword arguments, accepted
                and ignored for forwards compatibility.
        """
        if t is not None and t != "dataTable":
            raise ValueError(f"Unsupported data-table formula kind: {t!r}")
        self.ref = ref
        self.ca = bool(ca)
        self.dt2D = bool(dt2D)
        self.dtr = bool(dtr)
        self.r1 = r1
        self.r2 = r2
        self.del1 = bool(del1)
        self.del2 = bool(del2)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DataTableFormula):
            return NotImplemented
        return (
            self.ref == other.ref
            and self.ca == other.ca
            and self.dt2D == other.dt2D
            and self.dtr == other.dtr
            and self.r1 == other.r1
            and self.r2 == other.r2
            and self.del1 == other.del1
            and self.del2 == other.del2
        )

    def __hash__(self) -> int:
        return hash(
            (self.ref, self.ca, self.dt2D, self.dtr, self.r1, self.r2, self.del1, self.del2)
        )

    def __repr__(self) -> str:
        parts = [f"ref={self.ref!r}"]
        if self.ca:
            parts.append(f"ca={self.ca!r}")
        if self.dt2D:
            parts.append(f"dt2D={self.dt2D!r}")
        if self.dtr:
            parts.append(f"dtr={self.dtr!r}")
        if self.r1 is not None:
            parts.append(f"r1={self.r1!r}")
        if self.r2 is not None:
            parts.append(f"r2={self.r2!r}")
        if self.del1:
            parts.append(f"del1={self.del1!r}")
        if self.del2:
            parts.append(f"del2={self.del2!r}")
        return f"DataTableFormula({', '.join(parts)})"

    def __iter__(self):
        """Yield ``(attr, str)`` pairs matching openpyxl's writer contract.

        Order matches upstream so the resulting ``<f>`` element attribute
        order is stable across libraries. Falsy values are skipped.
        """
        from wolfxl.compat.strings import safe_string

        for key in ("t", "ref", "dt2D", "dtr", "r1", "r2", "del1", "del2", "ca"):
            value = getattr(self, key)
            if value:
                yield key, safe_string(value)


# ---------------------------------------------------------------------------
# openpyxl-shaped re-exports (RFC-060 Pod 2).
#
# ``openpyxl.cell.cell`` is a kitchen-sink module — user code routinely does
# ``from openpyxl.cell.cell import Cell, MergedCell, WriteOnlyCell``.  Wolfxl
# keeps each class at its own canonical home (``wolfxl._cell.Cell``,
# ``wolfxl.cell._merged.MergedCell``, ``wolfxl.cell._write_only.WriteOnlyCell``)
# and surfaces them all here so a one-line import swap works.
# ---------------------------------------------------------------------------

from wolfxl._cell import Cell  # noqa: E402
from wolfxl.cell._merged import MergedCell  # noqa: E402
from wolfxl.cell._write_only import WriteOnlyCell  # noqa: E402
from wolfxl.cell.rich_text import CellRichText  # noqa: E402
from wolfxl.utils.exceptions import IllegalCharacterError  # noqa: E402
from wolfxl.utils import get_column_letter  # noqa: E402
from wolfxl.worksheet.hyperlink import Hyperlink  # noqa: E402

STRING_TYPES = (str, bytes, CellRichText)
KNOWN_TYPES = NUMERIC_TYPES + TIME_TYPES + STRING_TYPES + (bool, type(None))
StyleableObject = Cell


__all__ = [
    "ArrayFormula",
    "Cell",
    "CellRichText",
    "DataTableFormula",
    "ERROR_CODES",
    "Hyperlink",
    "ILLEGAL_CHARACTERS_RE",
    "IllegalCharacterError",
    "KNOWN_TYPES",
    "MergedCell",
    "NUMERIC_TYPES",
    "STRING_TYPES",
    "StyleableObject",
    "TIME_FORMATS",
    "TIME_TYPES",
    "TYPE_BOOL",
    "TYPE_ERROR",
    "TYPE_FORMULA",
    "TYPE_FORMULA_CACHE_STRING",
    "TYPE_INLINE",
    "TYPE_NULL",
    "TYPE_NUMERIC",
    "TYPE_STRING",
    "VALID_TYPES",
    "WriteOnlyCell",
    "copy",
    "datetime",
    "get_column_letter",
    "get_time_format",
    "get_type",
    "is_date_format",
    "numbers",
    "re",
]
