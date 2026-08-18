from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_ooxml_corpus_portfolio.py"
    spec = importlib.util.spec_from_file_location("audit_ooxml_corpus_portfolio", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


portfolio = _load_module()


def _write_bucket_report(
    path: Path,
    *,
    workbooks: list[str],
    buckets: dict[str, list[str]],
    missing_buckets: Optional[list[str]] = None,
) -> Path:
    payload = {
        "ready": not missing_buckets,
        "workbook_count": len(workbooks),
        "skipped_workbook_count": 0,
        "missing_buckets": [] if missing_buckets is None else missing_buckets,
        "bucket_fixtures": buckets,
        "workbooks": [{"path": workbook} for workbook in workbooks],
    }
    path.write_text(json.dumps(payload))
    return path


def test_corpus_portfolio_accepts_aggregate_bucket_coverage(tmp_path: Path) -> None:
    required = sorted(portfolio.audit_ooxml_corpus_buckets.REQUIRED_BUCKETS)
    report_a = _write_bucket_report(
        tmp_path / "a.json",
        workbooks=["a.xlsx", "b.xlsx"],
        buckets={bucket: ["a.xlsx"] for bucket in required[:6]},
        missing_buckets=required[6:],
    )
    report_b = _write_bucket_report(
        tmp_path / "b.json",
        workbooks=["c.xlsx", "d.xlsx"],
        buckets={bucket: ["c.xlsx"] for bucket in required[6:]},
        missing_buckets=required[:6],
    )

    result = portfolio.audit_corpus_portfolio(
        [report_a, report_b],
        min_sources=2,
        min_workbooks=4,
    )

    assert result["ready"] is True
    assert result["source_count"] == 2
    assert result["workbook_count"] == 4
    assert result["missing_buckets"] == []
    assert result["threshold_failures"] == []


def test_corpus_portfolio_reports_missing_buckets_and_thresholds(tmp_path: Path) -> None:
    report = _write_bucket_report(
        tmp_path / "partial.json",
        workbooks=["a.xlsx"],
        buckets={"excel_authored": ["a.xlsx"]},
        missing_buckets=["macro_vba"],
    )

    result = portfolio.audit_corpus_portfolio(
        [report],
        min_sources=2,
        min_workbooks=3,
    )

    assert result["ready"] is False
    assert "macro_vba" in result["missing_buckets"]
    assert result["threshold_failures"] == [
        {"id": "min_workbooks", "actual": 1, "expected_at_least": 3},
        {"id": "min_sources", "actual": 1, "expected_at_least": 2},
    ]


def test_corpus_portfolio_deduplicates_workbooks(tmp_path: Path) -> None:
    report_a = _write_bucket_report(
        tmp_path / "a.json",
        workbooks=["same.xlsx"],
        buckets={"excel_authored": ["same.xlsx"]},
    )
    report_b = _write_bucket_report(
        tmp_path / "b.json",
        workbooks=["same.xlsx"],
        buckets={"excel_authored": ["same.xlsx"]},
    )

    result = portfolio.audit_corpus_portfolio(
        [report_a, report_b],
        min_sources=1,
        min_workbooks=1,
    )

    assert result["workbook_count"] == 1
    assert result["bucket_counts"]["excel_authored"] == 1


def test_corpus_portfolio_counts_distinct_non_empty_sources(tmp_path: Path) -> None:
    required = sorted(portfolio.audit_ooxml_corpus_buckets.REQUIRED_BUCKETS)
    report = _write_bucket_report(
        tmp_path / "real.json",
        workbooks=["same.xlsx"],
        buckets={bucket: ["same.xlsx"] for bucket in required},
    )
    empty_report = _write_bucket_report(
        tmp_path / "empty.json",
        workbooks=[],
        buckets={},
        missing_buckets=required,
    )

    result = portfolio.audit_corpus_portfolio(
        [report, report, empty_report],
        min_sources=2,
        min_workbooks=1,
    )

    assert result["ready"] is False
    assert result["source_count"] == 1
    assert result["input_report_count"] == 3
    assert result["threshold_failures"] == [
        {"id": "min_sources", "actual": 1, "expected_at_least": 2},
    ]
    assert [item["contributes_source"] for item in result["source_reports"]] == [
        True,
        True,
        False,
    ]
