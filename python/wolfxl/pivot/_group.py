"""``FieldGroup`` — date / range / discrete grouping for pivot cache fields.

Cache-scoped — when a pivot cache field is grouped (by date or by
numeric range), the source field gets a ``FieldGroup`` and the
cache materializes the synthesized group items into the cache's
shared items.

Recursive grouping: a grouped field can be grouped again
(``parent_index`` points at the parent FieldGroup's cache-field
index). Recursion depth is capped at 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


_VALID_GROUP_BY = (
    "years",
    "quarters",
    "months",
    "days",
    "hours",
    "minutes",
    "seconds",
)


@dataclass
class FieldGroupDate:
    """Date-grouping spec — emitted as the ``date`` sub-dict."""

    group_by: str
    start_date: str  # ISO 8601 'YYYY-MM-DDTHH:MM:SS'
    end_date: str

    def __post_init__(self) -> None:
        if self.group_by not in _VALID_GROUP_BY:
            raise ValueError(
                f"FieldGroupDate.group_by must be one of "
                f"{_VALID_GROUP_BY}, got {self.group_by!r}"
            )

    def to_rust_dict(self) -> dict:
        return {
            "group_by": self.group_by,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }


@dataclass
class FieldGroupRange:
    """Numeric-range grouping spec — emitted as the ``range`` sub-dict."""

    start: float
    end: float
    interval: float

    def __post_init__(self) -> None:
        if self.interval <= 0:
            raise ValueError(
                f"FieldGroupRange.interval must be > 0, "
                f"got {self.interval}"
            )
        if self.end < self.start:
            raise ValueError(
                f"FieldGroupRange.end ({self.end}) must be ≥ start "
                f"({self.start})"
            )

    def to_rust_dict(self) -> dict:
        return {
            "start": float(self.start),
            "end": float(self.end),
            "interval": float(self.interval),
        }


@dataclass
class FieldGroup:
    """Cache-scoped field-group — top-level dict for the Rust emitter.

    ``kind`` is one of ``"date"``, ``"range"``, ``"discrete"``.
    Mutually exclusive with the per-kind sub-blocks: a date group
    has ``date`` set and ``range=None``; a range group has ``range``
    set and ``date=None``; a discrete group has both ``None``.
    """

    field_index: int
    kind: str  # "date" | "range" | "discrete"
    parent_index: Optional[int] = None
    date: Optional[FieldGroupDate] = None
    range: Optional[FieldGroupRange] = None
    items: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in ("date", "range", "discrete"):
            raise ValueError(
                f"FieldGroup.kind must be one of "
                f"('date', 'range', 'discrete'), got {self.kind!r}"
            )
        if self.kind == "date" and self.date is None:
            raise ValueError("FieldGroup(kind='date') requires `date=`")
        if self.kind == "range" and self.range is None:
            raise ValueError("FieldGroup(kind='range') requires `range=`")
        if self.kind == "date" and self.range is not None:
            raise ValueError(
                "FieldGroup(kind='date') cannot also set `range=`"
            )
        if self.kind == "range" and self.date is not None:
            raise ValueError(
                "FieldGroup(kind='range') cannot also set `date=`"
            )

    def to_rust_dict(self) -> dict:
        return {
            "field_index": self.field_index,
            "parent_index": self.parent_index,
            "kind": self.kind,
            "date": self.date.to_rust_dict() if self.date else None,
            "range": self.range.to_rust_dict() if self.range else None,
            "items": [{"name": n} for n in self.items],
        }


# ---------------------------------------------------------------------------
# Synthesis helpers — used by PivotCache.group_field()
# ---------------------------------------------------------------------------


def synthesize_date_group_items(
    group_by: str,
    start: datetime | date,
    end: datetime | date,
) -> tuple[list[str], str, str]:
    """Build the synthesized group-item names for a date group.

    Returns ``(items, start_iso, end_iso)``. The shape Excel expects:
    leading ``"<MM/DD/YYYY"`` sentinel, then per-bucket labels, then
    trailing ``">MM/DD/YYYY"`` sentinel.
    """
    if isinstance(start, datetime):
        start_dt = start
    else:
        start_dt = datetime.combine(start, datetime.min.time())
    if isinstance(end, datetime):
        end_dt = end
    else:
        end_dt = datetime.combine(end, datetime.min.time())

    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    items: list[str] = [f"<{_fmt_us_date(start_dt)}"]

    if group_by == "years":
        for y in range(start_dt.year, end_dt.year + 1):
            items.append(str(y))
    elif group_by == "quarters":
        items.extend(["Qtr1", "Qtr2", "Qtr3", "Qtr4"])
    elif group_by == "months":
        items.extend(
            [
                "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
            ]
        )
    elif group_by == "days":
        # 1..31 — Excel emits per-day labels in this list shape.
        items.extend([f"{i}-day" for i in range(1, 32)])
    elif group_by == "hours":
        items.extend([f"{h}-hour" for h in range(0, 24)])
    elif group_by == "minutes":
        items.extend([f"{m}-min" for m in range(0, 60)])
    elif group_by == "seconds":
        items.extend([f"{s}-sec" for s in range(0, 60)])
    else:
        raise ValueError(f"unknown group_by={group_by!r}")

    items.append(f">{_fmt_us_date(end_dt)}")
    return items, start_iso, end_iso


def _fmt_us_date(d: datetime) -> str:
    return f"{d.month:02d}/{d.day:02d}/{d.year}"


def synthesize_range_group_items(
    start: float,
    end: float,
    interval: float,
) -> list[str]:
    """Build numeric-range group items in the shape Excel emits.

    Format: leading ``"<start"`` sentinel, then
    ``"start-(start+interval-1)"`` buckets, then trailing
    ``">end"`` sentinel.
    """
    if interval <= 0:
        raise ValueError("interval must be > 0")
    items: list[str] = [f"<{_fmt_num(start)}"]
    cur = start
    while cur < end:
        nxt = cur + interval
        upper = nxt - 1 if interval >= 1 else nxt
        if upper > end:
            upper = end
        items.append(f"{_fmt_num(cur)}-{_fmt_num(upper)}")
        cur = nxt
    items.append(f">{_fmt_num(end)}")
    return items


def _fmt_num(n: float) -> str:
    if float(n).is_integer():
        return str(int(n))
    return f"{n:g}"
