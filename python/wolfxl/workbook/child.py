"""``openpyxl.workbook.child`` — internal ``_WorkbookChild`` mixin."""

from __future__ import annotations

import re
import warnings
from typing import Any

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.worksheet.header_footer import HeaderFooter

INVALID_TITLE_REGEX = re.compile(r"[\\*?:/\[\]]")


def avoid_duplicate_name(names: list[str], value: str) -> str:
    """Return an openpyxl-style duplicate-safe sheet title."""
    match = [name for name in names if name.lower() == value.lower()]
    if not match:
        return value
    names_text = ",".join(names)
    sheet_title_regex = re.compile(f"(?P<title>{re.escape(value)})(?P<count>\\d*),?", re.I)
    matches = sheet_title_regex.findall(names_text)
    counts = [int(idx) for (_title, idx) in matches if idx.isdigit()]
    highest = max(counts) if counts else 0
    return f"{value}{highest + 1}"


class _WorkbookChild:
    """Small openpyxl-compatible base for sheet-like helper objects."""

    _default_title = "Sheet"
    _id = None
    _path = "{0}"

    def __init__(self, parent: Any = None, title: str | None = None) -> None:
        self._parent = parent
        self.__title = ""
        self.title = title or self._default_title
        self.HeaderFooter = HeaderFooter()

    @property
    def parent(self) -> Any:
        return self._parent

    @property
    def encoding(self) -> str:
        return getattr(self._parent, "encoding", "utf-8")

    @property
    def title(self) -> str:
        return self.__title

    @title.setter
    def title(self, value: str) -> None:
        if not self._parent:
            self.__title = value
            return
        if not value:
            raise ValueError("Title must have at least one character")
        if hasattr(value, "decode") and not isinstance(value, str):
            try:
                value = value.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ValueError("Worksheet titles must be str") from exc
        match = INVALID_TITLE_REGEX.search(value)
        if match:
            raise ValueError(f"Invalid character {match.group(0)} found in sheet title")
        if self.title is not None and self.title != value:
            value = avoid_duplicate_name(self.parent.sheetnames, value)
        if len(value) > 31:
            warnings.warn(
                "Title is more than 31 characters. Some applications may not be able to read the file",
                UserWarning,
                stacklevel=2,
            )
        self.__title = value

    @property
    def path(self) -> str:
        return self._path.format(self._id)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} "{self.title}">'


__all__ = ["_WorkbookChild"]

__getattr__ = _openpyxl_name_fallback(globals())
