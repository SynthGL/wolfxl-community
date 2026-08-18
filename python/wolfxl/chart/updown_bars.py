"""Up/down bar chart helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl.chart.shapes import GraphicalProperties
from wolfxl._compat import (
    _OpenpyxlSerialisable,
    _install_openpyxl_iter,
    _resolve_openpyxl_class,
)


@dataclass
class ChartLines:
    spPr: GraphicalProperties | None = None  # noqa: N815


@dataclass
class UpDownBars:
    gapWidth: int | None = None  # noqa: N815
    upBars: ChartLines | None = None  # noqa: N815
    downBars: ChartLines | None = None  # noqa: N815
    extLst: Any = None  # noqa: N815


_UPDOWN_XML_MODEL_NAMES = ("ChartLines", "UpDownBars")


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


def _from_openpyxl_updown_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_updown_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_updown_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_updown_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_updown_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _UPDOWN_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_updown_model(native_cls, value)


def _updown_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _updown_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_updown_model(cls, upstream_cls.from_tree(node))


def _updown_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_updown_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _updown_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_updown_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _updown_eq  # type: ignore[attr-defined]


_install_openpyxl_iter(ChartLines, UpDownBars)
_install_updown_xml_methods(ChartLines, UpDownBars)


ExtensionList = NestedGapAmount = Serialisable = Typed = _OpenpyxlSerialisable

__all__ = [
    "ChartLines",
    "ExtensionList",
    "GraphicalProperties",
    "NestedGapAmount",
    "Serialisable",
    "Typed",
    "UpDownBars",
]
