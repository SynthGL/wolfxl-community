"""`DoughnutChart` — re-export of the implementation in :mod:`pie_chart`.

openpyxl keeps ``DoughnutChart`` in ``pie_chart.py`` because it shares the
``_PieChartBase`` ancestor; we follow that layout but expose it under its
own module path too so users importing from either location keep working.
"""

from .pie_chart import DoughnutChart

__all__ = ["DoughnutChart"]
