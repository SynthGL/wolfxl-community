"""RFC-057 (Sprint Ο Pod 1C) — byte-stable diff-writer tests for
ArrayFormula / DataTableFormula / spill-children.

Verifies that writing the same workbook twice produces identical
``xl/worksheets/sheetN.xml`` bytes (modulo timestamp), so future
changes that perturb the order of attributes / elements in the new
emitter slots get caught immediately.

Run with ``WOLFXL_TEST_EPOCH=0`` to pin the embedded timestamp.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.cell.cell import ArrayFormula, DataTableFormula


@pytest.fixture(autouse=True)
def _pin_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


def _read_sheet_xml(p: Path) -> bytes:
    with zipfile.ZipFile(p) as z:
        return z.read("xl/worksheets/sheet1.xml")


def test_array_formula_byte_stable(tmp_path: Path) -> None:
    """Writing the same array-formula workbook twice yields identical sheet XML."""
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        wb.active["A1"] = ArrayFormula("A1:A5", "B1:B5*2")
        wb.active["B1"] = 1
        wb.active["B2"] = 2
        wb.active["B3"] = 3
        wb.active["B4"] = 4
        wb.active["B5"] = 5
        wb.save(str(p))

    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_data_table_formula_byte_stable(tmp_path: Path) -> None:
    """Writing the same data-table workbook twice yields identical sheet XML."""
    a = tmp_path / "a.xlsx"
    b = tmp_path / "b.xlsx"
    for p in (a, b):
        wb = wolfxl.Workbook()
        wb.active["B2"] = DataTableFormula(
            ref="B2:F11", dt2D=True, r1="A1", r2="A2"
        )
        wb.save(str(p))

    assert _read_sheet_xml(a) == _read_sheet_xml(b)


def test_array_formula_xml_attribute_order(tmp_path: Path) -> None:
    """Pin attribute ordering on the array-formula <f> element.

    Ordering matters for byte-stable golden tests: ``t`` first, then
    ``ref``.  This pins it so future emitter refactors can't reorder
    attributes silently.
    """
    p = tmp_path / "order.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = ArrayFormula("A1:A2", "B1:B2*2")
    wb.save(str(p))

    sheet = _read_sheet_xml(p).decode()
    # Specific byte-level expectation.
    assert '<f t="array" ref="A1:A2">B1:B2*2</f>' in sheet
    # Spill-child placeholder for A2.
    assert '<c r="A2"/>' in sheet
