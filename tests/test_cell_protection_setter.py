"""Round-trip and edge-case tests for ``cell.protection`` (G04 cell-half).

The openpyxl compat-oracle covers the canonical Protection(locked=True,
hidden=True) round-trip. This file covers the edge cases that the oracle
does not — notably the writer's dedup-by-xf path, where two cells with
different protections must land in different xf entries.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl
from wolfxl.styles import Protection


def test_protection_setter_basic_round_trip(tmp_path: Path) -> None:
    """Setting both flags to non-default round-trips through wolfxl reload."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    ws["A1"].protection = Protection(locked=False, hidden=True)
    out = tmp_path / "prot_basic.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    prot = ws2["A1"].protection
    assert prot.locked is False
    assert prot.hidden is True


def test_protection_setter_default_explicit_round_trip(tmp_path: Path) -> None:
    """Explicitly assigning the default (True/False) survives round-trip.

    A user opting in to the default still wants the override emitted so
    the cell carries an explicit ``applyProtection="1"`` - otherwise an
    Excel macro that toggles sheet-level protection later would silently
    flip the cell to the inherited value.
    """
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "default"
    ws["A1"].protection = Protection()
    out = tmp_path / "prot_default.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    prot = ws2["A1"].protection
    assert prot.locked is True
    assert prot.hidden is False


def test_protection_setter_distinct_xfs_per_cell(tmp_path: Path) -> None:
    """Cells with different protection flags must not dedupe to one xf."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "locked-hidden"
    ws["A1"].protection = Protection(locked=True, hidden=True)
    ws["B1"] = "unlocked-visible"
    ws["B1"].protection = Protection(locked=False, hidden=False)
    out = tmp_path / "prot_distinct.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    a1 = ws2["A1"].protection
    b1 = ws2["B1"].protection
    assert (a1.locked, a1.hidden) == (True, True)
    assert (b1.locked, b1.hidden) == (False, False)


def test_protection_no_assignment_returns_default() -> None:
    """A fresh cell with no assignment exposes the Excel default Protection."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    prot = ws["A1"].protection
    assert isinstance(prot, Protection)
    assert prot.locked is True
    assert prot.hidden is False


def test_protection_setter_locked_only(tmp_path: Path) -> None:
    """Setting locked=False, hidden=False (only locked changed) round-trips."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "unlocked"
    ws["A1"].protection = Protection(locked=False, hidden=False)
    out = tmp_path / "prot_locked_only.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    prot = ws2["A1"].protection
    assert prot.locked is False
    assert prot.hidden is False


@pytest.mark.parametrize(
    "locked,hidden",
    [(True, True), (True, False), (False, True), (False, False)],
)
def test_protection_setter_all_four_combinations(
    tmp_path: Path, locked: bool, hidden: bool
) -> None:
    """All four (locked, hidden) combinations survive a save+reload cycle."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    ws["A1"].protection = Protection(locked=locked, hidden=hidden)
    out = tmp_path / f"prot_{locked}_{hidden}.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2 is not None
    prot = ws2["A1"].protection
    assert prot.locked is locked
    assert prot.hidden is hidden
