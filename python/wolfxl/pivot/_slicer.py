"""``Slicer`` / ``SlicerCache`` / ``SlicerItem`` — pivot slicer support.

Mirrors :mod:`openpyxl.slicer`. The public surface:

- :class:`SlicerCache` — workbook-scoped cache; references a
  :class:`PivotCache` and a single field by name.
- :class:`Slicer` — sheet-scoped presentation pointing at a cache.
- :class:`SlicerItem` — one enumerated value (with hidden / no_data
  flags) inside a slicer cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ._cache import PivotCache


# ---------------------------------------------------------------------------
# SlicerItem
# ---------------------------------------------------------------------------


@dataclass
class SlicerItem:
    """Single enumerated slicer value.

    Setting ``hidden=True`` excludes the item from the slicer card's
    visible list (Excel still tracks the option but hides it).
    ``no_data=True`` means the source cache field has no records
    matching that value at refresh time.
    """

    name: str
    hidden: bool = False
    no_data: bool = False

    def to_rust_dict(self) -> dict:
        return {
            "name": self.name,
            "hidden": self.hidden,
            "no_data": self.no_data,
        }


# ---------------------------------------------------------------------------
# SlicerCache
# ---------------------------------------------------------------------------


_VALID_SORT_ORDERS = ("ascending", "descending", "none")


class SlicerCache:
    """Workbook-scoped slicer cache.

    Construct with a :class:`PivotCache` reference and a field
    name; register via :meth:`Workbook.add_slicer_cache`.

    Slicer caches are workbook-scoped — when a sheet is deep-cloned
    via :meth:`Workbook.copy_worksheet`, slicer caches are aliased
    (shared between source and clone). Slicer presentations on the
    cloned sheet are deep-cloned with the cache id preserved.
    """

    def __init__(
        self,
        name: str,
        *,
        source_pivot_cache: "PivotCache",
        field: str,
        sort_order: str = "ascending",
        custom_list_sort: bool = False,
        hide_items_with_no_data: bool = False,
        show_missing: bool = True,
    ) -> None:
        from ._cache import PivotCache

        if not isinstance(source_pivot_cache, PivotCache):
            raise TypeError(
                "SlicerCache.source_pivot_cache must be a PivotCache, "
                f"got {type(source_pivot_cache).__name__}"
            )
        if not isinstance(name, str) or not name:
            raise ValueError("SlicerCache requires a non-empty name")
        if sort_order not in _VALID_SORT_ORDERS:
            raise ValueError(
                f"sort_order must be one of {_VALID_SORT_ORDERS}, "
                f"got {sort_order!r}"
            )
        self.name = name
        self.source_pivot_cache = source_pivot_cache
        self.field = field
        self.sort_order = sort_order
        self.custom_list_sort = custom_list_sort
        self.hide_items_with_no_data = hide_items_with_no_data
        self.show_missing = show_missing
        self.items: list[SlicerItem] = []
        # Set by Workbook.add_slicer_cache.
        self._slicer_cache_id: int | None = None

    @property
    def slicer_cache_id(self) -> int:
        if self._slicer_cache_id is None:
            raise RuntimeError(
                "SlicerCache has not been registered yet — call "
                "Workbook.add_slicer_cache(cache) first"
            )
        return self._slicer_cache_id

    @property
    def source_field_index(self) -> int:
        """Resolve ``field`` (string) to a 0-based index inside the
        source pivot cache's ``fields``."""
        return self.source_pivot_cache.field_index(self.field)

    def add_item(
        self,
        name: str,
        *,
        hidden: bool = False,
        no_data: bool = False,
    ) -> SlicerItem:
        item = SlicerItem(name=name, hidden=hidden, no_data=no_data)
        self.items.append(item)
        return item

    def populate_items_from_cache(self) -> None:
        """Pull the source cache field's enumerated `<sharedItems>`
        and seed :attr:`items` with them.

        Called automatically by :meth:`Workbook.add_slicer_cache`
        when ``items`` is empty at registration time.
        """
        cf = self.source_pivot_cache.fields[self.source_field_index]
        si = cf.shared_items
        if si.items is None:
            return  # numeric range field, no enumeration
        # Reset existing — we are seeding from source.
        self.items = [
            SlicerItem(name=str(v.value) if v.value is not None else "")
            for v in si.items
            if v.kind != "missing"
        ]

    def to_rust_dict(self) -> dict:
        if self._slicer_cache_id is None:
            raise RuntimeError(
                "SlicerCache.slicer_cache_id not set — call "
                "Workbook.add_slicer_cache() first"
            )
        return {
            "name": self.name,
            "source_pivot_cache_id": self.source_pivot_cache.cache_id,
            "source_field_index": self.source_field_index,
            "sort_order": self.sort_order,
            "custom_list_sort": self.custom_list_sort,
            "hide_items_with_no_data": self.hide_items_with_no_data,
            "show_missing": self.show_missing,
            "items": [it.to_rust_dict() for it in self.items],
        }


# ---------------------------------------------------------------------------
# Slicer presentation
# ---------------------------------------------------------------------------


@dataclass
class Slicer:
    """Sheet-scoped slicer presentation.

    Anchored to a worksheet via :meth:`Worksheet.add_slicer(slicer,
    anchor)`.

    Slicer presentations deep-clone with the sheet when
    :meth:`Workbook.copy_worksheet` runs; the ``cache`` is aliased
    (workbook-scoped).
    """

    name: str
    cache: SlicerCache
    caption: str = ""
    row_height: int = 204
    column_count: int = 1
    show_caption: bool = True
    style: Optional[str] = "SlicerStyleLight1"
    locked: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Slicer requires a non-empty name")
        if not isinstance(self.cache, SlicerCache):
            raise TypeError(
                "Slicer.cache must be a SlicerCache, "
                f"got {type(self.cache).__name__}"
            )
        if self.column_count < 1:
            raise ValueError(
                f"Slicer.column_count must be ≥ 1, got {self.column_count}"
            )
        if self.row_height < 1:
            raise ValueError(
                f"Slicer.row_height must be ≥ 1, got {self.row_height}"
            )
        # Set by Worksheet.add_slicer.
        self.anchor: str | None = None

    def to_rust_dict(self) -> dict:
        if self.anchor is None:
            raise RuntimeError(
                "Slicer.anchor not set — call Worksheet.add_slicer() first"
            )
        return {
            "name": self.name,
            "cache_name": self.cache.name,
            "caption": self.caption,
            "row_height": self.row_height,
            "column_count": self.column_count,
            "show_caption": self.show_caption,
            "style": self.style,
            "locked": self.locked,
            "anchor": self.anchor,
        }
