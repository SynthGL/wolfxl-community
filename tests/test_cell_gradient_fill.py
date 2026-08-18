"""Regression tests for ``cell.fill = GradientFill(...)`` round-trip.

The wolfxl writer emits OOXML `<gradientFill>` (type/degree/left/right/top/
bottom + ordered `<stop>` children); the reader parses gradient blocks back
into Python ``GradientFill`` instances. These tests pin both ends.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.styles import Color
from wolfxl.styles.fills import GradientFill, PatternFill


def test_linear_gradient_fill_round_trips(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "g"
    ws["A1"].fill = GradientFill(
        type="linear",
        degree=45,
        stop=(Color("FF0000"), Color("0000FF")),
    )
    out = tmp_path / "linear.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    fill = ws2["A1"].fill
    assert isinstance(fill, GradientFill)
    assert fill.type == "linear"
    assert fill.degree == 45.0
    assert len(fill.stop) == 2
    assert fill.stop[0][0] == 0.0
    assert fill.stop[0][1].endswith("FF0000")
    assert fill.stop[1][0] == 1.0
    assert fill.stop[1][1].endswith("0000FF")


def test_path_gradient_fill_round_trips(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "g"
    ws["A1"].fill = GradientFill(
        type="path",
        left=0.5,
        right=0.5,
        top=0.5,
        bottom=0.5,
        stop=(Color("112233"),),
    )
    out = tmp_path / "path.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    fill = ws2["A1"].fill
    assert isinstance(fill, GradientFill)
    assert fill.type == "path"
    assert fill.left == 0.5
    assert fill.right == 0.5
    assert fill.top == 0.5
    assert fill.bottom == 0.5
    assert len(fill.stop) == 1


def test_gradient_fill_emits_gradientfill_in_styles_xml(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "g"
    ws["A1"].fill = GradientFill(
        type="linear",
        degree=90,
        stop=(Color("FF0000"), Color("00FF00")),
    )
    out = tmp_path / "g.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out) as z:
        styles = z.read("xl/styles.xml").decode()

    assert "<gradientFill" in styles
    assert 'degree="90"' in styles
    assert '<stop position="0">' in styles
    assert '<stop position="1">' in styles


def test_pattern_fill_unchanged_after_gradient_support(tmp_path: Path) -> None:
    """Sanity check: PatternFill path still works after extending FillSpec."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "p"
    ws["A1"].fill = PatternFill(patternType="solid", fgColor="FF112233")
    out = tmp_path / "p.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    fill = ws2["A1"].fill
    assert isinstance(fill, PatternFill)


@pytest.mark.parametrize("entry_kind", ["color_only", "tuple", "dict"])
def test_gradient_stop_input_normalization(tmp_path: Path, entry_kind: str) -> None:
    """The Python boundary normalizes openpyxl-style stop entries to a common shape."""
    if entry_kind == "color_only":
        stops: list = [Color("FF0000"), Color("00FF00")]
    elif entry_kind == "tuple":
        stops = [(0.0, "FF0000"), (1.0, "00FF00")]
    else:
        stops = [
            {"position": 0.0, "color": "FF0000"},
            {"position": 1.0, "color": "00FF00"},
        ]

    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "g"
    ws["A1"].fill = GradientFill(type="linear", degree=0, stop=stops)
    out = tmp_path / f"g_{entry_kind}.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    fill = ws2["A1"].fill
    assert isinstance(fill, GradientFill)
    assert len(fill.stop) == 2
