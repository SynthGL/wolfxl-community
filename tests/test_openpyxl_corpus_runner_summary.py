from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_runner() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_openpyxl_corpus.py"
    spec = importlib.util.spec_from_file_location("run_openpyxl_corpus", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def test_parse_pytest_summary_extracts_counts_from_pass_output() -> None:
    summary = runner._parse_pytest_summary(
        "...\n"
        "==== 2581 passed, 1 skipped, 1 deselected, 7 xfailed, 54 warnings in 4.55s ====\n"
    )

    assert summary == {
        "raw": "2581 passed, 1 skipped, 1 deselected, 7 xfailed, 54 warnings",
        "passed": 2581,
        "failed": 0,
        "skipped": 1,
        "deselected": 1,
        "xfailed": 7,
        "xpassed": 0,
        "warnings": 54,
        "error": 0,
        "duration_seconds": 4.55,
    }


def test_parse_pytest_summary_extracts_failure_and_error_counts() -> None:
    summary = runner._parse_pytest_summary(
        "==== 12 failed, 87 passed, 2 skipped, 1 xpassed, 3 errors in 10.00s ===="
    )

    assert summary["failed"] == 12
    assert summary["passed"] == 87
    assert summary["skipped"] == 2
    assert summary["xpassed"] == 1
    assert summary["error"] == 3
    assert summary["duration_seconds"] == 10.0


def test_parse_pytest_summary_handles_long_run_wallclock_suffix() -> None:
    # pytest's format_session_duration appends a " (H:MM:SS)" wall-clock suffix
    # once a run crosses 60 seconds. The full openpyxl corpus exceeds that, so
    # the real summary line carries the parenthetical the short-run tests miss.
    summary = runner._parse_pytest_summary(
        "==== 2581 passed, 1 skipped, 1 deselected, 7 xfailed, 54 warnings "
        "in 75.43s (0:01:15) ====\n"
    )

    assert summary == {
        "raw": "2581 passed, 1 skipped, 1 deselected, 7 xfailed, 54 warnings",
        "passed": 2581,
        "failed": 0,
        "skipped": 1,
        "deselected": 1,
        "xfailed": 7,
        "xpassed": 0,
        "warnings": 54,
        "error": 0,
        "duration_seconds": 75.43,
    }


def test_parse_pytest_summary_handles_multi_hour_wallclock_suffix() -> None:
    summary = runner._parse_pytest_summary(
        "==== 100 passed in 3725.00s (1:02:05) ====\n"
    )

    assert summary["passed"] == 100
    assert summary["duration_seconds"] == 3725.0


def test_parse_pytest_summary_accepts_quiet_summary_without_equals() -> None:
    summary = runner._parse_pytest_summary(
        "2581 passed, 1 skipped, 1 deselected, 7 xfailed, 54 warnings in 3.54s\n"
    )

    assert summary["passed"] == 2581
    assert summary["skipped"] == 1
    assert summary["deselected"] == 1
    assert summary["xfailed"] == 7
    assert summary["warnings"] == 54
    assert summary["duration_seconds"] == 3.54


def test_parse_pytest_summary_returns_null_counts_when_missing() -> None:
    summary = runner._parse_pytest_summary("collection failed before pytest summary")

    assert summary["raw"] is None
    assert summary["passed"] is None
    assert summary["duration_seconds"] is None


_JUNIT_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="1" failures="2" skipped="8" tests="2589" time="3.628">
    <testcase classname="m" name="pass_one"/>
    <testcase classname="m" name="xfail_one">
      <skipped type="pytest.xfail" message="expected"/>
    </testcase>
    <testcase classname="m" name="real_skip">
      <skipped type="pytest.skip" message="version guard"/>
    </testcase>
  </testsuite>
</testsuites>
"""


def test_parse_junit_counts_splits_xfail_out_of_skipped(tmp_path) -> None:
    report = tmp_path / "j.xml"
    report.write_text(_JUNIT_XML)

    counts = runner._parse_junit_counts(report)

    assert counts is not None
    assert counts["tests"] == 2589
    assert counts["failed"] == 2
    assert counts["error"] == 1
    # JUnit lumps the 1 xfail into skipped=8; the genuine-skip count is 7.
    assert counts["xfailed"] == 1
    assert counts["skipped"] == 7
    # passed = tests - failed - error - skipped_total = 2589 - 2 - 1 - 8.
    assert counts["passed"] == 2578
    assert counts["duration_seconds"] == 3.628
    # Non-recoverable from JUnit; deferred to the text summary.
    assert counts["xpassed"] is None


def test_parse_junit_counts_returns_none_when_missing(tmp_path) -> None:
    assert runner._parse_junit_counts(tmp_path / "absent.xml") is None


def test_merge_summary_prefers_junit_counts_over_absent_text_line() -> None:
    # Text line was suppressed by the import shim → all-null text summary.
    text = runner._parse_pytest_summary("no summary line here")
    junit = {
        "raw": None,
        "tests": 2589,
        "passed": 2581,
        "failed": 0,
        "error": 0,
        "skipped": 1,
        "xfailed": 7,
        "xpassed": None,
        "deselected": None,
        "warnings": None,
        "duration_seconds": 3.6,
    }

    merged = runner._merge_summary(text, junit)

    assert merged["passed"] == 2581
    assert merged["failed"] == 0
    assert merged["skipped"] == 1
    assert merged["xfailed"] == 7
    assert merged["tests"] == 2589
    assert merged["duration_seconds"] == 3.6


def test_merge_summary_keeps_text_only_fields_and_falls_back() -> None:
    text = runner._parse_pytest_summary(
        "==== 87 passed, 2 skipped, 1 xpassed, 3 deselected in 10.00s ===="
    )

    # No JUnit report → text summary is returned unchanged.
    assert runner._merge_summary(text, None) is text

    junit = {
        "raw": None,
        "tests": 92,
        "passed": 87,
        "failed": 0,
        "error": 0,
        "skipped": 2,
        "xfailed": 0,
        "xpassed": None,
        "deselected": None,
        "warnings": None,
        "duration_seconds": 10.0,
    }
    merged = runner._merge_summary(text, junit)
    # xpassed/deselected have no JUnit representation; kept from the text line.
    assert merged["xpassed"] == 1
    assert merged["deselected"] == 3
    assert merged["passed"] == 87


def test_allowlist_category_counts_marks_true_wolfxl_gaps() -> None:
    counts = runner._allowlist_category_counts(
        {
            "entries": [
                {"nodeid": "a.py", "category": "infra_mismatch"},
                {"nodeid": "b.py", "category": "true_wolfxl_gap"},
                {"nodeid": "c.py", "category": "true_wolfxl_gap"},
                {"nodeid": "d.py"},
                "legacy-nodeid",
            ]
        }
    )

    assert counts == {
        "infra_mismatch": 1,
        "true_wolfxl_gap": 2,
        "uncategorized": 2,
    }
