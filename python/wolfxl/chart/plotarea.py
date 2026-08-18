"""Plot area compatibility model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wolfxl._compat import (
    _OpenpyxlSerialisable,
    _install_openpyxl_iter,
    _resolve_openpyxl_class,
)
from wolfxl.chart.area_chart import AreaChart, AreaChart3D
from wolfxl.chart.axis import (
    DateAxis,
    NumericAxis,
    SeriesAxis,
    TextAxis,
    _to_native_axis_model,
)
from wolfxl.chart.bar_chart import BarChart, BarChart3D
from wolfxl.chart.bubble_chart import BubbleChart
from wolfxl.chart.doughnut_chart import DoughnutChart
from wolfxl.chart.layout import Layout
from wolfxl.chart.line_chart import LineChart, LineChart3D
from wolfxl.chart.pie_chart import PieChart, PieChart3D
from wolfxl.chart.projected_pie_chart import ProjectedPieChart
from wolfxl.chart.radar_chart import RadarChart
from wolfxl.chart.scatter_chart import ScatterChart
from wolfxl.chart.stock_chart import StockChart
from wolfxl.chart.surface_chart import SurfaceChart, SurfaceChart3D
from wolfxl.chart.text import RichText
from wolfxl.chart.shapes import GraphicalProperties


@dataclass
class DataTable:
    showHorzBorder: bool | None = None  # noqa: N815
    showVertBorder: bool | None = None  # noqa: N815
    showOutline: bool | None = None  # noqa: N815
    showKeys: bool | None = None  # noqa: N815
    spPr: GraphicalProperties | None = None  # noqa: N815
    txPr: RichText | None = None  # noqa: N815
    extLst: Any = None  # noqa: N815


@dataclass(init=False)
class PlotArea:
    layout: Layout | None = None
    charts: list[Any] = field(default_factory=list)
    axes: list[Any] = field(default_factory=list)
    dTable: DataTable | None = None  # noqa: N815
    spPr: GraphicalProperties | None = None  # noqa: N815
    extLst: Any = None  # noqa: N815

    def __init__(
        self,
        layout: Layout | None = None,
        charts: list[Any] | tuple[Any, ...] | None = None,
        axes: list[Any] | tuple[Any, ...] | None = None,
        dTable: DataTable | None = None,  # noqa: N803
        spPr: GraphicalProperties | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
        _charts: list[Any] | tuple[Any, ...] | None = None,
        _axes: list[Any] | tuple[Any, ...] | None = None,
        **kw: Any,
    ) -> None:
        self.layout = layout
        self.charts = list(charts if charts is not None else (_charts or []))
        self.axes = list(axes if axes is not None else (_axes or []))
        self.dTable = dTable
        self.spPr = spPr
        self.extLst = extLst
        for key, value in kw.items():
            setattr(self, key, value)

    @property
    def _charts(self) -> list[Any]:
        return self.charts

    @_charts.setter
    def _charts(self, value: list[Any] | tuple[Any, ...]) -> None:
        self.charts = list(value)

    @property
    def _axes(self) -> list[Any]:
        return self.axes

    @_axes.setter
    def _axes(self, value: list[Any] | tuple[Any, ...]) -> None:
        self.axes = list(value)

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        if value is None:
            return
        if name in _CHART_PART_NAMES:
            charts = self.__dict__.setdefault("charts", [])
            charts.append(value)
        elif name in _AXIS_PART_NAMES:
            axes = self.__dict__.setdefault("axes", [])
            axes.append(value)


_CHART_PART_NAMES = {
    "areaChart",
    "area3DChart",
    "lineChart",
    "line3DChart",
    "stockChart",
    "radarChart",
    "scatterChart",
    "pieChart",
    "pie3DChart",
    "doughnutChart",
    "barChart",
    "bar3DChart",
    "ofPieChart",
    "surfaceChart",
    "surface3DChart",
    "bubbleChart",
}

_AXIS_PART_NAMES = {"valAx", "catAx", "dateAx", "serAx"}

_PLOTAREA_XML_MODEL_NAMES = ("DataTable", "PlotArea")


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
        if getattr(value, "tagname", None) in _CHART_PART_NAMES:
            from wolfxl.chart._chart import _chart_to_openpyxl_model

            return _chart_to_openpyxl_model(value)

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


def _from_openpyxl_plotarea_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_plotarea_model(getattr(value, name))
    native = native_cls(**kwargs)
    if native_cls is PlotArea:
        _bind_plotarea_axes(native)
    return native


def _bind_plotarea_axes(plot: PlotArea) -> None:
    axes = {axis.axId: axis for axis in plot._axes}
    for chart in plot._charts:
        if isinstance(chart, (ScatterChart, BubbleChart)):
            if len(chart.axId) >= 2:
                chart.x_axis = axes.get(chart.axId[0], chart.x_axis)
                chart.y_axis = axes.get(chart.axId[1], chart.y_axis)
            continue

        for ax_id in chart.axId:
            axis = axes.get(ax_id)
            if axis is None:
                if hasattr(chart, "z_axis"):
                    chart.z_axis = None
                continue
            if axis.tagname in ("catAx", "dateAx"):
                chart.x_axis = axis
            elif axis.tagname == "valAx":
                chart.y_axis = axis
            elif axis.tagname == "serAx":
                chart.z_axis = axis


def _to_native_plotarea_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_plotarea_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_plotarea_model(item) for item in value)
    if value.__class__.__module__.startswith("openpyxl.chart.axis"):
        return _to_native_axis_model(value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type):
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_plotarea_model(native_cls, value)


def _plotarea_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _plotarea_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_plotarea_model(cls, upstream_cls.from_tree(node))


def _plotarea_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_plotarea_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _plotarea_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_plotarea_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _plotarea_eq  # type: ignore[attr-defined]


Alias = _OpenpyxlSerialisable
ExtensionList = _OpenpyxlSerialisable
MultiSequence = _OpenpyxlSerialisable
MultiSequencePart = _OpenpyxlSerialisable
NestedBool = _OpenpyxlSerialisable
Serialisable = _OpenpyxlSerialisable
Typed = _OpenpyxlSerialisable

_install_openpyxl_iter(DataTable, PlotArea)
_install_plotarea_xml_methods(DataTable, PlotArea)

__all__ = [
    "Alias",
    "AreaChart",
    "AreaChart3D",
    "BarChart",
    "BarChart3D",
    "BubbleChart",
    "DataTable",
    "DateAxis",
    "DoughnutChart",
    "ExtensionList",
    "GraphicalProperties",
    "Layout",
    "LineChart",
    "LineChart3D",
    "MultiSequence",
    "MultiSequencePart",
    "NestedBool",
    "NumericAxis",
    "PieChart",
    "PieChart3D",
    "PlotArea",
    "ProjectedPieChart",
    "RadarChart",
    "RichText",
    "ScatterChart",
    "Serialisable",
    "SeriesAxis",
    "StockChart",
    "SurfaceChart",
    "SurfaceChart3D",
    "TextAxis",
    "Typed",
]
