"""Chart reader compatibility."""

from __future__ import annotations

from typing import Any

from wolfxl.chart.chartspace import ChartSpace


def read_chart(chartspace: Any) -> Any:
    cs = chartspace if hasattr(chartspace, "chart") else ChartSpace()
    container = cs.chart
    plot = getattr(container, "plotArea", None)
    charts = list(getattr(plot, "_charts", []) or [])
    if not charts:
        return cs

    chart = charts[0]
    chart._charts = charts
    chart._title = getattr(container, "title", None)
    if getattr(container, "dispBlanksAs", None) is not None:
        chart.display_blanks = container.dispBlanksAs
    if getattr(container, "plotVisOnly", None) is not None:
        chart.visible_cells_only = bool(container.plotVisOnly)
    chart.layout = getattr(plot, "layout", None)
    chart.legend = getattr(container, "legend", None)

    chart.floor = getattr(container, "floor", None)
    chart.sideWall = getattr(container, "sideWall", None)
    chart.backWall = getattr(container, "backWall", None)
    chart.pivotSource = getattr(cs, "pivotSource", None)
    chart.pivotFormats = getattr(container, "pivotFmts", ()) or ()
    chart.idx_base = min((s.idx for s in chart.series), default=0)
    chart._reindex()

    chart.graphical_properties = getattr(cs, "spPr", None)
    return chart


__all__ = ["read_chart"]
