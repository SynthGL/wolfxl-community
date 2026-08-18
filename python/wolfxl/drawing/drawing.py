"""Drawing container compatibility."""

from __future__ import annotations

import math

from wolfxl._compat import _resolve_openpyxl_class
from wolfxl.drawing.spreadsheet_drawing import SpreadsheetDrawing as Drawing
from wolfxl.utils.units import pixels_to_EMU

Drawing = _resolve_openpyxl_class(__name__, "Drawing") or Drawing

__all__ = ["Drawing", "math", "pixels_to_EMU"]
