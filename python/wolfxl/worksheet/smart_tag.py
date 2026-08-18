"""Worksheet smart-tag compatibility."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable

CellSmartTag = _make_serialisable("CellSmartTag")
CellSmartTagPr = _make_serialisable("CellSmartTagPr")
CellSmartTags = _make_serialisable("CellSmartTags")
SmartTags = _make_serialisable("SmartTags")
Bool = Integer = Sequence = Serialisable = String = _OpenpyxlSerialisable

__all__ = [
    "Bool",
    "CellSmartTag",
    "CellSmartTagPr",
    "CellSmartTags",
    "Integer",
    "Sequence",
    "Serialisable",
    "SmartTags",
    "String",
]
