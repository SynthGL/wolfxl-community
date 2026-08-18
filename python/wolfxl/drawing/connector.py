"""Drawing connector compatibility."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable, _resolve_openpyxl_class
from wolfxl.chart.shapes import GraphicalProperties
from wolfxl.chart.text import RichText

def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


for _name in (
    "Connection", "ConnectorLocking", "ConnectorNonVisual", "ConnectorShape",
    "NonVisualConnectorProperties", "NonVisualDrawingProps",
    "NonVisualDrawingShapeProps", "OfficeArtExtensionList", "Shape",
    "ShapeMeta", "ShapeStyle",
):
    globals()[_name] = _openpyxl_class(_name)

Alias = Bool = Integer = Serialisable = String = Typed = _OpenpyxlSerialisable

__all__ = [name for name in list(globals()) if not name.startswith("_")]
