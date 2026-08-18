"""High-use openpyxl workflow parity checks.

These tests pin everyday Workbook/Worksheet/Cell idioms that downstream code
expects to survive a one-line ``openpyxl`` -> ``wolfxl`` import swap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import wolfxl

openpyxl = pytest.importorskip("openpyxl")


def _close(workbook: Any) -> None:
    close = getattr(workbook, "close", None)
    if close is not None:
        close()


def _high_use_workbook_flow(xl: Any, path: Path) -> dict[str, Any]:
    wb = xl.Workbook()
    transactions = wb.active
    transactions.title = "Transactions"
    lookup = wb.create_sheet("Lookup")
    summary = wb.create_sheet("Summary", 0)
    raw = wb.create_sheet("Raw Data", index=1)

    transactions.append(["Date", "Customer", "Amount", "Status"])
    transactions.append(["2026-01-01", "Acme", 125.5, "Booked"])
    transactions.append({"A": "2026-01-02", "B": "Beta", 3: 99, "D": "Pending"})
    transactions.cell(row=4, column=1, value="2026-01-03")
    transactions.cell(row=4, column=2, value="Coda")
    transactions.cell(row=4, column=3, value=250)
    transactions["D4"] = "Booked"
    transactions["F2"] = "manual review"

    lookup.append(["code", "label"])
    lookup.append(["B", "Booked"])
    lookup.append(["P", "Pending"])

    summary["A1"] = "Executive Summary"
    summary.merge_cells("A1:B1")
    summary["A3"] = "Rows"
    summary["B3"] = transactions.max_row - 1
    summary["A4"] = "Largest amount"
    summary["B4"] = 250

    raw["A1"] = "source"
    raw["B1"] = "status"
    raw.append(["import.csv", "loaded"])

    in_memory = {
        "sheetnames": tuple(wb.sheetnames),
        "active_title": wb.active.title,
        "indexes": {
            "Summary": wb.index(summary),
            "Raw Data": wb.index(raw),
            "Transactions": wb.index(transactions),
            "Lookup": wb.index(lookup),
        },
        "lookup_by_title": wb["Transactions"].title,
        "cell_identity": (
            transactions["C2"].coordinate,
            transactions["C2"].row,
            transactions["C2"].column,
            transactions.cell(row=2, column=3).value,
        ),
        "range_values": tuple(
            tuple(cell.value for cell in row) for row in transactions["A1:D3"]
        ),
        "row_two": tuple(cell.value for cell in transactions[2]),
        "column_c": tuple(cell.value for cell in transactions["C"]),
        "dimensions": (
            transactions.max_row,
            transactions.max_column,
            transactions.calculate_dimension(),
            transactions.dimensions,
        ),
        "summary_merge": (
            summary["A1"].value,
            summary["B1"].value,
            type(summary["B1"]).__name__,
            tuple(sorted(str(rng) for rng in summary.merged_cells.ranges)),
        ),
    }

    wb.save(path)
    _close(wb)
    return in_memory


def _read_saved_summary(xl: Any, path: Path) -> dict[str, Any]:
    wb = xl.load_workbook(path, data_only=False)
    transactions = wb["Transactions"]
    summary = wb["Summary"]
    result = {
        "sheetnames": tuple(wb.sheetnames),
        "indexes": {
            "Summary": wb.index(summary),
            "Raw Data": wb.index(wb["Raw Data"]),
            "Transactions": wb.index(transactions),
            "Lookup": wb.index(wb["Lookup"]),
        },
        "transactions_rows": tuple(
            tuple(row)
            for row in transactions.iter_rows(
                min_row=1,
                max_row=4,
                min_col=1,
                max_col=6,
                values_only=True,
            )
        ),
        "transactions_dimensions": (
            transactions.max_row,
            transactions.max_column,
            transactions.calculate_dimension(),
            transactions.dimensions,
        ),
        "summary_values": tuple(
            tuple(row)
            for row in summary.iter_rows(
                min_row=1,
                max_row=4,
                min_col=1,
                max_col=2,
                values_only=True,
            )
        ),
        "summary_merge": (
            summary["A1"].value,
            summary["B1"].value,
            type(summary["B1"]).__name__,
            tuple(sorted(str(rng) for rng in summary.merged_cells.ranges)),
        ),
    }
    _close(wb)
    return result


def test_high_use_workbook_flow_matches_openpyxl_in_memory(tmp_path: Path) -> None:
    expected = _high_use_workbook_flow(openpyxl, tmp_path / "openpyxl.xlsx")
    actual = _high_use_workbook_flow(wolfxl, tmp_path / "wolfxl.xlsx")

    assert actual == expected


def test_wolfxl_saved_high_use_workbook_cross_reads_with_openpyxl(
    tmp_path: Path,
) -> None:
    openpyxl_path = tmp_path / "openpyxl.xlsx"
    wolfxl_path = tmp_path / "wolfxl.xlsx"
    _high_use_workbook_flow(openpyxl, openpyxl_path)
    _high_use_workbook_flow(wolfxl, wolfxl_path)

    assert _read_saved_summary(openpyxl, wolfxl_path) == _read_saved_summary(
        openpyxl,
        openpyxl_path,
    )


def test_openpyxl_saved_high_use_workbook_reopens_like_openpyxl(
    tmp_path: Path,
) -> None:
    path = tmp_path / "openpyxl.xlsx"
    _high_use_workbook_flow(openpyxl, path)

    assert _read_saved_summary(wolfxl, path) == _read_saved_summary(openpyxl, path)
