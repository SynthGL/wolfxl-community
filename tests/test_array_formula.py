"""RFC-057 (Sprint Ο Pod 1C) — ArrayFormula tests.

Covers the public Python API: constructor, equality, repr, hashing,
``cell.value = ArrayFormula(...)`` setter contract for both write-mode
and modify-mode, spill-range placeholder generation, and round-trip
of the typed instance through ``cell.value``.
"""

from __future__ import annotations

from pathlib import Path


import wolfxl
from wolfxl.cell.cell import ArrayFormula


# ----------------------------------------------------------------------
# 1) Class semantics
# ----------------------------------------------------------------------


def test_constructor_kwargs() -> None:
    af = ArrayFormula(ref="A1:A10", text="B1:B10*2")
    assert af.ref == "A1:A10"
    assert af.text == "B1:B10*2"


def test_constructor_positional() -> None:
    af = ArrayFormula("A1:A10", "SUM(B1:B10*C1:C10)")
    assert af.ref == "A1:A10"
    assert af.text == "SUM(B1:B10*C1:C10)"


def test_constructor_text_optional() -> None:
    af = ArrayFormula("A1:A10")
    assert af.ref == "A1:A10"
    assert af.text == ""


def test_constructor_strips_leading_equals() -> None:
    af = ArrayFormula("A1:A10", "=B1:B10*2")
    assert af.text == "B1:B10*2"


def test_constructor_strips_cse_braces() -> None:
    af = ArrayFormula("A1:A10", "{=B1:B10*2}")
    assert af.text == "B1:B10*2"


def test_constructor_strips_braces_only() -> None:
    af = ArrayFormula("A1:A10", "{B1:B10*2}")
    assert af.text == "B1:B10*2"


def test_equality_same_values() -> None:
    a = ArrayFormula("A1:A10", "B1:B10*2")
    b = ArrayFormula("A1:A10", "B1:B10*2")
    assert a == b


def test_equality_different_ref() -> None:
    a = ArrayFormula("A1:A10", "B1:B10*2")
    b = ArrayFormula("A1:A20", "B1:B10*2")
    assert a != b


def test_equality_different_text() -> None:
    a = ArrayFormula("A1:A10", "B1:B10*2")
    b = ArrayFormula("A1:A10", "B1:B10*3")
    assert a != b


def test_equality_against_other_type() -> None:
    a = ArrayFormula("A1:A10", "B1:B10*2")
    assert a != "B1:B10*2"
    assert a != ("A1:A10", "B1:B10*2")


def test_repr_format() -> None:
    af = ArrayFormula("A1:A10", "B1:B10*2")
    assert repr(af) == "ArrayFormula(ref='A1:A10', text='B1:B10*2')"


def test_hashable() -> None:
    af = ArrayFormula("A1:A10", "B1:B10*2")
    assert hash(af) == hash(ArrayFormula("A1:A10", "B1:B10*2"))
    s = {af, ArrayFormula("A1:A10", "B1:B10*2")}
    assert len(s) == 1


# ----------------------------------------------------------------------
# 2) Cell.value setter / getter contract
# ----------------------------------------------------------------------


def test_setter_populates_metadata() -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    af = ArrayFormula("A1:A10", "B1:B10*2")
    ws["A1"].value = af
    cell = ws["A1"]
    assert cell._formula_type == "array"
    assert cell._array_ref == "A1:A10"
    assert cell._formula_text == "B1:B10*2"


def test_getter_returns_array_formula_instance() -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    af = ArrayFormula("A1:A10", "B1:B10*2")
    ws["A1"] = af
    val = ws["A1"].value
    assert isinstance(val, ArrayFormula)
    assert val.ref == "A1:A10"
    assert val.text == "B1:B10*2"


def test_spill_children_register_as_pending(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = ArrayFormula("A1:A3", "B1:B3*2")
    # The master + every other cell in the spill range should be on
    # the pending map.
    pending = ws._pending_array_formulas  # noqa: SLF001
    assert pending[(1, 1)][0] == "array"
    assert pending[(2, 1)][0] == "spill_child"
    assert pending[(3, 1)][0] == "spill_child"


def test_spill_child_value_returns_none() -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = ArrayFormula("A1:A3", "B1:B3*2")
    # A2 and A3 are inside the spill range — getter returns None.
    assert ws["A2"].value is None
    assert ws["A3"].value is None


def test_replacing_array_with_plain_clears_metadata() -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = ArrayFormula("A1:A3", "B1:B3*2")
    # Now overwrite with a plain value.
    ws["A1"] = 42
    cell = ws["A1"]
    assert cell._formula_type is None
    assert cell._array_ref is None
    assert cell.value == 42


# ----------------------------------------------------------------------
# 3) Round-trip via write mode
# ----------------------------------------------------------------------


def test_round_trip_write_mode(tmp_path: Path) -> None:
    p = tmp_path / "wm_array.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = ArrayFormula("A1:A3", "B1:B3*2")
    ws["B1"] = 1
    ws["B2"] = 2
    ws["B3"] = 3
    wb.save(str(p))

    reloaded = wolfxl.load_workbook(str(p))
    a1 = reloaded.active["A1"].value
    assert isinstance(a1, ArrayFormula)
    assert a1.ref == "A1:A3"
    assert a1.text == "B1:B3*2"
    # Spill children are None.
    assert reloaded.active["A2"].value is None
    assert reloaded.active["A3"].value is None
    # Untouched neighbor cells survive.
    assert reloaded.active["B1"].value == 1
    assert reloaded.active["B3"].value == 3
    assert reloaded.active.array_formulae == {"A1": "A1:A3"}


def test_array_formulae_uses_reader_index_not_grid_scan() -> None:
    class FakeReader:
        def read_sheet_array_formulas(self, sheet: str) -> dict[str, dict[str, str]]:
            assert sheet == "Sheet"
            return {"A1": {"kind": "array", "ref": "A1:A3"}}

        def read_cell_array_formula(self, sheet: str, coord: str) -> None:
            raise AssertionError(f"unexpected per-cell array formula probe for {sheet}!{coord}")

    wb = wolfxl.Workbook()
    ws = wb.active
    ws["ZZ2000"] = "force a large sparse used range"
    wb._rust_reader = FakeReader()  # noqa: SLF001

    assert ws.array_formulae == {"A1": "A1:A3"}


def test_array_formulae_excludes_overwritten_reader_formula(tmp_path: Path) -> None:
    src = tmp_path / "src.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = ArrayFormula("A1:A3", "B1:B3*2")
    wb.save(str(src))

    loaded = wolfxl.load_workbook(str(src), modify=True)
    loaded.active["A1"] = 123

    assert loaded.active.array_formulae == {}


def test_round_trip_modify_mode(tmp_path: Path) -> None:
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = "plain"
    wb.active["B1"] = 1
    wb.active["B2"] = 2
    wb.active["B3"] = 3
    wb.save(str(src))

    wb = wolfxl.load_workbook(str(src), modify=True)
    wb.active["A1"] = ArrayFormula("A1:A3", "B1:B3*2")
    wb.save(str(dst))

    reloaded = wolfxl.load_workbook(str(dst))
    a1 = reloaded.active["A1"].value
    assert isinstance(a1, ArrayFormula)
    assert a1.ref == "A1:A3"
    assert a1.text == "B1:B3*2"
    # B-column values survive the patch.
    assert reloaded.active["B1"].value == 1
    assert reloaded.active["B2"].value == 2
    assert reloaded.active["B3"].value == 3


def test_xml_emits_array_formula(tmp_path: Path) -> None:
    """Sanity check: byte-level XML carries the right ``<f t="array">``."""
    import zipfile

    p = tmp_path / "xml.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = ArrayFormula("A1:A3", "B1:B3*2")
    wb.save(str(p))

    with zipfile.ZipFile(p) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert '<f t="array" ref="A1:A3">B1:B3*2</f>' in sheet
    # Spill children show up as bare `<c r=".."/>`.
    assert '<c r="A2"/>' in sheet
    assert '<c r="A3"/>' in sheet
