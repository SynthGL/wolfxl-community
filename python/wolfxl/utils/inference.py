"""Value inference helpers compatible with openpyxl."""

from __future__ import annotations

import datetime
import re
from typing import Any

from wolfxl.styles import numbers

PERCENT_REGEX = re.compile(r"^(?P<number>\-?[0-9]*\.?[0-9]*\s?)\%$")
TIME_REGEX = re.compile(
    r"""
^(?: # HH:MM and HH:MM:SS
(?P<hour>[0-1]{0,1}[0-9]{2}):
(?P<minute>[0-5][0-9]):?
(?P<second>[0-5][0-9])?$)
|
^(?: # MM:SS.
([0-5][0-9]):
([0-5][0-9])?\.
(?P<microsecond>\d{1,6}))
""",
    re.VERBOSE,
)
NUMBER_REGEX = re.compile(r"^-?([\d]|[\d]+\.[\d]*|\.[\d]+|[1-9][\d]+\.?[\d]*)((E|e)[-+]?[\d]+)?$")


def cast_numeric(value: Any) -> int | float | Any:
    if NUMBER_REGEX.match(value):
        try:
            return int(value)
        except ValueError:
            return float(value)
    return None


def cast_percentage(value: Any) -> float | Any:
    match = PERCENT_REGEX.match(value)
    if match:
        return float(match.group("number")) / 100
    return None


def cast_time(value: Any) -> datetime.time | Any:
    match = TIME_REGEX.match(value)
    if match:
        if match.group("microsecond") is not None:
            value = value[:12]
            pattern = "%M:%S.%f"
        elif match.group("second") is None:
            pattern = "%H:%M"
        else:
            pattern = "%H:%M:%S"
        value = datetime.datetime.strptime(value, pattern)
        return value.time()
    return None


__all__ = [
    "NUMBER_REGEX",
    "PERCENT_REGEX",
    "TIME_REGEX",
    "cast_numeric",
    "cast_percentage",
    "cast_time",
    "datetime",
    "numbers",
    "re",
]
