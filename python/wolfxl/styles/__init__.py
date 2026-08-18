"""``wolfxl.styles`` — openpyxl-shape style surface."""

from __future__ import annotations

from wolfxl._styles import Alignment, Border, Color, Font, PatternFill, Side
from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.styles._named_style import NamedStyle
from wolfxl.styles.fills import Fill, GradientFill
from wolfxl.styles.numbers import NumberFormatDescriptor, is_builtin, is_date_format
from wolfxl.styles.protection import Protection
from wolfxl._styles import Font as DEFAULT_FONT

__all__ = [
    "Alignment",
    "Border",
    "Color",
    "DEFAULT_FONT",
    "Font",
    "Fill",
    "GradientFill",
    "NamedStyle",
    "PatternFill",
    "Protection",
    "Side",
    "NumberFormatDescriptor",
    "is_builtin",
    "is_date_format",
]

__getattr__ = _openpyxl_name_fallback(globals())
