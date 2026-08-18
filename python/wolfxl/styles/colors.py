"""``openpyxl.styles.colors`` — re-export shim for ``Color`` + the legacy palette.

Pod 2 (RFC-060).
"""

from __future__ import annotations

import re
from typing import Any

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl._styles import COLOR_INDEX, Color
from wolfxl.styles.stylesheet import ColorList

aRGB_REGEX = re.compile("^[A-Fa-f0-9]{8}$|^[A-Fa-f0-9]{6}$")


class RGB:
    """Compatibility validator type for openpyxl's RGB descriptor."""

    expected_type = str

    def __init__(self, name: str | None = None, **kw: Any) -> None:
        self.name = name
        self.allow_none = kw.get("allow_none", False)

    def __set__(self, instance: Any, value: str | None) -> None:
        if value is None and self.allow_none:
            instance.__dict__[self.name] = None
            return
        if value is None or aRGB_REGEX.match(value) is None:
            raise ValueError("Colors must be aRGB hex values")
        if len(value) == 6:
            value = "00" + value
        instance.__dict__[self.name] = value


class ColorDescriptor:
    expected_type = Color

    def __init__(self, name: str | None = None, **kw: Any) -> None:
        self.name = name
        self.kw = kw

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.name)

    def __set__(self, instance: Any, value: Color | str) -> None:
        if isinstance(value, str):
            value = Color(rgb=value)
        if not isinstance(value, Color):
            raise TypeError("expected <class 'Color'>")
        instance.__dict__[self.name] = value


# Aliases openpyxl exposes for the most common palette positions.
BLACK = "00000000"
WHITE = "00FFFFFF"
RED = "00FF0000"
DARKRED = "00800000"
BLUE = "000000FF"
DARKBLUE = "00000080"
GREEN = "0000FF00"
DARKGREEN = "00008000"
YELLOW = "00FFFF00"
DARKYELLOW = "00808000"


__all__ = [
    "BLACK",
    "BLUE",
    "COLOR_INDEX",
    "Color",
    "ColorDescriptor",
    "ColorList",
    "DARKBLUE",
    "DARKGREEN",
    "DARKRED",
    "DARKYELLOW",
    "GREEN",
    "RED",
    "RGB",
    "WHITE",
    "YELLOW",
    "aRGB_REGEX",
]

__getattr__ = _openpyxl_name_fallback(globals())
