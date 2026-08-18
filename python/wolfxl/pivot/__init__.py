"""``wolfxl.pivot`` — pivot-table construction.

Mirrors :mod:`openpyxl.pivot`. The public surface is:

- :class:`PivotCache` — the schema + records snapshot for a source
  range. Constructed by the user, registered via
  :meth:`Workbook.add_pivot_cache`, and emitted as
  ``xl/pivotCache/pivotCacheDefinition{N}.xml`` plus a companion
  ``pivotCacheRecords{N}.xml``.
- :class:`PivotTable` — the layout (rows/cols/data/page assignments)
  pointing at a cache. Registered via
  :meth:`Worksheet.add_pivot_table`. Emitted as
  ``xl/pivotTables/pivotTable{N}.xml``.
- :class:`PivotField` / :class:`DataField` / :class:`RowField` /
  :class:`ColumnField` / :class:`PageField` — explicit builders for
  pivot-table axes when the bare-string convenience form
  (``rows=["region"]``) doesn't fit.
- :class:`PivotTableHandle` — modify-mode handle returned by
  :meth:`Workbook.pivot_tables` for mutating pivot tables in an
  existing workbook without rebuilding the cache.
- :class:`Reference` — re-exported from :mod:`wolfxl.chart.reference`
  for source-range construction (the OOXML cache uses the exact same
  shape).

Capabilities
------------

Cache + records construction, layout serialization, slicers,
calculated fields and items, field grouping (range, date, items),
and pivot styling (formats, pivot areas, conditional formatting).
Source-data ranges currently restricted to in-workbook
``WorksheetSource``; external connections are not yet wired.

The Rust emit functions live in ``crates/wolfxl-pivot`` (PyO3-free)
and are reached via the ``wolfxl._rust`` bindings:

- ``serialize_pivot_cache_dict(d) -> bytes``
- ``serialize_pivot_records_dict(d) -> bytes``
- ``serialize_pivot_table_dict(d) -> bytes``
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from wolfxl.chart.reference import Reference
from ._cache import (
    CacheField,
    CacheValue,
    PivotCache,
    SharedItems,
    WorksheetSource,
)
from ._table import (
    ColumnField,
    DataField,
    DataFunction,
    Location,
    PageField,
    PivotField,
    PivotItem,
    PivotSource,
    PivotTable,
    PivotTableStyleInfo,
    RowField,
)
from ._handle import PivotTableHandle
from ._slicer import Slicer, SlicerCache, SlicerItem
from ._calc import CalculatedField, CalculatedItem
from ._group import FieldGroup, FieldGroupRange, FieldGroupDate
from ._styling import (
    ChartFormat,
    Format,
    PivotArea,
    PivotConditionalFormat,
)


def __getattr__(name: str) -> Any:
    if name in {"cache", "fields", "record", "table"}:
        module = import_module(f"wolfxl.pivot.{name}")
        globals()[name] = module
        return module
    raise AttributeError(name)

__all__ = [
    # Cache layer
    "PivotCache",
    "CacheField",
    "SharedItems",
    "CacheValue",
    "WorksheetSource",
    # Table layer
    "PivotTable",
    "PivotField",
    "DataField",
    "DataFunction",
    "RowField",
    "ColumnField",
    "PageField",
    "PivotItem",
    "Location",
    "PivotTableStyleInfo",
    # Modify-mode mutation
    "PivotTableHandle",
    # Chart linkage
    "PivotSource",
    # Shared with charts
    "Reference",
    # Slicers
    "Slicer",
    "SlicerCache",
    "SlicerItem",
    # Calculated fields and items
    "CalculatedField",
    "CalculatedItem",
    # Group items
    "FieldGroup",
    "FieldGroupRange",
    "FieldGroupDate",
    # Pivot styling
    "Format",
    "PivotArea",
    "PivotConditionalFormat",
    "ChartFormat",
]
