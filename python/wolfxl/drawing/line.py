"""Re-export of :class:`wolfxl.chart.shapes.LineProperties`.

openpyxl exposes ``LineProperties`` at ``openpyxl.drawing.line.LineProperties``;
mirroring that import path is required for source compatibility with
existing openpyxl-based code.

Sprint Μ Pod-β (RFC-046) — added during integrator finalize.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable, _openpyxl_name_fallback, _resolve_openpyxl_class
from wolfxl.chart.shapes import LineProperties as _ChartLineProperties

_OpenpyxlLineProperties = _resolve_openpyxl_class(__name__, "LineProperties")


if _OpenpyxlLineProperties is None:
    LineProperties = _ChartLineProperties
else:

    class LineProperties(_OpenpyxlLineProperties):  # type: ignore[misc, valid-type]
        """Openpyxl XML line model with WolfXL chart-emitter dict support."""

        __attrs__ = _OpenpyxlLineProperties.__attrs__
        __elements__ = _OpenpyxlLineProperties.__elements__
        __namespaced__ = _OpenpyxlLineProperties.__namespaced__
        __nested__ = _OpenpyxlLineProperties.__nested__
        __nested_namespaced__ = getattr(_OpenpyxlLineProperties, "__nested_namespaced__", None)

        def to_dict(self) -> dict[str, Any]:
            d: dict[str, Any] = {}
            for name in ("w", "cap", "cmpd", "solidFill", "prstDash", "noFill"):
                value = getattr(self, name, None)
                if value is not None and value is not False:
                    d[name] = value
            return d

def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


for _name in ("DashStop", "DashStopList", "LineEndProperties"):
    globals()[_name] = _openpyxl_class(_name)

Alias = Bool = EmptyTag = Float = Integer = MinMax = NoneSet = Percentage = Serialisable = Set = Typed = _OpenpyxlSerialisable

__all__ = ["DashStop", "DashStopList", "LineEndProperties", "LineProperties"]

__getattr__ = _openpyxl_name_fallback(globals())
