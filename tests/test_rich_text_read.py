"""Sprint Ι Pod-α — rich-text read tests.

openpyxl writes a fixture with various run shapes (single run, multi
run, bold+italic, color, font name, mixed plain/rich); wolfxl reads it
back and verifies the structured runs match.

Default ``Cell.value`` returns the flattened plain string (matches
openpyxl 3.x's default).  ``Cell.rich_text`` always exposes the
structured runs.  ``load_workbook(rich_text=True)`` flips
``Cell.value`` itself to ``CellRichText``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl
from wolfxl.cell.rich_text import CellRichText, InlineFont, TextBlock

openpyxl = pytest.importorskip("openpyxl")
op_rt = pytest.importorskip("openpyxl.cell.rich_text")


@pytest.fixture
def fixture_path(tmp_path: Path) -> Path:
    """Build a workbook with a variety of rich-text shapes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    # A1: single-run (one styled run only).
    ws["A1"] = op_rt.CellRichText(
        [op_rt.TextBlock(op_rt.InlineFont(b=True), "single-bold")]
    )
    # A2: multi-run with plain string mixed in.
    ws["A2"] = op_rt.CellRichText(
        [
            op_rt.TextBlock(op_rt.InlineFont(b=True), "Bold"),
            " regular",
            op_rt.TextBlock(op_rt.InlineFont(i=True), "italic"),
        ]
    )
    # A3: bold + italic + color in a single run.
    ws["A3"] = op_rt.CellRichText(
        [
            op_rt.TextBlock(
                op_rt.InlineFont(b=True, i=True, color="FFFF0000"),
                "BoldItalicRed",
            )
        ]
    )
    # A4: explicit font name and size.
    ws["A4"] = op_rt.CellRichText(
        [op_rt.TextBlock(op_rt.InlineFont(rFont="Arial", sz=14), "arial14")]
    )
    # A5: plain (non-rich) string — must stay a plain str, rich_text is None.
    ws["A5"] = "plain only"
    # A6: rich text with leading + trailing whitespace runs.
    ws["A6"] = op_rt.CellRichText(
        [
            op_rt.TextBlock(op_rt.InlineFont(b=True), "  pad  "),
            " tail ",
        ]
    )
    p = tmp_path / "rt_read.xlsx"
    wb.save(p)
    return p


def test_single_run_reads_as_cellrichtext(fixture_path: Path) -> None:
    wb = wolfxl.load_workbook(str(fixture_path))
    rt = wb.active["A1"].rich_text
    assert isinstance(rt, CellRichText)
    assert len(rt) == 1
    assert isinstance(rt[0], TextBlock)
    assert rt[0].text == "single-bold"
    assert rt[0].font.b is True


def test_multi_run_preserves_order_and_types(fixture_path: Path) -> None:
    wb = wolfxl.load_workbook(str(fixture_path))
    rt = wb.active["A2"].rich_text
    assert isinstance(rt, CellRichText)
    assert len(rt) == 3
    # First run: bold TextBlock.
    assert isinstance(rt[0], TextBlock)
    assert rt[0].text == "Bold"
    assert rt[0].font.b is True
    # Second run: plain string (preserves leading space).
    assert rt[1] == " regular"
    # Third run: italic TextBlock.
    assert isinstance(rt[2], TextBlock)
    assert rt[2].text == "italic"
    assert rt[2].font.i is True


def test_bold_italic_color_combined(fixture_path: Path) -> None:
    wb = wolfxl.load_workbook(str(fixture_path))
    rt = wb.active["A3"].rich_text
    assert isinstance(rt, CellRichText)
    assert len(rt) == 1
    block = rt[0]
    assert isinstance(block, TextBlock)
    assert block.text == "BoldItalicRed"
    assert block.font.b is True
    assert block.font.i is True
    # Color round-trips as the openpyxl-written hex (with alpha prefix).
    assert block.font.color == "FFFF0000"


def test_font_name_and_size(fixture_path: Path) -> None:
    wb = wolfxl.load_workbook(str(fixture_path))
    rt = wb.active["A4"].rich_text
    assert isinstance(rt, CellRichText)
    assert len(rt) == 1
    block = rt[0]
    assert block.font.rFont == "Arial"
    assert block.font.sz == 14.0


def test_plain_cell_returns_none_for_rich_text(fixture_path: Path) -> None:
    wb = wolfxl.load_workbook(str(fixture_path))
    cell = wb.active["A5"]
    # Plain str cells: rich_text is None, value is the str.
    assert cell.rich_text is None
    assert cell.value == "plain only"


def test_default_value_flattens_to_str(fixture_path: Path) -> None:
    """Default ``load_workbook`` keeps ``Cell.value`` as flattened ``str``."""
    wb = wolfxl.load_workbook(str(fixture_path))
    assert wb.active["A1"].value == "single-bold"
    # Value flattens runs in document order.
    assert wb.active["A2"].value == "Bold regularitalic"


def test_rich_text_kwarg_flips_value_to_cellrichtext(fixture_path: Path) -> None:
    """``rich_text=True`` makes ``Cell.value`` return ``CellRichText``."""
    wb = wolfxl.load_workbook(str(fixture_path), rich_text=True)
    val = wb.active["A1"].value
    assert isinstance(val, CellRichText)
    # Plain cells stay as plain str even in rich_text mode.
    assert wb.active["A5"].value == "plain only"


def test_whitespace_runs_round_trip(fixture_path: Path) -> None:
    wb = wolfxl.load_workbook(str(fixture_path))
    rt = wb.active["A6"].rich_text
    assert isinstance(rt, CellRichText)
    # First run keeps its leading + trailing spaces.
    assert isinstance(rt[0], TextBlock)
    assert rt[0].text == "  pad  "
    # Second run is a plain string with leading + trailing spaces.
    assert rt[1] == " tail "


def test_inline_font_shim_constructor() -> None:
    """The local InlineFont shim accepts the same kwargs as openpyxl's."""
    f = InlineFont(b=True, i=False, sz=12.5, color="FF00FF00", rFont="Calibri")
    assert f.b is True
    assert f.i is False
    assert f.sz == 12.5
    assert f.color == "FF00FF00"
    assert f.rFont == "Calibri"
    # ``u=True`` coerces to ``"single"`` (matches openpyxl).
    f2 = InlineFont(u=True)
    assert f2.u == "single"


def test_cellrichtext_iter_protocol() -> None:
    rt = CellRichText([TextBlock(InlineFont(b=True), "x"), " y"])
    items = list(rt)
    assert len(items) == 2
    assert items[0].text == "x"
    assert items[1] == " y"
    # Flattens to a plain str via __str__.
    assert str(rt) == "x y"
