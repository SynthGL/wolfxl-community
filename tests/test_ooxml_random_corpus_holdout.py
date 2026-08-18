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
        / "audit_ooxml_random_corpus_holdout.py"
    )
    spec = importlib.util.spec_from_file_location(
        "audit_ooxml_random_corpus_holdout", script
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


holdout = _load_module()


def _write_bucket_report(
    path: Path,
    *,
    workbook_paths: list[Path],
    bucket_by_workbook: dict[Path, list[str]],
) -> Path:
    bucket_fixtures: dict[str, list[str]] = {}
    for workbook_path, buckets in bucket_by_workbook.items():
        for bucket in buckets:
            bucket_fixtures.setdefault(bucket, []).append(str(workbook_path))
    payload = {
        "ready": True,
        "workbook_count": len(workbook_paths),
        "skipped_workbook_count": 0,
        "missing_buckets": [],
        "bucket_fixtures": bucket_fixtures,
        "workbooks": [
            {
                "path": str(workbook_path),
                "buckets": bucket_by_workbook.get(workbook_path, []),
            }
            for workbook_path in workbook_paths
        ],
    }
    path.write_text(json.dumps(payload))
    return path


def _write_portfolio(path: Path, reports: list[Path]) -> Path:
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "source_reports": [
                    {"path": str(report), "contributes_source": True}
                    for report in reports
                ],
            }
        )
    )
    return path


def test_random_holdout_is_deterministic_and_counts_sources(tmp_path: Path) -> None:
    workbooks = []
    for index in range(6):
        workbook = tmp_path / f"book-{index}.xlsx"
        workbook.write_text("placeholder")
        workbooks.append(workbook)
    report_a = _write_bucket_report(
        tmp_path / "a.json",
        workbook_paths=workbooks[:3],
        bucket_by_workbook={
            workbooks[0]: ["excel_authored", "chart_or_chart_style"],
            workbooks[1]: ["excel_authored"],
            workbooks[2]: ["external_tool_authored"],
        },
    )
    report_b = _write_bucket_report(
        tmp_path / "b.json",
        workbook_paths=workbooks[3:],
        bucket_by_workbook={
            workbooks[3]: ["macro_vba"],
            workbooks[4]: ["table_structured_ref_or_validation"],
            workbooks[5]: ["workbook_global_state"],
        },
    )
    portfolio = _write_portfolio(tmp_path / "portfolio.json", [report_a, report_b])

    first = holdout.audit_random_holdout(
        portfolio,
        sample_size=4,
        seed="stable",
        min_sample_size=4,
        min_sources=2,
    )
    second = holdout.audit_random_holdout(
        portfolio,
        sample_size=4,
        seed="stable",
        min_sample_size=4,
        min_sources=2,
    )

    assert first["ready"] is True
    assert first["selected_workbooks"] == second["selected_workbooks"]
    assert first["population_count"] == 6
    assert first["selected_count"] == 4
    assert first["selected_source_count"] == 2
    assert first["missing_selected_files"] == []
    assert first["threshold_failures"] == []


def test_random_holdout_reports_threshold_and_missing_file_failures(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.xlsx"
    missing = tmp_path / "missing.xlsx"
    existing.write_text("placeholder")
    report = _write_bucket_report(
        tmp_path / "source.json",
        workbook_paths=[existing, missing],
        bucket_by_workbook={
            existing: ["excel_authored"],
            missing: ["external_tool_authored"],
        },
    )
    portfolio = _write_portfolio(tmp_path / "portfolio.json", [report])

    result = holdout.audit_random_holdout(
        portfolio,
        sample_size=2,
        seed="stable",
        min_sample_size=3,
        min_sources=2,
    )

    assert result["ready"] is False
    assert result["missing_selected_files"] == [str(missing)]
    assert result["threshold_failures"] == [
        {"id": "min_sample_size", "actual": 2, "expected_at_least": 3},
        {"id": "min_sources", "actual": 1, "expected_at_least": 2},
    ]


def test_random_holdout_can_stage_selected_workbooks(tmp_path: Path) -> None:
    workbook = tmp_path / "book one.xlsx"
    workbook.write_text("placeholder")
    report = _write_bucket_report(
        tmp_path / "source.json",
        workbook_paths=[workbook],
        bucket_by_workbook={workbook: ["excel_authored"]},
    )
    portfolio = _write_portfolio(tmp_path / "portfolio.json", [report])
    stage_dir = tmp_path / "stage"

    result = holdout.audit_random_holdout(
        portfolio,
        sample_size=1,
        seed="stable",
        min_sample_size=1,
        min_sources=1,
        stage_dir=stage_dir,
    )

    assert result["ready"] is True
    assert result["staged_workbooks"][0]["status"] == "copied"
    assert Path(result["staged_workbooks"][0]["path"]).is_file()
    assert "book_one.xlsx" in result["staged_workbooks"][0]["path"]


def test_random_holdout_resolves_repo_relative_workbook_paths(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    workbook = repo / "tests" / "fixtures" / "book.xlsx"
    workbook.parent.mkdir(parents=True)
    workbook.write_text("placeholder")
    report_dir = repo / "docs" / "fidelity" / "evidence" / "sample"
    report_dir.mkdir(parents=True)
    report = _write_bucket_report(
        report_dir / "report.json",
        workbook_paths=[Path("tests/fixtures/book.xlsx")],
        bucket_by_workbook={Path("tests/fixtures/book.xlsx"): ["excel_authored"]},
    )
    portfolio = _write_portfolio(report_dir / "portfolio.json", [report])
    monkeypatch.chdir(repo)

    result = holdout.audit_random_holdout(
        portfolio,
        sample_size=1,
        seed="stable",
        min_sample_size=1,
        min_sources=1,
    )

    assert result["ready"] is True
    assert result["missing_selected_files"] == []
    assert result["selected_workbooks"][0]["path"] == str(workbook)


def test_random_holdout_resolves_relative_reports_and_workbooks(
    tmp_path: Path,
) -> None:
    report_dir = tmp_path / "reports"
    workbook_dir = tmp_path / "books"
    report_dir.mkdir()
    workbook_dir.mkdir()
    workbook = workbook_dir / "book one.xlsx"
    workbook.write_text("placeholder")
    report = report_dir / "source.json"
    report.write_text(
        json.dumps(
            {
                "ready": True,
                "workbooks": [
                    {
                        "path": "../books/book one.xlsx",
                        "buckets": ["excel_authored"],
                    }
                ],
                "bucket_fixtures": {
                    "chart_or_chart_style": ["../books/book one.xlsx"]
                },
            }
        )
    )
    portfolio = tmp_path / "portfolio.json"
    portfolio.write_text(
        json.dumps(
            {
                "ready": True,
                "source_reports": [
                    {"path": "reports/source.json", "contributes_source": True},
                    {"path": str(report), "contributes_source": True},
                ],
            }
        )
    )

    result = holdout.audit_random_holdout(
        portfolio,
        sample_size=1,
        seed="stable",
        min_sample_size=1,
        min_sources=1,
        stage_dir=tmp_path / "stage",
    )

    assert result["ready"] is True
    assert result["population_count"] == 1
    assert result["selected_source_count"] == 1
    assert result["selected_workbooks"][0]["path"] == str(workbook.resolve())
    assert result["selected_workbooks"][0]["source_reports"] == [str(report.resolve())]
    assert result["selected_workbooks"][0]["buckets"] == [
        "chart_or_chart_style",
        "excel_authored",
    ]
    assert result["missing_selected_files"] == []
    assert result["staged_workbooks"][0]["status"] == "copied"


def test_random_holdout_skips_non_contributing_portfolio_reports(
    tmp_path: Path,
) -> None:
    included = tmp_path / "included.xlsx"
    excluded = tmp_path / "excluded.xlsx"
    included.write_text("placeholder")
    excluded.write_text("placeholder")
    included_report = _write_bucket_report(
        tmp_path / "included.json",
        workbook_paths=[included],
        bucket_by_workbook={included: ["excel_authored"]},
    )
    excluded_report = _write_bucket_report(
        tmp_path / "excluded.json",
        workbook_paths=[excluded],
        bucket_by_workbook={excluded: ["external_tool_authored"]},
    )
    portfolio = tmp_path / "portfolio.json"
    portfolio.write_text(
        json.dumps(
            {
                "ready": True,
                "source_reports": [
                    {"path": str(included_report), "contributes_source": True},
                    {"path": str(excluded_report), "contributes_source": False},
                ],
            }
        )
    )

    result = holdout.audit_random_holdout(
        portfolio,
        sample_size=10,
        seed="stable",
        min_sample_size=1,
        min_sources=1,
    )

    assert result["ready"] is True
    assert result["population_count"] == 1
    assert [item["path"] for item in result["selected_workbooks"]] == [str(included)]
    assert result["selected_source_paths"] == [str(included_report.resolve())]
