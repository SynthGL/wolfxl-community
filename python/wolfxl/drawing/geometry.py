"""Drawing geometry compatibility containers."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable, _resolve_openpyxl_class
from wolfxl.chart.shapes import LineProperties
from wolfxl.drawing.colors import OfficeArtExtensionList
from wolfxl.xml.constants import DRAWING_NS

def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


for _name in (
    "AdjPoint2D", "AdjustHandleList", "Backdrop", "Bevel", "Camera",
    "ConnectionSite", "ConnectionSiteList", "Coordinate", "CustomGeometry2D",
    "FontReference", "GeomGuide", "GeomGuideList", "GeomRect",
    "GroupTransform2D", "LightRig", "Path2D", "Path2DList", "Point2D",
    "Point3D", "PositiveSize2D", "PresetGeometry2D", "PresetTextShape", "Scene3D", "Shape3D",
    "SphereCoords", "StyleMatrixReference", "Transform2D", "Vector3D",
):
    globals()[_name] = _openpyxl_class(_name)

ShapeStyle = _openpyxl_class("ShapeStyle")
Alias = Bool = Color = Float = Integer = MinMax = NoneSet = Percentage = Serialisable = Set = String = Typed = _OpenpyxlSerialisable

__all__ = [name for name in list(globals()) if not name.startswith("_")]
