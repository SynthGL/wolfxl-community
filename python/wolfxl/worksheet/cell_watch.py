"""Worksheet cell-watch compatibility."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable

CellWatch = _make_serialisable("CellWatch")
CellWatches = _make_serialisable("CellWatches")
Sequence = Serialisable = String = _OpenpyxlSerialisable

__all__ = ["CellWatch", "CellWatches", "Sequence", "Serialisable", "String"]
