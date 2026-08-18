"""Worksheet drawing relationship compatibility."""

from __future__ import annotations

from wolfxl._compat import _make_serialisable

Drawing = _make_serialisable("Drawing")
Relation = Serialisable = object

__all__ = ["Drawing", "Relation", "Serialisable"]
