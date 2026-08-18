"""Openpyxl-shaped styleable import path."""

from __future__ import annotations

from copy import copy
from typing import Any

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.styles import NamedStyle
from wolfxl.styles.cell_style import StyleArray
from wolfxl.styles.numbers import (
    BUILTIN_FORMATS,
    BUILTIN_FORMATS_MAX_SIZE,
    BUILTIN_FORMATS_REVERSE,
)

_BUILTIN_STYLE_NAMES = {
    "Normal",
    "Comma",
    "Comma [0]",
    "Currency",
    "Currency [0]",
    "Percent",
    "Hyperlink",
    "Followed Hyperlink",
}


class StyleDescriptor:
    def __init__(self, collection: str, key: str) -> None:
        self.collection = collection
        self.key = key

    def __set__(self, instance: Any, value: Any) -> None:
        collection = getattr(instance.parent.parent, self.collection)
        if instance._style is None:
            instance._style = StyleArray()
        setattr(instance._style, self.key, collection.add(value))

    def __get__(self, instance: Any, cls: type | None = None) -> Any:
        if instance is None:
            return self
        collection = getattr(instance.parent.parent, self.collection)
        if instance._style is None:
            instance._style = StyleArray()
        return collection[getattr(instance._style, self.key)]


class NumberFormatDescriptor:
    key = "numFmtId"
    collection = "_number_formats"

    def __set__(self, instance: Any, value: str) -> None:
        collection = getattr(instance.parent.parent, self.collection)
        if value in BUILTIN_FORMATS_REVERSE:
            idx = BUILTIN_FORMATS_REVERSE[value]
        else:
            idx = collection.add(value) + BUILTIN_FORMATS_MAX_SIZE
        if instance._style is None:
            instance._style = StyleArray()
        setattr(instance._style, self.key, idx)

    def __get__(self, instance: Any, cls: type | None = None) -> str:
        if instance is None:
            return self  # type: ignore[return-value]
        if instance._style is None:
            instance._style = StyleArray()
        idx = getattr(instance._style, self.key)
        if idx < BUILTIN_FORMATS_MAX_SIZE:
            return BUILTIN_FORMATS.get(idx, "General")
        collection = getattr(instance.parent.parent, self.collection)
        return collection[idx - BUILTIN_FORMATS_MAX_SIZE]


class NamedStyleDescriptor:
    key = "xfId"
    collection = "_named_styles"

    def __set__(self, instance: Any, value: str | NamedStyle) -> None:
        if instance._style is None:
            instance._style = StyleArray()
        workbook = instance.parent.parent
        collection = getattr(workbook, self.collection)
        if isinstance(value, NamedStyle):
            style = value
            if style.name not in collection.names:
                workbook.add_named_style(style)
        elif value not in collection.names:
            if value not in _BUILTIN_STYLE_NAMES:
                raise ValueError(f"{value} is not a known style")
            style = NamedStyle(name=value)
            workbook.add_named_style(style)
        else:
            style = collection[value]
        instance._style = copy(style.as_tuple())

    def __get__(self, instance: Any, cls: type | None = None) -> str:
        if instance is None:
            return self  # type: ignore[return-value]
        if instance._style is None:
            instance._style = StyleArray()
        collection = getattr(instance.parent.parent, self.collection)
        return collection.names[getattr(instance._style, self.key)]


class StyleArrayDescriptor:
    def __init__(self, key: str) -> None:
        self.key = key

    def __set__(self, instance: Any, value: bool) -> None:
        if instance._style is None:
            instance._style = StyleArray()
        setattr(instance._style, self.key, value)

    def __get__(self, instance: Any, cls: type | None = None) -> bool:
        if instance is None:
            return self  # type: ignore[return-value]
        if instance._style is None:
            return False
        return bool(getattr(instance._style, self.key))


class StyleableObject:
    font = StyleDescriptor("_fonts", "fontId")
    fill = StyleDescriptor("_fills", "fillId")
    border = StyleDescriptor("_borders", "borderId")
    number_format = NumberFormatDescriptor()
    protection = StyleDescriptor("_protections", "protectionId")
    alignment = StyleDescriptor("_alignments", "alignmentId")
    style = NamedStyleDescriptor()
    quotePrefix = StyleArrayDescriptor("quotePrefix")
    pivotButton = StyleArrayDescriptor("pivotButton")

    __slots__ = ("parent", "_style")

    def __init__(self, sheet: Any, style_array: Any = None) -> None:
        self.parent = sheet
        self._style = StyleArray(style_array) if style_array is not None else None

    @property
    def style_id(self) -> int:
        if self._style is None:
            self._style = StyleArray()
        return self.parent.parent._cell_styles.add(self._style)

    @property
    def has_style(self) -> bool:
        if self._style is None:
            return False
        return any(self._style)

__all__ = [
    "BUILTIN_FORMATS",
    "BUILTIN_FORMATS_MAX_SIZE",
    "BUILTIN_FORMATS_REVERSE",
    "NamedStyleDescriptor",
    "NumberFormatDescriptor",
    "StyleArray",
    "StyleArrayDescriptor",
    "StyleDescriptor",
    "StyleableObject",
]

__getattr__ = _openpyxl_name_fallback(globals())
