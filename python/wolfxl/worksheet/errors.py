"""Worksheet ignored-error compatibility."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable
from wolfxl.descriptors.excel import CellRange

Extension = _make_serialisable("Extension")
ExtensionList = _make_serialisable("ExtensionList")
IgnoredError = _make_serialisable("IgnoredError")
IgnoredErrors = _make_serialisable("IgnoredErrors")
Bool = Sequence = Serialisable = String = Typed = _OpenpyxlSerialisable

__all__ = [
    "Bool",
    "CellRange",
    "Extension",
    "ExtensionList",
    "IgnoredError",
    "IgnoredErrors",
    "Sequence",
    "Serialisable",
    "String",
    "Typed",
]
