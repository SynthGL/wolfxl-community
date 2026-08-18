"""Drawing picture compatibility containers."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable, _resolve_openpyxl_class
from wolfxl.chart.shapes import GraphicalProperties
from wolfxl.drawing.fill import BlipFillProperties
from wolfxl.xml.constants import DRAWING_NS

def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


for _name in (
    "NonVisualDrawingProps", "NonVisualPictureProperties", "OfficeArtExtensionList",
    "PictureFrame", "PictureLocking", "PictureNonVisual",
):
    globals()[_name] = _openpyxl_class(_name)

ShapeStyle = _openpyxl_class("ShapeStyle")
Alias = Bool = Serialisable = String = Typed = _OpenpyxlSerialisable

__all__ = [name for name in list(globals()) if not name.startswith("_")]
