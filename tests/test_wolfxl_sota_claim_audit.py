from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "audit_wolfxl_sota_claim.py"
    spec = importlib.util.spec_from_file_location("audit_wolfxl_sota_claim", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sota = _load_module()
FIXED_NOW_UTC = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _benchmark_metadata(
    *,
    git_dirty: bool = False,
    timestamp_utc: str | None = "2026-06-01T00:00:00Z",
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "git_commit": "test-git-commit",
        "git_dirty": git_dirty,
        "python": "3.12.3",
        "platform": "test-platform",
        "machine": "arm64",
        "cpu_brand": "test-cpu",
        "wolfxl_version": "2.0.0",
        "openpyxl_version": "3.1.5",
        "rounds": 9,
    }
    if timestamp_utc is not None:
        metadata["timestamp_utc"] = timestamp_utc
    return metadata


@pytest.fixture(autouse=True)
def _freeze_sota_audit_clock(monkeypatch, request) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            if tz is None:
                return FIXED_NOW_UTC.replace(tzinfo=None)
            return FIXED_NOW_UTC.astimezone(tz)

    monkeypatch.setattr(sota, "datetime", FrozenDateTime)
    if not request.node.name.startswith("test_benchmark_source_relevance"):
        monkeypatch.setattr(
            sota,
            "_benchmark_source_relevance_summary",
            lambda _label, _benchmark, payload: {
                "source_relevance_ready": True,
                "source_relevance_status": "fixture_checked",
                "source_relevance_base_git_commit": (payload.get("metadata") or {}).get(
                    "git_commit"
                ),
                "source_relevance_current_git_commit": (payload.get("metadata") or {}).get(
                    "git_commit"
                ),
                "source_relevance_changed_path_count": 0,
                "source_relevance_relevant_changed_path_count": 0,
                "source_relevance_relevant_changed_paths": [],
                "source_relevance_dirty_relevant_paths": [],
                "source_relevance_relevant_path_prefixes": list(
                    sota.BENCHMARK_RELEVANT_SOURCE_PATHS
                ),
                "source_relevance_blockers": [],
            },
        )


def _write_rust_competitor_benchmark(
    path: Path,
    speedup: float = 2.5,
    *,
    memory_ratio: float | None = None,
    memory_excess_bytes: int = -40_000_000,
    git_dirty: bool = False,
    timestamp_utc: str | None = "2026-06-01T00:00:00Z",
) -> None:
    def cases_for_competitor(competitor: str) -> list[str]:
        families = sota.DEFAULT_RUST_COMPETITOR_REQUIRED_CASE_FAMILIES[competitor]
        cases_by_family = {
            "plain_value_write": "write_cell_by_cell_plain",
            "high_cardinality_string_write": "write_unique_strings_plain",
            "formula_write": "write_formulas_plain",
            "styled_value_write": "write_styled_values",
            "multi_sheet_write": "write_multi_sheet_plain",
            "plain_value_read": "read_values_plain",
            "formula_text_read": "read_formula_text",
            "existing_workbook_modify": "modify_existing_workbook_plain",
        }
        return [cases_by_family[family] for family in families]

    rows = [
        (competitor, case)
        for competitor in sota.DEFAULT_RUST_COMPETITORS
        for case in cases_for_competitor(competitor)
    ]

    metadata = _benchmark_metadata(git_dirty=git_dirty, timestamp_utc=timestamp_utc)
    payload = {
        "metadata": metadata,
        "results": [
            {
                "case": case,
                "competitor": competitor,
                "competitor_version": f"{index}.0.0",
            }
            for index, (competitor, case) in enumerate(
                rows,
                start=1,
            )
        ],
        "comparisons": [
            {
                "case": case,
                "competitor": competitor,
                "speedup_vs_competitor": speedup,
                "wolfxl_api_surface": "python_public_api",
                "competitor_api_surface": "python_binding_api",
                "same_api_surface": False,
            }
            for competitor, case in rows
        ],
    }
    if memory_ratio is not None:
        payload["memory_comparisons"] = [
            {
                "case": case,
                "competitor": competitor,
                "peak_rss_ratio_vs_competitor": memory_ratio,
                "peak_rss_excess_bytes": memory_excess_bytes,
                "wolfxl_api_surface": "python_public_api",
                "competitor_api_surface": "python_binding_api",
                "same_api_surface": False,
            }
            for competitor, case in rows
        ]
    path.write_text(json.dumps(payload))


def _default_rust_case_count() -> int:
    return sum(
        len(sota.DEFAULT_RUST_COMPETITOR_REQUIRED_CASE_FAMILIES[competitor])
        for competitor in sota.DEFAULT_RUST_COMPETITORS
    )


def _write_rust_competitor_set_report(
    path: Path,
    *,
    ready: bool = True,
    timestamp_utc: str | None = "2026-06-01T00:00:00Z",
    below_threshold_hits: list[dict[str, object]] | None = None,
) -> None:
    metadata = {
        "registry_metadata_fetched": True,
        "crates_io_discovery_fetched": True,
        "pypi_discovery_fetched": True,
        "discovery_queries": ["xlsx", "excel", "spreadsheet"],
        "discovery_per_page": 50,
        "discovery_min_downloads": 1000,
        "discovery_min_recent_downloads": 50,
        "pypi_discovery_name_terms": [
            "xlsx",
            "xlsm",
            "xlsb",
            "excel",
            "spreadsheet",
            "calamine",
        ],
        "pypi_discovery_rust_hint_terms": [
            "rust",
            "calamine",
            "maturin",
            "pyo3",
            "rust_xlsxwriter",
            "fastexcel",
            "fastxlsx",
        ],
        "pypi_discovery_candidate_limit": 250,
    }
    if timestamp_utc is not None:
        metadata["timestamp_utc"] = timestamp_utc
    path.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "main_rust_competitor_set_ready": ready,
                "blockers": [] if ready else ["competitor discovery failed"],
                "packages": [
                    {
                        "id": competitor,
                        "package": competitor,
                        "source": (
                            "pypi"
                            if competitor == "python-calamine"
                            else "crates.io"
                        ),
                        "gate_status": "required",
                        "registry": {"version": "1.2.3"},
                        "aliases": (["xlsxwriter-rs"] if competitor == "xlsxwriter" else []),
                    }
                    for competitor in sota.DEFAULT_RUST_COMPETITORS
                ]
                + [
                    {
                        "id": "xlsxwriter-rs",
                        "package": "xlsxwriter-rs",
                        "source": "crates.io",
                        "gate_status": "watchlist",
                        "registry": {"version": "0.1.0"},
                        "aliases": [],
                    }
                ],
                "required_competitors": list(sota.DEFAULT_RUST_COMPETITORS),
                "benchmark_present": True,
                "benchmark_competitors": list(sota.DEFAULT_RUST_COMPETITORS),
                "benchmark_competitor_versions": {
                    competitor: "1.2.3" for competitor in sota.DEFAULT_RUST_COMPETITORS
                },
                "required_competitor_version_evidence": [
                    {
                        "competitor": competitor,
                        "package": competitor,
                        "source": (
                            "pypi"
                            if competitor == "python-calamine"
                            else "crates.io"
                        ),
                        "aliases": (
                            ["xlsxwriter-rs"] if competitor == "xlsxwriter" else []
                        ),
                        "benchmark_version": "1.2.3",
                        "benchmark_api_surfaces": (
                            ["python_binding_api"]
                            if competitor in {"fastexcel", "python-calamine"}
                            else ["direct_rust_api"]
                        ),
                        "registry_version": "1.2.3",
                        "version_captured": True,
                    }
                    for competitor in sota.DEFAULT_RUST_COMPETITORS
                ],
                "missing_from_benchmark": [],
                "missing_benchmark_versions": [],
                "stale_benchmark_versions": [],
                "missing_required_case_family_count": 0,
                "missing_required_case_families": [],
                "watchlist_promotion_review_ready": True,
                "watchlist_promotion_review_count": 3,
                "watchlist_packages_requiring_promotion": [],
                "watchlist_promotion_adoption_missing_count": 0,
                "watchlist_promotion_adoption_missing": [],
                "watchlist_promotion_adoption_complete": True,
                "watchlist_promotion_adoption_caveat": None,
                "watchlist_adoption_attention_review_count": 1,
                "watchlist_adoption_attention_reviews": [
                    {
                        "id": "python-calamine-reducto",
                        "source": "pypi",
                        "promotion_risk": "medium",
                        "adoption_recent_downloads": 47565,
                        "max_promotion_ratio": 0.9513,
                        "positioning_handling": "covered_by_required_lanes",
                        "related_required_competitors": [
                            "python-calamine",
                            "calamine",
                        ],
                        "basis": "Fork of the required python-calamine lane.",
                        "next_trigger": "Promote if it becomes the main package.",
                    }
                ],
                "watchlist_promotion_reviews": [
                    {
                        "id": "xlsxwriter-rs",
                        "decision": "remain_watchlist",
                        "promotion_needed_now": False,
                        "related_required_competitors": ["xlsxwriter"],
                    },
                    {
                        "id": "rustypyxl",
                        "decision": "remain_watchlist",
                        "promotion_needed_now": False,
                        "related_required_competitors": [],
                    },
                    {
                        "id": "office-oxide",
                        "decision": "remain_watchlist",
                        "promotion_needed_now": False,
                        "related_required_competitors": [],
                    },
                ],
                "discovery_error_queries": [],
                "pypi_discovery_error_queries": [],
                "unclassified_discovery_hits": [],
                "unclassified_pypi_discovery_hits": [],
                "unclassified_relevant_below_threshold_hits": below_threshold_hits or [],
                "status_counts": {
                    "required": len(sota.DEFAULT_RUST_COMPETITORS),
                    "watchlist": 3,
                },
            }
        )
    )


def test_benchmark_source_relevance_blocks_changed_source(monkeypatch) -> None:
    base_sha = "a" * 40
    current_sha = "b" * 40

    def fake_git_stdout(args: tuple[str, ...]) -> str:
        if args == ("rev-parse", "HEAD"):
            return current_sha
        if args == ("diff", "--name-only", f"{base_sha}..HEAD"):
            return "\n".join(
                [
                    "docs/trust/report.md",
                    "crates/wolfxl-reader/src/lib.rs",
                    "scripts/audit_wolfxl_sota_claim.py",
                ]
            )
        if args == ("status", "--porcelain=v1", "--untracked-files=no"):
            return "\n".join(
                [
                    " M python/wolfxl/__init__.py",
                    " M docs/trust/report.md",
                ]
            )
        raise AssertionError(args)

    monkeypatch.setattr(sota, "_git_stdout", fake_git_stdout)
    monkeypatch.setattr(sota, "_git_success", lambda _args: True)
    monkeypatch.setattr(
        sota,
        "_git_path_has_non_whitespace_diff",
        lambda _rev, _path: True,
    )

    report = sota._benchmark_source_relevance_summary(
        "Rust competitor",
        sota.ROOT / "docs" / "performance" / "baselines" / "fixture.json",
        {"metadata": {"git_commit": base_sha}},
    )

    assert report["source_relevance_ready"] is False
    assert report["source_relevance_status"] == "blocked"
    assert report["source_relevance_current_git_commit"] == current_sha
    assert report["source_relevance_changed_path_count"] == 3
    assert report["source_relevance_relevant_changed_paths"] == [
        "crates/wolfxl-reader/src/lib.rs",
    ]
    assert report["source_relevance_dirty_relevant_paths"] == [
        "python/wolfxl/__init__.py",
    ]
    assert len(report["source_relevance_blockers"]) == 2


def test_benchmark_source_relevance_ignores_whitespace_only_dirty_source(
    monkeypatch,
) -> None:
    base_sha = "a" * 40
    current_sha = "b" * 40

    def fake_git_stdout(args: tuple[str, ...]) -> str:
        if args == ("rev-parse", "HEAD"):
            return current_sha
        if args == ("diff", "--name-only", f"{base_sha}..HEAD"):
            return ""
        if args == ("status", "--porcelain=v1", "--untracked-files=no"):
            return " M crates/wolfxl-writer/src/model/worksheet.rs"
        raise AssertionError(args)

    monkeypatch.setattr(sota, "_git_stdout", fake_git_stdout)
    monkeypatch.setattr(sota, "_git_success", lambda _args: True)
    monkeypatch.setattr(
        sota,
        "_git_path_has_non_whitespace_diff",
        lambda _rev, _path: False,
    )

    report = sota._benchmark_source_relevance_summary(
        "Rust competitor",
        sota.ROOT / "docs" / "performance" / "baselines" / "fixture.json",
        {"metadata": {"git_commit": base_sha}},
    )

    assert report["source_relevance_ready"] is True
    assert report["source_relevance_dirty_relevant_paths"] == []
    assert report["source_relevance_blockers"] == []


def test_git_dirty_tracked_paths_preserves_dotfile_status_columns(
    monkeypatch,
) -> None:
    def fake_git_stdout(args: tuple[str, ...]) -> str:
        if args == ("status", "--porcelain=v1", "--untracked-files=no"):
            return " M .gitignore\n M crates/wolfxl-writer/src/model/worksheet.rs"
        raise AssertionError(args)

    monkeypatch.setattr(sota, "_git_stdout", fake_git_stdout)

    assert sota._git_dirty_tracked_paths() == [
        ".gitignore",
        "crates/wolfxl-writer/src/model/worksheet.rs",
    ]


def test_pyproject_marker_description_diff_is_not_benchmark_relevant(
    monkeypatch,
) -> None:
    before = b"""
[tool.pytest.ini_options]
markers = [
    "rich_features: old wording",
    "slow: timing-sensitive tests",
]
"""
    after = b"""
[tool.pytest.ini_options]
markers = [
    "rich_features: new wording",
    "slow: timing-sensitive tests",
]
"""
    renamed = b"""
[tool.pytest.ini_options]
markers = [
    "different_name: new wording",
    "slow: timing-sensitive tests",
]
"""

    monkeypatch.setattr(
        sota,
        "_git_path_version_pair",
        lambda _revision, _path: (before, after),
    )

    assert sota._pyproject_diff_is_benchmark_neutral(None, "pyproject.toml") is True

    monkeypatch.setattr(
        sota,
        "_git_path_version_pair",
        lambda _revision, _path: (before, renamed),
    )

    assert sota._pyproject_diff_is_benchmark_neutral(None, "pyproject.toml") is False


def test_rustfmt_normalized_versions_match_ignores_formatting(monkeypatch) -> None:
    before = b"""
fn unchanged(a: bool, b: bool, c: bool, d: bool) -> bool {
    !(
        a
            && b
            && c
            && d
    )
}
"""
    after = b"""
fn unchanged(a: bool, b: bool, c: bool, d: bool) -> bool {
    !(a
        && b
        && c
        && d)
}
"""

    monkeypatch.setattr(
        sota,
        "_git_path_version_pair",
        lambda _revision, _path: (before, after),
    )

    assert (
        sota._rustfmt_normalized_versions_match(
            None,
            "crates/wolfxl-writer/src/model/worksheet.rs",
        )
        is True
    )


def test_pyproject_optional_dependency_change_is_not_benchmark_relevant(
    monkeypatch,
) -> None:
    # Mirrors PR #288: adding a [project.optional-dependencies] group (here a
    # test-only extras list) cannot move benchmark numbers, because optional
    # extras are not part of wolfxl's default install closure. The benchmarked
    # artifact is the built wheel plus its required [project].dependencies, whose
    # identity is governed by [build-system], [tool.maturin], Cargo.*, crates/,
    # src/, and [project].dependencies - none of which live under
    # optional-dependencies. Such a diff must not stale a benchmark pin. By
    # contrast, a runtime-dependency or build-system change is benchmark-relevant.
    base = b"""
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "wolfxl"
version = "2.0.0"
dependencies = ["defusedxml>=0.7.1,<1.0"]

[project.optional-dependencies]
calc = ["formulas>=1.3.3,<2.0"]
encrypted = ["msoffcrypto-tool>=5.4,<6.0"]
"""
    optional_dep_added = b"""
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "wolfxl"
version = "2.0.0"
dependencies = ["defusedxml>=0.7.1,<1.0"]

[project.optional-dependencies]
calc = ["formulas>=1.3.3,<2.0"]
encrypted = ["msoffcrypto-tool>=5.4,<6.0"]
# test extras mirror the deps CI installs
test = ["pytest>=7.4", "pytest-xdist>=3.3", "openpyxl>=3.1", "Pillow>=10.0"]
"""
    runtime_dep_changed = b"""
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "wolfxl"
version = "2.0.0"
dependencies = ["defusedxml>=0.7.1,<1.0", "numpy>=2.0"]

[project.optional-dependencies]
calc = ["formulas>=1.3.3,<2.0"]
encrypted = ["msoffcrypto-tool>=5.4,<6.0"]
"""
    build_system_changed = b"""
[build-system]
requires = ["maturin>=2.0,<3.0"]
build-backend = "maturin"

[project]
name = "wolfxl"
version = "2.0.0"
dependencies = ["defusedxml>=0.7.1,<1.0"]

[project.optional-dependencies]
calc = ["formulas>=1.3.3,<2.0"]
encrypted = ["msoffcrypto-tool>=5.4,<6.0"]
"""

    monkeypatch.setattr(
        sota, "_git_path_version_pair", lambda _rev, _path: (base, optional_dep_added)
    )
    assert sota._pyproject_diff_is_benchmark_neutral(None, "pyproject.toml") is True

    monkeypatch.setattr(
        sota, "_git_path_version_pair", lambda _rev, _path: (base, runtime_dep_changed)
    )
    assert sota._pyproject_diff_is_benchmark_neutral(None, "pyproject.toml") is False

    monkeypatch.setattr(
        sota, "_git_path_version_pair", lambda _rev, _path: (base, build_system_changed)
    )
    assert sota._pyproject_diff_is_benchmark_neutral(None, "pyproject.toml") is False


def test_benchmark_source_relevance_skips_synthetic_tmp_benchmarks(
    tmp_path: Path,
) -> None:
    report = sota._benchmark_source_relevance_summary(
        "Rust competitor",
        tmp_path / "fixture.json",
        {"metadata": {"git_commit": "test-git-commit"}},
    )

    assert report["source_relevance_ready"] is False
    assert report["source_relevance_status"] == "not_checked_outside_repo"
    assert report["source_relevance_blockers"] == [
        "Rust competitor benchmark source relevance was not checked because "
        "the benchmark file is outside the repository"
    ]


def test_benchmark_source_relevance_blocks_non_sha_git_commit() -> None:
    report = sota._benchmark_source_relevance_summary(
        "Rust competitor",
        sota.ROOT / "docs" / "performance" / "baselines" / "fixture.json",
        {"metadata": {"git_commit": "test-git-commit"}},
    )

    assert report["source_relevance_ready"] is False
    assert report["source_relevance_status"] == "not_checked_non_sha_git_commit"
    assert report["source_relevance_blockers"] == [
        "Rust competitor benchmark metadata.git_commit is not a git SHA"
    ]


def _write_rust_watchlist_benchmark(
    path: Path,
    *,
    speedup: float = 1.5,
    git_dirty: bool = False,
    timestamp_utc: str | None = "2026-06-01T00:00:00Z",
) -> None:
    metadata = _benchmark_metadata(git_dirty=git_dirty, timestamp_utc=timestamp_utc)
    path.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "results": [
                    {
                        "case": "read_values_plain",
                        "competitor": "rustypyxl",
                        "competitor_version": "0.3.1",
                    }
                ],
                "comparisons": [
                    {
                        "case": "read_values_plain",
                        "competitor": "rustypyxl",
                        "speedup_vs_competitor": speedup,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "python_binding_api",
                        "same_api_surface": False,
                    }
                ],
            }
        )
    )


def _write_ready_openpyxl_benchmark(
    path: Path,
    *,
    timestamp_utc: str | None = "2026-06-01T00:00:00Z",
) -> None:
    metadata = _benchmark_metadata(timestamp_utc=timestamp_utc)
    path.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )


def _patch_ready_claim_inputs(monkeypatch) -> None:
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )


def test_sota_audit_blocks_claim_when_evidence_or_speed_is_not_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "fast",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 3.0,
                    },
                    {
                        "case": "weak",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 1.5,
                    },
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": False,
            "exhaustive_claim_ready": False,
            "missing_requirement_ids": ["current_evidence_bundle_ready"],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": False,
            "bundle_issue_count": 2,
            "overall_missing_action_counts": {"defer_excel_batch": 2},
            "overall_missing_lane_counts": {"render": 2},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["compat"]["openpyxl_gap_count"] == 0
    assert report["performance"]["weak_case_count"] == 1
    assert report["performance"]["weak_cases"][0]["case"] == "weak"
    assert report["evidence"]["bundle_ready"] is False
    assert report["evidence"]["missing_report_count"] == 2
    assert report["evidence"]["remaining_direct_headless_step_count"] == 0
    assert report["evidence"]["remaining_deferred_excel_step_count"] == 2
    assert report["evidence"]["remaining_followup_coverage_gate_count"] == 0
    assert report["evidence"]["independent_headless_backlog_clear"] is True
    assert report["evidence"]["next_required_proof_mode"] == "explicit_excel_batch"
    assert "current supported-fidelity evidence bundle is not ready" in report["blockers"]
    assert "exhaustive no-gap claim is still unproven" in report["blockers"]


def test_sota_audit_reports_remaining_coverage_gates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": False,
            "exhaustive_claim_ready": False,
            "missing_requirement_ids": ["current_evidence_bundle_ready"],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": False,
            "bundle_issue_count": 2,
            "overall_missing_action_counts": {"rerun_after_upstream_evidence": 1},
            "overall_missing_lane_counts": {"coverage_gate": 1},
            "steps": [
                {
                    "name": "excel_render_full_pack_coverage_gate",
                    "lane": "coverage_gate",
                    "action": "rerun_after_upstream_evidence",
                    "missing_known_upstream_report_count": 1,
                    "missing_upstream_report_names": ["excel_render_full_pack_report"],
                    "unknown_upstream_report_count": 1,
                    "unknown_upstream_reports": ["/tmp/old-render-report.json"],
                },
                {
                    "name": "excel_render_full_pack_report",
                    "lane": "render",
                    "action": "defer_excel_batch",
                },
            ],
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["evidence"]["remaining_coverage_gate_count"] == 1
    assert report["evidence"]["remaining_followup_coverage_gate_count"] == 1
    assert report["evidence"]["next_required_proof_mode"] == "headless_after_upstream_evidence"
    assert report["evidence"]["remaining_coverage_gates"] == [
        {
            "name": "excel_render_full_pack_coverage_gate",
            "missing_known_upstream_report_count": 1,
            "missing_upstream_report_names": ["excel_render_full_pack_report"],
            "unknown_upstream_report_count": 1,
            "unknown_upstream_reports": ["/tmp/old-render-report.json"],
        }
    ]


def test_sota_audit_groups_remaining_evidence_by_next_proof_batch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": False,
            "exhaustive_claim_ready": False,
            "missing_requirement_ids": ["current_evidence_bundle_ready"],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": False,
            "bundle_issue_count": 3,
            "overall_missing_action_counts": {
                "defer_excel_batch": 2,
                "rerun_after_upstream_evidence": 1,
            },
            "overall_missing_lane_counts": {"render": 2, "coverage_gate": 1},
            "selected_dependency_round_counts": {"0": 1, "1": 2},
            "selected_unresolved_dependency_step_count": 0,
            "steps": [
                {
                    "name": "first_render",
                    "lane": "render",
                    "action": "defer_excel_batch",
                    "dependency_round": 0,
                    "opens_excel_or_render_oracle": True,
                },
                {
                    "name": "second_render",
                    "lane": "render",
                    "action": "defer_excel_batch",
                    "dependency_round": 1,
                    "opens_excel_or_render_oracle": True,
                },
                {
                    "name": "coverage_after_render",
                    "lane": "coverage_gate",
                    "action": "rerun_after_upstream_evidence",
                    "dependency_round": 1,
                    "opens_excel_or_render_oracle": False,
                },
            ],
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["evidence"]["remaining_dependency_round_counts"] == {"0": 1, "1": 2}
    assert report["evidence"]["remaining_unresolved_dependency_step_count"] == 0
    assert report["evidence"]["missing_report_count"] == 3
    assert report["evidence"]["remaining_direct_headless_step_count"] == 0
    assert report["evidence"]["remaining_deferred_excel_step_count"] == 2
    assert report["evidence"]["remaining_followup_coverage_gate_count"] == 1
    assert report["evidence"]["independent_headless_backlog_clear"] is True
    assert report["evidence"]["next_required_proof_mode"] == "explicit_excel_batch"
    assert report["evidence"]["next_proof_batch_count"] == 2
    assert report["evidence"]["next_proof_batches"] == [
        {
            "dependency_round": 0,
            "name": "round_0",
            "step_count": 1,
            "lane_counts": {"render": 1},
            "action_counts": {"defer_excel_batch": 1},
            "excel_or_render_step_count": 1,
            "coverage_gate_count": 0,
            "requires_explicit_excel_batch": True,
            "safe_to_execute_automatically": False,
            "sample_step_names": ["first_render"],
        },
        {
            "dependency_round": 1,
            "name": "round_1",
            "step_count": 2,
            "lane_counts": {"coverage_gate": 1, "render": 1},
            "action_counts": {
                "defer_excel_batch": 1,
                "rerun_after_upstream_evidence": 1,
            },
            "excel_or_render_step_count": 1,
            "coverage_gate_count": 1,
            "requires_explicit_excel_batch": True,
            "safe_to_execute_automatically": False,
            "sample_step_names": ["second_render", "coverage_after_render"],
        },
    ]


def test_sota_audit_compacts_missing_requirement_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": False,
            "exhaustive_claim_ready": False,
            "missing_requirement_ids": [
                "current_evidence_bundle_ready",
                "feature_specific_intentional_render_equivalence",
            ],
            "missing_requirements": [
                {
                    "id": "current_evidence_bundle_ready",
                    "status": "missing",
                    "evidence": {
                        "ready": False,
                        "report_count": 12,
                        "producer_count": 12,
                        "issue_count": 2,
                        "missing_report_lane_counts": {"render": 2},
                        "missing_report_action_counts": {"defer_excel_batch": 2},
                        "unused_large_list": ["do not expose"],
                    },
                },
                {
                    "id": "feature_specific_intentional_render_equivalence",
                    "status": "open",
                    "reason": "render proof is still not exhaustive",
                    "evidence": {
                        "ready_report_count": 3,
                        "excel_report_count": 2,
                        "frontier_candidate_count": 1,
                        "frontier_expected_report_count": 4,
                        "frontier_observed_report_count": 3,
                        "frontier_missing_report_count": 1,
                        "frontier_missing_candidate_count": 1,
                        "frontier_empty_candidate_count": 0,
                        "frontier_evidence_ready": False,
                        "coverage_matrix": {
                            "current_target_ready": False,
                            "expected_mutation_count": 7,
                            "observed_expected_mutation_count": 4,
                            "missing_expected_mutation_count": 3,
                            "missing_expected_mutations": ["rename_first_sheet"],
                        },
                        "render_delta_evidence": {
                            "required_report_count": 2,
                            "present_report_count": 2,
                            "ready_report_count": 1,
                            "changed_count": 1,
                        },
                    },
                },
            ],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": False,
            "bundle_issue_count": 2,
            "overall_missing_action_counts": {"defer_excel_batch": 2},
            "overall_missing_lane_counts": {"render": 2},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    requirements = report["evidence"]["missing_requirements"]
    assert [requirement["id"] for requirement in requirements] == [
        "current_evidence_bundle_ready",
        "feature_specific_intentional_render_equivalence",
    ]
    assert requirements[0]["evidence_summary"] == {
        "ready": False,
        "report_count": 12,
        "producer_count": 12,
        "issue_count": 2,
        "missing_report_lane_counts": {"render": 2},
        "missing_report_action_counts": {"defer_excel_batch": 2},
    }
    assert requirements[1]["reason"] == "render proof is still not exhaustive"
    assert requirements[1]["evidence_summary"]["coverage_matrix"] == {
        "current_target_ready": False,
        "expected_mutation_count": 7,
        "observed_expected_mutation_count": 4,
        "missing_expected_mutation_count": 3,
        "missing_expected_mutations": ["rename_first_sheet"],
    }
    assert requirements[1]["evidence_summary"]["frontier_expected_report_count"] == 4
    assert requirements[1]["evidence_summary"]["frontier_observed_report_count"] == 3
    assert requirements[1]["evidence_summary"]["frontier_missing_report_count"] == 1
    assert requirements[1]["evidence_summary"]["frontier_missing_candidate_count"] == 1
    assert requirements[1]["evidence_summary"]["frontier_empty_candidate_count"] == 0
    assert requirements[1]["evidence_summary"]["frontier_evidence_ready"] is False


def test_sota_audit_can_pass_when_all_inputs_are_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is True
    assert report["sota_confidence_ready"] is True
    assert report["supported_scope_sota_gate_ready"] is True
    assert report["claim_gates"] == {
        "api_compat_gate_ready": True,
        "current_fidelity_gate_ready": True,
        "openpyxl_performance_gate_ready": True,
        "rust_competitor_benchmark_gate_ready": True,
        "rust_competitor_set_gate_ready": True,
        "rust_watchlist_gate_ready": True,
        "rust_competitor_gate_ready": True,
        "finite_evidence_frontiers_ready": True,
        "supported_scope_sota_gate_ready": True,
        "exhaustive_claim_ready": True,
    }
    assert report["blockers"] == []
    assert report["performance"]["min_observed_speedup"] == 2.5
    assert report["performance"]["benchmark_timestamp_utc"] == "2026-06-01T00:00:00Z"
    assert report["performance"]["benchmark_age_days"] == 0.0
    assert report["performance"]["benchmark_max_age_days"] == 14.0
    assert report["performance"]["benchmark_fresh"] is True
    assert report["performance"]["freshness_blockers"] == []
    assert report["rust_competitors"]["missing_competitors"] == []
    assert report["rust_competitors"]["missing_version_competitors"] == []
    assert report["rust_competitors"]["required_case_family_count"] == _default_rust_case_count()
    assert (
        report["rust_competitors"]["covered_required_case_family_count"]
        == _default_rust_case_count()
    )
    rust_xlsxwriter_coverage = next(
        row
        for row in report["rust_competitors"]["required_case_family_coverage"]
        if row["competitor"] == "rust_xlsxwriter"
    )
    assert rust_xlsxwriter_coverage["families"][0] == {
        "family": "plain_value_write",
        "required_terms": ["write", "plain"],
        "covered": True,
        "matched_cases": ["write_cell_by_cell_plain"],
    }
    assert report["rust_competitors"]["benchmark_timestamp_utc"] == ("2026-06-01T00:00:00Z")
    assert report["rust_competitors"]["benchmark_fresh"] is True
    assert report["rust_competitors"]["freshness_blockers"] == []
    assert report["rust_competitor_set"]["main_rust_competitor_set_ready"] is True
    assert report["rust_competitor_set"]["report_timestamp_utc"] == ("2026-06-01T00:00:00Z")
    assert report["rust_competitor_set"]["report_age_days"] == 0.0
    assert report["rust_competitor_set"]["max_age_days"] == 14.0
    assert report["rust_competitor_set"]["report_fresh"] is True
    assert report["rust_competitor_set"]["freshness_blockers"] == []
    assert report["rust_competitor_set"]["registry_metadata_fetched"] is True
    assert report["rust_competitor_set"]["crates_io_discovery_fetched"] is True
    assert report["rust_competitor_set"]["discovery_queries"] == [
        "xlsx",
        "excel",
        "spreadsheet",
    ]
    assert report["rust_competitor_set"]["discovery_per_page"] == 50
    assert report["rust_competitor_set"]["discovery_min_downloads"] == 1000
    assert report["rust_competitor_set"]["discovery_min_recent_downloads"] == 50
    assert report["rust_competitor_set"]["discovery_error_queries"] == []
    assert report["rust_competitor_set"]["benchmark_present"] is True
    assert report["rust_competitor_set"]["benchmark_competitor_versions"] == {
        competitor: "1.2.3" for competitor in sota.DEFAULT_RUST_COMPETITORS
    }
    assert {
        row["competitor"]: row["version_captured"]
        for row in report["rust_competitor_set"]["required_competitor_version_evidence"]
    } == {competitor: True for competitor in sota.DEFAULT_RUST_COMPETITORS}
    assert report["rust_competitor_set"]["missing_required_version_evidence"] == []
    assert report["rust_competitor_set"]["missing_from_benchmark"] == []
    assert report["rust_competitor_set"]["missing_benchmark_versions"] == []
    assert report["rust_competitor_set"]["stale_benchmark_versions"] == []
    assert report["rust_competitor_set"]["missing_required_case_family_count"] == 0
    assert report["rust_competitor_set"]["missing_required_case_families"] == []
    assert report["rust_competitor_set"]["status_counts"]["watchlist"] == 3
    assert report["rust_competitor_set"]["watchlist_promotion_review_ready"] is True
    assert report["rust_competitor_set"]["watchlist_promotion_review_count"] == 3
    assert report["rust_competitor_set"]["watchlist_packages_requiring_promotion"] == []
    assert report["rust_competitor_set"]["watchlist_promotion_adoption_complete"] is True
    assert report["rust_competitor_set"][
        "watchlist_promotion_adoption_missing"
    ] == []
    assert report["rust_competitor_set"]["watchlist_promotion_adoption_caveat"] is None
    assert (
        report["rust_competitor_set"]["watchlist_adoption_attention_review_count"]
        == 1
    )
    assert report["rust_competitor_set"]["watchlist_adoption_attention_reviews"][0][
        "id"
    ] == "python-calamine-reducto"
    assert report["rust_competitor_set"]["required_competitor_aliases"] == {
        "xlsxwriter": ["xlsxwriter-rs"]
    }
    assert (
        report["rust_competitor_set"]["requested_competitor_name_resolution_ready"]
        is True
    )
    assert (
        report["rust_competitor_set"]["requested_competitor_name_resolution_count"]
        == 1
    )
    assert report["rust_competitor_set"][
        "requested_competitor_name_resolution_blockers"
    ] == []
    assert report["rust_competitor_set"]["requested_competitor_name_resolutions"] == [
        {
            "requested_name": "xlsxwriter-rs",
            "resolution": "required_competitor_alias",
            "resolves_to_competitor": "xlsxwriter",
            "benchmarked_package": "xlsxwriter",
            "benchmarked_version": "1.2.3",
            "exact_package": "xlsxwriter-rs",
            "exact_package_source": "crates.io",
            "exact_package_gate_status": "watchlist",
            "exact_package_version": "0.1.0",
            "exact_package_decision": "remain_watchlist",
            "exact_package_promotion_needed_now": False,
            "exact_package_related_required_competitors": ["xlsxwriter"],
            "exact_package_reviewed": True,
            "requirement_satisfied": True,
        }
    ]
    assert report["rust_competitor_set"]["unclassified_discovery_hit_count"] == 0
    assert report["rust_competitor_set"]["unclassified_relevant_below_threshold_hit_count"] == 0
    assert report["rust_competitor_set"]["unclassified_relevant_below_threshold_hits"] == []
    markdown = sota.format_markdown_report(report)
    assert "| xlsxwriter | xlsxwriter-rs | Required writer comparator |" in markdown
    assert "Required Rust benchmark case-family coverage:" in markdown
    assert (
        "| rust_xlsxwriter | plain_value_write | true | write_cell_by_cell_plain |"
        in markdown
    )


def test_sota_audit_preserves_below_threshold_rust_hits(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark_path = tmp_path / "benchmark.json"
    rust_benchmark_path = tmp_path / "rust-benchmark.json"
    _write_ready_openpyxl_benchmark(benchmark_path)
    _write_rust_competitor_benchmark(rust_benchmark_path)
    rust_set_report = tmp_path / "rust-set.json"
    _write_rust_competitor_set_report(
        rust_set_report,
        below_threshold_hits=[
            {
                "query": "ooxml",
                "rank": 7,
                "id": "tiny-ooxml",
                "version": "0.0.1",
                "downloads": 12,
                "recent_downloads": 3,
                "description": "Tiny OOXML helper",
                "classified": False,
                "gate_status": None,
                "relevant_to_excel_library": True,
                "above_review_threshold": False,
            }
        ],
    )
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark_path,
        rust_competitor_benchmark=rust_benchmark_path,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
        now_utc=FIXED_NOW_UTC,
    )

    assert (
        report["rust_competitor_set"][
            "unclassified_relevant_below_threshold_hit_count"
        ]
        == 1
    )
    assert report["rust_competitor_set"][
        "unclassified_relevant_below_threshold_hits"
    ] == [
        {
            "query": "ooxml",
            "rank": 7,
            "id": "tiny-ooxml",
            "version": "0.0.1",
            "downloads": 12,
            "recent_downloads": 3,
            "description": "Tiny OOXML helper",
            "classified": False,
            "gate_status": None,
            "relevant_to_excel_library": True,
            "above_review_threshold": False,
        }
    ]
    assert report["claim_gates"]["rust_competitor_set_gate_ready"] is True


def test_sota_audit_blocks_missing_required_version_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    payload = json.loads(rust_set_report.read_text())
    for row in payload["required_competitor_version_evidence"]:
        if row["competitor"] == "calamine":
            row["registry_version"] = None
            row["version_captured"] = False
    rust_set_report.write_text(json.dumps(payload))
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["supported_scope_sota_gate_ready"] is False
    assert report["claim_gates"]["rust_competitor_set_gate_ready"] is False
    assert report["rust_competitor_set"]["missing_required_version_evidence"] == [
        "calamine"
    ]
    assert (
        "Rust competitor set audit is missing captured registry version evidence for: calamine"
        in report["blockers"]
    )


def test_sota_audit_blocks_rust_competitor_set_without_case_family_summary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    payload = json.loads(rust_set_report.read_text())
    del payload["missing_required_case_family_count"]
    del payload["missing_required_case_families"]
    rust_set_report.write_text(json.dumps(payload))
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["claim_gates"]["rust_competitor_set_gate_ready"] is False
    assert report["rust_competitor_set"]["missing_required_case_family_count"] is None
    assert (
        "Rust competitor set audit is missing required case-family coverage summary"
        in report["blockers"]
    )


def test_sota_audit_blocks_watchlist_package_that_requires_promotion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    payload = json.loads(rust_set_report.read_text())
    payload["watchlist_promotion_review_ready"] = False
    payload["watchlist_packages_requiring_promotion"] = ["rustypyxl"]
    rust_set_report.write_text(json.dumps(payload))
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["claim_gates"]["rust_competitor_set_gate_ready"] is False
    assert report["rust_competitor_set"]["watchlist_promotion_review_ready"] is False
    assert report["rust_competitor_set"]["watchlist_packages_requiring_promotion"] == [
        "rustypyxl"
    ]
    assert "Rust watchlist packages need promotion to required lanes: rustypyxl" in (
        report["blockers"]
    )


def test_sota_audit_blocks_missing_watchlist_adoption_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    payload = json.loads(rust_set_report.read_text())
    payload["watchlist_promotion_adoption_missing_count"] = 1
    payload["watchlist_promotion_adoption_missing"] = ["rustypyxl"]
    payload["watchlist_promotion_adoption_complete"] = False
    payload["watchlist_promotion_adoption_caveat"] = (
        "Objective watchlist promotion can be applied where registry adoption "
        "data exists; watchlist packages without adoption data remain reviewed "
        "caveats."
    )
    rust_set_report.write_text(json.dumps(payload))
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["supported_scope_sota_gate_ready"] is False
    assert report["claim_gates"]["rust_competitor_set_gate_ready"] is False
    assert (
        report["rust_competitor_set"]["watchlist_promotion_adoption_complete"]
        is False
    )
    assert report["rust_competitor_set"][
        "watchlist_promotion_adoption_missing"
    ] == ["rustypyxl"]
    assert "Rust watchlist adoption evidence is missing for: rustypyxl" in (
        report["blockers"]
    )


def test_sota_audit_blocks_requested_competitor_name_resolution_gap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    payload = json.loads(rust_set_report.read_text())
    payload["watchlist_promotion_reviews"][0]["promotion_needed_now"] = True
    payload["watchlist_promotion_reviews"][0]["decision"] = "promote_to_required"
    rust_set_report.write_text(json.dumps(payload))
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["supported_scope_sota_gate_ready"] is False
    assert report["claim_gates"]["rust_competitor_set_gate_ready"] is False
    assert (
        report["rust_competitor_set"]["requested_competitor_name_resolution_ready"]
        is False
    )
    assert report["rust_competitor_set"][
        "requested_competitor_name_resolution_blockers"
    ] == ["xlsxwriter-rs"]
    assert report["rust_competitor_set"]["requested_competitor_name_resolutions"][
        0
    ]["requirement_satisfied"] is False
    assert (
        "Rust requested competitor name resolution is not ready: xlsxwriter-rs"
        in report["blockers"]
    )


def test_sota_audit_blocks_openpyxl_benchmark_missing_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    payload = json.loads(benchmark.read_text())
    del payload["metadata"]["openpyxl_version"]
    benchmark.write_text(json.dumps(payload))
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["claim_gates"]["openpyxl_performance_gate_ready"] is False
    assert report["performance"]["benchmark_metadata_ready"] is False
    assert report["performance"]["benchmark_metadata_missing_fields"] == ["openpyxl_version"]
    assert report["performance"]["metadata_blockers"] == [
        "openpyxl performance benchmark is missing metadata fields: openpyxl_version"
    ]
    assert report["blockers"] == [
        "openpyxl performance benchmark is missing metadata fields: openpyxl_version"
    ]


def test_sota_audit_blocks_rust_benchmark_missing_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(rust_benchmark)
    payload = json.loads(rust_benchmark.read_text())
    del payload["metadata"]["cpu_brand"]
    rust_benchmark.write_text(json.dumps(payload))
    _write_rust_competitor_set_report(rust_set_report)
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["claim_gates"]["rust_competitor_benchmark_gate_ready"] is False
    assert report["claim_gates"]["rust_competitor_gate_ready"] is False
    assert report["rust_competitors"]["benchmark_metadata_ready"] is False
    assert report["rust_competitors"]["benchmark_metadata_missing_fields"] == ["cpu_brand"]
    assert report["rust_competitors"]["metadata_blockers"] == [
        "Rust competitor benchmark is missing metadata fields: cpu_brand"
    ]
    assert report["blockers"] == ["Rust competitor benchmark is missing metadata fields: cpu_brand"]


def test_sota_audit_blocks_stale_openpyxl_benchmark(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(
        benchmark,
        timestamp_utc="2026-05-01T00:00:00Z",
    )
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["claim_gates"]["openpyxl_performance_gate_ready"] is False
    assert report["performance"]["benchmark_fresh"] is False
    assert report["performance"]["benchmark_age_days"] == 31.0
    assert report["performance"]["freshness_blockers"] == [
        "openpyxl performance benchmark is stale: 31.000 days old, max 14.000"
    ]
    assert report["blockers"] == [
        "openpyxl performance benchmark is stale: 31.000 days old, max 14.000"
    ]


def test_sota_audit_blocks_stale_rust_competitor_benchmark(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(
        rust_benchmark,
        timestamp_utc="2026-05-01T00:00:00Z",
    )
    _write_rust_competitor_set_report(rust_set_report)
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["claim_gates"]["rust_competitor_benchmark_gate_ready"] is False
    assert report["claim_gates"]["rust_competitor_gate_ready"] is False
    assert report["rust_competitors"]["benchmark_fresh"] is False
    assert report["rust_competitors"]["freshness_blockers"] == [
        "Rust competitor benchmark is stale: 31.000 days old, max 14.000"
    ]
    assert report["blockers"] == ["Rust competitor benchmark is stale: 31.000 days old, max 14.000"]


def test_sota_audit_blocks_rust_watchlist_benchmark_without_timestamp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_watchlist = tmp_path / "rust-watchlist.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_watchlist_benchmark(rust_watchlist, timestamp_utc=None)
    _write_rust_competitor_set_report(rust_set_report)
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_watchlist_benchmark=rust_watchlist,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["claim_gates"]["rust_watchlist_gate_ready"] is False
    assert report["claim_gates"]["rust_competitor_gate_ready"] is False
    assert report["rust_watchlist"]["benchmark_fresh"] is False
    assert report["rust_watchlist"]["freshness_blockers"] == [
        "Rust watchlist benchmark is missing metadata.timestamp_utc"
    ]
    assert report["blockers"] == ["Rust watchlist benchmark is missing metadata.timestamp_utc"]


def test_sota_audit_blocks_stale_rust_competitor_set_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(
        rust_set_report,
        timestamp_utc="2026-05-01T00:00:00Z",
    )
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["supported_scope_sota_gate_ready"] is False
    assert report["claim_gates"]["rust_competitor_set_gate_ready"] is False
    assert report["rust_competitor_set"]["report_fresh"] is False
    assert report["rust_competitor_set"]["report_age_days"] == 31.0
    assert report["rust_competitor_set"]["freshness_blockers"] == [
        "Rust competitor set audit is stale: 31.000 days old, max 14.000"
    ]
    assert report["blockers"] == ["Rust competitor set audit is stale: 31.000 days old, max 14.000"]


def test_sota_audit_blocks_rust_competitor_set_report_without_timestamp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_ready_openpyxl_benchmark(benchmark)
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report, timestamp_utc=None)
    _patch_ready_claim_inputs(monkeypatch)

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["claim_gates"]["rust_competitor_set_gate_ready"] is False
    assert report["rust_competitor_set"]["report_fresh"] is False
    assert report["rust_competitor_set"]["report_age_days"] is None
    assert report["rust_competitor_set"]["freshness_blockers"] == [
        "Rust competitor set audit is missing timestamp_utc"
    ]
    assert report["blockers"] == ["Rust competitor set audit is missing timestamp_utc"]


def test_sota_audit_separates_supported_scope_gate_from_exhaustive_claim(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": False,
            "finite_evidence_frontiers_ready": True,
            "finite_evidence_frontier_blocker_ids": [],
            "unbounded_claim_boundary_ids": ["future_surface_exhaustiveness"],
            "missing_requirement_ids": ["future_surface_exhaustiveness"],
            "missing_requirements": [
                {
                    "id": "future_surface_exhaustiveness",
                    "status": "open",
                    "reason": "future surfaces are open-ended",
                    "evidence": {
                        "present_gap_radar_report_count": 49,
                        "required_gap_radar_report_count": 49,
                        "clear_gap_radar_report_count": 49,
                        "fixture_count": 783,
                    },
                }
            ],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["supported_scope_sota_gate_ready"] is True
    assert report["claim_gates"]["current_fidelity_gate_ready"] is True
    assert report["claim_gates"]["rust_competitor_gate_ready"] is True
    assert report["claim_gates"]["finite_evidence_frontiers_ready"] is True
    assert report["claim_gates"]["exhaustive_claim_ready"] is False
    assert report["evidence"]["finite_evidence_frontiers_ready"] is True
    assert report["evidence"]["finite_evidence_frontier_blocker_ids"] == []
    assert report["evidence"]["unbounded_claim_boundary_ids"] == ["future_surface_exhaustiveness"]
    assert report["sota_claim_ready"] is False
    assert report["blockers"] == ["exhaustive no-gap claim is still unproven"]

    markdown = sota.format_markdown_report(report)

    assert "| Supported-scope SOTA gate ready | true |" in markdown
    assert "| Current fidelity gate ready | true |" in markdown
    assert "| Rust competitor gate ready | true |" in markdown
    assert "| Finite named-frontier evidence ready | true |" in markdown
    assert "| Exhaustive all-future-surface claim ready | false |" in markdown
    assert "the supported-scope gates are green today" in markdown
    assert "named finite frontier evidence is also green" in markdown


def test_compat_summary_includes_parity_surface_known_gaps() -> None:
    summary = sota._compat_summary()

    assert summary["compat_spec_gap_count"] == 0
    assert summary["surface_entry_count"] > 0
    assert summary["surface_known_gap_count"] == 0
    assert summary["out_of_scope_count"] == 7
    assert summary["out_of_scope_openpyxl_advantage_count"] == 0
    assert summary["openpyxl_gap_count"] == 0


def test_sota_audit_blocks_openpyxl_surface_known_gaps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota,
        "_compat_summary",
        lambda: {
            "status_totals": {"supported": 1},
            "compat_spec_gap_count": 0,
            "compat_spec_gaps": [],
            "surface_entry_count": 1,
            "surface_known_gap_count": 1,
            "surface_known_gaps": [
                {
                    "openpyxl_path": "openpyxl.example.Missing",
                    "wolfxl_path": None,
                    "notes": "missing example",
                }
            ],
            "out_of_scope_count": 0,
            "out_of_scope_openpyxl_advantage_count": 0,
            "out_of_scope_openpyxl_advantages": [],
            "openpyxl_gap_count": 1,
            "openpyxl_gaps": [
                {
                    "id": "openpyxl.example.Missing",
                    "status": "known_gap",
                    "notes": "missing example",
                }
            ],
        },
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["compat"]["surface_known_gap_count"] == 1
    assert "openpyxl parity surface still has known gaps" in report["blockers"]


def test_sota_audit_blocks_ambiguous_out_of_scope_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota,
        "_compat_summary",
        lambda: {
            "status_totals": {"supported": 1, "out_of_scope": 1},
            "compat_spec_gap_count": 0,
            "compat_spec_gaps": [],
            "surface_entry_count": 1,
            "surface_known_gap_count": 0,
            "surface_known_gaps": [],
            "out_of_scope_count": 1,
            "out_of_scope_openpyxl_advantage_count": 1,
            "out_of_scope_openpyxl_advantages": [
                {
                    "id": "ambiguous",
                    "openpyxl": "available in openpyxl",
                    "wolfxl": "out of scope",
                    "notes": "ambiguous",
                }
            ],
            "openpyxl_gap_count": 0,
            "openpyxl_gaps": [],
        },
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert "out-of-scope compatibility rows may still be openpyxl advantages" in report["blockers"]


def test_sota_audit_surfaces_clean_rust_watchlist_benchmark(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_watchlist_benchmark = tmp_path / "rust-watchlist-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_watchlist_benchmark(rust_watchlist_benchmark)
    _write_rust_competitor_set_report(rust_set_report)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_watchlist_benchmark=rust_watchlist_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is True
    assert report["sota_confidence_ready"] is True
    assert report["blockers"] == []
    assert report["rust_watchlist"]["covered_competitors"] == ["rustypyxl"]
    assert report["rust_watchlist"]["competitor_versions"] == {"rustypyxl": "0.3.1"}
    assert report["rust_watchlist"]["min_observed_speedup"] == 1.5


def test_rust_watchlist_summary_prefers_direct_modify_rows(tmp_path: Path) -> None:
    benchmark = tmp_path / "rust-watchlist-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "results": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "office_oxide",
                        "competitor_version": "0.1.2",
                    }
                ],
                "comparisons": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "office_oxide",
                        "speedup_vs_competitor": 1.5,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": False,
                    }
                ],
                "wolfxl_direct_modify_comparisons": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "office_oxide",
                        "speedup_vs_competitor": 2.4,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    }
                ],
                "memory_comparisons": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "office_oxide",
                        "wolfxl_peak_rss_bytes": 58_000_000,
                        "competitor_peak_rss_bytes": 20_000_000,
                        "peak_rss_excess_bytes": 38_000_000,
                        "peak_rss_ratio_vs_competitor": 2.9,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": False,
                    }
                ],
                "wolfxl_direct_modify_memory_comparisons": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "office_oxide",
                        "wolfxl_peak_rss_bytes": 16_000_000,
                        "competitor_peak_rss_bytes": 20_000_000,
                        "peak_rss_excess_bytes": -4_000_000,
                        "peak_rss_ratio_vs_competitor": 0.8,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    }
                ],
            }
        )
    )

    report = sota._rust_watchlist_summary(
        benchmark,
        min_speedup=1.0,
        headroom_warning=1.1,
        required_competitors=sota.DEFAULT_RUST_COMPETITORS,
        max_age_days=14.0,
        now_utc=FIXED_NOW_UTC,
    )

    assert report["covered_competitors"] == ["office_oxide"]
    assert report["min_observed_speedup"] == 2.4
    assert report["memory_comparison_count"] == 1
    assert report["max_observed_memory_ratio"] == 0.8
    assert report["weak_memory_case_count"] == 0
    assert report["weak_memory_cases"] == []


def test_sota_audit_blocks_weak_supplied_rust_watchlist_benchmark(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_watchlist_benchmark = tmp_path / "rust-watchlist-benchmark.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    _write_rust_watchlist_benchmark(rust_watchlist_benchmark, speedup=0.9)
    _write_rust_competitor_set_report(rust_set_report)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_watchlist_benchmark=rust_watchlist_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert "1 Rust watchlist benchmark lanes are below 1.00x" in report["blockers"]
    assert report["rust_watchlist"]["weak_case_count"] == 1
    markdown = sota.format_markdown_report(report)
    assert "speed evidence is not the blocker" not in markdown
    assert "supplied Rust watchlist evidence is red" in markdown
    assert "1 optional watchlist lane is below the strict 1.00x line" in markdown
    assert "blocked by weak Rust watchlist evidence" in markdown


def test_sota_audit_warns_on_thin_rust_headroom_without_blocking(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_watchlist = tmp_path / "rust-watchlist.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_rust_competitor_benchmark(rust_benchmark, speedup=1.05)
    _write_rust_watchlist_benchmark(rust_watchlist)
    _write_rust_competitor_set_report(rust_set_report)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
            "selected_dependency_round_counts": {},
            "selected_unresolved_dependency_step_count": 0,
            "steps": [],
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        rust_competitor_set_report=rust_set_report,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
        rust_min_speedup=1.0,
        rust_headroom_warning=1.1,
    )

    assert report["sota_claim_ready"] is True
    assert report["sota_confidence_ready"] is False
    assert report["blockers"] == []
    assert report["confidence_warnings"] == [
        "17 Rust competitor lanes clear 1.00x but are below the 1.10x confidence warning line"
    ]
    assert report["rust_competitors"]["thin_margin_case_count"] == _default_rust_case_count()
    assert report["rust_competitors"]["thin_margin_cases"][0]["competitor"] == "rust_xlsxwriter"
    assert report["rust_competitors"]["headroom_warning_threshold"] == 1.1


def test_sota_audit_strict_confidence_fails_on_warnings(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_watchlist = tmp_path / "rust-watchlist.json"
    rust_set_report = tmp_path / "rust-set-report.json"
    _write_rust_competitor_benchmark(rust_benchmark, speedup=1.05)
    _write_rust_watchlist_benchmark(rust_watchlist)
    _write_rust_competitor_set_report(rust_set_report)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
            "selected_dependency_round_counts": {},
            "selected_unresolved_dependency_step_count": 0,
            "steps": [],
        },
    )

    exit_code = sota.main(
        [
            "--evidence-manifest",
            str(tmp_path / "bundle.json"),
            "--benchmark",
            str(benchmark),
            "--rust-competitor-benchmark",
            str(rust_benchmark),
            "--rust-watchlist-benchmark",
            str(rust_watchlist),
            "--rust-competitor-set-report",
            str(rust_set_report),
            "--strict-confidence",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["sota_claim_ready"] is True
    assert output["sota_confidence_ready"] is False
    assert output["confidence_warnings"]


def test_markdown_report_does_not_call_rust_warnings_clear_when_present() -> None:
    report = {
        "sota_claim_ready": False,
        "sota_confidence_ready": False,
        "blockers": ["evidence still missing"],
        "confidence_warnings": ["thin Rust lane"],
        "performance": {"min_observed_speedup": 2.5},
        "rust_competitors": {
            "min_observed_speedup": 1.05,
            "claim_basis_counts": {},
            "claim_comparison_rows": [],
            "public_rows_replaced_by_same_surface": [],
        },
        "rust_watchlist": {"min_observed_speedup": 1.5},
        "rust_competitor_set": {
            "required_competitors": [],
            "blockers": [],
        },
        "evidence": {
            "missing_report_count": 1,
            "remaining_direct_headless_step_count": 0,
            "remaining_deferred_excel_step_count": 1,
            "remaining_followup_coverage_gate_count": 0,
            "next_required_proof_mode": "explicit_excel_batch",
        },
        "inputs": {},
    }

    markdown = sota.format_markdown_report(report)

    assert "Rust confidence warnings are clear" not in markdown
    assert "1 Rust confidence warning remains" in markdown


def test_markdown_report_describes_no_queued_proof_batch_when_mode_is_none() -> None:
    report = {
        "sota_claim_ready": False,
        "sota_confidence_ready": False,
        "blockers": ["exhaustive no-gap claim is still unproven"],
        "confidence_warnings": [],
        "compat": {},
        "performance": {"min_observed_speedup": 2.5},
        "rust_competitors": {
            "min_observed_speedup": 1.25,
            "missing_required_case_family_count": 0,
            "claim_basis_counts": {},
            "claim_comparison_rows": [],
            "public_rows_replaced_by_same_surface": [],
        },
        "rust_watchlist": {"min_observed_speedup": 1.5},
        "rust_competitor_set": {
            "required_competitors": [],
            "blockers": [],
        },
        "evidence": {
            "missing_report_count": 0,
            "remaining_direct_headless_step_count": 0,
            "remaining_deferred_excel_step_count": 0,
            "remaining_followup_coverage_gate_count": 0,
            "next_required_proof_mode": "none",
        },
        "inputs": {},
    }

    markdown = sota.format_markdown_report(report)

    assert "The next real proof step is the planned Excel evidence batch" not in markdown
    assert "no deferred Excel reports" in markdown
    assert "not by a missing queued evidence report" in markdown


def test_sota_audit_requires_rust_competitor_set_report_when_configured(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        require_rust_competitor_set_report=True,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert "no Rust competitor set audit JSON supplied" in report["blockers"]


def test_sota_audit_blocks_dirty_benchmark_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark, git_dirty=True)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(git_dirty=True),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert "openpyxl benchmark was captured from a dirty git worktree" in report["blockers"]
    assert "Rust competitor benchmark was captured from a dirty git worktree" in report["blockers"]


def test_sota_audit_blocks_memory_regressions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
                "memory_comparisons": [
                    {
                        "case": "good_memory",
                        "engine": "wolfxl",
                        "peak_rss_ratio_vs_openpyxl": 0.75,
                    },
                    {
                        "case": "weak_memory",
                        "engine": "wolfxl",
                        "peak_rss_ratio_vs_openpyxl": 1.05,
                    },
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["performance"]["weak_memory_case_count"] == 1
    assert report["performance"]["weak_memory_cases"][0]["case"] == "weak_memory"
    assert "1 memory benchmark lanes peak above 1.00x openpyxl" in report["blockers"]


def test_sota_audit_treats_tiny_memory_excess_as_near_parity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
                "memory": [
                    {
                        "case": "small_read",
                        "engine": "openpyxl",
                        "peak_rss_bytes": 60_000_000,
                        "delta_rss_bytes": 2_000_000,
                    },
                    {
                        "case": "small_read",
                        "engine": "wolfxl",
                        "peak_rss_bytes": 61_000_000,
                        "delta_rss_bytes": 2_200_000,
                    },
                ],
                "memory_comparisons": [
                    {
                        "case": "small_read",
                        "engine": "wolfxl",
                        "peak_rss_ratio_vs_openpyxl": 1.0167,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is True
    assert report["performance"]["weak_memory_case_count"] == 0
    assert report["performance"]["near_parity_memory_case_count"] == 1
    near_parity = report["performance"]["near_parity_memory_cases"][0]
    assert near_parity["case"] == "small_read"
    assert near_parity["peak_rss_excess_bytes"] == 1_000_000
    assert report["blockers"] == []


def test_sota_audit_blocks_material_memory_excess_with_raw_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
                "memory": [
                    {
                        "case": "big_read",
                        "engine": "openpyxl",
                        "peak_rss_bytes": 60_000_000,
                        "delta_rss_bytes": 2_000_000,
                    },
                    {
                        "case": "big_read",
                        "engine": "wolfxl",
                        "peak_rss_bytes": 70_000_000,
                        "delta_rss_bytes": 12_000_000,
                    },
                ],
                "memory_comparisons": [
                    {
                        "case": "big_read",
                        "engine": "wolfxl",
                        "peak_rss_ratio_vs_openpyxl": 1.1667,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["performance"]["weak_memory_case_count"] == 1
    assert report["performance"]["near_parity_memory_case_count"] == 0
    assert report["performance"]["weak_memory_cases"][0]["case"] == "big_read"
    assert report["performance"]["weak_memory_cases"][0]["peak_rss_excess_bytes"] == 10_000_000


def test_latest_benchmark_json_ignores_non_openpyxl_audit_reports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark_dir = tmp_path / "docs" / "performance" / "baselines"
    benchmark_dir.mkdir(parents=True)
    openpyxl_benchmark = benchmark_dir / "2026-05-31-openpyxl.json"
    rust_benchmark = benchmark_dir / "2026-05-31-current-rust-competitors.json"
    rust_set_audit = benchmark_dir / "2026-05-31-current-rust-competitor-set-audit.json"
    openpyxl_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "read_values_plain",
                        "competitor": "calamine",
                        "speedup_vs_competitor": 1.2,
                    }
                ],
            }
        )
    )
    rust_set_audit.write_text(
        json.dumps(
            {
                "main_rust_competitor_set_ready": True,
                "required_competitors": list(sota.DEFAULT_RUST_COMPETITORS),
            }
        )
    )
    rust_benchmark.touch()
    rust_set_audit.touch()
    monkeypatch.setattr(sota, "ROOT", tmp_path)

    assert sota._latest_benchmark_json() == openpyxl_benchmark


def test_sota_audit_blocks_temporary_wolfxl_benchmark_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    temp_root = Path(tempfile.gettempdir())
    benchmark = temp_root / "wolfxl-sota-audit-openpyxl-benchmark.json"
    rust_benchmark = temp_root / "wolfxl-sota-audit-rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    _write_rust_competitor_benchmark(rust_benchmark)
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    try:
        report = sota.audit_sota_claim(
            evidence_manifest=tmp_path / "bundle.json",
            benchmark=benchmark,
            rust_competitor_benchmark=rust_benchmark,
            min_speedup=2.0,
        )
    finally:
        benchmark.unlink(missing_ok=True)
        rust_benchmark.unlink(missing_ok=True)

    assert report["sota_claim_ready"] is False
    assert "openpyxl benchmark JSON is in volatile temporary storage" in report["blockers"]
    assert "Rust competitor benchmark JSON is in volatile temporary storage" in report["blockers"]


def test_sota_audit_uses_separate_rust_speed_threshold(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark, speedup=1.1)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is True
    assert report["rust_competitors"]["min_speedup_required"] == 1.0
    assert report["rust_competitors"]["weak_case_count"] == 0


def test_sota_audit_allows_stricter_rust_speed_threshold(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark, speedup=1.1)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
        rust_min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["rust_competitors"]["min_speedup_required"] == 2.0
    assert report["rust_competitors"]["weak_case_count"] == _default_rust_case_count()


def test_sota_audit_blocks_claim_when_rust_versions_are_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "read_values_plain",
                        "competitor": competitor,
                        "speedup_vs_competitor": 2.5,
                    }
                    for competitor in sota.DEFAULT_RUST_COMPETITORS
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["rust_competitors"]["missing_competitors"] == []
    assert report["rust_competitors"]["missing_version_competitors"] == list(
        sota.DEFAULT_RUST_COMPETITORS
    )
    assert "Rust competitor benchmark is missing resolved versions for:" in report["blockers"][0]


def test_sota_audit_uses_operation_phase_for_modify_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    _write_rust_competitor_benchmark(rust_benchmark)
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "modify_two_cells_plain",
                        "engine": "wolfxl_modify",
                        "speedup_vs_openpyxl": 1.2,
                    }
                ],
                "operation_comparisons": [
                    {
                        "case": "modify_two_cells_plain",
                        "engine": "wolfxl_modify",
                        "phase": "modify_save",
                        "speedup_vs_openpyxl": 8.0,
                        "speedup_basis": "operation_phase",
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is True
    assert report["performance"]["weak_case_count"] == 0
    assert report["performance"]["min_observed_speedup"] == 8.0


def test_sota_audit_blocks_claim_without_rust_competitor_benchmark(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert "no Rust competitor benchmark JSON supplied" in report["blockers"]
    assert report["rust_competitors"]["missing_competitors"] == list(sota.DEFAULT_RUST_COMPETITORS)


def test_sota_audit_blocks_claim_when_rust_competitor_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "write_plain",
                        "competitor": "rust_xlsxwriter",
                        "speedup_vs_competitor": 2.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert "Rust competitor benchmark is missing:" in report["blockers"][0]
    assert report["rust_competitors"]["covered_competitors"] == ["rust_xlsxwriter"]


def test_sota_audit_reports_rust_api_surface_pairs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    _write_rust_competitor_benchmark(rust_benchmark)
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["rust_competitors"]["api_surface_pairs"] == {
        "python_public_api -> python_binding_api": _default_rust_case_count()
    }
    assert report["rust_competitors"]["claim_basis_counts"] == {
        "public_api": _default_rust_case_count()
    }
    assert len(report["rust_competitors"]["claim_comparison_rows"]) == _default_rust_case_count()
    assert report["rust_competitors"]["public_rows_replaced_by_same_surface_count"] == 0
    assert (
        report["rust_competitors"]["cross_surface_comparison_count"] == _default_rust_case_count()
    )
    assert report["rust_competitors"]["missing_api_surface_count"] == 0


def test_sota_audit_summarizes_rust_memory_comparison_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    _write_rust_competitor_benchmark(
        rust_benchmark,
        memory_ratio=0.75,
        memory_excess_bytes=-25_000_000,
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    rust = report["rust_competitors"]
    assert rust["memory_comparison_count"] == _default_rust_case_count()
    assert rust["max_observed_memory_ratio"] == 0.75
    assert rust["weak_memory_case_count"] == 0
    assert rust["near_parity_memory_case_count"] == 0


def test_sota_audit_blocks_material_rust_memory_excess(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    _write_rust_competitor_benchmark(
        rust_benchmark,
        memory_ratio=1.25,
        memory_excess_bytes=20_000_000,
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    rust = report["rust_competitors"]
    assert rust["memory_comparison_count"] == _default_rust_case_count()
    assert rust["weak_memory_case_count"] == _default_rust_case_count()
    assert rust["weak_memory_cases"][0]["peak_rss_ratio_vs_competitor"] == 1.25
    assert report["claim_gates"]["rust_competitor_benchmark_gate_ready"] is False
    assert report["claim_gates"]["rust_competitor_gate_ready"] is False
    assert report["supported_scope_sota_gate_ready"] is False
    assert "17 Rust competitor memory lanes peak above 1.00x" in report["blockers"]


def test_rust_summary_prefers_streaming_direct_writer_memory(
    tmp_path: Path,
) -> None:
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "results": [
                    {
                        "case": "write_cell_by_cell_plain",
                        "competitor": "rust_xlsxwriter",
                        "competitor_version": "0.95.0",
                    },
                ],
                "comparisons": [
                    {
                        "case": "write_cell_by_cell_plain",
                        "competitor": "rust_xlsxwriter",
                        "speedup_vs_competitor": 2.5,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": False,
                    },
                ],
                "memory_comparisons": [
                    {
                        "case": "write_cell_by_cell_plain",
                        "competitor": "rust_xlsxwriter",
                        "peak_rss_ratio_vs_competitor": 1.25,
                        "peak_rss_excess_bytes": 20_000_000,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": False,
                    },
                ],
                "wolfxl_streaming_direct_writer_memory_comparisons": [
                    {
                        "case": "write_cell_by_cell_plain",
                        "competitor": "rust_xlsxwriter",
                        "peak_rss_ratio_vs_competitor": 1.05,
                        "peak_rss_excess_bytes": 2_000_000,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    },
                ],
            }
        )
    )

    rust = sota._rust_competitor_summary(
        rust_benchmark,
        min_speedup=2.0,
        headroom_warning=1.25,
        required_competitors=("rust_xlsxwriter",),
        max_memory_ratio=1.0,
        memory_noise_tolerance_bytes=3 * 1024 * 1024,
        max_age_days=7,
        now_utc=FIXED_NOW_UTC,
    )

    assert rust["memory_comparison_count"] == 1
    assert rust["max_observed_memory_ratio"] == 1.05
    assert rust["weak_memory_case_count"] == 0
    assert rust["near_parity_memory_case_count"] == 1
    assert rust["near_parity_memory_cases"][0]["wolfxl_api_surface"] == "direct_rust_api"


def test_rust_summary_prefers_direct_modify_memory(
    tmp_path: Path,
) -> None:
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "results": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "umya-spreadsheet",
                        "competitor_version": "2.3.3",
                    },
                ],
                "comparisons": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "umya-spreadsheet",
                        "speedup_vs_competitor": 4.0,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": False,
                    },
                ],
                "wolfxl_direct_modify_comparisons": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "umya-spreadsheet",
                        "speedup_vs_competitor": 3.0,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    },
                ],
                "memory_comparisons": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "umya-spreadsheet",
                        "peak_rss_ratio_vs_competitor": 3.2,
                        "peak_rss_excess_bytes": 36_000_000,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": False,
                    },
                ],
                "wolfxl_direct_modify_memory_comparisons": [
                    {
                        "case": "modify_existing_workbook_plain",
                        "competitor": "umya-spreadsheet",
                        "peak_rss_ratio_vs_competitor": 0.8,
                        "peak_rss_excess_bytes": -3_000_000,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    },
                ],
            }
        )
    )

    rust = sota._rust_competitor_summary(
        rust_benchmark,
        min_speedup=1.0,
        headroom_warning=1.25,
        required_competitors=("umya-spreadsheet",),
        max_memory_ratio=1.0,
        memory_noise_tolerance_bytes=3 * 1024 * 1024,
        max_age_days=7,
        now_utc=FIXED_NOW_UTC,
    )

    assert rust["memory_comparison_count"] == 1
    assert rust["max_observed_memory_ratio"] == 0.8
    assert rust["weak_memory_case_count"] == 0
    assert rust["api_surface_pairs"] == {"direct_rust_api -> direct_rust_api": 1}
    assert rust["claim_basis_counts"] == {"direct_rust_same_surface": 1}


def test_sota_audit_uses_same_surface_direct_rust_diagnostic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "results": [
                    {
                        "case": "read_values_plain",
                        "competitor": "calamine",
                        "competitor_version": "0.35.0",
                    },
                    {
                        "case": "read_formula_text",
                        "competitor": "calamine",
                        "competitor_version": "0.35.0",
                    },
                ],
                "comparisons": [
                    {
                        "case": "read_values_plain",
                        "competitor": "calamine",
                        "speedup_vs_competitor": 0.75,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": False,
                    },
                    {
                        "case": "read_formula_text",
                        "competitor": "calamine",
                        "speedup_vs_competitor": 0.8,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": False,
                    },
                ],
                "wolfxl_direct_core_comparisons": [
                    {
                        "case": "read_values_plain",
                        "competitor": "calamine",
                        "speedup_vs_competitor": 1.25,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    },
                    {
                        "case": "read_formula_text",
                        "competitor": "calamine",
                        "speedup_vs_competitor": 1.3,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    },
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        required_rust_competitors=("calamine",),
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is True
    assert report["rust_competitors"]["weak_case_count"] == 0
    assert report["rust_competitors"]["comparison_count"] == 2
    assert report["rust_competitors"]["raw_public_comparison_count"] == 2
    assert report["rust_competitors"]["same_surface_direct_comparison_count"] == 2
    assert report["rust_competitors"]["api_surface_pairs"] == {
        "direct_rust_api -> direct_rust_api": 2
    }
    assert report["rust_competitors"]["claim_basis_counts"] == {"direct_rust_same_surface": 2}
    assert report["rust_competitors"]["claim_comparison_rows"] == [
        {
            "case": "read_formula_text",
            "claim_basis": "direct_rust_same_surface",
            "competitor": "calamine",
            "competitor_version": "0.35.0",
            "competitor_api_surface": "direct_rust_api",
            "same_api_surface": True,
            "speedup_vs_competitor": 1.3,
            "wolfxl_api_surface": "direct_rust_api",
        },
        {
            "case": "read_values_plain",
            "claim_basis": "direct_rust_same_surface",
            "competitor": "calamine",
            "competitor_version": "0.35.0",
            "competitor_api_surface": "direct_rust_api",
            "same_api_surface": True,
            "speedup_vs_competitor": 1.25,
            "wolfxl_api_surface": "direct_rust_api",
        },
    ]
    assert report["rust_competitors"]["public_rows_replaced_by_same_surface_count"] == 2
    assert report["rust_competitors"]["public_rows_replaced_by_same_surface"] == [
        {
            "case": "read_formula_text",
            "competitor": "calamine",
            "competitor_version": "0.35.0",
            "competitor_api_surface": "direct_rust_api",
            "same_api_surface": False,
            "speedup_vs_competitor": 0.8,
            "wolfxl_api_surface": "python_public_api",
        },
        {
            "case": "read_values_plain",
            "competitor": "calamine",
            "competitor_version": "0.35.0",
            "competitor_api_surface": "direct_rust_api",
            "same_api_surface": False,
            "speedup_vs_competitor": 0.75,
            "wolfxl_api_surface": "python_public_api",
        },
    ]


def test_sota_audit_blocks_rust_competitor_in_wrong_lane(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    _write_rust_competitor_benchmark(rust_benchmark)
    payload = json.loads(rust_benchmark.read_text())
    for comparison in payload["comparisons"]:
        if comparison["competitor"] == "calamine":
            comparison["case"] = "write_cell_by_cell_plain"
    rust_benchmark.write_text(json.dumps(payload))
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["rust_competitors"]["missing_required_lanes"] == [
        {
            "competitor": "calamine",
            "required_case_prefixes": ["read_"],
            "observed_cases": ["write_cell_by_cell_plain"],
        }
    ]
    assert any(
        blocker.startswith("Rust competitor benchmark has competitors in the wrong benchmark lane:")
        for blocker in report["blockers"]
    )


def test_sota_audit_blocks_missing_rust_case_families(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "results": [
                    {
                        "case": "write_cell_by_cell_plain",
                        "competitor": "rust_xlsxwriter",
                        "competitor_version": "0.95.0",
                    }
                ],
                "comparisons": [
                    {
                        "case": "write_cell_by_cell_plain",
                        "competitor": "rust_xlsxwriter",
                        "speedup_vs_competitor": 2.5,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        required_rust_competitors=("rust_xlsxwriter",),
        min_speedup=2.0,
    )

    assert report["sota_claim_ready"] is False
    assert report["rust_competitors"]["missing_required_case_families"] == [
        {
            "competitor": "rust_xlsxwriter",
            "missing_case_families": [
                "high_cardinality_string_write",
                "formula_write",
                "styled_value_write",
                "multi_sheet_write",
            ],
            "observed_cases": ["write_cell_by_cell_plain"],
        }
    ]
    assert report["rust_competitors"]["required_case_family_count"] == 5
    assert report["rust_competitors"]["covered_required_case_family_count"] == 1
    assert report["rust_competitors"]["required_case_family_coverage"] == [
        {
            "competitor": "rust_xlsxwriter",
            "observed_cases": ["write_cell_by_cell_plain"],
            "families": [
                {
                    "family": "plain_value_write",
                    "required_terms": ["write", "plain"],
                    "covered": True,
                    "matched_cases": ["write_cell_by_cell_plain"],
                },
                {
                    "family": "high_cardinality_string_write",
                    "required_terms": ["write", "unique", "string"],
                    "covered": False,
                    "matched_cases": [],
                },
                {
                    "family": "formula_write",
                    "required_terms": ["write", "formula"],
                    "covered": False,
                    "matched_cases": [],
                },
                {
                    "family": "styled_value_write",
                    "required_terms": ["write", "style"],
                    "covered": False,
                    "matched_cases": [],
                },
                {
                    "family": "multi_sheet_write",
                    "required_terms": ["write", "multi"],
                    "covered": False,
                    "matched_cases": [],
                },
            ],
        }
    ]
    assert any(
        blocker.startswith("Rust competitor benchmark is missing required case families:")
        for blocker in report["blockers"]
    )


def test_sota_case_family_coverage_does_not_cross_count_plain_terms(
    tmp_path: Path,
) -> None:
    rust_benchmark = tmp_path / "rust-benchmark.json"
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "results": [
                    {
                        "case": "write_multi_sheet_plain",
                        "competitor": "rust_xlsxwriter",
                        "competitor_version": "0.95.0",
                    }
                ],
                "comparisons": [
                    {
                        "case": "write_multi_sheet_plain",
                        "competitor": "rust_xlsxwriter",
                        "speedup_vs_competitor": 2.5,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    }
                ],
            }
        )
    )

    rust = sota._rust_competitor_summary(
        rust_benchmark,
        min_speedup=2.0,
        headroom_warning=1.25,
        required_competitors=("rust_xlsxwriter",),
        max_memory_ratio=1.0,
        memory_noise_tolerance_bytes=3 * 1024 * 1024,
        max_age_days=7,
        now_utc=FIXED_NOW_UTC,
    )

    assert rust["missing_required_case_families"] == [
        {
            "competitor": "rust_xlsxwriter",
            "missing_case_families": [
                "plain_value_write",
                "high_cardinality_string_write",
                "formula_write",
                "styled_value_write",
            ],
            "observed_cases": ["write_multi_sheet_plain"],
        }
    ]
    coverage = rust["required_case_family_coverage"][0]["families"]
    assert [family["covered"] for family in coverage] == [False, False, False, False, True]


def test_sota_audit_blocks_missing_and_weak_rust_competitors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "write_plain",
                        "competitor": "rust_xlsxwriter",
                        "speedup_vs_competitor": 0.5,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
        },
    )

    report = sota.audit_sota_claim(
        evidence_manifest=tmp_path / "bundle.json",
        benchmark=benchmark,
        rust_competitor_benchmark=rust_benchmark,
        min_speedup=2.0,
    )

    assert "Rust competitor benchmark is missing:" in report["blockers"][0]
    assert "1 Rust competitor benchmark lanes are below 1.00x" in report["blockers"]


def test_sota_audit_strict_cli_returns_nonzero_when_not_ready(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text(json.dumps({"comparisons": []}))
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": False,
            "exhaustive_claim_ready": False,
            "missing_requirement_ids": ["current_evidence_bundle_ready"],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": False,
            "bundle_issue_count": 1,
            "overall_missing_action_counts": {"defer_excel_batch": 1},
            "overall_missing_lane_counts": {"render": 1},
        },
    )

    code = sota.main(
        [
            "--evidence-manifest",
            str(tmp_path / "bundle.json"),
            "--benchmark",
            str(benchmark),
            "--strict",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["sota_claim_ready"] is False
    assert "benchmark JSON has no openpyxl comparison rows" in payload["blockers"]


def test_sota_audit_cli_writes_json_and_markdown_outputs(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    benchmark = tmp_path / "benchmark.json"
    rust_benchmark = tmp_path / "rust-benchmark.json"
    output = tmp_path / "sota.json"
    markdown_output = tmp_path / "sota.md"
    benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "comparisons": [
                    {
                        "case": "strong",
                        "engine": "wolfxl",
                        "speedup_vs_openpyxl": 2.5,
                    }
                ],
            }
        )
    )
    rust_benchmark.write_text(
        json.dumps(
            {
                "metadata": _benchmark_metadata(),
                "results": [
                    {
                        "case": "read_values_plain",
                        "competitor": "calamine",
                        "competitor_version": "0.35.0",
                    }
                ],
                "comparisons": [
                    {
                        "case": "read_values_plain",
                        "competitor": "calamine",
                        "speedup_vs_competitor": 0.75,
                        "wolfxl_api_surface": "python_public_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": False,
                    }
                ],
                "wolfxl_direct_core_comparisons": [
                    {
                        "case": "read_values_plain",
                        "competitor": "calamine",
                        "speedup_vs_competitor": 1.25,
                        "wolfxl_api_surface": "direct_rust_api",
                        "competitor_api_surface": "direct_rust_api",
                        "same_api_surface": True,
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        sota.audit_ooxml_completion_claim,
        "audit_completion_claim",
        lambda _manifest: {
            "current_supported_claim_ready": True,
            "exhaustive_claim_ready": True,
            "missing_requirement_ids": [],
        },
    )
    monkeypatch.setattr(
        sota.plan_ooxml_evidence_batch,
        "plan_batch",
        lambda _manifest: {
            "bundle_ready": True,
            "bundle_issue_count": 0,
            "overall_missing_action_counts": {},
            "overall_missing_lane_counts": {},
            "selected_dependency_round_counts": {},
            "selected_unresolved_dependency_step_count": 0,
            "selected_steps": [],
        },
    )

    code = sota.main(
        [
            "--evidence-manifest",
            str(tmp_path / "bundle.json"),
            "--benchmark",
            str(benchmark),
            "--rust-competitor-benchmark",
            str(rust_benchmark),
            "--allow-missing-rust-competitor-set-report",
            "--output",
            str(output),
            "--markdown-output",
            str(markdown_output),
            "--rust-min-speedup",
            "1.0",
        ]
    )
    printed = json.loads(capsys.readouterr().out)
    payload = json.loads(output.read_text())
    markdown = markdown_output.read_text()

    assert code == 0
    assert printed["sota_claim_ready"] is False
    assert "Rust competitor benchmark is missing:" in printed["blockers"][0]
    assert payload["rust_competitors"]["claim_basis_counts"] == {"direct_rust_same_surface": 1}
    assert payload["inputs"]["evidence_manifest"] == str(tmp_path / "bundle.json")
    assert payload["inputs"]["rust_competitor_benchmark"] == str(rust_benchmark)
    assert payload["inputs"]["output"] == str(output)
    assert payload["inputs"]["markdown_output"] == str(markdown_output)
    assert "# Current SOTA Claim Audit" in markdown
    assert "## Rust Fair-Comparison Basis" in markdown
    assert "raw Python-wrapper row against `calamine` is `0.750x`" in markdown
    assert "| calamine | 0.35.0 | direct_rust_same_surface | 1.250x |" in markdown
    assert "## Reproduce" in markdown
    assert f"--output {output}" in markdown
    assert f"--markdown-output {markdown_output}" in markdown
    assert "--strict-confidence" in markdown


def test_sota_audit_cli_defaults_point_at_current_claim_proof(
    monkeypatch,
    capsys,
) -> None:
    captured: dict[str, object] = {}

    def fake_audit_sota_claim(**kwargs):
        captured.update(kwargs)
        return {
            "inputs": {},
            "sota_claim_ready": False,
            "sota_confidence_ready": False,
        }

    monkeypatch.setattr(sota, "audit_sota_claim", fake_audit_sota_claim)

    code = sota.main([])
    printed = json.loads(capsys.readouterr().out)

    assert code == 0
    assert printed["sota_claim_ready"] is False
    assert (
        Path(captured["benchmark"]).name
        == "2026-06-10-current-openpyxl-full-clean.json"
    )
    assert (
        Path(captured["rust_competitor_benchmark"]).name
        == "2026-06-10-required-rust-10k-with-memory-clean.json"
    )
    assert (
        Path(captured["rust_watchlist_benchmark"]).name
        == "2026-06-10-current-office-oxide-watchlist-10k-clean.json"
    )
    assert (
        Path(captured["rust_competitor_set_report"]).name
        == "2026-06-05-rust-competitor-set-live-recheck.json"
    )
    assert captured["require_rust_competitor_set_report"] is True
