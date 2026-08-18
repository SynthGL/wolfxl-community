"""Shim for ``openpyxl.drawing``."""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.drawing.spreadsheet_drawing import SpreadsheetDrawing as Drawing
from wolfxl.drawing.image import Image
from wolfxl.drawing.spreadsheet_drawing import (
    AbsoluteAnchor,
    AnchorMarker,
    OneCellAnchor,
    TwoCellAnchor,
    XDRPoint2D,
    XDRPositiveSize2D,
)

__all__ = [
    "AbsoluteAnchor",
    "AnchorMarker",
    "Drawing",
    "Image",
    "OneCellAnchor",
    "TwoCellAnchor",
    "XDRPoint2D",
    "XDRPositiveSize2D",
]

__getattr__ = _openpyxl_name_fallback(globals())
