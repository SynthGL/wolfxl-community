"""``openpyxl.pivot.fields`` import-compat surface."""

from __future__ import annotations

from wolfxl._compat import _make_serialisable, _resolve_openpyxl_class
from wolfxl.descriptors.base import Bool, DateTime, Float, Integer, String, Tuple as _DescriptorTuple, Typed
from wolfxl.descriptors.excel import HexBinary
from wolfxl.descriptors.sequence import Sequence
from wolfxl.descriptors.serialisable import Serialisable
from wolfxl.pivot._table import (
    ColumnField,
    DataField,
    PageField,
    PivotField,
    PivotItem,
    RowField,
)
from wolfxl.pivot.record import Boolean, DateTimeField, Error, Index, Missing, Number, Text, TupleList


Tuple = _resolve_openpyxl_class(__name__, "Tuple") or _DescriptorTuple or _make_serialisable("Tuple")

__all__ = [
    "Bool",
    "Boolean",
    "ColumnField",
    "DataField",
    "DateTime",
    "DateTimeField",
    "Error",
    "Float",
    "HexBinary",
    "Index",
    "Integer",
    "Missing",
    "Number",
    "PageField",
    "PivotField",
    "PivotItem",
    "RowField",
    "Sequence",
    "Serialisable",
    "String",
    "Text",
    "Tuple",
    "TupleList",
    "Typed",
]
