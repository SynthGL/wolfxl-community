from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_trust_report_freshness.py"
    spec = importlib.util.spec_from_file_location("audit_trust_report_freshness", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_trust_report_freshness_current_repo_is_fresh(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_trust_report_freshness.py"
    output = tmp_path / "trust-report-freshness-audit.json"
    markdown_output = tmp_path / "trust-report-freshness-audit.md"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--output",
            str(output),
            "--markdown-output",
            str(markdown_output),
        ],
        check=True,
        cwd=script.parents[1],
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["ready"] is True, report["issues"]
    assert report["issue_count"] == 0, report["issues"]
    assert report["upstream_check_count"] == 7
    assert {row["name"] for row in report["checks"]} == {
        "public_claim_wording",
        "current_sota_claim_audit",
        "public_claim_dimensions",
        "release_artifact_coverage",
        "release_artifact_proof_workflow",
        "release_artifact_trigger_readiness",
        "final_sota_blockers",
        "fidelity_proof_flow_status",
        "performance_proof_flow_status",
        "sota_snapshot_wording",
        "followup_claim_blockers",
        "historical_claim_wording",
        "real_world_fidelity_plan_state",
    }
    assert {row["name"] for row in report["upstream_checks"]} == {
        "openpyxl_benchmark_source",
        "rust_competitor_benchmark_source",
        "rust_watchlist_benchmark_source",
        "rust_competitor_set_report",
        "release_artifact_benchmark_rerun_source",
        "fidelity_proof_flow",
        "final_sota_boundary_chain",
    }
    assert all(row["fresh"] is True for row in report["checks"])
    upstream_by_name = {row["name"]: row for row in report["upstream_checks"]}
    assert upstream_by_name["rust_competitor_set_report"]["fresh"] is True
    assert upstream_by_name["release_artifact_benchmark_rerun_source"]["fresh"] is True
    assert upstream_by_name["openpyxl_benchmark_source"]["fresh"] is True
    assert upstream_by_name["rust_competitor_benchmark_source"]["fresh"] is True
    assert upstream_by_name["rust_watchlist_benchmark_source"]["fresh"] is True
    assert upstream_by_name["fidelity_proof_flow"]["fresh"] is True
    assert upstream_by_name["final_sota_boundary_chain"]["fresh"] is True
    assert upstream_by_name["openpyxl_benchmark_source"]["issues"] == []
    assert upstream_by_name["rust_competitor_benchmark_source"]["issues"] == []
    assert upstream_by_name["rust_watchlist_benchmark_source"]["issues"] == []
    assert upstream_by_name["fidelity_proof_flow"]["issues"] == []
    assert upstream_by_name["final_sota_boundary_chain"]["issues"] == []
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "worker_status_audit_ready"
    ] is True
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "worker_no_rejected_or_mismatched_handoffs"
    ] is True
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "worker_handoff_mismatch_count"
    ] == 0
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "worker_rejected_handoff_shard_count"
    ] == 0
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "worker_execute_reports_needed_for_current_evidence"
    ] is False
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "worker_durable_reports_missing_for_execute_count"
    ] == 0
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "subagent_handoffs_ready"
    ] is True
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "subagent_unexpected_acceptance_count"
    ] == 0
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "subagent_unexpected_rejection_count"
    ] == 0
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "current_worker_handoffs_ready"
    ] is True
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "current_worker_unexpected_acceptance_count"
    ] == 0
    assert upstream_by_name["fidelity_proof_flow"]["evidence"][
        "current_worker_unexpected_rejection_count"
    ] == 0
    assert upstream_by_name["rust_competitor_set_report"]["evidence"][
        "required_competitors"
    ] == [
        "rust_xlsxwriter",
        "xlsxwriter",
        "calamine",
        "umya-spreadsheet",
        "fastexcel",
        "python-calamine",
    ]
    assert upstream_by_name["rust_competitor_set_report"]["evidence"][
        "benchmark_competitors"
    ] == [
        "calamine",
        "fastexcel",
        "python-calamine",
        "rust_xlsxwriter",
        "umya-spreadsheet",
        "xlsxwriter",
    ]
    assert upstream_by_name["rust_competitor_set_report"]["evidence"][
        "required_version_evidence_competitors"
    ] == [
        "rust_xlsxwriter",
        "xlsxwriter",
        "calamine",
        "umya-spreadsheet",
        "fastexcel",
        "python-calamine",
    ]
    xlsxwriter_rs_resolution = upstream_by_name["rust_competitor_set_report"][
        "evidence"
    ]["xlsxwriter_rs_resolution"]
    assert xlsxwriter_rs_resolution["requested_name"] == "xlsxwriter-rs"
    assert xlsxwriter_rs_resolution["resolves_to_competitor"] == "xlsxwriter"
    assert xlsxwriter_rs_resolution["requirement_satisfied"] is True
    assert upstream_by_name["rust_competitor_set_report"]["evidence"][
        "user_requested_rust_competitor_names"
    ] == [
        "rust_xlsxwriter",
        "xlsxwriter-rs",
        "calamine",
        "umya-spreadsheet",
        "fastexcel",
        "python-calamine",
    ]
    assert upstream_by_name["rust_competitor_set_report"]["evidence"][
        "user_requested_rust_competitor_names_satisfied"
    ] is True
    assert upstream_by_name["rust_competitor_set_report"]["evidence"][
        "user_requested_rust_competitor_name_blockers"
    ] == []
    assert upstream_by_name["rust_competitor_set_report"]["evidence"][
        "user_requested_rust_competitor_name_resolution_count"
    ] == 6
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "final_audit_ready"
    ] is True
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "audit_failed_checks"
    ] == []
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "failed_checks"
    ] == ["broad_no_reason_claim_ready"]
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "dimensions_expected_broad_boundaries_ready"
    ] is True
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "remaining_actionable_evidence_step_count"
    ] == 0
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "remaining_claim_wording_boundary_count"
    ] == 5
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "remaining_blocker_ids"
    ] == [
        "cross_platform_release_artifact_coverage",
        "ecosystem_maturity_and_long_tail_workflows",
        "all_high_risk_render_variants",
        "all_click_level_interaction_variants",
        "future_real_world_excel_surfaces",
    ]
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "remaining_actionable_headless_blocker_ids"
    ] == []
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "remaining_actionable_excel_blocker_ids"
    ] == []
    assert upstream_by_name["final_sota_boundary_chain"]["evidence"][
        "remaining_next_required_proof_mode"
    ] == "none"


def test_upstream_row_flags_failed_source_relevance(tmp_path: Path) -> None:
    path = tmp_path / "sota.json"
    row = audit._upstream_row(
        "openpyxl_benchmark_source",
        path,
        {
            "source_relevance_ready": False,
            "source_relevance_blockers": ["benchmark source changed"],
        },
        [
            audit._expect_source_relevance(
                {
                    "source_relevance_ready": False,
                    "source_relevance_blockers": ["benchmark source changed"],
                    "source_relevance_dirty_relevant_paths": [],
                },
                "openpyxl benchmark",
            )
        ],
    )

    assert row["fresh"] is False
    assert row["issues"] == [
        {
            "check": "openpyxl_benchmark_source",
            "kind": "upstream",
            "path": str(path),
            "reason": (
                "openpyxl benchmark source relevance is blocked: "
                "benchmark source changed"
            ),
        }
    ]


def test_final_sota_boundary_chain_upstream_row_flags_regression(
    tmp_path: Path,
) -> None:
    path = tmp_path / "final-sota-blockers.json"
    row = audit._upstream_row(
        "final_sota_boundary_chain",
        path,
        {
            "final_audit_ready": False,
            "audit_failed_checks": ["supported_scope_ready"],
            "failed_checks": ["broad_no_reason_claim_ready", "supported_scope_ready"],
            "dimensions_expected_broad_boundaries_ready": False,
            "dimensions_expected_broad_boundary_gap_count": 1,
            "remaining_actionable_headless_step_count": 1,
            "remaining_actionable_excel_step_count": 1,
            "remaining_actionable_evidence_step_count": 2,
            "remaining_claim_wording_boundary_count": 4,
            "remaining_blocker_count": 4,
            "remaining_blocker_ids": ["cross_platform_release_artifact_coverage"],
            "remaining_actionable_headless_blocker_ids": ["openpyxl_speed"],
            "remaining_actionable_excel_blocker_ids": ["all_high_risk_render_variants"],
            "remaining_next_required_proof_mode": "excel",
        },
        [
            audit._expect_true(
                False,
                "final SOTA blocker audit is not healthy",
            ),
            audit._expect_equal(
                ["supported_scope_ready"],
                [],
                "final SOTA blocker audit has unexpected audit failed checks",
            ),
            audit._expect_equal(
                ["broad_no_reason_claim_ready", "supported_scope_ready"],
                ["broad_no_reason_claim_ready"],
                "final SOTA blocker audit has unexpected failed checks",
            ),
            audit._expect_true(
                False,
                "final SOTA broad-boundary chain is not ready",
            ),
            audit._expect_zero(
                1,
                "final SOTA broad-boundary chain has gaps",
            ),
            audit._expect_zero(
                1,
                "final SOTA actionability has remaining headless work",
            ),
            audit._expect_zero(
                1,
                "final SOTA actionability has remaining Excel work",
            ),
            audit._expect_zero(
                2,
                "final SOTA actionability has remaining evidence work",
            ),
            audit._expect_equal(
                4,
                5,
                "final SOTA actionability has unexpected claim wording boundary count",
            ),
            audit._expect_equal(
                4,
                5,
                "final SOTA actionability has unexpected remaining blocker count",
            ),
            audit._expect_equal(
                ["cross_platform_release_artifact_coverage"],
                [
                    "cross_platform_release_artifact_coverage",
                    "ecosystem_maturity_and_long_tail_workflows",
                    "all_high_risk_render_variants",
                    "all_click_level_interaction_variants",
                    "future_real_world_excel_surfaces",
                ],
                "final SOTA actionability has unexpected remaining blocker ids",
            ),
            audit._expect_equal(
                ["openpyxl_speed"],
                [],
                "final SOTA actionability has actionable headless blocker ids",
            ),
            audit._expect_equal(
                ["all_high_risk_render_variants"],
                [],
                "final SOTA actionability has actionable Excel blocker ids",
            ),
            audit._expect_equal(
                "excel",
                "none",
                "final SOTA actionability has unexpected next proof mode",
            ),
        ],
    )

    assert row["fresh"] is False
    assert [issue["reason"] for issue in row["issues"]] == [
        "final SOTA blocker audit is not healthy",
        "final SOTA blocker audit has unexpected audit failed checks",
        "final SOTA blocker audit has unexpected failed checks",
        "final SOTA broad-boundary chain is not ready",
        "final SOTA broad-boundary chain has gaps",
        "final SOTA actionability has remaining headless work",
        "final SOTA actionability has remaining Excel work",
        "final SOTA actionability has remaining evidence work",
        "final SOTA actionability has unexpected claim wording boundary count",
        "final SOTA actionability has unexpected remaining blocker count",
        "final SOTA actionability has unexpected remaining blocker ids",
        "final SOTA actionability has actionable headless blocker ids",
        "final SOTA actionability has actionable Excel blocker ids",
        "final SOTA actionability has unexpected next proof mode",
    ]


def test_fidelity_proof_flow_upstream_row_flags_worker_handoff_regression(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sota-proof-flow-status.json"
    row = audit._upstream_row(
        "fidelity_proof_flow",
        path,
        {
            "worker_status_audit_ready": False,
            "worker_no_rejected_or_mismatched_handoffs": False,
            "worker_handoff_mismatch_count": 1,
            "worker_rejected_handoff_shard_count": 1,
            "worker_execute_reports_needed_for_current_evidence": True,
            "worker_durable_reports_missing_for_execute_count": 2,
            "subagent_handoffs_ready": False,
            "subagent_unexpected_acceptance_count": 1,
            "subagent_unexpected_rejection_count": 1,
            "current_worker_handoffs_ready": False,
            "current_worker_unexpected_acceptance_count": 1,
            "current_worker_unexpected_rejection_count": 1,
        },
        [
            audit._expect_true(
                False,
                "worker handoff status audit is not ready",
            ),
            audit._expect_true(
                False,
                "worker handoff status has rejected or mismatched handoffs",
            ),
            audit._expect_zero(
                1,
                "worker handoff status has mismatched handoffs",
            ),
            audit._expect_zero(
                1,
                "worker handoff status has rejected handoffs",
            ),
            audit._expect_false(
                True,
                "worker execute reports are still needed for current evidence",
            ),
            audit._expect_zero(
                2,
                "worker execute handoff has missing durable reports",
            ),
            audit._expect_true(
                False,
                "subagent handoff audit is not ready",
            ),
            audit._expect_zero(
                1,
                "subagent handoff audit has unexpected acceptances",
            ),
            audit._expect_zero(
                1,
                "subagent handoff audit has unexpected rejections",
            ),
            audit._expect_true(
                False,
                "current worker handoff audit is not ready",
            ),
            audit._expect_zero(
                1,
                "current worker handoff audit has unexpected acceptances",
            ),
            audit._expect_zero(
                1,
                "current worker handoff audit has unexpected rejections",
            ),
        ],
    )

    assert row["fresh"] is False
    assert [issue["reason"] for issue in row["issues"]] == [
        "worker handoff status audit is not ready",
        "worker handoff status has rejected or mismatched handoffs",
        "worker handoff status has mismatched handoffs",
        "worker handoff status has rejected handoffs",
        "worker execute reports are still needed for current evidence",
        "worker execute handoff has missing durable reports",
        "subagent handoff audit is not ready",
        "subagent handoff audit has unexpected acceptances",
        "subagent handoff audit has unexpected rejections",
        "current worker handoff audit is not ready",
        "current worker handoff audit has unexpected acceptances",
        "current worker handoff audit has unexpected rejections",
    ]


def test_compare_report_flags_stale_content(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text('{"ready": false}\n', encoding="utf-8")
    issues: list[dict[str, object]] = []

    status = audit._compare_report(
        "example",
        "json",
        path,
        '{"ready": true}\n',
        issues,
    )

    assert status["matches_generated"] is False
    assert issues == [
        {
            "check": "example",
            "kind": "json",
            "path": str(path),
            "reason": "checked-in report differs from freshly generated report",
            "first_difference": "line 1: actual='{\"ready\": false}'; generated='{\"ready\": true}'",
            "actual_sha256": status["actual_sha256"],
            "generated_sha256": status["generated_sha256"],
        }
    ]


def test_current_sota_claim_freshness_ignores_only_volatile_fields() -> None:
    actual = {
        "sota_claim_ready": False,
        "supported_scope_sota_gate_ready": True,
        "rust_competitor_set": {
            "main_rust_competitor_set_ready": True,
            "missing_from_benchmark": [],
            "missing_benchmark_versions": [],
            "report_age_days": 0.1,
        },
        "rust_competitors": {
            "source_relevance_ready": True,
            "source_relevance_status": "checked_since_benchmark_sha",
            "source_relevance_current_git_commit": "new",
            "source_relevance_changed_path_count": 10,
            "source_relevance_relevant_changed_path_count": 0,
            "source_relevance_relevant_changed_paths": [],
            "source_relevance_dirty_relevant_paths": [],
            "source_relevance_blockers": [],
            "benchmark_age_days": 0.2,
        },
    }
    expected = {
        **actual,
        "rust_competitor_set": {
            **actual["rust_competitor_set"],
            "report_age_days": 0.5,
        },
        "rust_competitors": {
            **actual["rust_competitors"],
            "source_relevance_status": "current_head",
            "source_relevance_current_git_commit": "old",
            "source_relevance_changed_path_count": 1,
            "benchmark_age_days": 0.6,
        },
    }

    normalized_actual, normalized_expected = (
        audit._normalize_current_sota_claim_for_freshness(
            audit.json.dumps(actual),
            audit.json.dumps(expected),
        )
    )

    assert normalized_actual == normalized_expected


def test_current_sota_claim_freshness_catches_real_gate_regression() -> None:
    actual = {
        "sota_claim_ready": False,
        "supported_scope_sota_gate_ready": True,
        "rust_competitor_set": {
            "main_rust_competitor_set_ready": True,
            "missing_from_benchmark": [],
            "missing_benchmark_versions": [],
        },
    }
    expected = {
        **actual,
        "rust_competitor_set": {
            **actual["rust_competitor_set"],
            "missing_from_benchmark": ["calamine"],
        },
    }

    normalized_actual, normalized_expected = (
        audit._normalize_current_sota_claim_for_freshness(
            audit.json.dumps(actual),
            audit.json.dumps(expected),
        )
    )

    assert normalized_actual != normalized_expected


def test_current_sota_claim_freshness_catches_source_relevance_regression() -> None:
    actual = {
        "rust_competitors": {
            "source_relevance_ready": True,
            "source_relevance_status": "checked_since_benchmark_sha",
            "source_relevance_relevant_changed_path_count": 0,
            "source_relevance_relevant_changed_paths": [],
            "source_relevance_dirty_relevant_paths": [],
            "source_relevance_blockers": [],
        },
    }
    expected = {
        "rust_competitors": {
            **actual["rust_competitors"],
            "source_relevance_ready": False,
            "source_relevance_relevant_changed_path_count": 1,
            "source_relevance_relevant_changed_paths": ["crates/wolfxl/src/lib.rs"],
            "source_relevance_blockers": ["benchmark-relevant source changed"],
        },
    }

    normalized_actual, normalized_expected = (
        audit._normalize_current_sota_claim_for_freshness(
            audit.json.dumps(actual),
            audit.json.dumps(expected),
        )
    )

    assert normalized_actual != normalized_expected


def test_proof_flow_freshness_catches_missing_report_regression() -> None:
    actual = {
        "headless_work_available": False,
        "excel_approval_required": False,
        "sota": {
            "evidence": {
                "missing_report_count": 0,
                "remaining_direct_headless_step_count": 0,
                "remaining_deferred_excel_step_count": 0,
                "report_age_days": 0.1,
            }
        },
    }
    expected = {
        **actual,
        "sota": {
            "evidence": {
                **actual["sota"]["evidence"],
                "missing_report_count": 1,
            }
        },
    }

    normalized_actual, normalized_expected = (
        audit._normalize_fidelity_proof_flow_for_freshness(
            audit.json.dumps(actual),
            audit.json.dumps(expected),
        )
    )

    assert normalized_actual != normalized_expected


def test_proof_flow_freshness_ignores_release_report_head_position() -> None:
    actual = {
        "release_artifact_coverage": {
            "ready": True,
            "current_repo_head_sha": "branch-sha",
            "current_report_head_sha": "branch-sha",
            "current_release_relevant_source_sha": "source-sha",
        },
        "sota": {
            "evidence": {
                "release_artifact_current_repo_head_sha": "branch-sha",
                "release_artifact_current_report_head_sha": "branch-sha",
                "release_artifact_current_release_relevant_source_sha": "source-sha",
                "remaining_direct_headless_step_count": 0,
            }
        },
    }
    expected = {
        "release_artifact_coverage": {
            **actual["release_artifact_coverage"],
            "current_repo_head_sha": "ci-merge-sha",
            "current_report_head_sha": "ci-merge-sha",
        },
        "sota": {
            "evidence": {
                **actual["sota"]["evidence"],
                "release_artifact_current_repo_head_sha": "ci-merge-sha",
                "release_artifact_current_report_head_sha": "ci-merge-sha",
            }
        },
    }

    normalized_actual, normalized_expected = (
        audit._normalize_fidelity_proof_flow_for_freshness(
            audit.json.dumps(actual),
            audit.json.dumps(expected),
        )
    )

    assert normalized_actual == normalized_expected


def test_release_coverage_freshness_ignores_current_head_position() -> None:
    actual = _release_coverage_payload()
    expected = {
        **_release_coverage_payload(),
        "current_repo_head_sha": "ci-merge-sha",
        "current_head_sha": "old-sha",
        "current_report_head_sha": "ci-merge-sha",
        "current_worktree_release_relevant_dirty_path_count": 0,
        "current_worktree_release_relevant_dirty_paths": [],
        "currentness_ready": False,
        "current_head_proven_lane_count": 0,
        "stale_proven_lane_count": 26,
        "stale_proven_lanes": [
            {"id": "wheel:linux:x86_64:cp312", "git_sha": "old-sha"}
        ],
    }

    normalized_actual, normalized_expected = (
        audit._normalize_release_coverage_for_freshness(
            audit.json.dumps(actual),
            audit.json.dumps(expected),
        )
    )

    assert normalized_actual == normalized_expected


def test_release_coverage_freshness_catches_missing_lane_regression() -> None:
    actual = _release_coverage_payload()
    expected = {
        **_release_coverage_payload(),
        "ready": False,
        "coverage_ready": False,
        "proven_lane_count": 25,
        "missing_lane_count": 1,
        "missing_lanes": [{"id": "wheel:linux:x86_64:cp312"}],
    }

    normalized_actual, normalized_expected = (
        audit._normalize_release_coverage_for_freshness(
            audit.json.dumps(actual),
            audit.json.dumps(expected),
        )
    )

    assert normalized_actual != normalized_expected


def test_release_coverage_freshness_catches_content_dirty_regression() -> None:
    actual = _release_coverage_payload()
    expected = {
        **_release_coverage_payload(),
        "ready": False,
        "currentness_ready": False,
        "current_worktree_release_relevant_content_dirty_path_count": 1,
        "current_worktree_release_relevant_content_dirty_paths": [
            "crates/wolfxl-writer/src/model/worksheet.rs"
        ],
    }

    normalized_actual, normalized_expected = (
        audit._normalize_release_coverage_for_freshness(
            audit.json.dumps(actual),
            audit.json.dumps(expected),
        )
    )

    assert normalized_actual != normalized_expected


def test_trigger_readiness_freshness_ignores_checkout_position(
    tmp_path: Path,
) -> None:
    path = tmp_path / "trigger.json"
    actual = _trigger_readiness_payload()
    expected = {
        **actual,
        "ready": False,
        "current_branch": "",
        "upstream_branch": None,
        "current_branch_pushed": False,
        "current_branch_has_unpushed_commits": True,
        "branch_push_ready_now": False,
        "trigger_mode": "not_triggerable",
        "repository": None,
        "repository_url": None,
        "default_branch": None,
        "default_branch_workflow": {"exists": False, "error": "default branch is unknown"},
    }
    path.write_text(audit.json.dumps(actual, indent=2, sort_keys=True) + "\n")
    issues: list[dict[str, object]] = []

    status = audit._compare_report(
        "release_artifact_trigger_readiness",
        "json",
        path,
        audit.json.dumps(expected, indent=2, sort_keys=True) + "\n",
        issues,
        audit._normalize_trigger_readiness_for_freshness,
    )

    assert status["matches_generated"] is True
    assert issues == []


def test_trigger_readiness_freshness_catches_local_workflow_failure(
    tmp_path: Path,
) -> None:
    path = tmp_path / "trigger.json"
    actual = _trigger_readiness_payload()
    expected = {
        **_trigger_readiness_payload(),
        "ready": False,
        "current_branch_pushed": False,
        "branch_push_ready_now": False,
        "branch_push_requires_push": True,
        "trigger_mode": "push_required",
        "local_workflow_ready": False,
        "local_workflow_dispatch_ready": False,
    }
    path.write_text(audit.json.dumps(actual, indent=2, sort_keys=True) + "\n")
    issues: list[dict[str, object]] = []

    status = audit._compare_report(
        "release_artifact_trigger_readiness",
        "json",
        path,
        audit.json.dumps(expected, indent=2, sort_keys=True) + "\n",
        issues,
        audit._normalize_trigger_readiness_for_freshness,
    )

    assert status["matches_generated"] is False
    assert issues[0]["reason"] == "checked-in report differs from freshly generated report"


def test_trigger_readiness_freshness_catches_workflow_identity_regression(
    tmp_path: Path,
) -> None:
    path = tmp_path / "trigger.json"
    actual = _trigger_readiness_payload()
    expected = {
        **_trigger_readiness_payload(),
        "workflow_path": ".github/workflows/release.yml",
        "local_workflow_audit_source": "docs/trust/other-workflow-audit.json",
    }
    path.write_text(audit.json.dumps(actual, indent=2, sort_keys=True) + "\n")
    issues: list[dict[str, object]] = []

    status = audit._compare_report(
        "release_artifact_trigger_readiness",
        "json",
        path,
        audit.json.dumps(expected, indent=2, sort_keys=True) + "\n",
        issues,
        audit._normalize_trigger_readiness_for_freshness,
    )

    assert status["matches_generated"] is False
    assert issues[0]["reason"] == "checked-in report differs from freshly generated report"


def test_trigger_readiness_freshness_catches_audit_ready_regression(
    tmp_path: Path,
) -> None:
    path = tmp_path / "trigger.json"
    actual = _trigger_readiness_payload()
    expected = {
        **_trigger_readiness_payload(),
        "audit_ready": False,
    }
    path.write_text(audit.json.dumps(actual, indent=2, sort_keys=True) + "\n")
    issues: list[dict[str, object]] = []

    status = audit._compare_report(
        "release_artifact_trigger_readiness",
        "json",
        path,
        audit.json.dumps(expected, indent=2, sort_keys=True) + "\n",
        issues,
        audit._normalize_trigger_readiness_for_freshness,
    )

    assert status["matches_generated"] is False
    assert issues[0]["reason"] == "checked-in report differs from freshly generated report"


def _release_coverage_payload() -> dict[str, object]:
    return {
        "ready": True,
        "audit_ready": True,
        "coverage_ready": True,
        "currentness_ready": True,
        "current_repo_head_sha": "branch-sha",
        "current_head_sha": "new-sha",
        "current_report_head_sha": "branch-sha",
        "current_release_relevant_source_sha": "new-sha",
        "current_worktree_release_relevant_dirty_path_count": 1,
        "current_worktree_release_relevant_dirty_paths": [
            "crates/wolfxl-writer/src/model/worksheet.rs"
        ],
        "current_worktree_release_relevant_content_dirty_path_count": 0,
        "current_worktree_release_relevant_content_dirty_paths": [],
        "expected_lane_count": 26,
        "proven_lane_count": 26,
        "missing_lane_count": 0,
        "missing_lanes": [],
        "current_head_proven_lane_count": 26,
        "stale_proven_lane_count": 0,
        "stale_proven_lanes": [],
    }


def _trigger_readiness_payload() -> dict[str, object]:
    return {
        "audit_ready": True,
        "ready": True,
        "current_branch": "codex/example",
        "upstream_branch": "origin/codex/example",
        "current_branch_pushed": True,
        "current_branch_has_unpushed_commits": False,
        "branch_push_ready_now": True,
        "branch_push_requires_push": False,
        "trigger_mode": "branch_push",
        "repository": "SynthGL/wolfxl",
        "repository_url": "https://github.com/SynthGL/wolfxl",
        "default_branch": "main",
        "default_branch_workflow": {
            "exists": False,
            "error": "gh: Not Found (HTTP 404)",
            "ref": "main",
        },
        "workflow_on_default_branch": False,
        "manual_dispatch_ready_now": False,
        "workflow_path": ".github/workflows/release-artifact-proof.yml",
        "local_workflow_audit_source": (
            "docs/trust/release-artifact-proof-workflow-audit.json"
        ),
        "local_workflow_ready": True,
        "local_branch_push_ready": True,
        "local_workflow_dispatch_ready": True,
        "initial_proof_branch": "codex/example",
        "claim_boundary": "release lanes are only proven after GitHub artifacts import",
    }


def test_generator_script_identity_requires_hash() -> None:
    reason = audit._expect_generator_script_identity(
        {
            "generator_script_source": "current report repository",
            "generator_script_path": "scripts/run_release_artifact_benchmark_smoke.py",
            "generator_script_git_sha": "abc123",
        },
        "release-artifact benchmark rerun",
    )

    assert reason == "release-artifact benchmark rerun generator script SHA-256 is missing"


def test_generator_script_identity_checks_git_history() -> None:
    script_path = "scripts/run_release_artifact_benchmark_smoke.py"
    git_sha = "09301a72e7339d75a02e07ddcc2c1b87578d50dc"
    script_sha256 = (
        "54e1239468a3c905fb4805ade0a0386d2e70d36b9fddbb316d4c986396353122"
    )

    reason = audit._expect_generator_script_identity(
        {
            "generator_script_source": "current report repository",
            "generator_script_path": script_path,
            "generator_script_git_sha": git_sha,
            "generator_script_sha256": script_sha256,
        },
        "release-artifact benchmark rerun",
    )

    assert reason is None


def test_generator_script_identity_blocks_hash_mismatch() -> None:
    reason = audit._expect_generator_script_identity(
        {
            "generator_script_source": "current report repository",
            "generator_script_path": "scripts/run_release_artifact_benchmark_smoke.py",
            "generator_script_git_sha": "09301a72e7339d75a02e07ddcc2c1b87578d50dc",
            "generator_script_sha256": "0" * 64,
        },
        "release-artifact benchmark rerun",
    )

    assert (
        reason
        == "release-artifact benchmark rerun generator script SHA-256 does not match git history"
    )
