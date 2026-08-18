"""Shim for ``openpyxl.styles.named_styles`` — see ``wolfxl.styles.NamedStyle``."""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.styles import NamedStyle
from wolfxl.styles._named_style import _NamedCellStyle, _NamedCellStyleList
from wolfxl.styles.numbers import BUILTIN_FORMATS_MAX_SIZE, BUILTIN_FORMATS_REVERSE
from wolfxl.styles.stylesheet import NamedStyleList

__all__ = [
    "BUILTIN_FORMATS_MAX_SIZE",
    "BUILTIN_FORMATS_REVERSE",
    "NamedStyle",
    "NamedStyleList",
    "_NamedCellStyle",
    "_NamedCellStyleList",
]

__getattr__ = _openpyxl_name_fallback(globals())
