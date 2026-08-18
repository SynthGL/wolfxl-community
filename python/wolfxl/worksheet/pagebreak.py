"""``openpyxl.worksheet.pagebreak`` — page-break value types.

Sprint Π Pod Π-α (RFC-062). Real implementations of ``Break`` /
``RowBreak`` / ``ColBreak`` plus a ``PageBreakList`` container. Wolfxl
constructs page-break XML at write time and splices it into existing
sheets in modify mode (Phase 2.5r).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from wolfxl._compat import _iter_openpyxl_attrs, _openpyxl_name_fallback
from wolfxl.xml.functions import Element


@dataclass
class Break:
    """Single page break (``CT_Break``, ECMA-376 §18.3.1.1).

    Attributes:
        id: 1-based row or column index above/left of the break.
        min: optional min cell in the break range (default 0).
        max: optional max cell in the break range (default
            16383 for col-breaks / 1048575 for row-breaks — Excel's
            full-axis sentinel).
        man: ``True`` for manual breaks (the default); ``False`` for
            automatic page-fit breaks.
        pt: ``True`` only when the break was inserted to fit the
            printer's page size — almost never user-set.
    """

    id: int = 0
    min: int | None = 0
    max: int | None = 16383
    man: bool = True
    pt: bool | None = None

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self)

    def to_rust_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "min": self.min,
            "max": self.max,
            "man": self.man,
            "pt": self.pt,
        }

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> Any:
        node = Element(tagname or "brk")
        for name, value in self:
            node.set(name, value)
        return node


@dataclass(init=False)
class RowBreak(Break):
    """Page break between rows. ``id`` is the row above the break."""

    tagname = "rowBreaks"

    def __init__(
        self,
        count: int | None = None,  # noqa: ARG002
        manualBreakCount: int | None = None,  # noqa: N803, ARG002
        brk: list["Break"] | tuple["Break", ...] = (),
        id: int = 0,  # noqa: A002
        min: int | None = 0,  # noqa: A002
        max: int | None = 16383,  # noqa: A002
        man: bool = True,
        pt: bool | None = None,
    ) -> None:
        super().__init__(id=id, min=min, max=max, man=man, pt=pt)
        self.brk = list(brk)

    @property
    def count(self) -> int:
        return len(self.brk)

    @property
    def manualBreakCount(self) -> int:  # noqa: N802
        return len(self.brk)

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, ("count", "manualBreakCount"))

    def __len__(self) -> int:
        return len(self.brk or [])

    def append(self, brk: Break | None = None) -> None:
        breaks = list(self.brk or [])
        if brk is None or not isinstance(brk, Break):
            brk = Break(id=len(breaks) + 1)
        breaks.append(brk)
        self.brk = breaks

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> Any:
        node = Element(tagname or self.tagname)
        for name, value in self:
            node.set(name, value)
        for brk in self.brk:
            node.append(brk.to_tree())
        return node


class ColBreak(RowBreak):
    """Page break between columns. ``id`` is the column to the left of the break."""

    tagname = "colBreaks"


# openpyxl's class is named ``Break`` but the module also exposes
# ``PageBreak`` as a row-break alias for a long-deprecated path.
PageBreak = RowBreak


@dataclass
class PageBreakList:
    """Container for a sequence of :class:`Break` instances.

    Backs ``ws.row_breaks`` / ``ws.col_breaks``. Provides
    list-like ``append`` / ``__iter__`` / ``__len__`` plus the
    openpyxl-named ``count`` and ``manualBreakCount`` mirror
    attributes that Excel writes onto ``<rowBreaks>`` /
    ``<colBreaks>``.
    """

    breaks: list[Break] = field(default_factory=list)
    count: int = 0
    manualBreakCount: int = 0  # noqa: N815  — openpyxl casing

    def __post_init__(self) -> None:
        # Recompute counters in case the user supplied ``breaks=[…]``.
        self._refresh_counts()

    # ---- public API ------------------------------------------------------

    def append(self, brk: Break | None = None) -> None:
        """Append *brk* and refresh the count attributes."""
        if brk is None:
            brk = Break(id=len(self.breaks) + 1, min=0, max=16383, pt=None)
        elif not isinstance(brk, Break):
            raise TypeError(
                f"PageBreakList.append: expected Break, got {type(brk).__name__}"
            )
        self.breaks.append(brk)
        self._refresh_counts()

    def __len__(self) -> int:
        return len(self.breaks)

    def __iter__(self) -> Iterator[Break]:
        return iter(self.breaks)

    def __bool__(self) -> bool:
        return bool(self.breaks)

    # openpyxl exposes a ``__contains__`` via list-like behaviour.
    def __contains__(self, item: Any) -> bool:
        return item in self.breaks

    def to_rust_dict(self) -> dict[str, Any]:
        """Return the §10 dict shape consumed by the Rust patcher."""
        return {
            "count": self.count,
            "manual_break_count": self.manualBreakCount,
            "breaks": [b.to_rust_dict() for b in self.breaks],
        }

    # ---- internals -------------------------------------------------------

    def _refresh_counts(self) -> None:
        self.count = len(self.breaks)
        self.manualBreakCount = sum(1 for b in self.breaks if b.man)


__all__ = ["Break", "ColBreak", "PageBreak", "PageBreakList", "RowBreak"]

__getattr__ = _openpyxl_name_fallback(globals())
