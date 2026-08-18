"""Drawing graphic compatibility containers."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _install_openpyxl_iter, _make_serialisable, _resolve_openpyxl_class
from wolfxl.drawing.fill import BlipFillProperties, GradientFillProperties
from wolfxl.drawing.xdr import XDRTransform2D
from wolfxl.xml.constants import CHART_NS, DRAWING_NS

def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


for _name in (
    "Blip", "ChartRelation", "GraphicData", "GraphicFrame",
    "GraphicFrameLocking", "GraphicObject", "GroupShape",
    "GroupShapeProperties", "NonVisualDrawingProps", "NonVisualGraphicFrame",
    "NonVisualGraphicFrameProperties", "NonVisualGroupShape",
    "OfficeArtExtensionList", "PictureFrame",
):
    globals()[_name] = _openpyxl_class(_name)

_install_openpyxl_iter(XDRTransform2D)

Alias = Bool = EffectContainer = EffectList = Serialisable = String = Typed = _OpenpyxlSerialisable

__all__ = [name for name in list(globals()) if not name.startswith("_")]
