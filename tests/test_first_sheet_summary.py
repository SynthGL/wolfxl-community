from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

import wolfxl

pytest.importorskip("wolfxl._rust")


def test_first_sheet_value_summary_accepts_pathlike(tmp_path: Path) -> None:
    path = tmp_path / "values.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.append([1, "customer", 2.5])
    ws.append([2, None, 3.5])
    wb.save(path)
    wb.close()

    assert wolfxl.read_first_sheet_value_summary(path) == {
        "rows": 2,
        "numeric_checksum": 9.0,
    }


def test_first_sheet_formula_summary_accepts_pathlike(tmp_path: Path) -> None:
    path = tmp_path / "formulas.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.append([1, 2, "=A1+B1", "label", "=SUM(A1:B1)"])
    ws.append([2, 4, "=A2+B2", "label", "=SUM(A2:B2)"])
    wb.save(path)
    wb.close()

    assert wolfxl.read_first_sheet_formula_summary(path) == {
        "rows": 2,
        "first_col_numeric_checksum": 3.0,
        "formula_cells": 4,
    }
