"""Regression tests for combined-style flush (G05 sub-fix).

Setting font + fill + border + alignment + number_format + protection on
one cell used to mint two xf records (format-only and border-only) and
the cell ended up bound to whichever was written last. The Python flush
layer now merges border keys into the format dict, so a single
``write_cell_format`` call interns one combined xf record.
"""
from __future__ import annotations

from pathlib import Path

import wolfxl
from wolfxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Protection,
    Side,
)


def test_all_six_style_attrs_round_trip(tmp_path: Path) -> None:
    """font + fill + border + alignment + number_format + protection persist."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    ws["A1"].font = Font(bold=True)
    ws["A1"].fill = PatternFill(fill_type="solid", fgColor="FF00FF00")
    ws["A1"].border = Border(left=Side(style="thin"))
    ws["A1"].alignment = Alignment(horizontal="center")
    ws["A1"].number_format = "0.00"
    ws["A1"].protection = Protection(locked=False, hidden=True)
    out = tmp_path / "combo.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    cell = ws2["A1"]
    assert cell.font.bold is True
    assert cell.fill.fgColor.rgb == "FF00FF00"
    assert cell.border.left.style == "thin"
    assert cell.alignment.horizontal == "center"
    assert cell.number_format == "0.00"
    assert cell.protection.locked is False
    assert cell.protection.hidden is True


def test_border_then_font_does_not_overwrite(tmp_path: Path) -> None:
    """Setting border first then font does not overwrite border on save."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    ws["A1"].border = Border(left=Side(style="thick"))
    ws["A1"].font = Font(italic=True)
    out = tmp_path / "border_then_font.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    cell = ws2["A1"]
    assert cell.font.italic is True
    assert cell.border.left.style == "thick"


def test_combined_styles_dedupe_across_cells(tmp_path: Path) -> None:
    """Two cells with identical combined styles share one xf record."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    for coord in ("A1", "B1"):
        ws[coord] = coord
        ws[coord].font = Font(bold=True)
        ws[coord].border = Border(top=Side(style="medium"))
    out = tmp_path / "dedupe.xlsx"
    wb.save(out)

    import zipfile
    with zipfile.ZipFile(out) as z:
        styles = z.read("xl/styles.xml").decode()
    cellxfs_open = styles.index("<cellXfs")
    cellxfs_close = styles.index("</cellXfs>", cellxfs_open)
    cellxfs_block = styles[cellxfs_open:cellxfs_close]
    xf_count = cellxfs_block.count("<xf ")
    assert xf_count == 2, f"expected 1 default + 1 combined xf; got {xf_count}: {cellxfs_block}"


def test_combined_styles_distinct_when_attrs_differ(tmp_path: Path) -> None:
    """Two cells with different combined styles produce distinct xf records."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "a"
    ws["A1"].font = Font(bold=True)
    ws["A1"].border = Border(left=Side(style="thin"))
    ws["B1"] = "b"
    ws["B1"].font = Font(bold=True)
    ws["B1"].border = Border(left=Side(style="thick"))
    out = tmp_path / "distinct.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    assert ws2["A1"].border.left.style == "thin"
    assert ws2["B1"].border.left.style == "thick"
    assert ws2["A1"].font.bold is True
    assert ws2["B1"].font.bold is True
