"""DrawingML fill primitives — ColorChoice, SolidColorFillProperties, etc.

Mirrors :mod:`openpyxl.drawing.fill` but lightweight: the Rust chart
emitter only consumes string colour values, so most of openpyxl's
descriptor soup is collapsed to a tiny dataclass-style holder that
``GraphicalProperties.solidFill`` accepts in place of a raw string.

Sprint Μ Pod-β (RFC-046) — added during integrator finalize to satisfy
test contract surfaces that import from ``wolfxl.drawing.fill`` directly
(matching openpyxl's import path).
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import (
    _make_serialisable,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)

PRESET_COLORS: list[str] = []


class ColorChoice:
    """`<a:srgbClr>` / `<a:schemeClr>` / `<a:prstClr>` colour choice.

    A user passes ``ColorChoice(srgbClr="00FF00")`` to spec a literal
    RGB colour, or ``schemeClr="accent1"`` for a theme-resolved colour.

    The Rust emitter consumes the resolved hex string (or scheme name);
    when this object is used as ``GraphicalProperties.solidFill``, the
    chart serialiser unwraps it via ``__str__``.
    """

    __slots__ = (
        "scrgbClr",
        "srgbClr",
        "schemeClr",
        "prstClr",
        "hslClr",
        "sysClr",
    )

    def __init__(
        self,
        scrgbClr: Any | None = None,
        srgbClr: str | None = None,
        schemeClr: str | None = None,
        prstClr: str | None = None,
        hslClr: str | None = None,
        sysClr: str | None = None,
        **kw: Any,
    ) -> None:
        self.scrgbClr = scrgbClr if scrgbClr is not None else kw.get("scrgbClr")
        self.srgbClr = srgbClr
        self.schemeClr = schemeClr
        self.prstClr = prstClr
        self.hslClr = hslClr
        self.sysClr = sysClr

    def __str__(self) -> str:
        # The chart emitter consumes solidFill as a string today; pick
        # the first non-None choice. Theme resolution is the writer's
        # responsibility (see Pod-α charts.rs).
        for v in (
            self.scrgbClr,
            self.srgbClr,
            self.schemeClr,
            self.prstClr,
            self.hslClr,
            self.sysClr,
        ):
            if v:
                return v
        return ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.scrgbClr is not None:
            d["scrgbClr"] = self.scrgbClr
        if self.srgbClr is not None:
            d["srgbClr"] = self.srgbClr
        if self.schemeClr is not None:
            d["schemeClr"] = self.schemeClr
        if self.prstClr is not None:
            d["prstClr"] = self.prstClr
        if self.hslClr is not None:
            d["hslClr"] = self.hslClr
        if self.sysClr is not None:
            d["sysClr"] = self.sysClr
        return d


def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(name)


Blip = _openpyxl_class("Blip")
BlipFillProperties = _openpyxl_class("BlipFillProperties")
GradientFillProperties = _openpyxl_class("GradientFillProperties")
GradientStop = _openpyxl_class("GradientStop")
LinearShadeProperties = _openpyxl_class("LinearShadeProperties")
PathShadeProperties = _openpyxl_class("PathShadeProperties")
PatternFillProperties = _openpyxl_class("PatternFillProperties")
RelativeRect = _openpyxl_class("RelativeRect")
StretchInfoProperties = _openpyxl_class("StretchInfoProperties")

__all__ = [
    "Blip",
    "BlipFillProperties",
    "ColorChoice",
    "GradientFillProperties",
    "GradientStop",
    "LinearShadeProperties",
    "PathShadeProperties",
    "PatternFillProperties",
    "PRESET_COLORS",
    "RelativeRect",
    "StretchInfoProperties",
]

__getattr__ = _openpyxl_name_fallback(globals())
