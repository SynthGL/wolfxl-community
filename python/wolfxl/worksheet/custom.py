"""Worksheet custom properties compatibility."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable

CustomProperties = _make_serialisable("CustomProperties")
CustomProperty = _make_serialisable("CustomProperty")
Sequence = Serialisable = String = _OpenpyxlSerialisable

__all__ = ["CustomProperties", "CustomProperty", "Sequence", "Serialisable", "String"]
