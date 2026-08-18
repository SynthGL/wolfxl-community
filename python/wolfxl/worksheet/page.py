"""``openpyxl.worksheet.page`` — page-margin / print-options / page-setup.

Re-exports real implementations from :mod:`wolfxl.worksheet.page_setup`
(landed by Sprint-Ο Pod-1A.5 / RFC-055).
"""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.worksheet.page_setup import (
    PageMargins,
    PageSetup,
    PrintOptions,
    PrintPageSetup,
)

__all__ = ["PageMargins", "PageSetup", "PrintOptions", "PrintPageSetup"]

__getattr__ = _openpyxl_name_fallback(globals())
