"""openpyxl.compat.strings compatibility helpers."""

from __future__ import annotations

from datetime import datetime
from math import isinf, isnan
import sys
from typing import Any

from wolfxl.compat.numbers import NUMERIC_TYPES

VER = sys.version_info


def safe_string(value: Any) -> str:
    """Convert values to openpyxl's XML-safe string representation."""
    if isinstance(value, NUMERIC_TYPES):
        if isnan(value) or isinf(value):
            value = ""
        else:
            value = "%.16g" % value
    if value is None:
        value = "none"
    elif isinstance(value, datetime):
        value = value.isoformat()
    elif not isinstance(value, str):
        value = str(value)
    return value


__all__ = [
    "NUMERIC_TYPES",
    "VER",
    "datetime",
    "isinf",
    "isnan",
    "safe_string",
    "sys",
]
