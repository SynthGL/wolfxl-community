"""``openpyxl.worksheet._write_only`` import shim."""

from __future__ import annotations

from types import GeneratorType

from wolfxl._cell import Cell
from wolfxl._worksheet import Worksheet
from wolfxl._worksheet_write_only import WriteOnlyCell, WriteOnlyWorksheet
from wolfxl.worksheet._writer import WorksheetWriter
from wolfxl.utils.exceptions import WorkbookAlreadySaved


def isgenerator(value: object) -> bool:
    return isinstance(value, GeneratorType)


__all__ = [
    "Cell",
    "WorkbookAlreadySaved",
    "Worksheet",
    "WorksheetWriter",
    "WriteOnlyCell",
    "WriteOnlyWorksheet",
    "isgenerator",
]
