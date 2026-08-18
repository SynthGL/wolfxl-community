"""``openpyxl.chartsheet.properties`` compatibility."""

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.chartsheet.chartsheet import ChartsheetProperties
from wolfxl.styles.colors import Color

__all__ = ["ChartsheetProperties", "Color"]

__getattr__ = _openpyxl_name_fallback(globals())
