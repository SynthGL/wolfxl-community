"""Excel serial ↔ Python datetime conversions, openpyxl-compatible.

Reproduces openpyxl's handling of the **1900 leap-year bug**: Excel believes
1900-02-29 exists, so the 1900 epoch is offset to ``datetime(1899, 12, 30)``
and serials in ``(0, 60)`` get a +1 day correction. Pinned by
``tests/parity/test_utils_parity.py``.
"""

from __future__ import annotations

import datetime as _dt
from math import isnan
import re

WINDOWS_EPOCH = _dt.datetime(1899, 12, 30)
MAC_EPOCH = _dt.datetime(1904, 1, 1)

# openpyxl exports CALENDAR_WINDOWS_1900 as the WINDOWS_EPOCH datetime itself
# (re-bound at module load — see openpyxl/utils/datetime.py:17).
CALENDAR_WINDOWS_1900 = WINDOWS_EPOCH
CALENDAR_MAC_1904 = MAC_EPOCH

_SECS_PER_DAY = 86400
SECS_PER_DAY = _SECS_PER_DAY

datetime = _dt

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ISO_REGEX = re.compile(
    r"""
(?P<date>(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}))?T?
(?P<time>(?P<hour>\d{2}):(?P<minute>\d{2})(:(?P<second>\d{2})(?P<microsecond>\.\d{1,3})?)?)?Z?""",
    re.VERBOSE,
)
ISO_DURATION = re.compile(
    r"PT((?P<hours>\d+)H)?((?P<minutes>\d+)M)?((?P<seconds>\d+(\.\d{1,3})?)S)?"
)


def to_ISO8601(dt: _dt.date | _dt.time | _dt.datetime | _dt.timedelta) -> str:
    """Convert a date/time object to openpyxl's ISO-8601 string shape."""
    if hasattr(dt, "microsecond") and dt.microsecond:
        return dt.isoformat(timespec="milliseconds")  # type: ignore[call-arg]
    return dt.isoformat()


def from_ISO8601(
    formatted_string: str | None,
) -> _dt.date | _dt.time | _dt.datetime | _dt.timedelta | None:
    """Convert openpyxl-supported ISO-8601 strings to Python objects."""
    if not formatted_string:
        return None

    match = ISO_REGEX.match(formatted_string)
    if match and any(match.groups()):
        parts = match.groupdict(0)
        for key in ["year", "month", "day", "hour", "minute", "second"]:
            if parts[key]:
                parts[key] = int(parts[key])

        if parts["microsecond"]:
            parts["microsecond"] = int(float(parts["microsecond"]) * 1_000_000)

        if not parts["date"]:
            return _dt.time(
                parts["hour"],
                parts["minute"],
                parts["second"],
                parts["microsecond"],
            )
        if not parts["time"]:
            return _dt.date(parts["year"], parts["month"], parts["day"])

        del parts["time"]
        del parts["date"]
        return _dt.datetime(**parts)

    match = ISO_DURATION.match(formatted_string)
    if match and any(match.groups()):
        parts = match.groupdict(0)
        for key, value in parts.items():
            if value:
                parts[key] = float(value)
        return _dt.timedelta(**parts)

    raise ValueError(f"Invalid datetime value {formatted_string}")


def to_excel(
    dt: _dt.date | _dt.time | _dt.datetime | _dt.timedelta,
    epoch: _dt.datetime = WINDOWS_EPOCH,
) -> float | int | None:
    """Convert Python date/time objects to Excel serial values."""
    if isinstance(dt, _dt.time):
        return time_to_days(dt)
    if isinstance(dt, _dt.timedelta):
        return timedelta_to_days(dt)
    if isnan(dt.year):  # type: ignore[arg-type]  # Pandas supports Not a Date.
        return None

    if not hasattr(dt, "date"):
        dt = _dt.datetime.combine(dt, _dt.time())

    days = (dt - epoch).days
    if 0 < days <= 60 and epoch == WINDOWS_EPOCH:
        days -= 1
    return days + time_to_days(dt)


def from_excel(
    value: float | int | None,
    epoch: _dt.datetime = WINDOWS_EPOCH,
    timedelta: bool = False,
) -> _dt.datetime | _dt.time | _dt.timedelta | None:
    """Excel serial → ``datetime`` (or ``time`` for fractional-only values).

    Returns ``None`` when ``value`` is ``None``. Bug-for-bug compatible with
    openpyxl 3.1.x — including the 1900 leap-year adjustment.
    """
    if value is None:
        return None

    if timedelta:
        td = _dt.timedelta(days=value)
        if td.microseconds:
            td = _dt.timedelta(
                seconds=td.total_seconds() // 1,
                microseconds=round(td.microseconds, -3),
            )
        return td

    day, fraction = divmod(value, 1)
    diff = _dt.timedelta(milliseconds=round(fraction * _SECS_PER_DAY * 1000))
    if 0 <= value < 1 and diff.days == 0:
        return _days_to_time(diff)
    if 0 < value < 60 and epoch == WINDOWS_EPOCH:
        day += 1
    return epoch + _dt.timedelta(days=day) + diff


def _days_to_time(value: _dt.timedelta) -> _dt.time:
    mins, seconds = divmod(value.seconds, 60)
    hours, mins = divmod(mins, 60)
    return _dt.time(hours, mins, seconds, value.microseconds)


def time_to_days(value: _dt.time | _dt.datetime) -> float:
    """Convert a time value to fractions of a day."""
    return (
        (value.hour * 3600)
        + (value.minute * 60)
        + value.second
        + value.microsecond / 10**6
    ) / SECS_PER_DAY


def timedelta_to_days(value: _dt.timedelta) -> float:
    """Convert a timedelta value to fractions of a day."""
    return value.total_seconds() / SECS_PER_DAY


def days_to_time(value: _dt.timedelta) -> _dt.time:
    return _days_to_time(value)


__all__ = [
    "CALENDAR_MAC_1904",
    "CALENDAR_WINDOWS_1900",
    "ISO_DURATION",
    "ISO_FORMAT",
    "ISO_REGEX",
    "MAC_EPOCH",
    "SECS_PER_DAY",
    "WINDOWS_EPOCH",
    "datetime",
    "days_to_time",
    "from_ISO8601",
    "from_excel",
    "isnan",
    "re",
    "time_to_days",
    "timedelta_to_days",
    "to_ISO8601",
    "to_excel",
]
