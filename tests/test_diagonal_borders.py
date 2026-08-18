"""Round-trip and modify-mode tests for diagonal borders (G03).

The compat-oracle covers the write-mode round-trip for ``diagonalUp``.
This file covers the gaps the oracle does not - both diagonal directions,
the dedup-by-xf path, and the modify-mode (load-modify-save) cycle that
goes through ``patcher_payload.dict_to_border_spec`` rather than the
write-mode dict path.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl
from wolfxl.styles import Border, Side


def test_diagonal_up_round_trip(tmp_path: Path) -> None:
    """diagonalUp + diagonal Side round-trips through wolfxl reload."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "diag-up"
    ws["A1"].border = Border(
        diagonal=Side(style="thin", color="FF112233"),
        diagonalUp=True,
        diagonalDown=False,
    )
    out = tmp_path / "diag_up.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    border = ws2["A1"].border
    assert border.diagonalUp is True
    assert border.diagonalDown is False
    assert border.diagonal.style == "thin"


def test_diagonal_down_round_trip(tmp_path: Path) -> None:
    """diagonalDown alone round-trips."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "diag-down"
    ws["A1"].border = Border(
        diagonal=Side(style="medium"),
        diagonalUp=False,
        diagonalDown=True,
    )
    out = tmp_path / "diag_down.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    border = ws2["A1"].border
    assert border.diagonalUp is False
    assert border.diagonalDown is True
    assert border.diagonal.style == "medium"


def test_diagonal_both_directions_round_trip(tmp_path: Path) -> None:
    """diagonalUp and diagonalDown together round-trip with the same Side."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "diag-x"
    ws["A1"].border = Border(
        diagonal=Side(style="thick", color="FFAA0011"),
        diagonalUp=True,
        diagonalDown=True,
    )
    out = tmp_path / "diag_both.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    border = ws2["A1"].border
    assert border.diagonalUp is True
    assert border.diagonalDown is True
    assert border.diagonal.style == "thick"


def test_diagonal_distinct_xfs_per_cell(tmp_path: Path) -> None:
    """Cells with different diagonal directions must not dedupe to one xf."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "up-only"
    ws["A1"].border = Border(
        diagonal=Side(style="thin"), diagonalUp=True, diagonalDown=False
    )
    ws["B1"] = "down-only"
    ws["B1"].border = Border(
        diagonal=Side(style="thin"), diagonalUp=False, diagonalDown=True
    )
    out = tmp_path / "diag_distinct.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    a1 = ws2["A1"].border
    b1 = ws2["B1"].border
    assert (a1.diagonalUp, a1.diagonalDown) == (True, False)
    assert (b1.diagonalUp, b1.diagonalDown) == (False, True)


def test_diagonal_no_assignment_returns_default() -> None:
    """A fresh cell exposes Border() with both diagonal flags False."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    border = ws["A1"].border
    assert border.diagonalUp is False
    assert border.diagonalDown is False
    assert border.diagonal.style is None


def test_diagonal_modify_mode_round_trip(tmp_path: Path) -> None:
    """Diagonal applied via load-modify-save persists through patcher path.

    Write mode and modify mode have parallel BorderSpec definitions
    (``crates/wolfxl-writer`` vs ``src/wolfxl/styles.rs``). This test
    exercises the patcher's ``dict_to_border_spec`` and the
    ``border_to_xml`` emit path that the writer-mode oracle probe does
    not reach.
    """
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "preexisting"
    src = tmp_path / "src.xlsx"
    wb.save(src)

    wb2 = wolfxl.load_workbook(src, modify=True)
    ws2 = wb2.active
    assert ws2 is not None
    ws2["A1"].border = Border(
        diagonal=Side(style="hair", color="FF333333"),
        diagonalUp=True,
        diagonalDown=True,
    )
    dst = tmp_path / "dst.xlsx"
    wb2.save(dst)

    wb3 = wolfxl.load_workbook(dst)
    ws3 = wb3.active
    assert ws3 is not None
    border = ws3["A1"].border
    assert border.diagonalUp is True
    assert border.diagonalDown is True
    assert border.diagonal.style == "hair"


@pytest.mark.parametrize(
    "diagonal_up,diagonal_down",
    [(True, True), (True, False), (False, True), (False, False)],
)
def test_diagonal_all_four_combinations(
    tmp_path: Path, diagonal_up: bool, diagonal_down: bool
) -> None:
    """All four (diagonalUp, diagonalDown) combinations survive round-trip.

    When both flags are False, no diagonal Side is emitted regardless of
    the ``diagonal=Side(...)`` argument - this matches openpyxl behavior
    where diagonal style is gated by at least one direction flag.
    """
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    ws["A1"].border = Border(
        diagonal=Side(style="thin"),
        diagonalUp=diagonal_up,
        diagonalDown=diagonal_down,
    )
    out = tmp_path / f"diag_{diagonal_up}_{diagonal_down}.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    border = ws2["A1"].border
    assert border.diagonalUp is diagonal_up
    assert border.diagonalDown is diagonal_down
    if diagonal_up or diagonal_down:
        assert border.diagonal.style == "thin"
