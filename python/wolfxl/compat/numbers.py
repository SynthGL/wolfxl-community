"""openpyxl.compat.numbers compatibility helpers."""

from __future__ import annotations

from decimal import Decimal

NUMPY = False
NUMERIC_TYPES = (int, float, Decimal)

try:  # pragma: no cover - numpy is optional in WolfXL's test env
    import numpy  # type: ignore[import-untyped]
except ImportError:
    pass
else:  # pragma: no cover - exercised only when numpy is installed
    NUMPY = True
    NUMERIC_TYPES = NUMERIC_TYPES + (
        numpy.short,
        numpy.ushort,
        numpy.intc,
        numpy.uintc,
        numpy.int_,
        numpy.uint,
        numpy.longlong,
        numpy.ulonglong,
        numpy.half,
        numpy.float16,
        numpy.single,
        numpy.double,
        numpy.longdouble,
        numpy.int8,
        numpy.int16,
        numpy.int32,
        numpy.int64,
        numpy.uint8,
        numpy.uint16,
        numpy.uint32,
        numpy.uint64,
        numpy.intp,
        numpy.uintp,
        numpy.float32,
        numpy.float64,
        numpy.bool_,
        numpy.floating,
        numpy.integer,
    )

__all__ = ["Decimal", "NUMERIC_TYPES", "NUMPY"]

