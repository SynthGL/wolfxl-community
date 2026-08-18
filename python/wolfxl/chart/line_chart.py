"""`LineChart` and `LineChart3D` — line plots.

Mirrors :class:`openpyxl.chart.line_chart.LineChart`.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _openpyxl_name_fallback

from ._chart import ChartBase, _install_chart_type_xml_methods
from .axis import ChartLines, NumericAxis, TextAxis
from .label import DataLabelList


_VALID_GROUPING = ("percentStacked", "standard", "stacked")


class _LineChartBase(ChartBase):
    """Shared state between flat and 3D line charts."""

    _series_type = "line"

    def __init__(
        self,
        grouping: str = "standard",
        varyColors: bool | None = None,
        ser: list[Any] | tuple[Any, ...] = (),
        dLbls: DataLabelList | None = None,
        dropLines: ChartLines | None = None,
        **kw: Any,
    ) -> None:
        if grouping not in _VALID_GROUPING:
            raise ValueError(f"grouping={grouping!r} not in {_VALID_GROUPING}")
        self.grouping = grouping
        self.vary_colors = varyColors
        self.dLbls = dLbls
        self.dropLines = dropLines
        super().__init__(**kw)
        self.ser = list(ser)

    @property
    def varyColors(self) -> bool | None:
        return self.vary_colors

    @varyColors.setter
    def varyColors(self, v: bool | None) -> None:
        self.vary_colors = v


class LineChart(_LineChartBase):
    """A flat (2D) line chart."""

    tagname = "lineChart"

    def __init__(
        self,
        hiLowLines: ChartLines | None = None,
        upDownBars: Any | None = None,
        marker: bool | None = None,
        smooth: bool | None = None,
        **kw: Any,
    ) -> None:
        super().__init__(**kw)
        self.hiLowLines = hiLowLines
        self.upDownBars = upDownBars
        self.marker = marker
        self.smooth = smooth
        self.x_axis = TextAxis()
        self.y_axis = NumericAxis()

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        """Flat per-type keys (snake_case)."""
        d: dict[str, Any] = {"grouping": self.grouping}
        if self.dropLines is not None:
            d["drop_lines"] = self.dropLines.to_dict()
        if self.hiLowLines is not None:
            d["hi_low_lines"] = self.hiLowLines.to_dict()
        if self.upDownBars is not None:
            d["up_down_bars"] = (
                self.upDownBars.to_dict()
                if hasattr(self.upDownBars, "to_dict")
                else self.upDownBars
            )
        if self.marker is not None:
            d["marker"] = self.marker
        if self.smooth is not None:
            d["smooth"] = self.smooth
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


class LineChart3D(_LineChartBase):
    """3D line chart.

    Defaults: rot_x=15, rot_y=20, perspective=30, depth_percent=100.
    """

    tagname = "line3DChart"

    def __init__(
        self,
        gapDepth: int | None = 150,
        view_3d: dict[str, Any] | None = None,
        **kw: Any,
    ) -> None:
        if gapDepth is not None and not (0 <= gapDepth <= 500):
            raise ValueError(f"gapDepth={gapDepth} must be in [0, 500]")
        super().__init__(**kw)
        self.gapDepth = gapDepth
        from .axis import NumericAxis, SeriesAxis, TextAxis
        self.x_axis = TextAxis()
        self.y_axis = NumericAxis()
        self.z_axis = SeriesAxis()
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
        d: dict[str, Any] = {"grouping": self.grouping}
        if self.gapDepth is not None:
            d["gap_depth"] = self.gapDepth
        v3d = {k: v for k, v in self.view_3d.items() if v is not None}
        if v3d:
            d["view_3d"] = v3d
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


_install_chart_type_xml_methods(LineChart, LineChart3D)


__all__ = ["LineChart", "LineChart3D"]

__getattr__ = _openpyxl_name_fallback(globals())
