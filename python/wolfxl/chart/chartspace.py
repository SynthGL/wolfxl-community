"""ChartSpace compatibility wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import (
    _OpenpyxlSerialisable,
    _install_openpyxl_iter,
    _resolve_openpyxl_class,
)
from wolfxl.chart.legend import Legend
from wolfxl.chart.pivot import PivotFormat, PivotSource
from wolfxl.chart.plotarea import PlotArea
from wolfxl.chart.print_settings import PrintSettings
from wolfxl.chart.shapes import GraphicalProperties
from wolfxl.chart.text import RichText
from wolfxl.chart.title import Title
from wolfxl.drawing.colors import ColorMapping
from wolfxl.packaging.relationship import Relationship
from wolfxl.xml.constants import CHART_NS


@dataclass
class Protection:
    chartObject: bool | None = None  # noqa: N815
    data: bool | None = None
    formatting: bool | None = None
    selection: bool | None = None
    userInterface: bool | None = None  # noqa: N815


@dataclass
class ChartContainer:
    title: Title | None = None
    autoTitleDeleted: bool | None = None  # noqa: N815
    pivotFmts: tuple[PivotFormat, ...] | list[PivotFormat] | None = ()  # noqa: N815
    view3D: Any = None  # noqa: N815
    floor: Any = None
    sideWall: Any = None  # noqa: N815
    backWall: Any = None  # noqa: N815
    plotArea: PlotArea | None = None  # noqa: N815
    legend: Legend | None = None
    plotVisOnly: bool | None = True  # noqa: N815
    dispBlanksAs: str | None = "gap"  # noqa: N815
    showDLblsOverMax: bool | None = None  # noqa: N815
    extLst: Any = None  # noqa: N815

    def __post_init__(self) -> None:
        if self.plotArea is None:
            self.plotArea = PlotArea()


@dataclass
class ExternalData:
    id: str | None = None
    autoUpdate: bool | None = None  # noqa: N815


@dataclass
class ChartSpace:
    date1904: bool | None = None
    lang: str | None = None
    roundedCorners: bool | None = None  # noqa: N815
    style: int | None = None
    clrMapOvr: ColorMapping | None = None  # noqa: N815
    pivotSource: PivotSource | None = None  # noqa: N815
    protection: Protection | None = None
    chart: ChartContainer | None = None
    spPr: GraphicalProperties | None = None  # noqa: N815
    txPr: RichText | None = None  # noqa: N815
    externalData: ExternalData | None = None  # noqa: N815
    printSettings: PrintSettings | None = None  # noqa: N815
    userShapes: Relationship | None = None  # noqa: N815
    extLst: Any = None  # noqa: N815


_CHARTSPACE_XML_MODEL_NAMES = (
    "Protection",
    "ChartContainer",
    "ExternalData",
    "ChartSpace",
)


def _xml_model_names(cls: type) -> tuple[str, ...]:
    return tuple(getattr(cls, "__attrs__", ())) + tuple(getattr(cls, "__elements__", ()))


def _to_openpyxl_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_openpyxl_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_openpyxl_model(item) for item in value)
    if str(getattr(value.__class__, "__module__", "")).startswith("wolfxl.chart"):
        if hasattr(value, "to_tree") and getattr(value, "tagname", None):
            return value
    if str(getattr(value.__class__, "__module__", "")).endswith(".plotarea"):
        from wolfxl.chart.plotarea import _to_openpyxl_model as _plotarea_to_openpyxl

        return _plotarea_to_openpyxl(value)
    if str(getattr(value.__class__, "__module__", "")).endswith(".shapes"):
        from wolfxl.chart.shapes import _to_openpyxl_model as _shape_to_openpyxl_model

        return _shape_to_openpyxl_model(value)

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


def _from_openpyxl_chartspace_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_chartspace_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_chartspace_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_chartspace_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_chartspace_model(item) for item in value)
    if str(getattr(value.__class__, "__module__", "")).startswith(
        "openpyxl.chart.plotarea"
    ):
        from wolfxl.chart.plotarea import _to_native_plotarea_model

        return _to_native_plotarea_model(value)
    if str(getattr(value.__class__, "__module__", "")).startswith(
        "openpyxl.chart.title"
    ):
        from wolfxl.chart.title import _to_native_title_model

        return _to_native_title_model(value)
    if str(getattr(value.__class__, "__module__", "")).startswith(
        "openpyxl.chart.shapes"
    ):
        from wolfxl.chart.shapes import _to_native_shape_model

        return _to_native_shape_model(value)

    native_cls = globals().get(value.__class__.__name__)
    if (
        not isinstance(native_cls, type)
        or native_cls.__name__ not in _CHARTSPACE_XML_MODEL_NAMES
    ):
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_chartspace_model(native_cls, value)


def _chartspace_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _chartspace_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_chartspace_model(cls, upstream_cls.from_tree(node))


def _chartspace_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_chartspace_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _chartspace_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_chartspace_from_tree)  # type: ignore[attr-defined]
        cls.__eq__ = _chartspace_eq  # type: ignore[attr-defined]


_install_openpyxl_iter(
    Protection,
    ChartContainer,
    ExternalData,
    ChartSpace,
    PivotFormat,
    PrintSettings,
)
_install_chartspace_xml_methods(
    Protection,
    ChartContainer,
    ExternalData,
    ChartSpace,
)

Alias = ExtensionList = NestedBool = NestedMinMax = NestedNoneSet = NestedSequence = NestedString = Relation = Serialisable = String = Typed = _OpenpyxlSerialisable

__all__ = [
    "Alias",
    "CHART_NS",
    "ChartContainer",
    "ChartSpace",
    "ColorMapping",
    "ExtensionList",
    "ExternalData",
    "GraphicalProperties",
    "Legend",
    "NestedBool",
    "NestedMinMax",
    "NestedNoneSet",
    "NestedSequence",
    "NestedString",
    "PivotFormat",
    "PivotSource",
    "PlotArea",
    "PrintSettings",
    "Protection",
    "Relation",
    "Relationship",
    "RichText",
    "Serialisable",
    "String",
    "Title",
    "Typed",
]
