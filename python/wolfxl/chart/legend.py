"""`<c:legend>` — chart legend.

Mirrors :class:`openpyxl.chart.legend.Legend`.
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
from .text import RichText


_VALID_LEGEND_POS = ("b", "tr", "l", "r", "t")


class LegendEntry:
    """`<c:legendEntry>` — per-series legend override (delete or restyle)."""

    __slots__ = ("idx", "delete", "txPr", "extLst")

    def __init__(
        self,
        idx: int = 0,
        delete: bool = False,
        txPr: RichText | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        if idx is not None:
            idx = _coerce_int(idx)
        if txPr is not None and not isinstance(txPr, RichText):
            raise TypeError(f"{type(self)}.txPr should be {RichText} but value is {type(txPr)}")
        self.idx = idx
        self.delete = delete
        self.txPr = txPr
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"idx": self.idx, "delete": self.delete}
        if self.txPr is not None:
            d["txPr"] = self.txPr.to_dict()
        return d


class Legend:
    """`<c:legend>` — placement + entry overrides + layout/text properties."""

    __slots__ = ("legendPos", "legendEntry", "layout", "overlay", "spPr", "txPr", "extLst")

    def __init__(
        self,
        legendPos: str = "r",
        legendEntry: list[LegendEntry] | tuple[LegendEntry, ...] = (),
        layout: Layout | None = None,
        overlay: bool | None = None,
        spPr: GraphicalProperties | None = None,
        txPr: RichText | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        if legendPos not in _VALID_LEGEND_POS:
            raise ValueError(f"legendPos={legendPos!r} not in {_VALID_LEGEND_POS}")
        for entry in legendEntry:
            if not isinstance(entry, LegendEntry):
                raise TypeError(f"expected {LegendEntry}")
        self.legendPos = legendPos
        self.legendEntry = list(legendEntry)
        self.layout = layout
        self.overlay = overlay
        self.spPr = spPr
        self.txPr = txPr
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    @property
    def position(self) -> str:
        return self.legendPos

    @position.setter
    def position(self, value: str) -> None:
        if value not in _VALID_LEGEND_POS:
            raise ValueError(f"position={value!r} not in {_VALID_LEGEND_POS}")
        self.legendPos = value

    def to_dict(self) -> dict[str, Any]:
        """Emit the §10.4 shape: ``{position, overlay, layout}`` (snake_case)."""
        d: dict[str, Any] = {
            "position": self.legendPos,
            "overlay": self.overlay,
            "layout": self.layout.to_dict() if self.layout is not None else None,
        }
        return d


_LEGEND_XML_MODEL_NAMES = ("Legend", "LegendEntry")


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


def _from_openpyxl_legend_model(native_cls: type, value: Any) -> Any:
    names = tuple(
        name
        for name in _xml_model_names(value.__class__)
        if name in tuple(getattr(native_cls, "__slots__", ()))
    )
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_legend_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_legend_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_legend_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_legend_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _LEGEND_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_legend_model(native_cls, value)


def _legend_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _legend_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_legend_model(cls, upstream_cls.from_tree(node))


def _legend_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_legend_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _legend_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_legend_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _legend_eq  # type: ignore[attr-defined]


_install_legend_xml_methods(Legend, LegendEntry)

_install_openpyxl_iter(Legend, LegendEntry)


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("expected <class 'int'>") from exc


__all__ = ["Legend", "LegendEntry"]

__getattr__ = _openpyxl_name_fallback(globals())
