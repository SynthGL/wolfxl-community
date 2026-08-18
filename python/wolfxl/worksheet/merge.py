"""``openpyxl.worksheet.merge`` — merge-cell value types.

Wolfxl tracks merged ranges as plain A1 strings on the Worksheet
proxy; this module surfaces the openpyxl-shaped value types so user
code that constructs them by hand (or ``isinstance``-checks against
them) ports mechanically.

Sprint Π Pod-β (RFC-063) replaced the ``MergeCell`` and ``MergeCells``
stubs with real type-only proxies over the underlying ``set[str]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
import copy
from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.cell._merged import MergedCell
from wolfxl._styles import Border
from wolfxl.xml.functions import Element
from wolfxl.worksheet.cell_range import CellRange


class MergedCellRange(CellRange):
    """A :class:`CellRange` flagged as a merged region.

    openpyxl stores merged regions as ``MergedCellRange`` instances
    (a ``CellRange`` subclass) on ``ws.merged_cells``.  Wolfxl uses
    plain strings, but the class is exposed here so user code that
    constructs one explicitly continues to work.
    """

    __slots__ = ("worksheet", "start_cell")

    def __init__(self, worksheet: Any = None, coord: str | None = None) -> None:
        if coord is None:
            coord = str(worksheet)
            worksheet = None
        self.worksheet = worksheet
        super().__init__(coord)
        self._get_borders()

    def _get_borders(self) -> None:
        if self.worksheet is None:
            self.start_cell = None
            return
        self.start_cell = self.worksheet.cell(self.min_row, self.min_col)
        end_cell = self.worksheet._cells.get((self.max_row, self.max_col))  # noqa: SLF001
        if end_cell is None:
            return
        start = self.start_cell.border
        end = end_cell.border
        self.start_cell.border = Border(
            left=start.left,
            right=end.right,
            top=start.top,
            bottom=end.bottom,
            diagonal=start.diagonal,
            diagonalUp=start.diagonalUp,
            diagonalDown=start.diagonalDown,
            outline=start.outline,
        )

    def format(self) -> None:
        """Apply start-cell borders and protection to cells in the merged range."""
        if self.worksheet is None or self.start_cell is None:
            return
        start_border = self.start_cell.border
        for name in ("top", "left", "right", "bottom"):
            side = getattr(start_border, name)
            if side is None:
                continue
            border = Border(**{name: side})
            for row, col in getattr(self, name):
                cell = self.worksheet._cells.get((row, col))  # noqa: SLF001
                if cell is None:
                    cell = self.worksheet.cell(row=row, column=col)
                cell.border = _combine_border(cell.border, border)

        protection = self.start_cell.protection
        if protection is not None:
            protected = copy.copy(protection)
            for row, col in self.cells:
                cell = self.worksheet._cells.get((row, col))  # noqa: SLF001
                if cell is None:
                    cell = self.worksheet.cell(row=row, column=col)
                cell.protection = copy.copy(protected)

    def __copy__(self) -> "MergedCellRange":
        copied = self.__class__(self.worksheet, self.coord)
        copied.title = self.title
        return copied


@dataclass
class MergeCell:
    """Single merged region (CT_MergeCell §18.3.1.55).

    Wolfxl stores merged ranges as plain A1 strings; this class
    provides the openpyxl-shaped type-wrapper so user code
    constructing a ``MergeCell`` continues to work.
    """

    ref: str

    @property
    def coord(self) -> str:
        """Alias for :attr:`ref` — openpyxl spells it both ways."""
        return self.ref

    def to_tree(self) -> Any:
        """Serialize to an openpyxl-shaped ``<mergeCell>`` element."""
        node = Element("mergeCell")
        node.set("ref", self.ref)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "MergeCell":
        """Parse a ``<mergeCell>`` element."""
        return cls(ref=node.attrib.get("ref", ""))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CellRange):
            return CellRange(self.ref) == other
        if isinstance(other, MergeCell):
            return self.ref == other.ref
        other_ref = getattr(other, "coord", None) or getattr(other, "ref", None)
        if other_ref is not None:
            return self.ref == str(other_ref)
        return False

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.ref


class MergeCells:
    """Container for :class:`MergeCell` entries (CT_MergeCells §18.3.1.56).

    Backed by ``ws.merged_cells`` (a plain ``set[str]``) when bound to
    a worksheet; otherwise backed by an in-memory list. The container
    surfaces ``__iter__`` / ``__len__`` / :attr:`count` / :meth:`append`
    / :meth:`remove` for openpyxl source compatibility.

    The wrapper is a *view* — mutations are mirrored back onto the
    worksheet's underlying set so the existing patcher / native-writer
    pipelines see them automatically.
    """

    __slots__ = ("worksheet", "_extra")

    def __init__(
        self,
        worksheet: Any = None,
        mergeCell: Iterable[Any] | None = None,  # noqa: N803 - openpyxl API
        count: int | None = None,  # noqa: ARG002
    ) -> None:
        self.worksheet = worksheet
        # Items added via the constructor when no worksheet is provided
        # (or that are explicitly stuffed via ``append``) live here when
        # the worksheet path isn't available.  When a worksheet *is*
        # provided, the constructor entries are folded into the
        # underlying ``ws.merged_cells`` set so the two views stay in
        # sync.
        self._extra: list[MergeCell] = []
        if mergeCell is not None:
            for item in mergeCell:
                self.append(item)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ws_set(self) -> set[str] | None:
        """Return the underlying ``ws._merged_ranges`` set, or ``None``."""
        ws = self.worksheet
        if ws is None:
            return None
        return getattr(ws, "_merged_ranges", None)

    @staticmethod
    def _coerce(item: Any) -> MergeCell:
        """Coerce *item* into a :class:`MergeCell`."""
        if isinstance(item, MergeCell):
            return item
        if isinstance(item, str):
            return MergeCell(ref=item)
        # Fall back to an attribute lookup so ``CellRange``-like inputs
        # (which carry a stringifiable form) work transparently.
        ref = getattr(item, "coord", None) or getattr(item, "ref", None)
        if ref is None:
            ref = str(item)
        return MergeCell(ref=str(ref))

    # ------------------------------------------------------------------
    # openpyxl-shape API
    # ------------------------------------------------------------------

    @property
    def mergeCell(self) -> list[MergeCell]:  # noqa: N802 - openpyxl API
        """Materialised list of :class:`MergeCell` entries (snapshot)."""
        return list(iter(self))

    @property
    def count(self) -> int:
        """Number of merged regions currently registered."""
        return len(self)

    def append(self, mc: Any) -> None:
        """Add a merged region (accepts a :class:`MergeCell` or A1 string)."""
        cell = self._coerce(mc)
        backing = self._ws_set()
        if backing is not None:
            backing.add(cell.ref)
        else:
            # Avoid duplicates when no worksheet is bound — match the
            # set-like semantics of the live path.
            if not any(existing.ref == cell.ref for existing in self._extra):
                self._extra.append(cell)

    def remove(self, mc: Any) -> None:
        """Remove a merged region (accepts a :class:`MergeCell` or A1 string)."""
        cell = self._coerce(mc)
        backing = self._ws_set()
        if backing is not None:
            backing.discard(cell.ref)
        else:
            self._extra = [existing for existing in self._extra if existing.ref != cell.ref]

    def __iter__(self) -> Iterator[MergeCell]:
        backing = self._ws_set()
        if backing is not None:
            # Sort for deterministic iteration — openpyxl's MultiCellRange
            # also yields refs in a canonical order.
            for ref in sorted(backing):
                yield MergeCell(ref=ref)
        else:
            yield from self._extra

    def __len__(self) -> int:
        backing = self._ws_set()
        if backing is not None:
            return len(backing)
        return len(self._extra)

    def __contains__(self, item: Any) -> bool:
        cell = self._coerce(item)
        backing = self._ws_set()
        if backing is not None:
            return cell.ref in backing
        return any(existing.ref == cell.ref for existing in self._extra)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        refs = [c.ref for c in self]
        return f"MergeCells(count={self.count}, refs={refs!r})"


def _combine_border(base: Border, overlay: Border) -> Border:
    return Border(
        left=overlay.left if overlay.left != Border().left else base.left,
        right=overlay.right if overlay.right != Border().right else base.right,
        top=overlay.top if overlay.top != Border().top else base.top,
        bottom=overlay.bottom if overlay.bottom != Border().bottom else base.bottom,
        diagonal=base.diagonal,
        diagonalUp=base.diagonalUp,
        diagonalDown=base.diagonalDown,
        outline=base.outline,
    )


__all__ = ["MergeCell", "MergeCells", "MergedCell", "MergedCellRange"]

__getattr__ = _openpyxl_name_fallback(globals())
