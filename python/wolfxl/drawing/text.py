"""Drawing text compatibility containers."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable, _resolve_openpyxl_class
from wolfxl.drawing.colors import ColorChoiceDescriptor, OfficeArtExtensionList
from wolfxl.drawing.fill import Blip, BlipFillProperties, GradientFillProperties, PatternFillProperties
from wolfxl.drawing.geometry import GeomGuide, GeomGuideList, PresetTextShape, Scene3D
from wolfxl.drawing.line import LineProperties
from wolfxl.xml.constants import DRAWING_NS

def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


for _name in (
    "AutonumberBullet", "CharacterProperties", "EmbeddedWAVAudioFile", "Font",
    "LineBreak", "ListStyle", "Paragraph", "ParagraphProperties",
    "RegularTextRun", "RichTextProperties", "Spacing", "TabStop",
    "TabStopList", "TextField", "TextNormalAutofit",
):
    globals()[_name] = _openpyxl_class(_name)

Run = RegularTextRun

Alias = Bool = Color = Coordinate = EffectContainer = EffectList = EmptyTag = HexBinary = Integer = MinMax = NestedBool = NestedInteger = NestedText = NestedValue = NoneSet = Relation = Sequence = Serialisable = Set = String = Typed = _OpenpyxlSerialisable
Hyperlink = _openpyxl_class("Hyperlink")

__all__ = [name for name in list(globals()) if not name.startswith("_")]
