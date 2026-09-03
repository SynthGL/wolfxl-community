from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest

import wolfxl
from wolfxl.operations.cli import (
    EXIT_INVALID_REQUEST,
    EXIT_OPERATION_FAILED,
    EXIT_SUCCESS,
    main,
)


def _write_sample_workbook(path: Path, value: str = "test") -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = value
    wb.save(path)


def test_guard_cli_positional_and_flags(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    w1 = tmp_path / "w1.xlsx"
    w2 = tmp_path / "w2.xlsx"
    _write_sample_workbook(w1)
    _write_sample_workbook(w2)

    # Positional
    rc = main(["guard", str(w1), str(w2)])
    assert rc == EXIT_SUCCESS
    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert data["status"] == "passed"
    assert data["issue_count"] == 0
    assert data["output"] is None

    # Flags with output
    report_file = tmp_path / "report.json"
    rc = main(["guard", "--before", str(w1), "--after", str(w2), "--output", str(report_file)])
    assert rc == EXIT_SUCCESS
    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert data["status"] == "passed"
    assert report_file.exists()
    full_report = json.loads(report_file.read_text(encoding="utf-8"))
    assert full_report["status"] == "passed"


def test_compare_cli_positional_and_flags(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    w1 = tmp_path / "w1.xlsx"
    w2 = tmp_path / "w2.xlsx"
    _write_sample_workbook(w1)
    _write_sample_workbook(w2)

    rc = main(["compare", str(w1), str(w2)])
    assert rc == EXIT_SUCCESS
    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert data["status"] == "passed"
    assert data["result"]["passed"] is True
    assert data["result"]["issue_count"] == 0


def test_compare_workbooks_python_api(tmp_path: Path) -> None:
    w1 = tmp_path / "w1.xlsx"
    w2 = tmp_path / "w2.xlsx"
    _write_sample_workbook(w1)
    _write_sample_workbook(w2)

    comparison = wolfxl.compare_workbooks(w1, w2)
    assert comparison.passed is True
    assert comparison.issue_count == 0
    assert comparison.status == "passed"
    assert comparison.before.filename == "w1.xlsx"
    assert comparison.after.filename == "w2.xlsx"
