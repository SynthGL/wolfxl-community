"""`<c:trendline>` — series trendlines.

Mirrors :class:`openpyxl.chart.trendline.Trendline`.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import (
    _install_openpyxl_iter,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)

from .layout import Layout
from .shapes import GraphicalProperties
from .text import RichText, Text


_VALID_TRENDLINE_TYPES = ("exp", "linear", "log", "movingAvg", "poly", "power")


class TrendlineLabel:
    """`<c:trendlineLbl>` — display label attached to a trendline."""

    __slots__ = ("layout", "tx", "numFmt", "spPr", "txPr", "extLst")

    def __init__(
        self,
        layout: Layout | None = None,
        tx: Text | None = None,
        numFmt: Any | None = None,
        spPr: GraphicalProperties | None = None,
        txPr: RichText | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.layout = layout
        self.tx = tx
        self.numFmt = numFmt
        self.spPr = spPr
        self.txPr = txPr
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.layout is not None:
            d["layout"] = self.layout.to_dict()
        if self.tx is not None:
            d["tx"] = self.tx.to_dict()
        if self.numFmt is not None:
            if hasattr(self.numFmt, "to_dict"):
                d["numFmt"] = self.numFmt.to_dict()
            else:
                d["numFmt"] = self.numFmt
        if self.spPr is not None:
            d["spPr"] = self.spPr.to_dict()
        if self.txPr is not None:
            d["txPr"] = self.txPr.to_dict()
        return d


class Trendline:
    """`<c:trendline>` — trendline kind, parameters, and display options."""

    __slots__ = (
        "name",
        "spPr",
        "trendlineType",
        "order",
        "period",
        "forward",
        "backward",
        "intercept",
        "dispRSqr",
        "dispEq",
        "trendlineLbl",
        "extLst",
    )

    def __init__(
        self,
        name: str | None = None,
        spPr: GraphicalProperties | None = None,
        trendlineType: str = "linear",
        order: int | None = None,
        period: int | None = None,
        forward: float | None = None,
        backward: float | None = None,
        intercept: float | None = None,
        dispRSqr: bool | None = None,
        dispEq: bool | None = None,
        trendlineLbl: TrendlineLabel | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        if trendlineType not in _VALID_TRENDLINE_TYPES:
            raise ValueError(
                f"trendlineType={trendlineType!r} not in {_VALID_TRENDLINE_TYPES}"
            )
        self.name = name
        self.spPr = spPr
        self.trendlineType = trendlineType
        self.order = order
        self.period = period
        self.forward = forward
        self.backward = backward
        self.intercept = intercept
        self.dispRSqr = dispRSqr
        self.dispEq = dispEq
        self.trendlineLbl = trendlineLbl
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"trendlineType": self.trendlineType}
        if self.name is not None:
            d["name"] = self.name
        if self.spPr is not None:
            d["spPr"] = self.spPr.to_dict()
        if self.order is not None:
            d["order"] = self.order
        if self.period is not None:
            d["period"] = self.period
        if self.forward is not None:
            d["forward"] = self.forward
        if self.backward is not None:
            d["backward"] = self.backward
        if self.intercept is not None:
            d["intercept"] = self.intercept
        if self.dispRSqr is not None:
            d["dispRSqr"] = self.dispRSqr
        if self.dispEq is not None:
            d["dispEq"] = self.dispEq
        if self.trendlineLbl is not None:
            d["trendlineLbl"] = self.trendlineLbl.to_dict()
        return d


_TRENDLINE_XML_MODEL_NAMES = ("TrendlineLabel", "Trendline")


def _xml_model_names(cls: type) -> tuple[str, ...]:
    return tuple(getattr(cls, "__attrs__", ())) + tuple(getattr(cls, "__elements__", ()))


def _to_openpyxl_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_openpyxl_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_openpyxl_model(item) for item in value)

    cls = value.__class__
    upstream_cls = _resolve_openpyxl_class(cls.__module__, cls.__name__)
    if upstream_cls is None or cls is upstream_cls:
        return value

    names = _xml_model_names(upstream_cls)
    if not names:
        return value

    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_openpyxl_model(getattr(value, name))
    return upstream_cls(**kwargs)


def _from_openpyxl_trendline_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_trendline_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_trendline_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_trendline_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_trendline_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _TRENDLINE_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_trendline_model(native_cls, value)


def _trendline_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _trendline_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_trendline_model(cls, upstream_cls.from_tree(node))


def _trendline_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_trendline_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _trendline_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_trendline_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _trendline_eq  # type: ignore[attr-defined]


_install_trendline_xml_methods(Trendline, TrendlineLabel)

_install_openpyxl_iter(Trendline, TrendlineLabel)

__all__ = ["Trendline", "TrendlineLabel"]

__getattr__ = _openpyxl_name_fallback(globals())
