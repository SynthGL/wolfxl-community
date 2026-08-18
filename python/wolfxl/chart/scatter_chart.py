"""`ScatterChart` — XY scatter plots.

Mirrors :class:`openpyxl.chart.scatter_chart.ScatterChart`.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _openpyxl_name_fallback

from ._chart import ChartBase, _install_chart_type_xml_methods
from .axis import NumericAxis
from .label import DataLabelList


_VALID_SCATTER_STYLE = (
    None,
    "none",
    "line",
    "lineMarker",
    "marker",
    "smooth",
    "smoothMarker",
)


class ScatterChart(ChartBase):
    """An XY scatter chart — both axes numeric, no implicit categories."""

    tagname = "scatterChart"
    _series_type = "scatter"

    def __init__(
        self,
        scatterStyle: str | None = None,
        varyColors: bool | None = None,
        ser: list[Any] | tuple[Any, ...] = (),
        dLbls: DataLabelList | None = None,
        **kw: Any,
    ) -> None:
        if scatterStyle not in _VALID_SCATTER_STYLE:
            raise ValueError(
                f"scatterStyle={scatterStyle!r} not in {_VALID_SCATTER_STYLE}"
            )
        self.scatterStyle = scatterStyle
        self.vary_colors = varyColors
        self.dLbls = dLbls
        super().__init__(**kw)
        self.ser = list(ser)
        self.x_axis = NumericAxis(axId=10, crossAx=20)
        self.y_axis = NumericAxis(axId=20, crossAx=10)

    @property
    def scatter_style(self) -> str | None:
        return self.scatterStyle

    @scatter_style.setter
    def scatter_style(self, v: str | None) -> None:
        if v not in _VALID_SCATTER_STYLE:
            raise ValueError(f"scatter_style={v!r} not in {_VALID_SCATTER_STYLE}")
        self.scatterStyle = v

    @property
    def varyColors(self) -> bool | None:
        return self.vary_colors

    @varyColors.setter
    def varyColors(self, v: bool | None) -> None:
        self.vary_colors = v

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        """Flat per-type keys (snake_case)."""
        d: dict[str, Any] = {}
        if self.scatterStyle is not None:
            d["scatter_style"] = self.scatterStyle
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


_install_chart_type_xml_methods(ScatterChart)


__all__ = ["ScatterChart"]

__getattr__ = _openpyxl_name_fallback(globals())
