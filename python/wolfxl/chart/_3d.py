"""3-D chart helper compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl.chart.picture import PictureOptions
from wolfxl.chart.shapes import GraphicalProperties
from wolfxl._compat import (
    _OpenpyxlSerialisable,
    _install_openpyxl_iter,
    _resolve_openpyxl_class,
)


@dataclass(init=False)
class View3D:
    __attrs__ = ()
    __elements__ = (
        "rotX",
        "hPercent",
        "rotY",
        "depthPercent",
        "rAngAx",
        "perspective",
    )

    rotX: int | float | None = 15.0  # noqa: N815
    hPercent: int | None = None  # noqa: N815
    rotY: int | None = 20  # noqa: N815
    depthPercent: int | None = None  # noqa: N815
    rAngAx: bool | None = True  # noqa: N815
    perspective: int | None = None

    def __init__(
        self,
        rotX: int | float | None = 15,  # noqa: N803
        hPercent: int | None = None,  # noqa: N803
        rotY: int | None = 20,  # noqa: N803
        depthPercent: int | None = None,  # noqa: N803
        rAngAx: bool | None = True,  # noqa: N803
        perspective: int | None = None,
        extLst: Any = None,  # noqa: N803
    ) -> None:
        self.rotX = float(rotX) if rotX is not None else None
        self.hPercent = hPercent
        self.rotY = rotY
        self.depthPercent = depthPercent
        self.rAngAx = rAngAx
        self.perspective = perspective
        if extLst is not None:
            self.extLst = extLst  # noqa: N815

    def __iter__(self):
        return iter(())


@dataclass
class Surface:
    thickness: int | None = None
    spPr: GraphicalProperties | None = None  # noqa: N815
    pictureOptions: PictureOptions | None = None  # noqa: N815
    extLst: Any = None  # noqa: N815


class _3DBase:
    """Base object for openpyxl-compatible 3-D chart surfaces."""

    tagname = "ChartBase"
    __attrs__ = ()
    __elements__ = ("backWall", "floor", "sideWall", "view3D")

    def __init__(
        self,
        view3D: View3D | None = None,  # noqa: N803
        floor: Surface | None = None,
        sideWall: Surface | None = None,  # noqa: N803
        backWall: Surface | None = None,  # noqa: N803
    ) -> None:
        self.view3D = view3D if view3D is not None else View3D()
        self.floor = floor if floor is not None else Surface()
        self.sideWall = sideWall if sideWall is not None else Surface()
        self.backWall = backWall if backWall is not None else Surface()


_3D_XML_MODEL_NAMES = ("View3D", "Surface", "_3DBase")


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


def _from_openpyxl_3d_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_3d_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_3d_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_3d_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_3d_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _3D_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_3d_model(native_cls, value)


def _3d_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _3d_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_3d_model(cls, upstream_cls.from_tree(node))


def _3d_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_3d_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _3d_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_3d_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _3d_eq  # type: ignore[attr-defined]


Alias = ExtensionList = NestedBool = NestedInteger = NestedMinMax = Serialisable = Typed = _OpenpyxlSerialisable

_install_openpyxl_iter(View3D, Surface, _3DBase)
_install_3d_xml_methods(View3D, Surface, _3DBase)

__all__ = [
    "Alias",
    "ExtensionList",
    "GraphicalProperties",
    "NestedBool",
    "NestedInteger",
    "NestedMinMax",
    "PictureOptions",
    "Serialisable",
    "Surface",
    "Typed",
    "View3D",
    "_3DBase",
]
