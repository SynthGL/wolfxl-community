from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "merge_ooxml_fidelity_mutation_reports.py"
    )
    spec = importlib.util.spec_from_file_location("merge_ooxml_fidelity_mutation_reports", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


merge = _load_module()


def _write_report(path: Path, *, fixture: str, mutation: str, status: str = "passed") -> None:
    path.write_text(
        json.dumps(
            {
                "fixture_dir": "/fixtures",
                "output_dir": str(path.parent),
                "mutations": [mutation],
                "recursive": True,
                "selected_fixture_patterns": [fixture],
                "exclude_fixture_patterns": [],
                "skip_invalid_source": False,
                "compact_report": True,
                "phase_timings": False,
                "progress": False,
                "unselected_fixture_count": 0,
                "unselected_fixtures": [],
                "skipped_fixture_count": 0,
                "skipped_fixtures": [],
                "result_count": 1,
                "failure_count": 0 if status == "passed" else 1,
                "status_counts": {status: 1},
                "results": [
                    {
                        "fixture": fixture,
                        "mutation": mutation,
                        "status": status,
                        "issue_count": 0,
                        "issues": [],
                        "expected_issue_count": 0,
                        "expected_issues": [],
                        "error": None,
                    }
                ],
            }
        )
        + "\n"
    )


def test_merge_reports_combines_results_and_counts(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_report(first, fixture="b.xlsx", mutation="rename_first_sheet")
    _write_report(second, fixture="a.xlsx", mutation="style_cell")

    merged = merge.merge_reports(
        [first, second],
        mutations=["style_cell", "rename_first_sheet"],
        output_dir="/merged",
    )

    assert merged["fixture_dir"] == "/fixtures"
    assert merged["output_dir"] == "/merged"
    assert merged["mutations"] == ["style_cell", "rename_first_sheet"]
    assert merged["result_count"] == 2
    assert merged["failure_count"] == 0
    assert merged["status_counts"] == {"passed": 2}
    assert [(result["fixture"], result["mutation"]) for result in merged["results"]] == [
        ("a.xlsx", "style_cell"),
        ("b.xlsx", "rename_first_sheet"),
    ]


def test_merge_reports_rejects_different_fixture_dirs(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_report(first, fixture="a.xlsx", mutation="style_cell")
    _write_report(second, fixture="a.xlsx", mutation="rename_first_sheet")
    payload = json.loads(second.read_text())
    payload["fixture_dir"] = "/other-fixtures"
    second.write_text(json.dumps(payload) + "\n")

    try:
        merge.merge_reports([first, second])
    except ValueError as exc:
        assert "fixture_dir" in str(exc)
    else:
        raise AssertionError("expected fixture_dir mismatch to fail")


def test_merge_cli_writes_output(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    output = tmp_path / "merged" / "report.json"
    _write_report(first, fixture="a.xlsx", mutation="style_cell")

    code = merge.main([str(first), "--output", str(output), "--mutation", "style_cell"])

    assert code == 0
    payload = json.loads(output.read_text())
    assert payload["result_count"] == 1
    assert payload["merged_report_count"] == 1
    assert payload["merged_report_names"] == [tmp_path.name]
