"""DrawingML color model compatibility."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable, _resolve_openpyxl_class
from wolfxl.xml.constants import DRAWING_NS

PRESET_COLORS: tuple[str, ...] = ()
SCHEME_COLORS: tuple[str, ...] = ()

def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


for _name in (
    "ColorChoice", "ColorChoiceDescriptor", "ColorMapping", "HSLColor",
    "OfficeArtExtensionList", "RGB", "RGBPercent", "SchemeColor",
    "SystemColor", "Transform",
):
    globals()[_name] = _openpyxl_class(_name)

Alias = EmptyTag = Integer = MinMax = NestedInteger = NestedNoneSet = NestedValue = Percentage = Serialisable = Set = Typed = _OpenpyxlSerialisable

__all__ = [name for name in list(globals()) if not name.startswith("_")]
