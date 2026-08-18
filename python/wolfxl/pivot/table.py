"""``openpyxl.pivot.table`` import-compat surface."""

from __future__ import annotations

from collections import defaultdict

from wolfxl._compat import _make_serialisable, _resolve_openpyxl_class
from wolfxl.descriptors.base import Bool, Integer, NoneSet, Set, String, Typed
from wolfxl.descriptors.excel import ExtensionList, Relation
from wolfxl.descriptors.sequence import NestedSequence, Sequence
from wolfxl.descriptors.serialisable import Serialisable
from wolfxl.packaging.relationship import Relationship, RelationshipList, get_rels_path
from wolfxl.pivot._table import (
    ColumnField as _NativeColumnField,
    DataField as _NativeDataField,
    DataFunction,
    Location as _NativeLocation,
    PageField as _NativePageField,
    PivotField as _NativePivotField,
    PivotItem as _NativePivotItem,
    PivotSource,
    PivotTable as _NativePivotTable,
    PivotTableStyleInfo,
    RowField as _NativeRowField,
)
from wolfxl.pivot.record import Index
from wolfxl.xml.constants import SHEET_MAIN_NS
from wolfxl.xml.functions import tostring

def _openpyxl_class(name: str, fallback: type | None = None) -> type:
    return _resolve_openpyxl_class(__name__, name) or fallback or _make_serialisable(name)

TableDefinition = _openpyxl_class("TableDefinition", _NativePivotTable)
PivotTable = _openpyxl_class("PivotTable", TableDefinition)
PivotField = _openpyxl_class("PivotField", _NativePivotField)
PivotItem = _openpyxl_class("PivotItem", _NativePivotItem)
DataField = _openpyxl_class("DataField", _NativeDataField)
Location = _openpyxl_class("Location", _NativeLocation)
PageField = _openpyxl_class("PageField", _NativePageField)
RowField = _openpyxl_class("RowField", _NativeRowField)
ColumnField = _openpyxl_class("ColumnField", _NativeColumnField)

AutoSortScope = _openpyxl_class("AutoSortScope")
ChartFormat = _openpyxl_class("ChartFormat")
ColHierarchiesUsage = _openpyxl_class("ColHierarchiesUsage")
ConditionalFormat = _openpyxl_class("ConditionalFormat")
ConditionalFormatList = _openpyxl_class("ConditionalFormatList")
FieldItem = _openpyxl_class("FieldItem")
Format = _openpyxl_class("Format")
HierarchyUsage = _openpyxl_class("HierarchyUsage")
MemberList = _openpyxl_class("MemberList")
MemberProperty = _openpyxl_class("MemberProperty")
PivotArea = _openpyxl_class("PivotArea")
PivotFilter = _openpyxl_class("PivotFilter")
PivotFilters = _openpyxl_class("PivotFilters")
PivotHierarchy = _openpyxl_class("PivotHierarchy")
PivotTableStyle = _openpyxl_class("PivotTableStyle")
Reference = _openpyxl_class("Reference")
RowColField = _openpyxl_class("RowColField")
RowColItem = _openpyxl_class("RowColItem")
RowHierarchiesUsage = _openpyxl_class("RowHierarchiesUsage")

try:
    from wolfxl.worksheet.filters import AutoFilter
except ImportError:  # pragma: no cover - filters are part of the normal wheel
    AutoFilter = _make_serialisable("AutoFilter")

_auto_filter_descriptor = getattr(PivotFilter, "autoFilter", None)
if hasattr(_auto_filter_descriptor, "expected_type"):
    _auto_filter_descriptor.expected_type = AutoFilter

__all__ = [
    "AutoFilter",
    "AutoSortScope",
    "Bool",
    "ChartFormat",
    "ColHierarchiesUsage",
    "ColumnField",
    "ConditionalFormat",
    "ConditionalFormatList",
    "DataField",
    "DataFunction",
    "ExtensionList",
    "FieldItem",
    "Format",
    "HierarchyUsage",
    "Index",
    "Integer",
    "Location",
    "MemberList",
    "MemberProperty",
    "NestedSequence",
    "NoneSet",
    "PageField",
    "PivotArea",
    "PivotField",
    "PivotFilter",
    "PivotFilters",
    "PivotHierarchy",
    "PivotItem",
    "PivotSource",
    "PivotTable",
    "PivotTableStyle",
    "PivotTableStyleInfo",
    "Reference",
    "Relation",
    "Relationship",
    "RelationshipList",
    "RowColField",
    "RowColItem",
    "RowField",
    "RowHierarchiesUsage",
    "SHEET_MAIN_NS",
    "Sequence",
    "Serialisable",
    "Set",
    "String",
    "TableDefinition",
    "Typed",
    "defaultdict",
    "get_rels_path",
    "tostring",
]
