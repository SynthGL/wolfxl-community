"""``openpyxl.styles.fonts`` — re-export shim for ``Font``.

Pod 2 (RFC-060).
"""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl._styles import Color, Font
from wolfxl.styles.colors import BLACK

DEFAULT_FONT = Font(name="Calibri", size=11, family=2, color=Color(theme=1), scheme="minor")

__all__ = ["BLACK", "DEFAULT_FONT", "Font"]

__getattr__ = _openpyxl_name_fallback(globals())
