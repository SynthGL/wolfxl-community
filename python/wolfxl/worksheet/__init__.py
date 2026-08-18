"""Shim for ``openpyxl.worksheet`` - subpackage re-exports.

openpyxl organizes worksheet-adjacent classes (DataValidation, Table,
Hyperlink, PageSetup, HeaderFooter, SheetView, SheetProtection) under
this package. wolfxl exposes the same module paths so imports succeed.

Sprint Ο Pod 1A (RFC-055) added: page_setup, header_footer, views,
protection, properties, print_settings.
"""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback

# Re-export key classes for ``from wolfxl.worksheet import X`` users.
from wolfxl.worksheet.page_setup import (
    PageMargins,
    PageSetup,
    PrintOptions,
    PrintPageSetup,
)
from wolfxl.worksheet.header_footer import (
    HeaderFooter,
    HeaderFooterItem,
)
from wolfxl.worksheet.views import (
    Pane,
    Selection,
    SheetView,
    SheetViewList,
)
from wolfxl.worksheet.protection import SheetProtection
from wolfxl.worksheet.properties import (
    Outline,
    PageSetupProperties,
    WorksheetProperties,
)
from wolfxl.worksheet.print_settings import (
    ColRange,
    PrintArea,
    PrintTitles,
    RowRange,
)

__all__ = [
    "PageMargins",
    "PageSetup",
    "PrintOptions",
    "PrintPageSetup",
    "HeaderFooter",
    "HeaderFooterItem",
    "Pane",
    "Selection",
    "SheetView",
    "SheetViewList",
    "SheetProtection",
    "Outline",
    "PageSetupProperties",
    "WorksheetProperties",
    "ColRange",
    "PrintArea",
    "PrintTitles",
    "RowRange",
]

__getattr__ = _openpyxl_name_fallback(globals())
