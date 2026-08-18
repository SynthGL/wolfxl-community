"""Drawing relationship compatibility."""

from __future__ import annotations

from wolfxl._compat import _make_serialisable
from wolfxl.xml.constants import CHART_NS

ChartRelation = _make_serialisable("ChartRelation")
Relation = Serialisable = object

__all__ = ["CHART_NS", "ChartRelation", "Relation", "Serialisable"]
