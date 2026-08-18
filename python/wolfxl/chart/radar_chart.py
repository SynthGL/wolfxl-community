"""`RadarChart` — radial / spider plots.

Mirrors :class:`openpyxl.chart.radar_chart.RadarChart`.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _openpyxl_name_fallback

from ._chart import ChartBase, _install_chart_type_xml_methods
from .axis import NumericAxis, TextAxis
from .label import DataLabelList


_VALID_RADAR_STYLE = ("standard", "marker", "filled")


class RadarChart(ChartBase):
    """A radar (spider) chart."""

    tagname = "radarChart"
    _series_type = "radar"

    def __init__(
        self,
        radarStyle: str = "standard",
        varyColors: bool | None = None,
        ser: list[Any] | tuple[Any, ...] = (),
        dLbls: DataLabelList | None = None,
        **kw: Any,
    ) -> None:
        if radarStyle not in _VALID_RADAR_STYLE:
            raise ValueError(f"radarStyle={radarStyle!r} not in {_VALID_RADAR_STYLE}")
        self.radarStyle = radarStyle
        self.vary_colors = varyColors
        self.dLbls = dLbls
        super().__init__(**kw)
        self.ser = list(ser)
        self.x_axis = TextAxis()
        self.y_axis = NumericAxis()

    @property
    def type(self) -> str:
        return self.radarStyle

    @type.setter
    def type(self, value: str) -> None:
        if value not in _VALID_RADAR_STYLE:
            raise ValueError(f"type={value!r} not in {_VALID_RADAR_STYLE}")
        self.radarStyle = value

    @property
    def radar_style(self) -> str:
        return self.radarStyle

    @radar_style.setter
    def radar_style(self, value: str) -> None:
        if value not in _VALID_RADAR_STYLE:
            raise ValueError(f"radar_style={value!r} not in {_VALID_RADAR_STYLE}")
        self.radarStyle = value

    @property
    def varyColors(self) -> bool | None:
        return self.vary_colors

    @varyColors.setter
    def varyColors(self, v: bool | None) -> None:
        self.vary_colors = v

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        """Flat per-type keys (snake_case)."""
        d: dict[str, Any] = {"radar_style": self.radarStyle}
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


_install_chart_type_xml_methods(RadarChart)


__all__ = ["RadarChart"]

__getattr__ = _openpyxl_name_fallback(globals())
