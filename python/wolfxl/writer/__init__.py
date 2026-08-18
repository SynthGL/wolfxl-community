"""``openpyxl.writer`` import compatibility."""

from __future__ import annotations

from wolfxl.writer.excel import ExcelWriter, save_workbook

__all__ = ["ExcelWriter", "save_workbook"]
