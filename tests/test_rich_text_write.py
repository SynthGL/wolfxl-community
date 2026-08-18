"""Sprint Ι Pod-α — rich-text write tests.

Covers both the write-mode native-writer path (brand-new workbook with
rich-text cells) and the modify-mode patcher path (replace plain →
rich, rich → rich, rich → plain).  Each test reloads via openpyxl to
prove the on-disk OOXML is well-formed and the runs survive.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl
from wolfxl.cell.rich_text import CellRichText, InlineFont, TextBlock

openpyxl = pytest.importorskip("openpyxl")
op_rt = pytest.importorskip("openpyxl.cell.rich_text")


def _runs_of(value):
    """Normalize an openpyxl ``CellRichText`` (or str) to a flat run list."""
    if isinstance(value, str):
        return [value]
    return list(value)


def test_write_mode_simple_rich_text(tmp_path: Path) -> None:
    """Brand-new workbook with one rich-text cell saves and reloads."""
    p = tmp_path / "wm.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = CellRichText(
        [TextBlock(InlineFont(b=True), "Bold"), " regular"]
    )
    wb.save(str(p))

    reloaded = openpyxl.load_workbook(p, rich_text=True)
    val = reloaded.active["A1"].value
    runs = _runs_of(val)
    assert len(runs) == 2
    # First run is bold "Bold".
    assert isinstance(runs[0], op_rt.TextBlock)
    assert runs[0].text == "Bold"
    assert runs[0].font.b is True
    # Second run is plain " regular".
    assert runs[1] == " regular"


def test_write_mode_multi_run_with_color_size_name(tmp_path: Path) -> None:
    p = tmp_path / "wm_mc.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = CellRichText(
        [
            TextBlock(InlineFont(b=True, i=True, color="FFFF0000"), "BIR"),
            TextBlock(InlineFont(rFont="Arial", sz=14), "arial14"),
        ]
    )
    wb.save(str(p))

    reloaded = openpyxl.load_workbook(p, rich_text=True)
    runs = _runs_of(reloaded.active["A1"].value)
    assert len(runs) == 2
    assert runs[0].text == "BIR"
    assert runs[0].font.b is True
    assert runs[0].font.i is True
    assert (runs[0].font.color and runs[0].font.color.rgb) == "FFFF0000"
    assert runs[1].text == "arial14"
    assert runs[1].font.rFont == "Arial"
    assert runs[1].font.sz == 14


def test_modify_mode_replace_plain_with_rich(tmp_path: Path) -> None:
    """In modify mode, replacing a plain string with rich-text round-trips."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    base = openpyxl.Workbook()
    base.active["A1"] = "plain string"
    base.save(src)

    wb = wolfxl.load_workbook(str(src), modify=True)
    wb.active["A1"] = CellRichText(
        [TextBlock(InlineFont(i=True), "italic"), " tail"]
    )
    wb.save(str(dst))

    reloaded = openpyxl.load_workbook(dst, rich_text=True)
    runs = _runs_of(reloaded.active["A1"].value)
    assert len(runs) == 2
    assert isinstance(runs[0], op_rt.TextBlock)
    assert runs[0].text == "italic"
    assert runs[0].font.i is True
    assert runs[1] == " tail"


def test_modify_mode_replace_rich_with_rich(tmp_path: Path) -> None:
    """Mutate one run inside an existing rich-text cell."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    base = openpyxl.Workbook()
    base.active["A1"] = op_rt.CellRichText(
        [op_rt.TextBlock(op_rt.InlineFont(b=True), "old")]
    )
    base.save(src)

    wb = wolfxl.load_workbook(str(src), modify=True)
    wb.active["A1"] = CellRichText(
        [
            TextBlock(InlineFont(b=True, i=True), "new"),
            " trailing",
        ]
    )
    wb.save(str(dst))

    reloaded = openpyxl.load_workbook(dst, rich_text=True)
    runs = _runs_of(reloaded.active["A1"].value)
    assert len(runs) == 2
    assert runs[0].text == "new"
    assert runs[0].font.b is True
    assert runs[0].font.i is True
    assert runs[1] == " trailing"


def test_modify_mode_replace_rich_with_plain(tmp_path: Path) -> None:
    """Replace a rich-text cell with a plain string."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    base = openpyxl.Workbook()
    base.active["A1"] = op_rt.CellRichText(
        [op_rt.TextBlock(op_rt.InlineFont(b=True), "rich was here")]
    )
    base.save(src)

    wb = wolfxl.load_workbook(str(src), modify=True)
    wb.active["A1"] = "now plain"
    wb.save(str(dst))

    reloaded = openpyxl.load_workbook(dst, rich_text=True)
    val = reloaded.active["A1"].value
    # Replacement with a plain string drops back to plain str.
    assert isinstance(val, str)
    assert val == "now plain"


def test_write_mode_xml_escaping(tmp_path: Path) -> None:
    """Special XML characters inside rich-text round-trip safely."""
    p = tmp_path / "esc.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = CellRichText(
        [
            TextBlock(InlineFont(b=True), "A & B"),
            ' quoted "x" <y>',
        ]
    )
    wb.save(str(p))

    reloaded = openpyxl.load_workbook(p, rich_text=True)
    runs = _runs_of(reloaded.active["A1"].value)
    assert runs[0].text == "A & B"
    assert runs[1] == ' quoted "x" <y>'
