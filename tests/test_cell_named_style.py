"""Regression tests for ``cell.style`` named-style round-trip (G05 follow-up).

The wolfxl writer stamps a registered NamedStyle's ``xfId`` slot onto the
``<xf>`` record so the reader can walk ``cellXfs[s].xf_id ->
cellStyles[xf_id]`` and resurface the name on load. These tests pin that
round-trip and the supporting validation behavior.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.styles import Font, NamedStyle


def test_cell_style_round_trips_through_save_and_reload(tmp_path: Path) -> None:
    """cell.style = "Highlight" survives a full save + load cycle."""
    wb = wolfxl.Workbook()
    style = NamedStyle(name="Highlight")
    style.font = Font(bold=True)
    wb.add_named_style(style)

    ws = wb.active
    assert ws is not None
    ws["A1"] = "named"
    ws["A1"].style = "Highlight"

    out = tmp_path / "named_style.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    assert ws2["A1"].style == "Highlight"


def test_cell_style_setter_rejects_unknown_name() -> None:
    """Assigning an unregistered style name raises before save."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    with pytest.raises(ValueError, match="not registered"):
        ws["A1"].style = "Definitely Not Registered"


def test_cell_style_setter_accepts_normal_without_registration() -> None:
    """The reserved Normal style is always accepted; no registration needed."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    ws["A1"].style = "Normal"  # must not raise
    assert ws["A1"].style == "Normal"


def test_builtin_named_style_font_can_be_mutated_per_workbook() -> None:
    """Changing one workbook's Normal font does not mutate another workbook."""
    wb1 = wolfxl.Workbook()
    wb2 = wolfxl.Workbook()

    normal = wb1._named_styles["Normal"]  # noqa: SLF001
    normal.font.color = "FF0000"

    assert normal.font.color.rgb == "00FF0000"
    assert wb2._named_styles["Normal"].font.color.index == 1  # noqa: SLF001


def test_cell_style_setter_clears_with_none(tmp_path: Path) -> None:
    """Setting cell.style = None clears any pending name binding."""
    wb = wolfxl.Workbook()
    style = NamedStyle(name="Highlight")
    style.font = Font(bold=True)
    wb.add_named_style(style)

    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    ws["A1"].style = "Highlight"
    ws["A1"].style = None
    out = tmp_path / "cleared.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    assert ws2["A1"].style is None


def test_named_style_xf_id_stamped_on_styles_xml(tmp_path: Path) -> None:
    """The styles.xml writer emits xfId="N" so reader downstream can resolve."""
    wb = wolfxl.Workbook()
    style = NamedStyle(name="Highlight")
    style.font = Font(bold=True)
    wb.add_named_style(style)

    ws = wb.active
    assert ws is not None
    ws["A1"] = "named"
    ws["A1"].style = "Highlight"

    out = tmp_path / "named_style.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out) as z:
        styles = z.read("xl/styles.xml").decode()

    assert '<cellStyle name="Highlight" xfId="1"/>' in styles
    assert 'xfId="1"' in styles


def test_named_style_dedupes_across_cells(tmp_path: Path) -> None:
    """Two cells with the same named style share one xf record."""
    wb = wolfxl.Workbook()
    style = NamedStyle(name="Metric")
    wb.add_named_style(style)

    ws = wb.active
    assert ws is not None
    for coord in ("A1", "B1"):
        ws[coord] = coord
        ws[coord].style = "Metric"

    out = tmp_path / "dedupe.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out) as z:
        styles = z.read("xl/styles.xml").decode()

    cellxfs_open = styles.index("<cellXfs")
    cellxfs_close = styles.index("</cellXfs>", cellxfs_open)
    cellxfs_block = styles[cellxfs_open:cellxfs_close]
    xf_count = cellxfs_block.count("<xf ")
    assert xf_count == 2, (
        f"expected 1 default + 1 Metric xf; got {xf_count}: {cellxfs_block}"
    )
