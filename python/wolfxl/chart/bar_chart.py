"""`BarChart` and `BarChart3D` — column / bar plots.

Mirrors :class:`openpyxl.chart.bar_chart.BarChart`.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _openpyxl_name_fallback

from ._3d import View3D, _3DBase
from ._chart import ChartBase, _install_chart_type_xml_methods
from .axis import ChartLines, NumericAxis, TextAxis
from .descriptors import NestedGapAmount, NestedOverlap
from .label import DataLabelList
from .legend import Legend


_VALID_BAR_DIR = ("bar", "col")
_VALID_GROUPING = ("percentStacked", "clustered", "standard", "stacked")


class _BarChartBase(ChartBase):
    """Shared state between flat and 3D bar charts."""

    _series_type = "bar"

    gapWidth = NestedGapAmount()
    overlap = NestedOverlap()

    def __init__(
        self,
        barDir: str = "col",
        grouping: str = "clustered",
        varyColors: bool | None = None,
        ser: list[Any] | tuple[Any, ...] = (),
        dLbls: DataLabelList | None = None,
        **kw: Any,
    ) -> None:
        if barDir not in _VALID_BAR_DIR:
            raise ValueError(f"barDir={barDir!r} not in {_VALID_BAR_DIR}")
        if grouping not in _VALID_GROUPING:
            raise ValueError(f"grouping={grouping!r} not in {_VALID_GROUPING}")
        self.barDir = barDir
        self.grouping = grouping
        self.vary_colors = varyColors
        self.dLbls = dLbls
        super().__init__(**kw)
        self.ser = list(ser)

    # openpyxl aliases
    @property
    def type(self) -> str:
        return self.barDir

    @type.setter
    def type(self, value: str) -> None:
        if value not in _VALID_BAR_DIR:
            raise ValueError(f"type={value!r} not in {_VALID_BAR_DIR}")
        self.barDir = value

    @property
    def varyColors(self) -> bool | None:
        return self.vary_colors

    @varyColors.setter
    def varyColors(self, v: bool | None) -> None:
        self.vary_colors = v


class BarChart(_BarChartBase):
    """A flat (2D) bar / column chart."""

    tagname = "barChart"

    def __init__(
        self,
        gapWidth: int | None = 150,
        overlap: int | None = None,
        serLines: ChartLines | None = None,
        **kw: Any,
    ) -> None:
        super().__init__(**kw)
        self.gapWidth = gapWidth
        self.overlap = overlap
        self.serLines = serLines
        self.x_axis = TextAxis()
        self.y_axis = NumericAxis()
        self.legend = Legend()

    # openpyxl alias for ``y_axis``
    @property
    def gap_width(self) -> int | None:
        return self.gapWidth

    @gap_width.setter
    def gap_width(self, v: int | None) -> None:
        self.gapWidth = v

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        """Flat per-type keys (snake_case, no envelope)."""
        d: dict[str, Any] = {
            "bar_dir": self.barDir,
            "grouping": self.grouping,
        }
        if self.gapWidth is not None:
            d["gap_width"] = self.gapWidth
        if self.overlap is not None:
            d["overlap"] = self.overlap
        if self.serLines is not None:
            d["ser_lines"] = self.serLines.to_dict()
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


class BarChart3D(_BarChartBase, _3DBase):
    """3D bar/column chart.

    Defaults: rot_x=15, rot_y=20, right_angle_axes=True, depth_percent=100.
    """

    tagname = "bar3DChart"

    def __init__(
        self,
        gapWidth: int | None = 150,
        gapDepth: int | None = 150,
        shape: str | None = None,
        view_3d: dict[str, Any] | None = None,
        **kw: Any,
    ) -> None:
        if gapWidth is not None and not (0 <= gapWidth <= 500):
            raise ValueError(f"gapWidth={gapWidth} must be in [0, 500]")
        if gapDepth is not None and not (0 <= gapDepth <= 500):
            raise ValueError(f"gapDepth={gapDepth} must be in [0, 500]")
        super().__init__(**kw)
        self.gapWidth = gapWidth
        self.gapDepth = gapDepth
        self.shape = shape
        # 3D needs catAx, valAx, and serAx
        from .axis import NumericAxis, SeriesAxis, TextAxis
        self.x_axis = TextAxis()
        self.y_axis = NumericAxis()
        self.z_axis = SeriesAxis()
        # Default per §11.1
        self.view_3d = {
            "rot_x": 15,
            "rot_y": 20,
            "right_angle_axes": True,
            "depth_percent": 100,
            "perspective": None,
        }
        if view_3d is not None:
            self.view_3d.update(view_3d)
        self.view3D = View3D(
            rotX=self.view_3d["rot_x"],
            rotY=self.view_3d["rot_y"],
            rAngAx=self.view_3d["right_angle_axes"],
            depthPercent=self.view_3d["depth_percent"],
            perspective=self.view_3d["perspective"],
        )

    @property
    def gap_width(self) -> int | None:
        return self.gapWidth

    @gap_width.setter
    def gap_width(self, v: int | None) -> None:
        if v is not None and not (0 <= v <= 500):
            raise ValueError(f"gap_width={v} must be in [0, 500]")
        self.gapWidth = v

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "bar_dir": self.barDir,
            "grouping": self.grouping,
        }
        if self.gapWidth is not None:
            d["gap_width"] = self.gapWidth
        if self.gapDepth is not None:
            d["gap_depth"] = self.gapDepth
        if self.shape is not None:
            d["shape"] = self.shape
        # view_3d emitted only if any field non-None
        v3d = {k: v for k, v in self.view_3d.items() if v is not None}
        if v3d:
            d["view_3d"] = v3d
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


_install_chart_type_xml_methods(BarChart, BarChart3D)


__all__ = ["BarChart", "BarChart3D"]

__getattr__ = _openpyxl_name_fallback(globals())
