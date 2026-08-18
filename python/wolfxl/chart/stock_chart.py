"""`StockChart` — OHLC stock chart.

Validates exactly 4 series in fixed Open / High / Low / Close order.
Emits ``hi_low_lines: True`` and ``up_down_bars: True`` flags by default.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _openpyxl_name_fallback

from ._chart import ChartBase, _install_chart_type_xml_methods
from .axis import NumericAxis, TextAxis
from .label import DataLabelList


class StockChart(ChartBase):
    """A stock chart — Open/High/Low/Close, exactly 4 series in that order."""

    tagname = "stockChart"
    _series_type = "line"

    def __init__(
        self,
        ser: list[Any] | tuple[Any, ...] = (),
        dLbls: DataLabelList | None = None,
        hi_low_lines: bool = True,
        up_down_bars: bool = True,
        **kw: Any,
    ) -> None:
        self.dLbls = dLbls
        self.hi_low_lines = bool(hi_low_lines)
        self.up_down_bars = bool(up_down_bars)
        super().__init__(**kw)
        self.ser = list(ser)
        self.x_axis = TextAxis()
        self.y_axis = NumericAxis()

    def _validate_at_emit(self) -> None:  # noqa: D401
        # StockChart REQUIRES exactly 4 series in OHLC order.
        if len(self.ser) != 4:
            raise ValueError(
                f"StockChart requires exactly 4 series (Open/High/Low/Close), "
                f"got {len(self.ser)}"
            )

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "hi_low_lines": self.hi_low_lines,
            "up_down_bars": self.up_down_bars,
        }
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


_install_chart_type_xml_methods(StockChart)


__all__ = ["StockChart"]

__getattr__ = _openpyxl_name_fallback(globals())
