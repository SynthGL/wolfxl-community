"""Read-only cell helpers compatible with ``openpyxl.cell.read_only``."""

from __future__ import annotations

from typing import Any

from wolfxl._cell import Cell
from wolfxl.styles.cell_style import StyleArray
from wolfxl.styles.numbers import BUILTIN_FORMATS, BUILTIN_FORMATS_MAX_SIZE
from wolfxl.utils import get_column_letter
from wolfxl.utils.datetime import from_excel
from wolfxl.utils.numbers import is_date_format


class ReadOnlyCell:
    """Immutable cell proxy used by openpyxl's read-only worksheet surface."""

    __slots__ = ("parent", "row", "column", "_value", "data_type", "_style_id")

    def __init__(
        self,
        sheet: Any,
        row: int,
        column: int,
        value: Any,
        data_type: str = "n",
        style_id: int = 0,
    ) -> None:
        self.parent = sheet
        self.row = row
        self.column = column
        self._value = value
        self.data_type = data_type
        self._style_id = style_id

    def __repr__(self) -> str:
        title = getattr(self.parent, "title", "")
        return f"<ReadOnlyCell {title!r}.{self.coordinate}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ReadOnlyCell):
            return False
        return all(getattr(self, attr) == getattr(other, attr) for attr in self.__slots__)

    def __ne__(self, other: object) -> bool:
        return not self == other

    @property
    def coordinate(self) -> str:
        return f"{get_column_letter(self.column)}{self.row}"

    @property
    def column_letter(self) -> str:
        return get_column_letter(self.column)

    @property
    def style_array(self) -> Any:
        workbook = _workbook(self.parent)
        styles = getattr(workbook, "_cell_styles", None)
        if styles is None:
            return StyleArray()
        try:
            return styles[self._style_id]
        except Exception:
            return StyleArray()

    @property
    def has_style(self) -> bool:
        return self._style_id != 0

    @property
    def number_format(self) -> Any:
        try:
            return _number_format_code(_workbook(self.parent), self.style_array.numFmtId)
        except Exception:
            return "General"

    @property
    def font(self) -> Any:
        return _style_part(self.parent, "_fonts", self.style_array.fontId)

    @property
    def fill(self) -> Any:
        return _style_part(self.parent, "_fills", self.style_array.fillId)

    @property
    def border(self) -> Any:
        return _style_part(self.parent, "_borders", self.style_array.borderId)

    @property
    def alignment(self) -> Any:
        return _style_part(self.parent, "_alignments", self.style_array.alignmentId)

    @property
    def protection(self) -> Any:
        return _style_part(self.parent, "_protections", self.style_array.protectionId)

    @property
    def is_date(self) -> bool:
        value = self.value
        if hasattr(value, "year") and hasattr(value, "month"):
            return True
        if self.data_type == "d":
            return True
        if self.data_type != "n":
            return False
        return is_date_format(self.number_format)

    @property
    def internal_value(self) -> Any:
        return self._value

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, value: Any) -> None:
        if self._value is not None:
            raise AttributeError("Cell is read only")
        self._value = value


class EmptyCell:
    """Singleton placeholder for missing read-only cells."""

    __slots__ = ()

    value = None
    is_date = False
    font = None
    border = None
    fill = None
    number_format = None
    alignment = None
    data_type = "n"

    def __repr__(self) -> str:
        return "<EmptyCell>"


EMPTY_CELL = EmptyCell()

__all__ = [
    "BUILTIN_FORMATS",
    "BUILTIN_FORMATS_MAX_SIZE",
    "Cell",
    "EMPTY_CELL",
    "EmptyCell",
    "ReadOnlyCell",
    "from_excel",
    "get_column_letter",
    "is_date_format",
]


def _number_format_code(workbook: Any, num_fmt_id: Any) -> str:
    try:
        fmt_id = int(num_fmt_id)
    except (TypeError, ValueError):
        return "General"
    if fmt_id in BUILTIN_FORMATS:
        return BUILTIN_FORMATS[fmt_id]
    custom_formats = getattr(workbook, "_number_formats", None)
    if isinstance(custom_formats, dict):
        value = custom_formats.get(fmt_id, custom_formats.get(str(fmt_id)))
        return value if isinstance(value, str) else "General"
    if isinstance(custom_formats, (list, tuple)) and fmt_id >= 164:
        idx = fmt_id - 164
        if 0 <= idx < len(custom_formats) and isinstance(custom_formats[idx], str):
            return custom_formats[idx]
    return "General"


def _workbook(sheet: Any) -> Any:
    return getattr(sheet, "parent", None)


def _style_part(sheet: Any, attr: str, idx: Any) -> Any:
    workbook = _workbook(sheet)
    values = getattr(workbook, attr, None)
    if values is None:
        return None
    try:
        return values[idx]
    except Exception:
        return None
