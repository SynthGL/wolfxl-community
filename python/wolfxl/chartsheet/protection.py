"""``openpyxl.chartsheet.protection`` compatibility."""

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.chartsheet.chartsheet import ChartsheetProtection

__all__ = ["ChartsheetProtection"]

__getattr__ = _openpyxl_name_fallback(globals())
