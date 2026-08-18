"""Drawing effect compatibility containers."""

from __future__ import annotations

from wolfxl._compat import _OpenpyxlSerialisable, _install_openpyxl_iter, _make_serialisable, _resolve_openpyxl_class
from wolfxl.drawing.fill import ColorChoice as Color
from wolfxl.drawing.fill import ColorChoice

def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


for _name in (
    "AlphaBiLevelEffect", "AlphaCeilingEffect", "AlphaFloorEffect",
    "AlphaInverseEffect", "AlphaModulateEffect", "AlphaModulateFixedEffect",
    "AlphaReplaceEffect", "BiLevelEffect", "BlurEffect", "ColorChangeEffect",
    "ColorReplaceEffect", "DuotoneEffect", "EffectContainer", "EffectList",
    "FillOverlayEffect", "GlowEffect", "GrayscaleEffect", "HSLEffect",
    "InnerShadowEffect", "LuminanceEffect", "OuterShadow",
    "PresetShadowEffect", "ReflectionEffect", "SoftEdgesEffect", "TintEffect",
):
    globals()[_name] = _openpyxl_class(_name)

_install_openpyxl_iter(Color, ColorChoice)

Bool = Float = Integer = Serialisable = Set = String = Typed = _OpenpyxlSerialisable

__all__ = [name for name in list(globals()) if not name.startswith("_")]
