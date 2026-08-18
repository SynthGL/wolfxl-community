"""Real-file open/save/reopen preservation checks.

These fixtures already live in the committed corpus. The test uses openpyxl as
the before/after oracle while WolfXL performs the middle read-modify-save step:

    openpyxl snapshot -> wolfxl.load_workbook(..., modify=True).save(...)
    -> openpyxl snapshot

That catches user-visible semantic drift that can hide behind ZIP-part
preservation: sheet names, dimensions, values/formulas, merged ranges,
comments, tables, and data validations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import warnings

import pytest

openpyxl = pytest.importorskip("openpyxl")
wolfxl = pytest.importorskip("wolfxl")

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class FixtureCase:
    path: Path
    required_signals: frozenset[str]

    @property
    def id(self) -> str:
        try:
            return self.path.relative_to(ROOT).as_posix()
        except ValueError:
            return self.path.as_posix()


FIXTURE_CASES = (
    FixtureCase(
        ROOT
        / "tests"
        / "fixtures"
        / "external_oracle"
        / "openpyxl-table-validation-image-comment.xlsx",
        frozenset({"comments", "tables", "data_validations"}),
    ),
    FixtureCase(
        ROOT
        / "tests"
        / "fixtures"
        / "external_oracle"
        / "npoi-formula-comment-merge-protection.xlsx",
        frozenset({"formulas", "merged_ranges", "comments"}),
    ),
    FixtureCase(
        ROOT
        / "tests"
        / "fixtures"
        / "external_oracle"
        / "real-excel-table-slicers.xlsx",
        frozenset({"formulas", "merged_ranges", "tables"}),
    ),
    FixtureCase(
        ROOT
        / "tests"
        / "parity"
        / "fixtures"
        / "synthgl_snapshot"
        / "time_series"
        / "ilpa_pe_fund_reporting_v1.1.xlsx",
        frozenset({"formulas", "merged_ranges", "multiple_sheets"}),
    ),
)


@pytest.mark.parametrize("case", FIXTURE_CASES, ids=lambda case: case.id)
def test_wolfxl_open_save_reopen_preserves_openpyxl_visible_semantics(
    case: FixtureCase, tmp_path: Path
) -> None:
    """WolfXL modify-save should be semantic no-op for real workbook fixtures."""
    assert case.path.is_file(), f"fixture missing: {case.path}"

    work_path = tmp_path / case.path.name
    saved_path = tmp_path / f"saved-{case.path.name}"
    shutil.copy2(case.path, work_path)

    before = _workbook_snapshot(work_path)
    _assert_required_signals(case, before)

    workbook = wolfxl.load_workbook(work_path, modify=True)
    try:
        workbook.save(saved_path)
    finally:
        workbook.close()

    after = _workbook_snapshot(saved_path)
    assert after == before


def _workbook_snapshot(path: Path) -> dict[str, object]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        workbook = openpyxl.load_workbook(path, data_only=False)
    try:
        return {
            "sheetnames": list(workbook.sheetnames),
            "worksheets": {
                worksheet.title: _worksheet_snapshot(worksheet)
                for worksheet in workbook.worksheets
            },
        }
    finally:
        workbook.close()


def _worksheet_snapshot(worksheet) -> dict[str, object]:  # noqa: ANN001
    return {
        "dimensions": (
            worksheet.max_row,
            worksheet.max_column,
            worksheet.calculate_dimension(),
        ),
        "cells": _cell_snapshot(worksheet),
        "merged_ranges": sorted(str(rng) for rng in worksheet.merged_cells.ranges),
        "comments": _comment_snapshot(worksheet),
        "tables": _table_snapshot(worksheet),
        "data_validations": _data_validation_snapshot(worksheet),
    }


def _cell_snapshot(worksheet) -> dict[str, tuple[object, str]]:  # noqa: ANN001
    cells: dict[str, tuple[object, str]] = {}
    for row in worksheet.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            cells[cell.coordinate] = (cell.value, cell.data_type)
    return cells


def _comment_snapshot(worksheet) -> dict[str, tuple[str, str]]:  # noqa: ANN001
    comments: dict[str, tuple[str, str]] = {}
    for row in worksheet.iter_rows():
        for cell in row:
            if cell.comment is None:
                continue
            comments[cell.coordinate] = (cell.comment.text, cell.comment.author)
    return comments


def _table_snapshot(worksheet) -> dict[str, str]:  # noqa: ANN001
    return {
        name: getattr(table, "ref", str(table))
        for name, table in worksheet.tables.items()
    }


def _data_validation_snapshot(worksheet) -> list[tuple[object, ...]]:  # noqa: ANN001
    validations = getattr(worksheet.data_validations, "dataValidation", []) or []
    return sorted(
        (
            str(validation.sqref),
            validation.type,
            validation.operator,
            validation.formula1,
            validation.formula2,
            bool(validation.allow_blank),
        )
        for validation in validations
    )


def _assert_required_signals(
    case: FixtureCase, snapshot: dict[str, object]
) -> None:
    observed = _observed_signals(snapshot)
    missing = case.required_signals - observed
    assert not missing, (
        f"{case.id} no longer covers expected preservation signals: "
        f"{sorted(missing)}"
    )


def _observed_signals(snapshot: dict[str, object]) -> set[str]:
    worksheets = snapshot["worksheets"]
    assert isinstance(worksheets, dict)

    observed: set[str] = set()
    if len(snapshot["sheetnames"]) > 1:
        observed.add("multiple_sheets")
    for worksheet_snapshot in worksheets.values():
        assert isinstance(worksheet_snapshot, dict)
        cells = worksheet_snapshot["cells"]
        assert isinstance(cells, dict)
        if any(
            isinstance(value, tuple) and value[1] == "f"
            for value in cells.values()
        ):
            observed.add("formulas")
        if worksheet_snapshot["merged_ranges"]:
            observed.add("merged_ranges")
        if worksheet_snapshot["comments"]:
            observed.add("comments")
        if worksheet_snapshot["tables"]:
            observed.add("tables")
        if worksheet_snapshot["data_validations"]:
            observed.add("data_validations")
    return observed
