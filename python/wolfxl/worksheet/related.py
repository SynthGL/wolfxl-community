"""``openpyxl.worksheet.related`` import shim."""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.worksheet.table import Related

Relation = Related

__all__ = ["Related", "Relation"]

__getattr__ = _openpyxl_name_fallback(globals())
