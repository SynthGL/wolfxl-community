"""Worksheet background picture compatibility."""

from __future__ import annotations

from wolfxl._compat import _make_serialisable

SheetBackgroundPicture = _make_serialisable("SheetBackgroundPicture")
Serialisable = object

__all__ = ["Serialisable", "SheetBackgroundPicture"]
