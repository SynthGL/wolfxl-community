"""``openpyxl.pivot.cache`` import-compat surface."""

from __future__ import annotations

from wolfxl._compat import _make_serialisable, _resolve_openpyxl_class
from wolfxl.descriptors.base import Bool, DateTime, Float, Integer, NoneSet, Set, String, Typed
from wolfxl.descriptors.excel import ExtensionList, HexBinary, Relation
from wolfxl.descriptors.nested import NestedInteger
from wolfxl.descriptors.sequence import MultiSequence, MultiSequencePart, NestedSequence, Sequence
from wolfxl.descriptors.serialisable import Serialisable
from wolfxl.packaging.relationship import Relationship, RelationshipList, get_rels_path
from wolfxl.pivot._cache import CacheValue, PivotCache
from wolfxl.pivot.record import Boolean, DateTimeField, Error, Missing, Number, Text, TupleList
from wolfxl.xml.constants import SHEET_MAIN_NS
from wolfxl.xml.functions import tostring

def _openpyxl_class(name: str, fallback: type | None = None) -> type:
    return _resolve_openpyxl_class(__name__, name) or fallback or _make_serialisable(name)

CacheDefinition = _openpyxl_class("CacheDefinition")
CacheField = _openpyxl_class("CacheField")
SharedItems = _openpyxl_class("SharedItems")
WorksheetSource = _openpyxl_class("WorksheetSource")
CacheHierarchy = _openpyxl_class("CacheHierarchy")
CacheSource = _openpyxl_class("CacheSource")
CalculatedItem = _openpyxl_class("CalculatedItem")
CalculatedMember = _openpyxl_class("CalculatedMember")
Consolidation = _openpyxl_class("Consolidation")
FieldGroup = _openpyxl_class("FieldGroup")
FieldUsage = _openpyxl_class("FieldUsage")
GroupItems = _openpyxl_class("GroupItems")
GroupLevel = _openpyxl_class("GroupLevel")
GroupMember = _openpyxl_class("GroupMember")
LevelGroup = _openpyxl_class("LevelGroup")
MeasureDimensionMap = _openpyxl_class("MeasureDimensionMap")
MeasureGroup = _openpyxl_class("MeasureGroup")
OLAPKPI = _openpyxl_class("OLAPKPI")
OLAPSet = _openpyxl_class("OLAPSet")
PCDSDTCEntries = _openpyxl_class("PCDSDTCEntries")
PageItem = _openpyxl_class("PageItem")
PivotArea = _openpyxl_class("PivotArea")
PivotDimension = _openpyxl_class("PivotDimension")
Query = _openpyxl_class("Query")
RangePr = _openpyxl_class("RangePr")
RangeSet = _openpyxl_class("RangeSet")
Reference = _openpyxl_class("Reference")
ServerFormat = _openpyxl_class("ServerFormat")
TupleCache = _openpyxl_class("TupleCache")

__all__ = [
    "Bool",
    "Boolean",
    "CacheDefinition",
    "CacheField",
    "CacheHierarchy",
    "CacheSource",
    "CacheValue",
    "CalculatedItem",
    "CalculatedMember",
    "Consolidation",
    "DateTime",
    "DateTimeField",
    "Error",
    "ExtensionList",
    "FieldGroup",
    "FieldUsage",
    "Float",
    "GroupItems",
    "GroupLevel",
    "GroupMember",
    "HexBinary",
    "Integer",
    "LevelGroup",
    "MeasureDimensionMap",
    "MeasureGroup",
    "Missing",
    "MultiSequence",
    "MultiSequencePart",
    "NestedInteger",
    "NestedSequence",
    "NoneSet",
    "Number",
    "OLAPKPI",
    "OLAPSet",
    "PCDSDTCEntries",
    "PageItem",
    "PivotArea",
    "PivotCache",
    "PivotDimension",
    "Query",
    "RangePr",
    "RangeSet",
    "Reference",
    "Relation",
    "Relationship",
    "RelationshipList",
    "SHEET_MAIN_NS",
    "Sequence",
    "Serialisable",
    "ServerFormat",
    "Set",
    "SharedItems",
    "String",
    "Text",
    "TupleCache",
    "TupleList",
    "Typed",
    "WorksheetSource",
    "get_rels_path",
    "tostring",
]
