"""`SurfaceChart` and `SurfaceChart3D`.

Both surface variants emit ``<c:surfaceChart>`` (2D) or
``<c:surface3DChart>`` (3D). The 2D form is a contour-style heatmap
projection; the 3D form is a perspective-rendered surface. Both
expose a ``wireframe: bool`` toggle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import (
    _install_openpyxl_iter,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)

from ._chart import ChartBase, _install_chart_type_xml_methods
from .axis import NumericAxis, SeriesAxis, TextAxis
from .label import DataLabelList
from .shapes import GraphicalProperties


@dataclass
class BandFormat:
    idx: int = 0
    spPr: GraphicalProperties | None = None  # noqa: N815


@dataclass
class BandFormatList:
    bandFmt: list[BandFormat] | tuple[BandFormat, ...] = ()  # noqa: N815


class _SurfaceChartBase(ChartBase):
    """Shared state between flat and 3D surface charts."""

    _series_type = "surface"

    def __init__(
        self,
        wireframe: bool | None = None,
        ser: list[Any] | tuple[Any, ...] = (),
        bandFmts: BandFormatList | None = None,
        dLbls: DataLabelList | None = None,
        **kw: Any,
    ) -> None:
        self.wireframe = wireframe
        self.bandFmts = bandFmts
        self.dLbls = dLbls
        super().__init__(**kw)
        self.ser = list(ser)
        self.x_axis = TextAxis()
        self.y_axis = NumericAxis()
        self.z_axis = SeriesAxis()


class SurfaceChart(_SurfaceChartBase):
    """A 2-D surface (contour) chart."""

    tagname = "surfaceChart"

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        d: dict[str, Any] = {"wireframe": True if self.wireframe is None else self.wireframe}
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


class SurfaceChart3D(_SurfaceChartBase):
    """A 3-D surface chart.

    Defaults: rot_x=15, rot_y=20, perspective=30, depth_percent=100.
    """

    tagname = "surface3DChart"

    def __init__(
        self,
        wireframe: bool | None = None,
        view_3d: dict[str, Any] | None = None,
        **kw: Any,
    ) -> None:
        super().__init__(wireframe=wireframe, **kw)
        self.view_3d = {
            "rot_x": 15,
            "rot_y": 20,
            "perspective": 30,
            "right_angle_axes": False,
            "depth_percent": 100,
        }
        if view_3d is not None:
            self.view_3d.update(view_3d)

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        d: dict[str, Any] = {"wireframe": True if self.wireframe is None else self.wireframe}
        v3d = {k: v for k, v in self.view_3d.items() if v is not None}
        if v3d:
            d["view_3d"] = v3d
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


_SURFACE_XML_MODEL_NAMES = ("BandFormat", "BandFormatList")


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
            if attr is None:
                continue
            kwargs[name] = _to_openpyxl_model(attr)
    return upstream_cls(**kwargs)


def _from_openpyxl_surface_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_surface_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_surface_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_surface_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_surface_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if (
        not isinstance(native_cls, type)
        or native_cls.__name__ not in _SURFACE_XML_MODEL_NAMES
    ):
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_surface_model(native_cls, value)


def _surface_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _surface_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_surface_model(cls, upstream_cls.from_tree(node))


def _surface_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_surface_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _surface_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_surface_from_tree)  # type: ignore[attr-defined]
        cls.__eq__ = _surface_eq  # type: ignore[attr-defined]


_install_chart_type_xml_methods(SurfaceChart, SurfaceChart3D)
_install_openpyxl_iter(BandFormat, BandFormatList)
_install_surface_xml_methods(BandFormat, BandFormatList)


__all__ = ["BandFormat", "BandFormatList", "SurfaceChart", "SurfaceChart3D"]

__getattr__ = _openpyxl_name_fallback(globals())
