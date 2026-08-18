"""``openpyxl.worksheet.formula`` — re-export for ArrayFormula / DataTableFormula.

Wolfxl's canonical home for these is :mod:`wolfxl.cell.cell` (RFC-057).
This module surfaces them at the openpyxl-shaped path.

Pod 2 (RFC-060 §2.1).
"""

from __future__ import annotations

from wolfxl._compat import _make_helper, _openpyxl_name_fallback
from wolfxl.cell.cell import ArrayFormula, DataTableFormula

safe_string = _make_helper("safe_string")

__all__ = ["ArrayFormula", "DataTableFormula", "safe_string"]

__getattr__ = _openpyxl_name_fallback(globals())
