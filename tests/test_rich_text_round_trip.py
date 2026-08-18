"""Sprint Ι Pod-α — full round-trip rich-text tests.

openpyxl writes a workbook with rich text, wolfxl loads + mutates one
run + saves, openpyxl reloads to verify the mutation landed cleanly
without disturbing the surrounding runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl
from wolfxl.cell.rich_text import CellRichText, InlineFont, TextBlock

openpyxl = pytest.importorskip("openpyxl")
op_rt = pytest.importorskip("openpyxl.cell.rich_text")


def _runs_of(value):
    if isinstance(value, str):
        return [value]
    return list(value)


def test_round_trip_mutate_one_run(tmp_path: Path) -> None:
    """Load a rich-text fixture, mutate the second run, save, reload."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    base = openpyxl.Workbook()
    base.active["A1"] = op_rt.CellRichText(
        [
            op_rt.TextBlock(op_rt.InlineFont(b=True), "first"),
            " ",
            op_rt.TextBlock(op_rt.InlineFont(i=True), "second"),
        ]
    )
    base.save(src)

    # Read via wolfxl, capture the structured runs, mutate the third
    # entry's text, save back via modify mode.
    wb = wolfxl.load_workbook(str(src), modify=True)
    rt = wb.active["A1"].rich_text
    assert rt is not None
    assert len(rt) == 3
    # Replace the entire CellRichText with a mutated copy that swaps
    # the third run's text and adds bold to the new one.
    new_rt = CellRichText(
        [
            TextBlock(InlineFont(b=True), "first"),
            " ",
            TextBlock(InlineFont(i=True, b=True), "third"),
        ]
    )
    wb.active["A1"] = new_rt
    wb.save(str(dst))

    reloaded = openpyxl.load_workbook(dst, rich_text=True)
    runs = _runs_of(reloaded.active["A1"].value)
    assert len(runs) == 3
    assert runs[0].text == "first"
    assert runs[0].font.b is True
    assert runs[1] == " "
    assert runs[2].text == "third"
    assert runs[2].font.i is True
    assert runs[2].font.b is True


def test_round_trip_via_wolfxl_only(tmp_path: Path) -> None:
    """wolfxl writes rich text, wolfxl reads it back identically."""
    p = tmp_path / "selfrt.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = CellRichText(
        [
            TextBlock(InlineFont(b=True, sz=12), "Bold12"),
            " ",
            TextBlock(InlineFont(i=True, color="FF0000FF"), "italicBlue"),
        ]
    )
    wb.save(str(p))

    reloaded = wolfxl.load_workbook(str(p))
    rt = reloaded.active["A1"].rich_text
    assert isinstance(rt, CellRichText)
    assert len(rt) == 3
    assert rt[0].text == "Bold12"
    assert rt[0].font.b is True
    assert rt[0].font.sz == 12.0
    assert rt[1] == " "
    assert rt[2].text == "italicBlue"
    assert rt[2].font.i is True
    assert rt[2].font.color == "FF0000FF"


def test_round_trip_preserves_neighboring_cells(tmp_path: Path) -> None:
    """Modifying one rich cell must not perturb its neighbors."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    base = openpyxl.Workbook()
    ws = base.active
    ws["A1"] = "neighbor before"
    ws["A2"] = op_rt.CellRichText(
        [op_rt.TextBlock(op_rt.InlineFont(b=True), "target")]
    )
    ws["A3"] = 42
    ws["A4"] = op_rt.CellRichText(
        [op_rt.TextBlock(op_rt.InlineFont(i=True), "untouched")]
    )
    base.save(src)

    wb = wolfxl.load_workbook(str(src), modify=True)
    wb.active["A2"] = CellRichText(
        [TextBlock(InlineFont(strike=True), "mutated")]
    )
    wb.save(str(dst))

    reloaded = openpyxl.load_workbook(dst, rich_text=True)
    assert reloaded.active["A1"].value == "neighbor before"
    a2 = _runs_of(reloaded.active["A2"].value)
    assert len(a2) == 1
    assert a2[0].text == "mutated"
    assert a2[0].font.strike is True
    assert reloaded.active["A3"].value == 42
    a4 = _runs_of(reloaded.active["A4"].value)
    assert len(a4) == 1
    assert a4[0].text == "untouched"
    assert a4[0].font.i is True
