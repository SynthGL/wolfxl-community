"""T1 PR5 — Worksheet writes: tables, data_validations, conditional_formatting.

Write mode (``Workbook()`` → ``ws.add_table``, ``ws.data_validations.append``,
``ws.conditional_formatting.add`` → ``wb.save``) must produce a valid xlsx
that openpyxl can read with all three features intact. Modify mode raises
``NotImplementedError`` with a T1.5 pointer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from wolfxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule
from wolfxl.worksheet.datavalidation import DataValidation
from wolfxl.worksheet.table import Table, TableColumn, TableStyleInfo

from wolfxl import Font, Workbook

openpyxl = pytest.importorskip("openpyxl")


def test_add_table_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "wolfxl_table.xlsx"
    wb = Workbook()
    ws = wb.active
    # Build a minimal data block for the table to cover.
    headers = ["Name", "Amount"]
    ws.append(headers)
    for i in range(1, 4):
        ws.append([f"R{i}", i * 10])

    t = Table(
        name="Sales",
        displayName="Sales",
        ref="A1:B4",
        tableStyleInfo=TableStyleInfo(name="TableStyleLight9"),
        tableColumns=[TableColumn(id=1, name="Name"), TableColumn(id=2, name="Amount")],
    )
    ws.add_table(t)
    # Pre-save: ws.tables already knows about it.
    assert "Sales" in ws.tables
    assert ws.tables["Sales"].ref == "A1:B4"
    wb.save(str(path))

    op_wb = openpyxl.load_workbook(path)
    op_ws = op_wb.active
    assert "Sales" in op_ws.tables
    assert op_ws.tables["Sales"].ref == "A1:B4"
    op_wb.close()


def test_table_no_style_and_totals_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "wolfxl_table_no_style_totals.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Item", "Count"])
    ws.append(["Apples", 2])
    ws.append(["Oranges", 3])
    ws.append(["Total", 5])

    table = Table(
        name="PlainTotals",
        displayName="PlainTotals",
        ref="A1:B4",
        tableColumns=[TableColumn(id=1, name="Item"), TableColumn(id=2, name="Count")],
    )
    table.totalsRowCount = 1
    ws.add_table(table)
    wb.save(str(path))

    op_wb = openpyxl.load_workbook(path)
    op_table = op_wb.active.tables["PlainTotals"]
    assert op_table.tableStyleInfo is None
    assert op_table.totalsRowCount == 1
    op_wb.close()


def test_data_validation_append_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "wolfxl_dv.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "Pick"
    dv = DataValidation(
        type="list",
        formula1='"Red,Blue,Green"',
        sqref="A2:A10",
        allowBlank=True,
    )
    ws.data_validations.append(dv)
    # Pre-save visibility.
    assert len(ws.data_validations) == 1
    wb.save(str(path))

    op_wb = openpyxl.load_workbook(path)
    op_ws = op_wb.active
    assert len(op_ws.data_validations.dataValidation) == 1
    op_dv = op_ws.data_validations.dataValidation[0]
    assert op_dv.type == "list"
    assert op_dv.formula1 == '"Red,Blue,Green"'


def test_conditional_formatting_add_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "wolfxl_cf.xlsx"
    wb = Workbook()
    ws = wb.active
    for i in range(1, 11):
        ws[f"B{i}"] = i * 5
    rule = CellIsRule(operator="greaterThan", formula=["50"])
    ws.conditional_formatting.add("B2:B10", rule)
    assert len(ws.conditional_formatting) == 1
    wb.save(str(path))

    op_wb = openpyxl.load_workbook(path)
    op_ws = op_wb.active
    entries = list(op_ws.conditional_formatting)
    assert any(
        any(getattr(r, "type", None) == "cellIs" for r in e.rules)
        for e in entries
    ), entries
    op_wb.close()


@pytest.mark.parametrize(
    ("rule", "rule_type"),
    [
        (DataBarRule(start_type="min", end_type="max", color="638EC6"), "dataBar"),
        (
            ColorScaleRule(
                start_type="min",
                start_color="AA0000",
                mid_type="percentile",
                mid_value=50,
                mid_color="FFFF00",
                end_type="max",
                end_color="00AA00",
            ),
            "colorScale",
        ),
    ],
)
def test_conditional_formatting_visual_rules_round_trip(
    tmp_path: Path,
    rule: object,
    rule_type: str,
) -> None:
    path = tmp_path / f"wolfxl_cf_{rule_type}.xlsx"
    wb = Workbook()
    ws = wb.active
    for i in range(1, 6):
        ws[f"B{i}"] = i
    ws.conditional_formatting.add("B1:B5", rule)
    wb.save(str(path))

    op_wb = openpyxl.load_workbook(path)
    entries = list(op_wb.active.conditional_formatting)
    assert any(
        any(getattr(r, "type", None) == rule_type for r in e.rules)
        for e in entries
    ), entries
    op_wb.close()


def test_double_underline_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "wolfxl_double_underline.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "Double"
    ws["A1"].font = Font(underline="double")
    wb.save(str(path))

    op_wb = openpyxl.load_workbook(path)
    assert op_wb.active["A1"].font.underline == "double"
    op_wb.close()


def test_add_table_rejects_non_table() -> None:
    wb = Workbook()
    ws = wb.active
    with pytest.raises(TypeError, match="Table"):
        ws.add_table("not a table")  # type: ignore[arg-type]


def test_modify_mode_add_table_queues(tmp_path: Path) -> None:
    """RFC-024 shipped: add_table works in modify mode. The queue lands
    in ``_pending_tables``; ``save()`` flushes it through the patcher.
    Round-trip coverage in ``tests/test_tables_modify.py``.
    """
    path = tmp_path / "exists.xlsx"
    openpyxl.Workbook().save(path)

    wb = Workbook._from_patcher(str(path))
    ws = wb.active
    t = Table(name="X", ref="A1:B2")
    ws.add_table(t)
    assert len(ws._pending_tables) == 1  # noqa: SLF001
    wb.close()


def test_modify_mode_dv_append_queues(tmp_path: Path) -> None:
    """RFC-025 shipped: DV append works in modify mode. The queue lands in
    ``_pending_data_validations``; ``save()`` flushes it through the
    patcher. Round-trip coverage in ``tests/test_modify_data_validations.py``.
    """
    path = tmp_path / "exists_dv.xlsx"
    openpyxl.Workbook().save(path)

    wb = Workbook._from_patcher(str(path))
    ws = wb.active
    dv = DataValidation(type="list", formula1='"a,b"', sqref="A1:A2")
    ws.data_validations.append(dv)
    assert len(ws._pending_data_validations) == 1  # noqa: SLF001
    wb.close()


def test_modify_mode_queues_cf_add(tmp_path: Path) -> None:
    path = tmp_path / "exists_cf.xlsx"
    openpyxl.Workbook().save(path)

    wb = Workbook._from_patcher(str(path))
    ws = wb.active
    ws.conditional_formatting.add("A1:A10", CellIsRule(operator="equal", formula=["1"]))
    assert len(ws._pending_conditional_formats) == 1  # noqa: SLF001
    wb.close()
