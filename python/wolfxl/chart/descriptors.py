"""Utility descriptors shared across the chart module.

Mirrors :mod:`openpyxl.chart.descriptors` — these are the bounded numeric
helpers that openpyxl uses for gap amounts, overlap, and free-form numeric
formats. We keep the names identical so that openpyxl-shaped client code
that imports them by name keeps working.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _openpyxl_name_fallback


class _BoundedNumber:
    """Validate a numeric attribute against an inclusive [min, max] range.

    Used by chart-side descriptors that need range-checking (gap width,
    overlap, etc.). Attribute access goes through ``__set_name__`` so
    each descriptor instance manages its own per-class slot name.
    """

    _min: float | None = None
    _max: float | None = None
    _allow_none: bool = True

    def __init__(
        self,
        min: float | None = None,
        max: float | None = None,
        allow_none: bool = True,
    ) -> None:
        if min is not None:
            self._min = min
        if max is not None:
            self._max = max
        self._allow_none = allow_none

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr = "_" + name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return getattr(instance, self._attr, None)

    def __set__(self, instance: Any, value: Any) -> None:
        if value is None:
            if not self._allow_none:
                raise ValueError(f"{self._attr[1:]} cannot be None")
            setattr(instance, self._attr, None)
            return
        v = float(value)
        if self._min is not None and v < self._min:
            raise ValueError(f"{self._attr[1:]}={v} below min={self._min}")
        if self._max is not None and v > self._max:
            raise ValueError(f"{self._attr[1:]}={v} above max={self._max}")
        setattr(instance, self._attr, v)


class NestedGapAmount(_BoundedNumber):
    """Gap amount for bar / pie variants — 0..500 (percentage units)."""

    def __init__(self, allow_none: bool = True) -> None:
        super().__init__(min=0, max=500, allow_none=allow_none)


class NestedOverlap(_BoundedNumber):
    """Bar-chart overlap percentage — -100..100."""

    def __init__(self, allow_none: bool = True) -> None:
        super().__init__(min=-100, max=100, allow_none=allow_none)


__all__ = ["NestedGapAmount", "NestedOverlap"]

__getattr__ = _openpyxl_name_fallback(globals())
