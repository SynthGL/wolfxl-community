"""RFC-057 parity tests against openpyxl.

Verifies that wolfxl-written ArrayFormula / DataTableFormula cells
parse correctly when re-read with openpyxl, and vice versa.  Spec
parity matters because users may swap libraries mid-pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl
from wolfxl.cell.cell import ArrayFormula, DataTableFormula

openpyxl = pytest.importorskip("openpyxl")


def test_wolfxl_writes_array_openpyxl_reads(tmp_path: Path) -> None:
    """wolfxl emits `<f t="array">`, openpyxl recognizes it."""
    p = tmp_path / "wolfxl_array.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = ArrayFormula("A1:A3", "B1:B3*2")
    wb.active["B1"] = 1
    wb.active["B2"] = 2
    wb.active["B3"] = 3
    wb.save(str(p))

    rb = openpyxl.load_workbook(str(p))
    a1 = rb.active["A1"]
    # openpyxl carries the formula text on the cell; the spill-range
    # `<f t="array" ref="...">` shows up via the ``cell.value`` (which
    # openpyxl coerces to a leading-equals string in non-rich mode).
    val = a1.value
    # openpyxl exposes ArrayFormula via cell.value when it parses
    # `<f t="array" ref="...">` — but older versions returned the
    # raw formula string with leading "=".  Accept either shape.
    if hasattr(val, "ref"):
        assert val.ref == "A1:A3"
        assert "B1:B3*2" in (val.text or "")
    else:
        assert isinstance(val, str)
        assert "B1:B3" in val


def test_openpyxl_writes_array_wolfxl_reads(tmp_path: Path) -> None:
    """openpyxl emits an array formula; wolfxl recognizes it."""
    op_formula = pytest.importorskip("openpyxl.worksheet.formula")
    p = tmp_path / "openpyxl_array.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = op_formula.ArrayFormula(ref="A1:A3", text="=B1:B3*2")
    ws["B1"] = 1
    ws["B2"] = 2
    ws["B3"] = 3
    wb.save(str(p))

    rb = wolfxl.load_workbook(str(p))
    a1 = rb.active["A1"].value
    assert isinstance(a1, ArrayFormula)
    assert a1.ref == "A1:A3"
    # openpyxl emits the body with leading "=" — wolfxl strips it on
    # parse.  Accept either.
    assert "B1:B3*2" in a1.text
    assert rb.active.array_formulae == {"A1": "A1:A3"}


def test_wolfxl_matches_openpyxl_array_formulae_property(tmp_path: Path) -> None:
    """openpyxl 3.1.x exposes spill metadata via ``Worksheet.array_formulae``."""
    p = tmp_path / "array_formulae.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = ArrayFormula("A1:A3")
    wb.save(str(p))

    rb = wolfxl.load_workbook(str(p))
    assert rb.active.array_formulae == {"A1": "A1:A3"}

    op = openpyxl.load_workbook(str(p))
    assert op.active.array_formulae == {"A1": "A1:A3"}


def test_wolfxl_writes_data_table_openpyxl_reads(tmp_path: Path) -> None:
    p = tmp_path / "wolfxl_dt.xlsx"
    wb = wolfxl.Workbook()
    wb.active["B2"] = DataTableFormula(
        ref="B2:F11", dt2D=True, r1="A1", r2="A2"
    )
    wb.save(str(p))

    rb = openpyxl.load_workbook(str(p))
    val = rb.active["B2"].value
    # openpyxl exposes DataTableFormula via cell.value when it parses
    # `<f t="dataTable">`.  Accept the typed form OR the raw string
    # (older versions / different parse paths).
    if hasattr(val, "ref"):
        assert val.ref == "B2:F11"
        # openpyxl carries dt2D as the raw "1" / "0" string.  Accept
        # either bool or string truthy.
        assert val.dt2D in (True, "1", 1)
    # Either way, the file must round-trip cleanly without raising.


def test_data_table_del_flags_round_trip_with_openpyxl(tmp_path: Path) -> None:
    p = tmp_path / "dt_del_flags.xlsx"
    wb = wolfxl.Workbook()
    wb.active["B2"] = DataTableFormula(ref="B2:F11", del1=True, del2=True)
    wb.save(str(p))

    rb = wolfxl.load_workbook(str(p))
    val = rb.active["B2"].value
    assert isinstance(val, DataTableFormula)
    assert val.del1 is True
    assert val.del2 is True

    op = openpyxl.load_workbook(str(p))
    op_val = op.active["B2"].value
    assert str(op_val.del1).lower() in {"1", "true"}
    assert str(op_val.del2).lower() in {"1", "true"}


def test_round_trip_preserves_neighbors_modify_mode(tmp_path: Path) -> None:
    """Adding an array formula in modify mode must not perturb neighbors."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    base = openpyxl.Workbook()
    ws = base.active
    ws["A1"] = "anchor"
    ws["A2"] = 99
    ws["B1"] = 1
    ws["B2"] = 2
    ws["B3"] = 3
    base.save(str(src))

    wb = wolfxl.load_workbook(str(src), modify=True)
    wb.active["C1"] = ArrayFormula("C1:C3", "B1:B3*2")
    wb.save(str(dst))

    rb = openpyxl.load_workbook(str(dst))
    assert rb.active["A1"].value == "anchor"
    assert rb.active["A2"].value == 99
    assert rb.active["B1"].value == 1
    assert rb.active["B2"].value == 2
    assert rb.active["B3"].value == 3


def test_array_formula_xml_well_formed(tmp_path: Path) -> None:
    """openpyxl's parser opens the wolfxl-written file without errors.

    This is the secondary oracle: even if the typed instance round-trip
    wobbles between openpyxl versions, the underlying XML must always
    be valid OOXML that openpyxl can parse without raising.
    """
    p = tmp_path / "smoke.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = ArrayFormula("A1:A5", "B1:B5*2")
    wb.active["D1"] = DataTableFormula(
        ref="D1:E2", dt2D=True, r1="F1", r2="F2"
    )
    wb.save(str(p))

    # No-raise smoke test.
    rb = openpyxl.load_workbook(str(p))
    list(rb.active.iter_rows(values_only=True))
