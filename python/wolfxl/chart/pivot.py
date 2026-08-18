"""Pivot chart helper compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _resolve_openpyxl_class
from wolfxl.chart.label import DataLabel
from wolfxl.chart.marker import Marker
from wolfxl.chart.shapes import GraphicalProperties
from wolfxl.chart.text import RichText


@dataclass
class PivotSource:
    name: str | None = None
    fmtId: int = 0  # noqa: N815
    extLst: Any = None  # noqa: N815


@dataclass(init=False)
class PivotFormat:
    __attrs__ = ()
    __elements__ = ("idx", "spPr", "txPr", "marker", "dLbl")

    idx: int | None = 0
    spPr: GraphicalProperties | None = None  # noqa: N815
    txPr: RichText | None = None  # noqa: N815
    marker: Marker | None = None
    dLbl: DataLabel | None = None  # noqa: N815

    def __init__(
        self,
        idx: int | None = 0,
        spPr: GraphicalProperties | None = None,  # noqa: N803
        txPr: RichText | None = None,  # noqa: N803
        marker: Marker | None = None,
        dLbl: DataLabel | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
    ) -> None:
        self.idx = idx
        self.spPr = spPr
        self.txPr = txPr
        self.marker = marker
        self.dLbl = dLbl
        if extLst is not None:
            self.extLst = extLst  # noqa: N815

    def __iter__(self):
        return iter(())


_PIVOT_XML_MODEL_NAMES = ("PivotSource", "PivotFormat")


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


def _from_openpyxl_pivot_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_pivot_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_pivot_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_pivot_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_pivot_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _PIVOT_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_pivot_model(native_cls, value)


def _pivot_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _pivot_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_pivot_model(cls, upstream_cls.from_tree(node))


def _pivot_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_pivot_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _pivot_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_pivot_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _pivot_eq  # type: ignore[attr-defined]


_install_pivot_xml_methods(PivotSource, PivotFormat)


Alias = ExtensionList = NestedInteger = NestedText = Serialisable = Typed = _OpenpyxlSerialisable

__all__ = [
    "Alias",
    "DataLabel",
    "ExtensionList",
    "GraphicalProperties",
    "Marker",
    "NestedInteger",
    "NestedText",
    "PivotFormat",
    "PivotSource",
    "RichText",
    "Serialisable",
    "Typed",
]
