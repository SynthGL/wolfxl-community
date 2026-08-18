"""Drawing non-visual properties compatibility containers."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable, _resolve_openpyxl_class
from wolfxl.drawing.geometry import GroupTransform2D, Scene3D
from wolfxl.xml.constants import DRAWING_NS

def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


for _name in (
    "GroupLocking", "GroupShapeProperties", "Hyperlink",
    "NonVisualDrawingProps", "NonVisualDrawingShapeProps",
    "NonVisualGroupDrawingShapeProps", "NonVisualGroupShape",
    "OfficeArtExtensionList",
):
    globals()[_name] = _openpyxl_class(_name)

Alias = Bool = Integer = NoneSet = Serialisable = Set = String = Typed = _OpenpyxlSerialisable

__all__ = [name for name in list(globals()) if not name.startswith("_")]
