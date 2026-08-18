"""``openpyxl.workbook.workbook`` — re-export for :class:`Workbook`.

Pod 2 (RFC-060).
"""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl._styles import COLOR_INDEX, Color, Font
from wolfxl._workbook import Workbook
from wolfxl.styles.borders import DEFAULT_BORDER
from wolfxl.styles.fills import DEFAULT_EMPTY_FILL, DEFAULT_GRAY_FILL
from wolfxl.utils.datetime import MAC_EPOCH, WINDOWS_EPOCH

DEFAULT_FONT = Font(name="Calibri", size=11, family=2, color=Color(theme=1), scheme="minor")
INTEGER_TYPES = (int,)

__all__ = [
    "COLOR_INDEX",
    "DEFAULT_BORDER",
    "DEFAULT_EMPTY_FILL",
    "DEFAULT_FONT",
    "DEFAULT_GRAY_FILL",
    "INTEGER_TYPES",
    "MAC_EPOCH",
    "WINDOWS_EPOCH",
    "Workbook",
]

__getattr__ = _openpyxl_name_fallback(globals())
