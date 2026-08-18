"""Drawing-ML graphical properties (`<c:spPr>` / `<a:spPr>`).

Mirrors :class:`openpyxl.chart.shapes.GraphicalProperties`. The DrawingML
spec for chart spPr is restrictive — no custGeom/prstGeom, no scene3d,
no bwMode — so this implementation only carries the fields that survive
chart-context serialisation.

Properties are stored as plain attributes; the ``to_dict()`` method emits
the camelCase XML names that the Rust emitter expects.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import (
    _install_openpyxl_iter,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)

PRESET_COLORS: list[str] = []


class LineProperties:
    """Drawing-ML `<a:ln>` line properties — width, dash, fill colour.

    Kept lightweight (vs. openpyxl's full ``LineProperties`` descriptor
    soup) because the chart emitter only reads ``w``, ``cap``, ``cmpd``,
    ``solidFill``, and ``prstDash``.
    """

    __slots__ = ("w", "cap", "cmpd", "solidFill", "prstDash", "noFill", "_extra")

    def __init__(
        self,
        w: int | None = None,
        cap: str | None = None,
        cmpd: str | None = None,
        solidFill: str | None = None,
        prstDash: str | None = "solid",
        noFill: bool | None = None,
        **kw: Any,
    ) -> None:
        self.w = w
        self.cap = cap
        self.cmpd = cmpd
        self.solidFill = solidFill
        self.prstDash = prstDash
        self.noFill = noFill
        self._extra = dict(kw)

    def __getattr__(self, name: str) -> Any:
        try:
            extra = object.__getattribute__(self, "_extra")
        except AttributeError as exc:
            raise AttributeError(name) from exc
        if name in extra:
            return extra[name]
        raise AttributeError(name)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.w is not None:
            d["w"] = self.w
        if self.cap is not None:
            d["cap"] = self.cap
        if self.cmpd is not None:
            d["cmpd"] = self.cmpd
        if self.solidFill is not None:
            d["solidFill"] = self.solidFill
        if self.prstDash is not None:
            d["prstDash"] = self.prstDash
        if self.noFill:
            d["noFill"] = True
        return d


class GraphicalProperties:
    """`<c:spPr>` — chart-side shape properties.

    Mirrors openpyxl's :class:`GraphicalProperties` but carries only the
    fields the chart-XML emitter uses: ``noFill``, ``solidFill``,
    ``ln``, plus the gradient/pattern fill placeholders (Rust side
    decides whether to emit them — for v1.5 we round-trip these as
    opaque dicts).
    """

    __slots__ = (
        "noFill",
        "solidFill",
        "gradFill",
        "pattFill",
        "ln",
        "_extra",
    )

    def __init__(
        self,
        noFill: bool | None = None,
        solidFill: str | None = None,
        gradFill: dict[str, Any] | None = None,
        pattFill: dict[str, Any] | None = None,
        ln: LineProperties | None = None,
        **kw: Any,
    ) -> None:
        self.noFill = noFill
        self.solidFill = solidFill
        self.gradFill = gradFill
        self.pattFill = pattFill
        self.ln = ln if ln is not None else LineProperties()
        self._extra = dict(kw)

    def __getattr__(self, name: str) -> Any:
        try:
            extra = object.__getattribute__(self, "_extra")
        except AttributeError as exc:
            raise AttributeError(name) from exc
        if name in extra:
            return extra[name]
        raise AttributeError(name)

    # openpyxl alias
    @property
    def line(self) -> LineProperties | None:
        return self.ln

    @line.setter
    def line(self, value: LineProperties | None) -> None:
        self.ln = value

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.noFill:
            d["noFill"] = True
        if self.solidFill is not None:
            # Accept either a raw hex/scheme string OR a ColorChoice
            # (or any object with __str__); the Rust emitter expects a str.
            d["solidFill"] = (
                self.solidFill
                if isinstance(self.solidFill, str)
                else str(self.solidFill)
            )
        if self.gradFill is not None:
            d["gradFill"] = self.gradFill
        if self.pattFill is not None:
            d["pattFill"] = self.pattFill
        if self.ln is not None:
            ln_dict = self.ln.to_dict()
            # Same coercion for nested LineProperties.solidFill.
            if "solidFill" in ln_dict and not isinstance(ln_dict["solidFill"], str):
                ln_dict["solidFill"] = str(ln_dict["solidFill"])
            d["ln"] = ln_dict
        return d


_SHAPE_XML_MODEL_NAMES = ("GraphicalProperties", "LineProperties")


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
            attr = getattr(value, name)
            if attr is None and not (
                isinstance(value, GraphicalProperties) and name == "ln"
            ):
                continue
            kwargs[name] = _to_openpyxl_model(attr)
    model = upstream_cls(**kwargs)
    if isinstance(value, GraphicalProperties) and value.ln is None:
        model.ln = None
    if (
        isinstance(value, LineProperties)
        and value.noFill
        and value.prstDash is None
        and hasattr(model, "prstDash")
    ):
        model.prstDash = None
    return model


def _from_openpyxl_shape_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_shape_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_shape_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_shape_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_shape_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _SHAPE_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_shape_model(native_cls, value)


def _shape_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _shape_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_shape_model(cls, upstream_cls.from_tree(node))


def _shape_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_shape_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _shape_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_shape_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _shape_eq  # type: ignore[attr-defined]


_install_shape_xml_methods(GraphicalProperties, LineProperties)

_install_openpyxl_iter(GraphicalProperties, LineProperties)

__all__ = ["GraphicalProperties", "LineProperties", "PRESET_COLORS"]

__getattr__ = _openpyxl_name_fallback(globals())
