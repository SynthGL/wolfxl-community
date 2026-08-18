"""Native reader comparisons against openpyxl-shaped expectations."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

openpyxl = pytest.importorskip("openpyxl")
openpyxl_formatting_rule = pytest.importorskip("openpyxl.formatting.rule")
openpyxl_datavalidation = pytest.importorskip("openpyxl.worksheet.datavalidation")
openpyxl_hyperlink = pytest.importorskip("openpyxl.worksheet.hyperlink")
openpyxl_table = pytest.importorskip("openpyxl.worksheet.table")
wolfxl = pytest.importorskip("wolfxl")

DataValidation = openpyxl_datavalidation.DataValidation
CellIsRule = openpyxl_formatting_rule.CellIsRule
FormulaRule = openpyxl_formatting_rule.FormulaRule
Hyperlink = openpyxl_hyperlink.Hyperlink
Table = openpyxl_table.Table
TableStyleInfo = openpyxl_table.TableStyleInfo


def _make_shadow_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Main"
    ws["A1"] = "label"
    ws["B1"] = "amount"
    ws["A2"] = "alpha"
    ws["B2"] = 1234.5
    ws["B2"].number_format = "#,##0.00"
    ws["A3"] = "when"
    ws["B3"] = dt.datetime(2024, 3, 5, 9, 45)
    ws["A4"] = "formula"
    ws["B4"] = "=B2*2"
    ws["A5"] = "link"
    ws["A5"].hyperlink = Hyperlink(
        ref="A5",
        target="https://example.com/shadow",
        tooltip="Shadow link",
    )
    ws["B5"] = "jump"
    ws["B5"].hyperlink = Hyperlink(ref="B5", location="Other!A1", display="Other")
    ws["A6"] = "note"
    ws["A6"].comment = openpyxl.comments.Comment("Shadow note", "Wolf")
    ws.row_dimensions[6].height = 24
    ws.row_dimensions[6].hidden = True
    ws.row_dimensions[6].outlineLevel = 1
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["C"].hidden = True
    ws.column_dimensions["C"].outlineLevel = 2
    dv = DataValidation(type="list", formula1='"Red,Blue"', allow_blank=True)
    dv.add("C2:C6")
    ws.add_data_validation(dv)
    table = Table(displayName="ShadowTable", ref="A1:B4")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    ws.add_table(table)
    ws.conditional_formatting.add(
        "B2:B4",
        CellIsRule(operator="greaterThan", formula=["100"]),
    )
    ws.conditional_formatting.add("B2:B4", FormulaRule(formula=["$B2=1234.5"]))
    ws.merge_cells("D1:E1")
    ws.freeze_panes = "B2"

    other = wb.create_sheet("Other")
    other["A1"] = True
    other["B1"] = "tail"

    wb.save(path)
    wb.close()


def _workbook_snapshot(wb: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"sheetnames": list(wb.sheetnames), "sheets": {}}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        values = list(ws.iter_rows(values_only=True))
        number_formats = {
            coord: ws[coord].number_format
            for coord in ("B2", "B3")
            if ws.max_row >= int(coord[1:])
        }
        merged = {str(r) for r in ws.merged_cells.ranges}
        hyperlinks = {
            coord: (
                ws[coord].hyperlink.target,
                ws[coord].hyperlink.location,
                _normalize_hyperlink_display(ws[coord].hyperlink.display, ws[coord].value),
                ws[coord].hyperlink.tooltip,
            )
            for coord in ("A5", "B5")
            if ws[coord].hyperlink is not None
        }
        comments = {
            coord: (ws[coord].comment.text, ws[coord].comment.author)
            for coord in ("A6",)
            if ws[coord].comment is not None
        }
        data_validations = getattr(
            ws.data_validations, "dataValidation", ws.data_validations
        )
        validations = [
            (dv.type, _strip_formula_prefix(dv.formula1), dv.allowBlank, str(dv.sqref))
            for dv in data_validations
        ]
        table_values = ws.tables.values()
        tables = {
            table.name: (
                table.ref,
                [column.name for column in table.tableColumns],
                table.tableStyleInfo.name if table.tableStyleInfo else None,
            )
            for table in table_values
        }
        conditional_formats = [
            (
                str(entry.sqref),
                [(rule.type, rule.operator, tuple(rule.formula)) for rule in entry.rules],
            )
            for entry in ws.conditional_formatting
        ]
        conditional_formats = [
            (
                sqref,
                [
                    (
                        rule_type,
                        operator,
                        tuple(_strip_formula_prefix(formula) for formula in formulas),
                    )
                    for rule_type, operator, formulas in rules
                ],
            )
            for sqref, rules in conditional_formats
        ]
        out["sheets"][sheet_name] = {
            "values": values,
            "number_formats": number_formats,
            "merged": merged,
            "hyperlinks": hyperlinks,
            "comments": comments,
            "freeze_panes": ws.freeze_panes,
            "row_height": ws.row_dimensions[6].height,
            "column_width": ws.column_dimensions["C"].width or 13.0,
            "row_hidden": ws.row_dimensions[6].hidden,
            "column_hidden": ws.column_dimensions["C"].hidden,
            "row_outline_level": ws.row_dimensions[6].outline_level,
            "column_outline_level": ws.column_dimensions["C"].outline_level,
            "data_validations": validations,
            "tables": tables,
            "conditional_formats": conditional_formats,
        }
    return out


def _strip_formula_prefix(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("="):
        return value[1:]
    return value


def _normalize_hyperlink_display(display: Any, cell_value: Any) -> Any:
    if display == cell_value:
        return None
    return display


def test_native_reader_snapshot_matches_openpyxl(
    tmp_path: Path,
) -> None:
    path = tmp_path / "shadow.xlsx"
    _make_shadow_xlsx(path)

    default = openpyxl.load_workbook(path, data_only=False)
    try:
        default_snapshot = _workbook_snapshot(default)
    finally:
        default.close()

    native = wolfxl.load_workbook(path, data_only=False)
    try:
        assert native._rust_reader.__class__.__name__ == "NativeXlsxBook"  # noqa: SLF001
        native_snapshot = _workbook_snapshot(native)
    finally:
        native.close()

    assert native_snapshot == default_snapshot


def test_default_eager_xlsx_reader_is_native(
    tmp_path: Path,
) -> None:
    path = tmp_path / "native-default.xlsx"
    _make_shadow_xlsx(path)

    wb = wolfxl.load_workbook(path, data_only=False)
    try:
        assert wb._rust_reader.__class__.__name__ == "NativeXlsxBook"  # noqa: SLF001
    finally:
        wb.close()
