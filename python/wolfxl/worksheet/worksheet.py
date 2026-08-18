"""``openpyxl.worksheet.worksheet`` — re-export shim for :class:`Worksheet`.

Pod 2 (RFC-060).
"""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl._worksheet_structural import gutter as _gutter
from wolfxl._worksheet import Worksheet

__all__ = ["Worksheet", "_gutter"]

__getattr__ = _openpyxl_name_fallback(globals())
