"""Reader namespace compatible with ``openpyxl.reader``."""

from __future__ import annotations

from importlib import import_module

from wolfxl import load_workbook

drawings = import_module("wolfxl.reader.drawings")
excel = import_module("wolfxl.reader.excel")
strings = import_module("wolfxl.reader.strings")
workbook = import_module("wolfxl.reader.workbook")

__all__ = ["drawings", "excel", "load_workbook", "strings", "workbook"]
