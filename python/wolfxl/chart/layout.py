"""`<c:layout>` and `<c:manualLayout>` — chart-element placement.

Mirrors :class:`openpyxl.chart.layout.Layout`. All fields are optional;
the Rust emitter omits the element entirely when every slot is None.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import (
    _install_openpyxl_iter,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)


class ManualLayout:
    """`<c:manualLayout>` — explicit placement (xMode/yMode + x/y/w/h)."""

    __slots__ = (
        "layoutTarget",
        "xMode",
        "yMode",
        "wMode",
        "hMode",
        "x",
        "y",
        "w",
        "h",
        "extLst",
    )

    _allowed = {
        "layoutTarget": ("inner", "outer"),
        "xMode": ("edge", "factor"),
        "yMode": ("edge", "factor"),
        "wMode": ("edge", "factor"),
        "hMode": ("edge", "factor"),
    }

    def __init__(
        self,
        layoutTarget: str | None = None,
        xMode: str | None = None,
        yMode: str | None = None,
        wMode: str = "factor",
        hMode: str = "factor",
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        for key, val in (
            ("layoutTarget", layoutTarget),
            ("xMode", xMode),
            ("yMode", yMode),
            ("wMode", wMode),
            ("hMode", hMode),
        ):
            if val is not None and val not in self._allowed[key]:
                raise ValueError(f"{key}={val!r} not in {self._allowed[key]}")
        self.layoutTarget = layoutTarget
        self.xMode = xMode
        self.yMode = yMode
        self.wMode = wMode
        self.hMode = hMode
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    # openpyxl aliases
    @property
    def width(self) -> float | None:
        return self.w

    @width.setter
    def width(self, v: float | None) -> None:
        self.w = v

    @property
    def height(self) -> float | None:
        return self.h

    @height.setter
    def height(self, v: float | None) -> None:
        self.h = v

    def to_dict(self) -> dict[str, Any] | None:
        """Emit the §10.5 shape (snake_case) — flat ``{x, y, w, h, *_mode, layout_target}``.

        Returns None when every field is None so the parent's
        ``layout`` key is omitted entirely.
        """
        d: dict[str, Any] = {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "layout_target": self.layoutTarget,
            "x_mode": self.xMode,
            "y_mode": self.yMode,
            "w_mode": self.wMode,
            "h_mode": self.hMode,
        }
        if all(v is None for v in d.values()):
            return None
        return d


class Layout:
    """`<c:layout>` — wraps an optional :class:`ManualLayout`."""

    __slots__ = ("manualLayout", "extLst")

    def __init__(
        self,
        manualLayout: ManualLayout | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.manualLayout = manualLayout
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    def to_dict(self) -> dict[str, Any] | None:
        """Emit the §10.5 shape: pass through ManualLayout's flat fields.

        Returns None when there's no manual layout (so the parent omits
        the layout key entirely per §10.5).
        """
        if self.manualLayout is None:
            return None
        return self.manualLayout.to_dict()


_LAYOUT_XML_MODEL_NAMES = ("ManualLayout", "Layout")


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


def _from_openpyxl_layout_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_layout_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_layout_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_layout_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_layout_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _LAYOUT_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_layout_model(native_cls, value)


def _layout_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _layout_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_layout_model(cls, upstream_cls.from_tree(node))


def _layout_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_layout_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _layout_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_layout_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _layout_eq  # type: ignore[attr-defined]


_install_layout_xml_methods(Layout, ManualLayout)

_install_openpyxl_iter(Layout, ManualLayout)

__all__ = ["Layout", "ManualLayout"]

__getattr__ = _openpyxl_name_fallback(globals())
