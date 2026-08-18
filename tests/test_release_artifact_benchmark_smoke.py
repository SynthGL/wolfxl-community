from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "run_release_artifact_benchmark_smoke.py"
    spec = importlib.util.spec_from_file_location("run_release_artifact_benchmark_smoke", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke = _load_module()


def test_execution_ready_is_separate_from_rust_speed_superiority() -> None:
    openpyxl_summary = {
        "comparison_count": 3,
        "weak_case_count": 0,
    }
    rust_summary = {
        "comparison_count": 14,
        "weak_case_count": 5,
        "missing_competitors": [],
        "missing_version_competitors": [],
        "skipped_required_competitors": [],
    }

    assert smoke._execution_ready(openpyxl_summary, rust_summary) is True
    assert smoke._openpyxl_superiority_ready(openpyxl_summary) is True
    assert smoke._rust_superiority_ready(rust_summary) is False


def test_required_rust_version_missing_blocks_execution_ready() -> None:
    rust_payload = {
        "results": [
            {"competitor": "rust_xlsxwriter", "competitor_version": "0.95.0"},
            {"competitor": "xlsxwriter", "competitor_version": "0.6.1"},
            {"competitor": "calamine", "competitor_version": "0.35.0"},
            {"competitor": "umya-spreadsheet", "competitor_version": "2.3.3"},
            {"competitor": "python-calamine", "competitor_version": "0.6.2"},
        ],
        "comparisons": [
            {"speedup_vs_competitor": 0.75},
        ],
        "missing_competitors": [],
        "skipped_competitors": [
            {"competitor": "wolfxl_writer_direct", "reason": "optional diagnostic failed"}
        ],
    }

    summary = smoke._rust_summary(rust_payload)

    assert summary["missing_version_competitors"] == ["fastexcel"]
    assert summary["optional_wolfxl_direct_skips"]
    assert summary["skipped_required_competitors"] == []
    assert smoke._execution_ready({"comparison_count": 1}, summary) is False


def test_rust_summary_prefers_direct_same_surface_rows() -> None:
    payload = {
        "results": [
            {"competitor": "rust_xlsxwriter", "competitor_version": "0.95.0"},
            {"competitor": "xlsxwriter", "competitor_version": "0.6.1"},
            {"competitor": "calamine", "competitor_version": "0.35.0"},
            {"competitor": "umya-spreadsheet", "competitor_version": "2.3.3"},
            {"competitor": "fastexcel", "competitor_version": "0.20.2"},
            {"competitor": "python-calamine", "competitor_version": "0.6.2"},
        ],
        "comparisons": [
            {
                "case": "write_styled_cells",
                "competitor": "rust_xlsxwriter",
                "competitor_api_surface": "direct_rust_api",
                "speedup_vs_competitor": 0.25,
            },
            {
                "case": "read_values_plain",
                "competitor": "fastexcel",
                "competitor_api_surface": "python_binding_api",
                "speedup_vs_competitor": 1.4,
            },
        ],
        "wolfxl_direct_writer_comparisons": [
            {
                "case": "write_styled_cells",
                "competitor": "rust_xlsxwriter",
                "competitor_api_surface": "direct_rust_api",
                "speedup_vs_competitor": 1.5,
            }
        ],
        "missing_competitors": [],
        "skipped_competitors": [],
    }

    summary = smoke._rust_summary(payload)

    assert summary["comparison_count"] == 2
    assert summary["raw_public_comparison_count"] == 2
    assert summary["same_surface_direct_comparison_count"] == 1
    assert summary["weak_case_count"] == 0
    assert summary["min_observed_speedup"] == 1.4
    assert summary["claim_basis_counts"] == {
        "direct_rust_same_surface": 1,
        "public_api": 1,
    }


def test_rust_summary_reports_memory_rows_and_weak_cases() -> None:
    payload = {
        "results": [
            {"competitor": "rust_xlsxwriter", "competitor_version": "0.95.0"},
            {"competitor": "xlsxwriter", "competitor_version": "0.6.1"},
            {"competitor": "calamine", "competitor_version": "0.35.0"},
            {"competitor": "umya-spreadsheet", "competitor_version": "2.3.3"},
            {"competitor": "fastexcel", "competitor_version": "0.20.2"},
            {"competitor": "python-calamine", "competitor_version": "0.6.2"},
        ],
        "comparisons": [
            {
                "case": "write_cell_by_cell_plain",
                "competitor": "rust_xlsxwriter",
                "speedup_vs_competitor": 1.5,
            },
        ],
        "memory_comparisons": [
            {
                "case": "write_cell_by_cell_plain",
                "competitor": "rust_xlsxwriter",
                "peak_rss_ratio_vs_competitor": 1.2,
                "peak_rss_excess_bytes": 10_000_000,
            },
        ],
        "missing_competitors": [],
        "skipped_competitors": [],
    }

    summary = smoke._rust_summary(payload)

    assert summary["memory_comparison_count"] == 1
    assert summary["max_observed_memory_ratio"] == 1.2
    assert summary["weak_memory_case_count"] == 1
    assert smoke._rust_memory_ready(summary) is False


def test_rust_summary_prefers_streaming_direct_memory_rows() -> None:
    payload = {
        "results": [
            {"competitor": "rust_xlsxwriter", "competitor_version": "0.95.0"},
            {"competitor": "xlsxwriter", "competitor_version": "0.6.1"},
            {"competitor": "calamine", "competitor_version": "0.35.0"},
            {"competitor": "umya-spreadsheet", "competitor_version": "2.3.3"},
            {"competitor": "fastexcel", "competitor_version": "0.20.2"},
            {"competitor": "python-calamine", "competitor_version": "0.6.2"},
        ],
        "comparisons": [
            {
                "case": "write_cell_by_cell_plain",
                "competitor": "rust_xlsxwriter",
                "competitor_api_surface": "direct_rust_api",
                "speedup_vs_competitor": 1.5,
            },
        ],
        "memory_comparisons": [
            {
                "case": "write_cell_by_cell_plain",
                "competitor": "rust_xlsxwriter",
                "competitor_api_surface": "direct_rust_api",
                "peak_rss_ratio_vs_competitor": 1.2,
                "peak_rss_excess_bytes": 10_000_000,
            },
        ],
        "wolfxl_streaming_direct_writer_memory_comparisons": [
            {
                "case": "write_cell_by_cell_plain",
                "competitor": "rust_xlsxwriter",
                "competitor_api_surface": "direct_rust_api",
                "peak_rss_ratio_vs_competitor": 1.1,
                "peak_rss_excess_bytes": 2_000_000,
            },
        ],
        "missing_competitors": [],
        "skipped_competitors": [],
    }

    summary = smoke._rust_summary(payload)

    assert summary["memory_comparison_count"] == 1
    assert summary["max_observed_memory_ratio"] == 1.1
    assert summary["weak_memory_case_count"] == 0
    assert summary["weak_memory_cases"] == []
    assert smoke._rust_memory_ready(summary) is True


def test_rust_summary_prefers_direct_modify_memory_rows() -> None:
    payload = {
        "results": [
            {"competitor": "rust_xlsxwriter", "competitor_version": "0.95.0"},
            {"competitor": "xlsxwriter", "competitor_version": "0.6.1"},
            {"competitor": "calamine", "competitor_version": "0.35.0"},
            {"competitor": "umya-spreadsheet", "competitor_version": "2.3.3"},
            {"competitor": "fastexcel", "competitor_version": "0.20.2"},
            {"competitor": "python-calamine", "competitor_version": "0.6.2"},
        ],
        "comparisons": [
            {
                "case": "modify_existing_workbook_plain",
                "competitor": "umya-spreadsheet",
                "competitor_api_surface": "direct_rust_api",
                "speedup_vs_competitor": 1.5,
            },
        ],
        "memory_comparisons": [
            {
                "case": "modify_existing_workbook_plain",
                "competitor": "umya-spreadsheet",
                "competitor_api_surface": "direct_rust_api",
                "peak_rss_ratio_vs_competitor": 3.2,
                "peak_rss_excess_bytes": 30_000_000,
            },
        ],
        "wolfxl_direct_modify_memory_comparisons": [
            {
                "case": "modify_existing_workbook_plain",
                "competitor": "umya-spreadsheet",
                "competitor_api_surface": "direct_rust_api",
                "peak_rss_ratio_vs_competitor": 0.8,
                "peak_rss_excess_bytes": -1_000_000,
            },
        ],
        "missing_competitors": [],
        "skipped_competitors": [],
    }

    summary = smoke._rust_summary(payload)

    assert summary["memory_comparison_count"] == 1
    assert summary["max_observed_memory_ratio"] == 0.8
    assert summary["weak_memory_case_count"] == 0
    assert summary["weak_memory_cases"] == []
    assert smoke._rust_memory_ready(summary) is True


def test_markdown_lists_wheel_identity_and_claim_basis() -> None:
    report = {
        "profile": "full",
        "ready": True,
        "openpyxl_superiority_ready": True,
        "openpyxl_sota_speed_ready": True,
        "openpyxl_memory_ready": True,
        "rust_superiority_ready": True,
        "rust_memory_ready": True,
        "broad_speed_superiority_ready": True,
        "full_release_artifact_rerun_ready": True,
        "source_git_sha": "abc123",
        "source_git_dirty": False,
        "report_repo_git_dirty": False,
        "generator_script_source": "fixture generator",
        "generator_script_path": "scripts/run_release_artifact_benchmark_smoke.py",
        "generator_script_sha256": "d" * 64,
        "wheel": {
            "filename": "wolfxl-2.0.0.whl",
            "metadata_version": "2.0.0",
            "wheel_tag": "cp312-cp312-macosx_11_0_arm64",
            "sha256": "c" * 64,
            "size_bytes": 1234,
        },
        "parameters": {
            "rows": 10,
            "cols": 5,
            "rounds": 2,
            "rust_rows": 10,
            "rust_cols": 5,
            "rust_rounds": 2,
            "memory_noise_tolerance_bytes": 3145728,
        },
        "openpyxl_benchmark_summary": {
            "comparison_count": 2,
            "min_observed_speedup": 2.5,
            "weak_sota_case_count": 0,
            "memory_comparison_count": 1,
            "max_observed_memory_ratio": 0.8,
            "weak_memory_case_count": 0,
        },
        "rust_benchmark_summary": {
            "comparison_count": 2,
            "min_observed_speedup": 1.2,
            "weak_case_count": 0,
            "memory_comparison_count": 2,
            "max_observed_memory_ratio": 0.9,
            "weak_memory_case_count": 0,
            "claim_basis_counts": {
                "direct_rust_same_surface": 1,
                "public_api": 1,
            },
            "missing_competitors": [],
            "missing_version_competitors": [],
            "skipped_required_competitors": [],
            "optional_wolfxl_direct_skips": [],
        },
        "notes": [],
    }

    markdown = smoke.format_markdown(report)

    assert f"| Wheel SHA-256 | `{'c' * 64}` |" in markdown
    assert "| Wheel size bytes | 1234 |" in markdown
    assert "| Rust memory ready | true |" in markdown
    assert "| Generator script source | fixture generator |" in markdown
    assert (
        "| Generator script path | scripts/run_release_artifact_benchmark_smoke.py |"
        in markdown
    )
    assert f"| Generator script SHA-256 | `{'d' * 64}` |" in markdown
    assert "| Rust memory comparison rows | 2 |" in markdown
    assert "| Rust weak memory rows | 0 |" in markdown
    assert "| Rust claim basis counts | direct_rust_same_surface=1, public_api=1 |" in markdown
    assert (
        "Rust memory ready is limited to the measured benchmark lanes and "
        "same-surface direct Rust row policy with the configured RSS noise "
        "tolerance of 3145728 bytes"
    ) in markdown
    assert (
        "it is not a claim that every WolfXL public write path uses less memory "
        "than every Rust writer competitor"
    ) in markdown
    assert "| Full release-artifact rerun ready | true |" in markdown
    assert "| Report repo Git dirty | false |" in markdown


def test_smoke_markdown_clarifies_full_rerun_profile_boundary() -> None:
    report = {
        "profile": "smoke",
        "ready": True,
        "openpyxl_superiority_ready": True,
        "openpyxl_sota_speed_ready": True,
        "openpyxl_memory_ready": True,
        "rust_superiority_ready": True,
        "rust_memory_ready": False,
        "broad_speed_superiority_ready": True,
        "release_artifact_benchmark_smoke_ready": True,
        "full_release_artifact_rerun_profile": False,
        "full_release_artifact_rerun_ready": False,
        "source_git_sha": "abc123",
        "source_git_dirty": False,
        "report_repo_git_dirty": False,
        "generator_script_source": "fixture generator",
        "generator_script_path": "scripts/run_release_artifact_benchmark_smoke.py",
        "generator_script_sha256": "d" * 64,
        "wheel": {
            "filename": "wolfxl-2.0.0.whl",
            "metadata_version": "2.0.0",
            "wheel_tag": "cp312-cp312-macosx_11_0_arm64",
            "sha256": "c" * 64,
            "size_bytes": 1234,
        },
        "parameters": {
            "rows": 10,
            "cols": 5,
            "rounds": 2,
            "rust_rows": 10,
            "rust_cols": 5,
            "rust_rounds": 2,
        },
        "openpyxl_benchmark_summary": {
            "comparison_count": 2,
            "min_observed_speedup": 2.5,
            "weak_sota_case_count": 0,
            "memory_comparison_count": 0,
            "max_observed_memory_ratio": None,
            "weak_memory_case_count": 0,
        },
        "rust_benchmark_summary": {
            "comparison_count": 2,
            "min_observed_speedup": 1.2,
            "weak_case_count": 0,
            "memory_comparison_count": 0,
            "max_observed_memory_ratio": None,
            "weak_memory_case_count": 0,
            "claim_basis_counts": {},
            "missing_competitors": [],
            "missing_version_competitors": [],
            "skipped_required_competitors": [],
            "optional_wolfxl_direct_skips": [],
        },
        "notes": [],
    }

    markdown = smoke.format_markdown(report)

    assert "| Release-artifact benchmark smoke ready | true |" in markdown
    assert "| This report is full release-artifact rerun profile | false |" in markdown
    assert "| Full release-artifact rerun ready | false |" not in markdown
    assert "| Report repo Git dirty | false |" in markdown
    assert "| Generator script source | fixture generator |" in markdown
    assert (
        "| Generator script path | scripts/run_release_artifact_benchmark_smoke.py |"
        in markdown
    )
    assert f"| Generator script SHA-256 | `{'d' * 64}` |" in markdown


def test_smoke_report_distinguishes_smoke_ready_from_full_rerun_gate() -> None:
    report = {
        "profile": "smoke",
        "ready": True,
        "execution_ready": True,
        "release_artifact_benchmark_smoke_ready": True,
        "full_release_artifact_rerun_profile": False,
        "full_release_artifact_rerun_ready": False,
        "notes": [
            "For this smoke profile, full_release_artifact_rerun_ready=false means this report is not the full rerun profile; use docs/trust/release-artifact-benchmark-rerun.json for the claim-grade full-rerun gate."
        ],
    }

    assert report["release_artifact_benchmark_smoke_ready"] is True
    assert report["full_release_artifact_rerun_profile"] is False
    assert report["full_release_artifact_rerun_ready"] is False
    assert "not the full rerun profile" in report["notes"][0]


def test_release_artifact_rust_command_captures_memory() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_release_artifact_benchmark_smoke.py"
    )
    source = script.read_text(encoding="utf-8")

    assert '"--capture-memory"' in source


def test_command_redaction_removes_temp_path() -> None:
    commands = [
        {
            "command": "/tmp/wolfxl-release-bench-abc/venv/bin/python script.py",
            "stdout": "wrote /tmp/wolfxl-release-bench-abc/out.xlsx",
            "stderr": "",
        }
    ]

    smoke._redact_command_paths(commands, Path("/tmp/wolfxl-release-bench-abc"))

    assert commands == [
        {
            "command": "<tempdir>/venv/bin/python script.py",
            "stdout": "wrote <tempdir>/out.xlsx",
            "stderr": "",
        }
    ]


def test_openpyxl_summary_uses_operation_phase_and_memory_tolerance() -> None:
    payload = {
        "comparisons": [
            {
                "case": "modify_two_cells_plain",
                "engine": "wolfxl_modify",
                "speedup_vs_openpyxl": 0.5,
            },
            {
                "case": "write_append_plain",
                "engine": "wolfxl_append",
                "speedup_vs_openpyxl": 3.0,
            },
        ],
        "operation_comparisons": [
            {
                "case": "modify_two_cells_plain",
                "engine": "wolfxl_modify",
                "speedup_vs_openpyxl": 4.0,
            }
        ],
        "memory": [
            {
                "case": "read_values_plain",
                "engine": "openpyxl",
                "peak_rss_bytes": 100_000_000,
            },
            {
                "case": "read_values_plain",
                "engine": "wolfxl",
                "peak_rss_bytes": 101_000_000,
            },
            {
                "case": "read_only_values_plain",
                "engine": "openpyxl",
                "peak_rss_bytes": 100_000_000,
            },
            {
                "case": "read_only_values_plain",
                "engine": "wolfxl",
                "peak_rss_bytes": 110_000_000,
            },
        ],
        "memory_comparisons": [
            {
                "case": "read_values_plain",
                "engine": "wolfxl",
                "peak_rss_ratio_vs_openpyxl": 1.01,
            },
            {
                "case": "read_only_values_plain",
                "engine": "wolfxl",
                "peak_rss_ratio_vs_openpyxl": 1.1,
            },
        ],
    }

    summary = smoke._openpyxl_summary(payload)

    assert summary["min_observed_speedup"] == 3.0
    assert summary["weak_sota_case_count"] == 0
    assert summary["memory_comparison_count"] == 2
    assert summary["weak_memory_case_count"] == 1
    assert summary["weak_memory_cases"][0]["case"] == "read_only_values_plain"
