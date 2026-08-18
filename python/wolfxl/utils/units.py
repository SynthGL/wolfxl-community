"""``openpyxl.utils.units``-shaped pixel/EMU/point conversion helpers.

Constants and helpers below mirror openpyxl's ``openpyxl/utils/units.py``
verbatim under its MIT license.  Drawing/image code converts between
EMU (English Metric Units, OOXML's universal unit, 914 400 per inch),
pixels (72 dpi assumption), points (1/72"), and column-width units.

Pod 2 (RFC-060) — these helpers were inlined inside the drawing/image
modules previously; this module is the openpyxl-shaped public path.
"""

from __future__ import annotations

import math

BASE_COL_WIDTH = 8
DEFAULT_COLUMN_WIDTH = 13
DEFAULT_HEADER = 0.3
DEFAULT_LEFT_MARGIN = 0.7
DEFAULT_ROW_HEIGHT = 15.0
DEFAULT_TOP_MARGIN = 0.7874

EMU_PER_PIXEL = 9525
EMU_PER_POINT = 12700
EMU_PER_CM = 360000
EMU_PER_INCH = 914400
EMU_PER_MM = 36000


def pixels_to_EMU(value: float) -> int:  # noqa: N802 — openpyxl public name
    """Pixels (96 dpi) → EMU."""
    return int(value * EMU_PER_PIXEL)


def EMU_to_pixels(value: float) -> int:  # noqa: N802
    """EMU → pixels (96 dpi, integer-rounded)."""
    return int(round(value / EMU_PER_PIXEL))


def points_to_pixels(value: float) -> int:
    """Points (1/72") → pixels (96 dpi, ceiling-rounded)."""
    return int(math.ceil(value * 96 / 72))


def pixels_to_points(value: float) -> float:
    """Pixels (96 dpi) → points (1/72")."""
    return value * 72 / 96


def cm_to_EMU(value: float) -> int:  # noqa: N802
    return int(value * EMU_PER_CM)


def inch_to_EMU(value: float) -> int:  # noqa: N802
    return int(value * EMU_PER_INCH)


def mm_to_EMU(value: float) -> int:  # noqa: N802
    return int(value * EMU_PER_MM)


def EMU_to_cm(value: float) -> float:  # noqa: N802
    return round(value / EMU_PER_CM, 4)


def EMU_to_inch(value: float) -> float:  # noqa: N802
    return round(value / EMU_PER_INCH, 4)


def inch_to_dxa(value: float) -> int:
    return int(value * 20 * 72)


def dxa_to_inch(value: float) -> float:
    return value / 72 / 20


def dxa_to_cm(value: float) -> float:
    return 2.54 * dxa_to_inch(value)


def cm_to_dxa(value: float) -> int:
    emu = cm_to_EMU(value)
    inch = EMU_to_inch(emu)
    return inch_to_dxa(inch)


def degrees_to_angle(value: float) -> int:
    return int(round(value * 60000))


def angle_to_degrees(value: float) -> float:
    return round(value / 60000, 2)


def short_color(color: str) -> str:
    return color[2:] if len(color) == 8 else color


__all__ = [
    "BASE_COL_WIDTH",
    "DEFAULT_COLUMN_WIDTH",
    "DEFAULT_HEADER",
    "DEFAULT_LEFT_MARGIN",
    "DEFAULT_ROW_HEIGHT",
    "DEFAULT_TOP_MARGIN",
    "EMU_PER_CM",
    "EMU_PER_INCH",
    "EMU_PER_MM",
    "EMU_PER_PIXEL",
    "EMU_PER_POINT",
    "EMU_to_cm",
    "EMU_to_inch",
    "EMU_to_pixels",
    "angle_to_degrees",
    "cm_to_EMU",
    "cm_to_dxa",
    "degrees_to_angle",
    "dxa_to_cm",
    "dxa_to_inch",
    "inch_to_EMU",
    "inch_to_dxa",
    "math",
    "mm_to_EMU",
    "pixels_to_EMU",
    "pixels_to_points",
    "points_to_pixels",
    "short_color",
]
