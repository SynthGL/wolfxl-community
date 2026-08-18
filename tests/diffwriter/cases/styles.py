"""Styling cases — fonts, fills, borders, alignment, number formats.

Each case applies a styling combination via the openpyxl-compatible
``Cell.font`` / ``Cell.fill`` / ``Cell.border`` / ``Cell.alignment`` /
``Cell.number_format`` API and routes through the standard Worksheet flush.
"""
from __future__ import annotations

from typing import Any


def _build_fonts(wb: Any) -> None:
    from wolfxl import Font
    ws = wb.active
    ws["A1"] = "bold"
    ws["A1"].font = Font(name="Calibri", size=11, bold=True)
    ws["A2"] = "italic"
    ws["A2"].font = Font(name="Arial", size=14, italic=True)
    ws["A3"] = "both"
    ws["A3"].font = Font(name="Calibri", size=12, bold=True, italic=True)


def _build_fills(wb: Any) -> None:
    from wolfxl import PatternFill
    ws = wb.active
    ws["A1"] = "yellow"
    ws["A1"].fill = PatternFill(patternType="solid", fgColor="FFFF00")
    ws["A2"] = "red"
    ws["A2"].fill = PatternFill(patternType="solid", fgColor="FF0000")


def _build_borders(wb: Any) -> None:
    from wolfxl import Border, Side
    ws = wb.active
    thin = Side(style="thin", color="000000")
    ws["A1"] = "boxed"
    ws["A1"].border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws["A2"] = "top-only"
    ws["A2"].border = Border(top=thin)


def _build_alignment(wb: Any) -> None:
    from wolfxl import Alignment
    ws = wb.active
    ws["A1"] = "center wrap"
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws["A2"] = "right"
    ws["A2"].alignment = Alignment(horizontal="right")


def _build_number_formats(wb: Any) -> None:
    ws = wb.active
    ws["A1"] = 0.5
    ws["A1"].number_format = "0.00%"
    ws["A2"] = 1234567.89
    ws["A2"].number_format = "#,##0.00"
    ws["A3"] = 0.123456789
    ws["A3"].number_format = "0.000000"
    # Built-in date format
    from datetime import datetime
    ws["B1"] = datetime(2026, 4, 24)
    ws["B1"].number_format = "yyyy-mm-dd"


CASES = [
    ("fonts_combination", _build_fonts),
    ("fills_solid_rgb", _build_fills),
    ("borders_all_sides", _build_borders),
    ("alignment_horiz_vert_wrap", _build_alignment),
    ("number_format_builtin_and_custom", _build_number_formats),
]
