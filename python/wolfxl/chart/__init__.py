"""``wolfxl.chart`` — openpyxl-shaped chart construction API.

Sixteen chart families covering both 2-D and 3-D variants:

* :class:`BarChart`, :class:`BarChart3D`
* :class:`LineChart`, :class:`LineChart3D`
* :class:`PieChart`, :class:`PieChart3D` / :class:`Pie3D`,
  :class:`DoughnutChart`, :class:`ProjectedPieChart`
* :class:`AreaChart`, :class:`AreaChart3D`
* :class:`ScatterChart`, :class:`BubbleChart`, :class:`RadarChart`
* :class:`SurfaceChart`, :class:`SurfaceChart3D`
* :class:`StockChart`

Construct charts exactly as you would with openpyxl::

    from wolfxl.chart import BarChart, Reference

    chart = BarChart()
    chart.title = "Sales"
    chart.style = 10
    data = Reference(ws, min_col=2, min_row=1, max_col=3, max_row=6)
    chart.add_data(data, titles_from_data=True)
    ws.add_chart(chart, "D2")
"""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback

from .area_chart import AreaChart, AreaChart3D
from .bar_chart import BarChart, BarChart3D
from .bubble_chart import BubbleChart
from .doughnut_chart import DoughnutChart
from .line_chart import LineChart, LineChart3D
from .pie_chart import Pie3D, PieChart, PieChart3D
from .projected_pie_chart import ProjectedPieChart
from .radar_chart import RadarChart
from .reference import Reference
from .scatter_chart import ScatterChart
from .series import Series, SeriesFactory, SeriesLabel, XYSeries
from .stock_chart import StockChart
from .surface_chart import SurfaceChart, SurfaceChart3D


__all__ = [
    "AreaChart",
    "AreaChart3D",
    "BarChart",
    "BarChart3D",
    "BubbleChart",
    "DoughnutChart",
    "LineChart",
    "LineChart3D",
    "Pie3D",
    "PieChart",
    "PieChart3D",
    "ProjectedPieChart",
    "RadarChart",
    "Reference",
    "ScatterChart",
    "Series",
    "SeriesFactory",
    "SeriesLabel",
    "StockChart",
    "SurfaceChart",
    "SurfaceChart3D",
    "XYSeries",
]

__getattr__ = _openpyxl_name_fallback(globals())
