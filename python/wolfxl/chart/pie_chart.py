"""`PieChart`, `DoughnutChart`, and 3D / projected variants.

Mirrors :class:`openpyxl.chart.pie_chart`.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _openpyxl_name_fallback

from ._chart import ChartBase, _install_chart_type_xml_methods
from .label import DataLabelList


class _PieChartBase(ChartBase):
    """Shared state between PieChart and DoughnutChart variants."""

    _series_type = "pie"

    def __init__(
        self,
        varyColors: bool | None = True,
        ser: list[Any] | tuple[Any, ...] = (),
        dLbls: DataLabelList | None = None,
        **kw: Any,
    ) -> None:
        self.vary_colors = varyColors
        self.dLbls = dLbls
        super().__init__(**kw)
        self.ser = list(ser)

    @property
    def varyColors(self) -> bool | None:
        return self.vary_colors

    @varyColors.setter
    def varyColors(self, v: bool | None) -> None:
        self.vary_colors = v


class PieChart(_PieChartBase):
    """A pie chart — single series, slice per category."""

    tagname = "pieChart"

    def __init__(self, firstSliceAng: int = 0, **kw: Any) -> None:
        if not (0 <= firstSliceAng <= 360):
            raise ValueError(f"firstSliceAng={firstSliceAng} must be in [0, 360]")
        super().__init__(**kw)
        self.firstSliceAng = firstSliceAng

    @property
    def first_slice_ang(self) -> int:
        return self.firstSliceAng

    @first_slice_ang.setter
    def first_slice_ang(self, v: int) -> None:
        if not (0 <= v <= 360):
            raise ValueError(f"first_slice_ang={v} must be in [0, 360]")
        self.firstSliceAng = v

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        """Flat per-type keys (snake_case)."""
        d: dict[str, Any] = {"first_slice_ang": self.firstSliceAng}
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


class DoughnutChart(_PieChartBase):
    """A doughnut chart — pie with a hole."""

    tagname = "doughnutChart"

    def __init__(
        self,
        firstSliceAng: int = 0,
        holeSize: int | None = 10,
        **kw: Any,
    ) -> None:
        if not (0 <= firstSliceAng <= 360):
            raise ValueError(f"firstSliceAng={firstSliceAng} must be in [0, 360]")
        if holeSize is not None and not (1 <= holeSize <= 90):
            raise ValueError(f"holeSize={holeSize} must be in [1, 90]")
        super().__init__(**kw)
        self.firstSliceAng = firstSliceAng
        self.holeSize = holeSize

    @property
    def hole_size(self) -> int | None:
        return self.holeSize

    @hole_size.setter
    def hole_size(self, v: int | None) -> None:
        if v is not None and not (1 <= v <= 90):
            raise ValueError(f"hole_size={v} must be in [1, 90]")
        self.holeSize = v

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        """Flat per-type keys (snake_case)."""
        d: dict[str, Any] = {"first_slice_ang": self.firstSliceAng}
        if self.holeSize is not None:
            d["hole_size"] = self.holeSize
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


class PieChart3D(_PieChartBase):
    """3D pie chart.

    Defaults: rot_x=30, rot_y=0, perspective=30.
    """

    tagname = "pie3DChart"

    def __init__(
        self,
        firstSliceAng: int = 0,
        view_3d: dict[str, Any] | None = None,
        **kw: Any,
    ) -> None:
        if not (0 <= firstSliceAng <= 360):
            raise ValueError(f"firstSliceAng={firstSliceAng} must be in [0, 360]")
        super().__init__(**kw)
        self.firstSliceAng = firstSliceAng
        self.view_3d = {
            "rot_x": 30,
            "rot_y": 0,
            "perspective": 30,
            "right_angle_axes": False,
        }
        if view_3d is not None:
            self.view_3d.update(view_3d)

    @property
    def first_slice_ang(self) -> int:
        return self.firstSliceAng

    @first_slice_ang.setter
    def first_slice_ang(self, v: int) -> None:
        if not (0 <= v <= 360):
            raise ValueError(f"first_slice_ang={v} must be in [0, 360]")
        self.firstSliceAng = v

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        d: dict[str, Any] = {"first_slice_ang": self.firstSliceAng}
        v3d = {k: v for k, v in self.view_3d.items() if v is not None}
        if v3d:
            d["view_3d"] = v3d
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


# openpyxl-style alias matching the openpyxl class name
Pie3D = PieChart3D

from .projected_pie_chart import CustomSplit, ProjectedPieChart

_install_chart_type_xml_methods(PieChart, PieChart3D, DoughnutChart)

__all__ = [
    "CustomSplit",
    "DoughnutChart",
    "Pie3D",
    "PieChart",
    "PieChart3D",
    "ProjectedPieChart",
]

__getattr__ = _openpyxl_name_fallback(globals())
