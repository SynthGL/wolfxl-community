"""`BubbleChart` — XY scatter with marker size encoding a third dimension.

Mirrors :class:`openpyxl.chart.bubble_chart.BubbleChart`.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _openpyxl_name_fallback

from ._chart import ChartBase, _install_chart_type_xml_methods
from .axis import NumericAxis
from .label import DataLabelList


_VALID_SIZE_REPRESENTS = (None, "area", "w")


class BubbleChart(ChartBase):
    """An XY bubble chart — third axis encoded in marker size."""

    tagname = "bubbleChart"
    _series_type = "bubble"

    def __init__(
        self,
        varyColors: bool | None = None,
        ser: list[Any] | tuple[Any, ...] = (),
        dLbls: DataLabelList | None = None,
        bubble3D: bool | None = None,
        bubbleScale: int | None = None,
        showNegBubbles: bool | None = None,
        sizeRepresents: str | None = None,
        **kw: Any,
    ) -> None:
        if bubbleScale is not None and not (0 <= bubbleScale <= 300):
            raise ValueError(f"bubbleScale={bubbleScale} must be in [0, 300]")
        if sizeRepresents not in _VALID_SIZE_REPRESENTS:
            raise ValueError(
                f"sizeRepresents={sizeRepresents!r} not in {_VALID_SIZE_REPRESENTS}"
            )
        self.vary_colors = varyColors
        self.dLbls = dLbls
        self.bubble3D = bubble3D
        self.bubbleScale = bubbleScale
        self.showNegBubbles = showNegBubbles
        self.sizeRepresents = sizeRepresents
        super().__init__(**kw)
        self.ser = list(ser)
        self.x_axis = NumericAxis(axId=10, crossAx=20)
        self.y_axis = NumericAxis(axId=20, crossAx=10)

    @property
    def varyColors(self) -> bool | None:
        return self.vary_colors

    @varyColors.setter
    def varyColors(self, v: bool | None) -> None:
        self.vary_colors = v

    @property
    def bubble_scale(self) -> int | None:
        return self.bubbleScale

    @bubble_scale.setter
    def bubble_scale(self, v: int | None) -> None:
        if v is not None and not (0 <= v <= 300):
            raise ValueError(f"bubble_scale={v} must be in [0, 300]")
        self.bubbleScale = v

    @property
    def show_neg_bubbles(self) -> bool | None:
        return self.showNegBubbles

    @show_neg_bubbles.setter
    def show_neg_bubbles(self, v: bool | None) -> None:
        self.showNegBubbles = v

    @property
    def size_represents(self) -> str | None:
        return self.sizeRepresents

    @size_represents.setter
    def size_represents(self, v: str | None) -> None:
        if v not in _VALID_SIZE_REPRESENTS:
            raise ValueError(f"size_represents={v!r} not in {_VALID_SIZE_REPRESENTS}")
        self.sizeRepresents = v

    def _chart_type_specific_keys(self) -> dict[str, Any]:
        """Flat per-type keys (snake_case)."""
        d: dict[str, Any] = {}
        if self.bubble3D is not None:
            d["bubble_3d"] = self.bubble3D
        if self.bubbleScale is not None:
            d["bubble_scale"] = self.bubbleScale
        if self.showNegBubbles is not None:
            d["show_neg_bubbles"] = self.showNegBubbles
        if self.sizeRepresents is not None:
            d["size_represents"] = self.sizeRepresents
        if self.dLbls is not None:
            from .series import _dlbls_to_snake
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())
        return d


_install_chart_type_xml_methods(BubbleChart)


__all__ = ["BubbleChart"]

__getattr__ = _openpyxl_name_fallback(globals())
