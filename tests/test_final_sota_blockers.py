from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_final_sota_blockers.py"
    spec = importlib.util.spec_from_file_location("audit_final_sota_blockers", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_final_sota_blocker_audit_current_repo_is_consistent() -> None:
    report = audit.audit_final_blockers()

    assert report["ready"] is False
    assert report["ready_meaning"].startswith("Broad no-reason claim readiness")
    assert report["audit_ready"] is True
    assert report["sota_claim_ready"] is False
    assert report["broad_no_reason_claim_ready"] is False
    assert report["supported_scope_ready"] is True
    assert report["competitor_gate_ready"] is True
    assert report["release_artifact_benchmark_rerun_ready"] is True
    assert report["proven_today"] == report["claim_boundary"]["proven_today"]
    assert report["promising_but_not_fully_proven"] == [
        "cross_platform_release_artifact_coverage"
    ]
    assert report["blocked_on_excel_evidence"] == []
    assert report["blocked_on_fresh_benchmark_source_evidence"] == []
    assert report["known_limitations"] == [
        "ecosystem_maturity_and_long_tail_workflows",
        "all_high_risk_render_variants",
        "all_click_level_interaction_variants",
        "future_real_world_excel_surfaces",
    ]
    assert report["supported_scope_caveats"] == report["claim_boundary"][
        "supported_scope_caveats"
    ]
    assert report["rust_competitor_scope_caveats"] == report["claim_boundary"][
        "rust_competitor_scope_caveats"
    ]
    assert report["excel_only_evidence_deferred"] is False
    assert report["failed_checks"] == [
        "broad_no_reason_claim_ready",
    ]
    assert report["audit_failed_checks"] == []
    assert report["checks"]["broad_no_reason_claim_ready"] is False
    assert report["checks"]["no_direct_headless_work_remains"] is True
    assert report["checks"]["remaining_blockers_have_no_actionable_evidence_steps"] is True
    assert report["checks"]["remaining_known_limitations_are_expected_claim_boundaries"] is True
    assert report["checks"]["dimensions_expected_broad_boundaries_gap_free"] is True
    assert report["checks"]["promising_items_are_explicitly_not_fully_proven"] is True
    assert report["checks"]["remaining_shortcomings_are_specific"] is True
    assert report["checks"]["broad_claim_still_not_ready"] is True
    assert report["finite_registered_evidence_complete"] is True
    assert report["remaining_direct_headless_step_count"] == 0
    assert report["remaining_deferred_excel_step_count"] == 0
    assert report["next_required_proof_mode"] == "none"
    assert report["proof_flow_ready"] is False
    assert report["current_phase"] == "final_sota_audit_blockers"
    assert report["headless_work_available"] is False
    assert report["excel_approval_required"] is False
    assert "Keep the broad all-future-surface SOTA claim gated" in report["proof_flow_next_action"]
    assert report["remaining_actionability"]["actionable_headless_step_count"] == 0
    assert report["remaining_actionability"]["actionable_excel_step_count"] == 0
    assert report["remaining_actionability"]["actionable_evidence_step_count"] == 0
    assert report["remaining_actionability"]["claim_wording_boundary_count"] == 5
    assert report["remaining_actionability"]["remaining_blocker_count"] == 5
    assert report["remaining_actionability"]["headless_work_available"] is False
    assert report["remaining_actionability"]["excel_approval_required"] is False
    assert report["remaining_actionability"]["next_required_proof_mode"] == "none"
    assert report["remaining_actionability"]["actionable_headless_blocker_ids"] == []
    assert report["remaining_actionability"]["actionable_excel_blocker_ids"] == []
    assert report["dimensions_expected_broad_boundaries"] == {
        "expected_ids": [
            "all_click_level_interaction_variants",
            "all_high_risk_render_variants",
            "cross_platform_release_artifact_coverage",
            "ecosystem_maturity_and_long_tail_workflows",
            "future_real_world_excel_surfaces",
        ],
        "gap_count": 0,
        "gaps": [],
        "observed_ids": [
            "all_click_level_interaction_variants",
            "all_high_risk_render_variants",
            "cross_platform_release_artifact_coverage",
            "ecosystem_maturity_and_long_tail_workflows",
            "future_real_world_excel_surfaces",
        ],
        "ready": True,
    }
    release_actionability = next(
        row
        for row in report["remaining_actionability"]["remaining_blockers"]
        if row["id"] == "cross_platform_release_artifact_coverage"
    )
    assert release_actionability["actionable_headless_task"] is False
    assert release_actionability["actionable_headless_step_count"] == 0
    assert release_actionability["not_proven_family_ids"] == [
        "unregistered_future_wheel_lanes",
        "installer_and_resolver_contexts",
        "alternate_distribution_channels",
        "workflow_topology_and_trigger_paths",
    ]
    assert "26 of 26 registered release-artifact lanes" in release_actionability["reason"]
    assert "0 missing and 0 stale lanes" in release_actionability["why_not_actionable_now"]
    assert "Register and prove any new release lane" in release_actionability[
        "what_would_make_actionable"
    ]
    actionability_by_id = {
        row["id"]: row for row in report["remaining_actionability"]["remaining_blockers"]
    }
    assert "unsupported APIs" in actionability_by_id[
        "ecosystem_maturity_and_long_tail_workflows"
    ]["why_not_actionable_now"]
    assert "74 ready reports" in actionability_by_id[
        "all_high_risk_render_variants"
    ]["why_not_actionable_now"]
    assert "0 unresolved non-boundary failures" in actionability_by_id[
        "all_click_level_interaction_variants"
    ]["why_not_actionable_now"]
    assert "920 fixtures" in actionability_by_id[
        "future_real_world_excel_surfaces"
    ]["why_not_actionable_now"]
    shortcomings = {row["id"]: row for row in report["remaining_shortcomings"]}
    assert set(shortcomings) == {
        "cross_platform_release_artifact_coverage",
        "ecosystem_maturity_and_long_tail_workflows",
        "all_high_risk_render_variants",
        "all_click_level_interaction_variants",
        "future_real_world_excel_surfaces",
    }
    assert all(row["supported_scope_impact"] is False for row in shortcomings.values())
    assert shortcomings["cross_platform_release_artifact_coverage"]["status"] == (
        "promising_but_not_fully_proven"
    )
    assert shortcomings["cross_platform_release_artifact_coverage"][
        "not_proven_family_ids"
    ] == [
        "unregistered_future_wheel_lanes",
        "installer_and_resolver_contexts",
        "alternate_distribution_channels",
        "workflow_topology_and_trigger_paths",
    ]
    assert shortcomings["ecosystem_maturity_and_long_tail_workflows"][
        "not_proven_family_ids"
    ] == [
        "unsupported_openpyxl_api",
        "unvalidated_business_template",
        "olap_external_cache_or_pivot_visuals",
        "adjacent_spreadsheet_surfaces",
        "organizational_dependency_familiarity",
    ]
    assert shortcomings["all_high_risk_render_variants"]["evidence_counts"][
        "ready_report_count"
    ] == 74
    assert shortcomings["all_click_level_interaction_variants"]["evidence_counts"][
        "known_boundary_failure_count"
    ] == 4
    assert shortcomings["future_real_world_excel_surfaces"]["evidence_counts"][
        "unknown_extension_uri_count"
    ] == 0
    assert report["claim_boundary"]["blocked_on_excel_evidence"] == []
    assert report["claim_boundary"]["blocked_on_fresh_benchmark_source_evidence"] == []
    assert report["claim_boundary_counts"] == {
        "blocked_on_excel_evidence": 0,
        "blocked_on_fresh_benchmark_source_evidence": 0,
        "known_limitations": 4,
        "promising_but_not_fully_proven": 1,
        "proven_today": 12,
        "rust_competitor_scope_caveats": 6,
        "supported_scope_caveats": 7,
    }
    assert report["finite_caveats"]["supported_scope_count"] == 7
    assert report["finite_caveats"]["rust_competitor_scope_count"] == 6
    assert (
        "pivot_cache_records_refresh_on_open" in report["claim_boundary"]["supported_scope_caveats"]
    )
    assert (
        "pivot_table_styling_beyond_pivotarea_pivot_cf"
        in report["claim_boundary"]["supported_scope_caveats"]
    )
    assert (
        "external_links_cached_data_not_dereferenced"
        in report["claim_boundary"]["supported_scope_caveats"]
    )
    assert (
        "rust_memory_uses_absolute_noise_tolerance"
        in report["claim_boundary"]["rust_competitor_scope_caveats"]
    )
    assert (
        "rust_same_surface_claim_basis" in report["claim_boundary"]["rust_competitor_scope_caveats"]
    )
    assert (
        "rust_memory_claim_path_specific"
        in report["claim_boundary"]["rust_competitor_scope_caveats"]
    )
    assert "openpyxl_speed" in report["claim_boundary"]["proven_today"]
    assert "openpyxl_memory" in report["claim_boundary"]["proven_today"]
    assert "rust_and_rust_backed_competitors" in report["claim_boundary"]["proven_today"]
    assert "rust_competitor_memory" in report["claim_boundary"]["proven_today"]
    assert "rust_competitor_memory" not in report["claim_boundary"]["promising_but_not_fully_proven"]
    assert "python_public_api_vs_direct_rust_speed" in report["claim_boundary"]["proven_today"]
    assert "release_artifact_benchmark_rerun" in report["claim_boundary"]["proven_today"]
    assert "release_artifact_benchmark_rerun" not in report["claim_boundary"]["known_limitations"]
    assert {item["id"] for item in report["remaining_blockers"]} == {
        "cross_platform_release_artifact_coverage",
        "ecosystem_maturity_and_long_tail_workflows",
        "all_high_risk_render_variants",
        "all_click_level_interaction_variants",
        "future_real_world_excel_surfaces",
    }
    assert {item["kind"] for item in report["remaining_blockers"]} == {
        "ecosystem_claim_boundary",
        "platform_release_claim_boundary",
        "unbounded_claim_boundary",
        "unbounded_future_surface_boundary",
    }
    assert report["rust_competitors"]["sota_missing_required_case_family_count"] == 0
    assert report["rust_competitors"]["competitor_set_missing_required_case_family_count"] == 0
    assert report["rust_competitors"]["requested_competitor_name_resolution_ready"] is True
    assert (
        report["rust_competitors"]["requested_competitor_name_resolutions"][0]["requested_name"]
        == "xlsxwriter-rs"
    )
    assert report["rust_competitors"]["user_requested_required_competitor_names"] == [
        "rust_xlsxwriter",
        "xlsxwriter-rs",
        "calamine",
        "umya-spreadsheet",
        "fastexcel",
        "python-calamine",
    ]
    assert (
        report["rust_competitors"]["user_requested_required_competitor_names_satisfied"]
        is True
    )
    assert report["rust_competitors"]["user_requested_required_competitor_name_blockers"] == []
    user_requested_rows = report["rust_competitors"][
        "user_requested_required_competitor_name_resolutions"
    ]
    assert [row["requested_name"] for row in user_requested_rows] == [
        "rust_xlsxwriter",
        "xlsxwriter-rs",
        "calamine",
        "umya-spreadsheet",
        "fastexcel",
        "python-calamine",
    ]
    xlsxwriter_rs_row = next(
        row for row in user_requested_rows if row["requested_name"] == "xlsxwriter-rs"
    )
    assert xlsxwriter_rs_row["evidence_lane"] == "xlsxwriter"
    assert xlsxwriter_rs_row["benchmarked_version"] == "0.6.1"
    assert xlsxwriter_rs_row["exact_package_version"] == "0.1.0"
    assert xlsxwriter_rs_row["requirement_satisfied"] is True
    assert report["rust_competitors"]["rust_watchlist_min_observed_speedup"] > 1.0
    assert report["rust_competitors"]["rust_watchlist_memory_comparison_count"] == 0
    assert report["rust_competitors"]["rust_watchlist_max_observed_memory_ratio"] is None
    assert report["rust_competitors"]["rust_watchlist_weak_memory_case_count"] == 0
    assert (
        report["rust_competitors"][
            "competitor_set_watchlist_adoption_attention_review_count"
        ]
        == 4
    )
    assert report["rust_competitors"][
        "competitor_set_watchlist_adoption_attention_reviews"
    ][0]["id"] == "python-calamine-reducto"
    assert (
        report["rust_competitors"]["competitor_set_unclassified_relevant_below_threshold_hit_count"]
        == 0
    )
    assert report["rust_competitors"][
        "competitor_set_unclassified_relevant_below_threshold_hit_ids"
    ] == []
    assert report["release_artifact_benchmark_rerun"]["wheel_metadata_ready"] is True
    assert report["release_artifact_benchmark_rerun"]["full_release_artifact_rerun_ready"] is True
    assert (
        report["release_artifact_benchmark_rerun"]["source_relevance_relevant_changed_path_count"]
        == 0
    )
    assert report["release_artifact_benchmark_rerun"]["platform"]
    assert (
        "zero benchmark-relevant committed changes"
        in report["release_artifact_benchmark_rerun"]["source_relevance_acceptance_rule"]
    )
    assert report["release_artifact_benchmark_rerun"]["openpyxl_memory_ready"] is True
    assert report["release_artifact_benchmark_rerun"]["openpyxl_weak_sota_case_count"] == 0
    assert report["release_artifact_benchmark_rerun"]["openpyxl_weak_memory_case_count"] == 0
    assert report["release_artifact_benchmark_rerun"]["rust_weak_case_count"] == 0
    assert {row["name"] for row in report["input_reports"]} == {
        "sota_report",
        "dimensions_report",
        "proof_flow_report",
        "release_artifact_benchmark_rerun",
        "evidence_manifest",
    }
    assert all(row["exists"] for row in report["input_reports"])
    assert all(row["sha256"] for row in report["input_reports"])


def test_final_sota_blocker_audit_blocks_missing_rust_version(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    sota = json.loads(paths["sota_report"].read_text(encoding="utf-8"))
    del sota["rust_competitors"]["competitor_versions"]["calamine"]
    paths["sota_report"].write_text(json.dumps(sota), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["competitor_gate_ready"] is False
    assert "competitor_gate_ready" in report["failed_checks"]


def test_release_artifact_platform_falls_back_to_benchmark_metadata() -> None:
    assert (
        audit._release_artifact_platform(
            {"openpyxl_benchmark_summary": {"metadata": {"platform": "fixture-platform"}}}
        )
        == "fixture-platform"
    )


def test_final_sota_blocker_audit_blocks_missing_rust_case_family_summary(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    sota = json.loads(paths["sota_report"].read_text(encoding="utf-8"))
    sota["rust_competitors"]["missing_required_case_family_count"] = None
    paths["sota_report"].write_text(json.dumps(sota), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["competitor_gate_ready"] is False
    assert "competitor_gate_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_missing_rust_set_benchmark_member(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    sota = json.loads(paths["sota_report"].read_text(encoding="utf-8"))
    sota["rust_competitor_set"]["benchmark_competitors"] = [
        name for name in audit.REQUIRED_RUST_COMPETITORS if name != "fastexcel"
    ]
    sota["rust_competitor_set"]["missing_from_benchmark"] = ["fastexcel"]
    paths["sota_report"].write_text(json.dumps(sota), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["competitor_gate_ready"] is False
    assert "competitor_gate_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_stale_rust_set_version(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    sota = json.loads(paths["sota_report"].read_text(encoding="utf-8"))
    sota["rust_competitor_set"]["stale_benchmark_versions"] = ["calamine"]
    paths["sota_report"].write_text(json.dumps(sota), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["competitor_gate_ready"] is False
    assert "competitor_gate_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_unclassified_rust_discovery_hit(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    sota = json.loads(paths["sota_report"].read_text(encoding="utf-8"))
    sota["rust_competitor_set"]["unclassified_discovery_hit_count"] = 1
    paths["sota_report"].write_text(json.dumps(sota), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["competitor_gate_ready"] is False
    assert "competitor_gate_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_missing_watchlist_adoption_evidence(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    sota = json.loads(paths["sota_report"].read_text(encoding="utf-8"))
    sota["rust_competitor_set"]["watchlist_promotion_adoption_complete"] = False
    sota["rust_competitor_set"]["watchlist_promotion_adoption_missing_count"] = 1
    sota["rust_competitor_set"]["watchlist_promotion_adoption_missing"] = [
        "rustypyxl"
    ]
    sota["rust_competitor_set"]["watchlist_promotion_adoption_caveat"] = (
        "Objective watchlist promotion can be applied where registry adoption "
        "data exists; watchlist packages without adoption data remain reviewed "
        "caveats."
    )
    paths["sota_report"].write_text(json.dumps(sota), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["competitor_gate_ready"] is False
    assert (
        report["rust_competitors"][
            "competitor_set_watchlist_promotion_adoption_complete"
        ]
        is False
    )
    assert report["rust_competitors"][
        "competitor_set_watchlist_promotion_adoption_missing"
    ] == ["rustypyxl"]
    assert "competitor_gate_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_missing_required_rust_alias(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    sota = json.loads(paths["sota_report"].read_text(encoding="utf-8"))
    sota["rust_competitor_set"]["required_competitor_aliases"] = {}
    paths["sota_report"].write_text(json.dumps(sota), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["competitor_gate_ready"] is False
    assert "competitor_gate_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_requested_competitor_name_gap(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    sota = json.loads(paths["sota_report"].read_text(encoding="utf-8"))
    row = sota["rust_competitor_set"]["requested_competitor_name_resolutions"][0]
    row["requirement_satisfied"] = False
    sota["rust_competitor_set"]["requested_competitor_name_resolution_ready"] = False
    sota["rust_competitor_set"]["requested_competitor_name_resolution_blockers"] = ["xlsxwriter-rs"]
    paths["sota_report"].write_text(json.dumps(sota), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["competitor_gate_ready"] is False
    assert report["rust_competitors"]["requested_competitor_name_resolution_ready"] is False
    assert report["rust_competitors"]["requested_competitor_name_resolution_blockers"] == [
        "xlsxwriter-rs"
    ]
    assert "competitor_gate_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_rust_source_relevance_gap(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    sota = json.loads(paths["sota_report"].read_text(encoding="utf-8"))
    sota["rust_competitors"]["source_relevance_ready"] = False
    sota["rust_competitors"]["source_relevance_blockers"] = [
        "benchmark-relevant source changed after benchmark"
    ]
    sota["rust_competitors"]["source_relevance_dirty_relevant_paths"] = [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    paths["sota_report"].write_text(json.dumps(sota), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["competitor_gate_ready"] is False
    assert report["rust_competitors"]["source_relevance_ready"] is False
    assert report["rust_competitors"]["source_relevance_blockers"] == [
        "benchmark-relevant source changed after benchmark"
    ]
    assert report["rust_competitors"]["source_relevance_dirty_relevant_paths"] == [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    assert "competitor_gate_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_remaining_excel_work(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    proof_flow = json.loads(paths["proof_flow_report"].read_text(encoding="utf-8"))
    proof_flow["sota"]["evidence"]["remaining_deferred_excel_step_count"] = 1
    paths["proof_flow_report"].write_text(json.dumps(proof_flow), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["remaining_deferred_excel_step_count"] == 1
    assert "no_deferred_excel_work_remains" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_actionable_non_boundary_blocker(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    dimensions = json.loads(paths["dimensions_report"].read_text(encoding="utf-8"))
    for row in dimensions["dimensions"]:
        if row["id"] == "openpyxl_speed":
            row["status"] = "blocked_on_fresh_benchmark_source_evidence"
            row["ready"] = False
            row["blocker"] = "benchmark source relevance is stale"
            row["evidence"] = {"source_relevance_ready": False}
    paths["dimensions_report"].write_text(json.dumps(dimensions), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert "remaining_blockers_have_no_actionable_evidence_steps" in report["failed_checks"]
    assert report["remaining_actionability"]["actionable_headless_step_count"] == 1
    assert report["remaining_actionability"]["actionable_headless_blocker_ids"] == [
        "openpyxl_speed"
    ]


def test_final_sota_blocker_audit_blocks_dimensions_boundary_gaps(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    dimensions = json.loads(paths["dimensions_report"].read_text(encoding="utf-8"))
    dimensions["expected_broad_claim_boundaries"] = [
        item
        for item in dimensions["expected_broad_claim_boundaries"]
        if item != "future_real_world_excel_surfaces"
    ]
    dimensions["expected_broad_claim_boundary_gap_count"] = 1
    dimensions["expected_broad_claim_boundary_gaps"] = [
        {
            "id": "future_real_world_excel_surfaces",
            "reason": "missing expected broad claim boundary",
        }
    ]
    paths["dimensions_report"].write_text(json.dumps(dimensions), encoding="utf-8")

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["dimensions_expected_broad_boundaries"]["ready"] is False
    assert "dimensions_expected_broad_boundaries_gap_free" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_missing_release_wheel_metadata(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    release = json.loads(paths["release_artifact_benchmark_rerun"].read_text(encoding="utf-8"))
    del release["wheel"]["sha256"]
    paths["release_artifact_benchmark_rerun"].write_text(
        json.dumps(release),
        encoding="utf-8",
    )

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["release_artifact_benchmark_rerun_ready"] is False
    assert report["release_artifact_benchmark_rerun"]["wheel_metadata_ready"] is False
    assert "release_artifact_benchmark_rerun_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_release_weak_or_skipped_cases(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    release = json.loads(paths["release_artifact_benchmark_rerun"].read_text(encoding="utf-8"))
    release["openpyxl_benchmark_summary"]["weak_memory_case_count"] = 1
    release["rust_benchmark_summary"]["skipped_required_competitors"] = ["rust_xlsxwriter"]
    paths["release_artifact_benchmark_rerun"].write_text(
        json.dumps(release),
        encoding="utf-8",
    )

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["release_artifact_benchmark_rerun_ready"] is False
    assert report["release_artifact_benchmark_rerun"]["openpyxl_weak_memory_case_count"] == 1
    assert report["release_artifact_benchmark_rerun"]["rust_skipped_required_competitors"] == [
        "rust_xlsxwriter"
    ]
    assert "release_artifact_benchmark_rerun_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_dirty_release_report_generator(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    release = json.loads(paths["release_artifact_benchmark_rerun"].read_text(encoding="utf-8"))
    release["report_repo_git_dirty"] = True
    paths["release_artifact_benchmark_rerun"].write_text(
        json.dumps(release),
        encoding="utf-8",
    )

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["release_artifact_benchmark_rerun_ready"] is False
    assert report["release_artifact_benchmark_rerun"]["report_repo_git_dirty"] is True
    assert "release_artifact_benchmark_rerun_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_release_source_relevance_gap(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    release = json.loads(paths["release_artifact_benchmark_rerun"].read_text(encoding="utf-8"))
    release["source_relevance_ready"] = False
    release["source_relevance_status"] = "blocked"
    release["source_relevance_blockers"] = [
        "release-artifact benchmark rerun has benchmark-relevant source changes"
    ]
    release["source_relevance_dirty_relevant_paths"] = [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    paths["release_artifact_benchmark_rerun"].write_text(
        json.dumps(release),
        encoding="utf-8",
    )

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["release_artifact_benchmark_rerun_ready"] is False
    assert report["release_artifact_benchmark_rerun"]["source_relevance_ready"] is False
    assert report["release_artifact_benchmark_rerun"]["source_relevance_dirty_relevant_paths"] == [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    assert "release_artifact_benchmark_rerun_ready" in report["failed_checks"]


def test_final_sota_blocker_audit_blocks_missing_release_rust_memory(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    release = json.loads(paths["release_artifact_benchmark_rerun"].read_text(encoding="utf-8"))
    release["rust_memory_ready"] = False
    release["rust_benchmark_summary"]["memory_comparison_count"] = 0
    release["rust_benchmark_summary"]["weak_memory_case_count"] = 0
    paths["release_artifact_benchmark_rerun"].write_text(
        json.dumps(release),
        encoding="utf-8",
    )

    report = audit.audit_final_blockers(**paths)

    assert report["ready"] is False
    assert report["release_artifact_benchmark_rerun_ready"] is False
    assert report["release_artifact_benchmark_rerun"]["rust_memory_ready"] is False
    assert report["release_artifact_benchmark_rerun"]["rust_memory_comparison_count"] == 0
    assert "release_artifact_benchmark_rerun_ready" in report["failed_checks"]


def test_final_sota_blocker_markdown_names_the_boundary(tmp_path: Path) -> None:
    report = audit.audit_final_blockers(**_write_inputs(tmp_path))
    markdown = audit.format_markdown(report)

    assert "# Final SOTA Blocker Audit" in markdown
    assert "| Final blocker audit healthy | true |" in markdown
    assert "| Final broad claim ready | false |" in markdown
    assert "| Ready field meaning | Broad no-reason claim readiness" in markdown
    assert "| Failed checks | broad_no_reason_claim_ready |" in markdown
    assert "| Audit failed checks | none |" in markdown
    assert "| SOTA claim ready | false |" in markdown
    assert "| Broad no-reason claim ready | false |" in markdown
    assert "| Remaining direct headless steps | 0 |" in markdown
    assert "| Remaining deferred Excel steps | 0 |" in markdown
    assert "| Proof-flow ready | false |" in markdown
    assert "| Proof-flow current phase | final_sota_audit_blockers |" in markdown
    assert "| Proof-flow headless work available | false |" in markdown
    assert "| Proof-flow Excel approval required | false |" in markdown
    assert "| Dimensions expected broad boundaries ready | true |" in markdown
    assert "| Dimensions expected broad boundary gaps | 0 |" in markdown
    assert (
        "| Dimensions expected broad boundary ids | all_click_level_interaction_variants, "
        "all_high_risk_render_variants, cross_platform_release_artifact_coverage, "
        "ecosystem_maturity_and_long_tail_workflows, future_real_world_excel_surfaces |"
    ) in markdown
    assert "| Proof-flow next action | None |" in markdown
    assert "## Remaining Actionability" in markdown
    assert "| Actionable headless steps | 0 |" in markdown
    assert "| Actionable Excel steps | 0 |" in markdown
    assert "| Claim wording boundaries | 5 |" in markdown
    assert (
        "| Conclusion | No remaining evidence task is identified by the current reports" in markdown
    )
    assert (
        "| Blocker | Headless task | Excel task | Not-proven families | "
        "Why not actionable now | What would make actionable |"
    ) in markdown
    assert (
        "| cross_platform_release_artifact_coverage | false | false | "
        "unregistered_future_wheel_lanes, installer_and_resolver_contexts, "
        "alternate_distribution_channels, workflow_topology_and_trigger_paths | "
        "The registered release-artifact lanes in the current evidence are complete."
    ) in markdown
    assert (
        "| future_real_world_excel_surfaces | false | false | "
        "unseen_ooxml_part_families, unseen_relationship_or_content_types, "
        "future_excel_feature_extensions | The current corpus has"
    ) in markdown
    assert "## Remaining Boundary Evidence" in markdown
    assert (
        "| cross_platform_release_artifact_coverage | "
        "cross_platform_release_artifact_coverage | "
        "unproven_release_family_count=4, "
        "unproven_release_family_ids=['unregistered_future_wheel_lanes', "
        "'installer_and_resolver_contexts', 'alternate_distribution_channels', "
        "'workflow_topology_and_trigger_paths'] |"
    ) in markdown
    assert (
        "| ecosystem_maturity_and_long_tail_workflows | "
        "ecosystem_maturity_and_long_tail_workflows | "
        "still_reasonable_use_case_count=5, "
        "still_reasonable_use_case_ids=['unsupported_openpyxl_api', "
        "'unvalidated_business_template', 'olap_external_cache_or_pivot_visuals', "
        "'adjacent_spreadsheet_surfaces', "
        "'organizational_dependency_familiarity'] |"
    ) in markdown
    assert (
        "| all_high_risk_render_variants | feature_specific_intentional_render_equivalence | "
        "ready_report_count=74, excel_report_count=70, passed_count=832, failure_count=0"
        in markdown
    )
    assert "unexhausted_boundary_family_count=3" in markdown
    assert "unseen_feature_edit_combinations" in markdown
    assert (
        "| all_click_level_interaction_variants | broader_click_level_interaction_variants | "
        "probe_report_count=242, ready_gate_report_count=107, completed_probe_report_count=135"
        in markdown
    )
    assert "prompt_and_dialog_variants" in markdown
    assert (
        "| future_real_world_excel_surfaces | future_surface_exhaustiveness | "
        "fixture_count=783, required_gap_radar_report_count=50" in markdown
    )
    assert "future_excel_feature_extensions" in markdown
    assert "## Remaining Shortcomings Inventory" in markdown
    assert (
        "| cross_platform_release_artifact_coverage | promising_but_not_fully_proven | "
        "false | unregistered_future_wheel_lanes, installer_and_resolver_contexts"
    ) in markdown
    assert (
        "| ecosystem_maturity_and_long_tail_workflows | known_limitation | false | "
        "unsupported_openpyxl_api, unvalidated_business_template"
    ) in markdown
    assert (
        "| all_high_risk_render_variants | known_limitation | false | "
        "unseen_feature_edit_combinations, template_specific_visual_acceptance"
    ) in markdown
    assert (
        "ready_report_count=74, excel_report_count=70, passed_count=832"
        in markdown
    )
    assert (
        "| all_click_level_interaction_variants | known_limitation | false | "
        "slicer_timeline_control_variants, prompt_and_dialog_variants"
    ) in markdown
    assert "known_boundary_failure_count=4" in markdown
    assert (
        "| future_real_world_excel_surfaces | known_limitation | false | "
        "unseen_ooxml_part_families, unseen_relationship_or_content_types"
    ) in markdown
    assert "## Input Reports" in markdown
    assert "| sota_report |" in markdown
    assert "| dimensions_report |" in markdown
    assert "## Rust Gate Evidence" in markdown
    assert (
        "| User-requested competitor names | rust_xlsxwriter, xlsxwriter-rs, "
        "calamine, umya-spreadsheet, fastexcel, python-calamine |"
    ) in markdown
    assert "| User-requested competitor names satisfied | true |" in markdown
    assert "| User-requested competitor name blockers | none |" in markdown
    assert (
        "| xlsxwriter lane | crates.io package `xlsxwriter` 0.6.1; "
        "repository alias `xlsxwriter-rs`; separate crates.io package "
        "`xlsxwriter-rs` 0.1.0 is not the benchmarked lane |"
    ) in markdown
    assert "| Required aliases | xlsxwriter: xlsxwriter-rs |" in markdown
    assert "| Current audit competitor versions | rust_xlsxwriter 0.95.0" in markdown
    assert "| Competitor-set versions | rust_xlsxwriter 0.95.0" in markdown
    assert "| Release artifact versions | rust_xlsxwriter 0.95.0" in markdown
    assert "| Competitor-set report | rust-set.json |" in markdown
    assert "| Competitor-set report timestamp | 2026-06-02T12:13:07Z |" in markdown
    assert "| Competitor-set report age days | 0.0 |" in markdown
    assert "| Competitor-set report fresh | true |" in markdown
    assert "| Competitor-set max age days | 14.0 |" in markdown
    assert "| Registry metadata fetched | true |" in markdown
    assert "| Crates.io discovery fetched | true |" in markdown
    assert "| Competitor-set discovery error queries | none |" in markdown
    assert "| Competitor-set freshness blockers | none |" in markdown
    assert "| Requested competitor name resolution ready | true |" in markdown
    assert (
        "| xlsxwriter-rs | watchlist | 0.1.0 | remain_watchlist | xlsxwriter | 0.6.1 | true |"
    ) in markdown
    assert "## User-Requested Rust Competitor Coverage" in markdown
    assert (
        "| xlsxwriter-rs | xlsxwriter | xlsxwriter | 0.6.1 | 0.6.1 | watchlist | 0.1.0 | true |"
    ) in markdown
    assert (
        "| python-calamine | python-calamine | python-calamine | 0.6.2 | 0.6.2 | "
        "required_benchmark_lane | 0.6.2 | true |"
    ) in markdown
    assert "## Rust Registry Version Evidence" in markdown
    assert (
        "| xlsxwriter | xlsxwriter | crates.io | xlsxwriter-rs | 0.6.1 | direct_rust_api | 0.6.1 | 0.6.1 | true | fixture_registry |"
        in markdown
    )
    assert (
        "| python-calamine | python-calamine | pypi | none | 0.6.2 | python_binding_api | 0.6.2 | 0.6.2 | true | fixture_registry |"
        in markdown
    )
    assert "| Current audit missing required case families | 0 |" in markdown
    assert "| Competitor-set missing required case families | 0 |" in markdown
    assert "| Competitor-set missing benchmark competitors | none |" in markdown
    assert "| Competitor-set missing benchmark versions | none |" in markdown
    assert "| Competitor-set stale benchmark versions | none |" in markdown
    assert "| Competitor-set unclassified discovery hits | 0 |" in markdown
    assert "| Competitor-set unclassified low-adoption relevant hits | 1 |" in markdown
    assert "## Rust Below-Threshold Discovery Hits" in markdown
    assert (
        "| tiny-ooxml | ooxml | 7 | 0.0.1 | 12 | 3 | "
        "relevant discovery hit, but below the review/adoption threshold |"
    ) in markdown
    assert "## Finite Caveats" in markdown
    assert (
        "| supported_scope | fixture supported caveat | `docs/example.md` | false | "
        "fixture supported caveat note |"
    ) in markdown
    assert (
        "| rust_competitors | fixture Rust caveat | `docs/rust.md` | false | "
        "fixture Rust caveat note |"
    ) in markdown
    assert "## Evidence Bundle" in markdown
    assert "| Bundle ready | true |" in markdown
    assert "| Report count | 1 |" in markdown
    assert "| Producer lane counts | other=1 |" in markdown
    assert "## Release Artifact Evidence" in markdown
    assert "| Wheel metadata ready | true |" in markdown
    assert f"| Wheel SHA-256 | {'c' * 64} |" in markdown
    assert "| Wheel size bytes | 1234 |" in markdown
    assert "| Source git SHA | abc123 |" in markdown
    assert "| Report repo git SHA | report123 |" in markdown
    assert "| Report repo git dirty | false |" in markdown
    assert "| Generator script source | fixture generator |" in markdown
    assert "| OpenPyXL weak speed cases | 0 |" in markdown
    assert "| OpenPyXL weak memory cases | 0 |" in markdown
    assert "| Rust weak cases | 0 |" in markdown
    assert "| Rust skipped required competitors | none |" in markdown
    assert "unbounded_future_surface_boundary" in markdown


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    evidence_manifest = _write_evidence_manifest(tmp_path)
    return {
        "sota_report": _write_sota_report(tmp_path),
        "dimensions_report": _write_dimensions_report(tmp_path),
        "proof_flow_report": _write_proof_flow_report(tmp_path),
        "release_artifact_benchmark_rerun": _write_release_rerun(tmp_path),
        "evidence_manifest": evidence_manifest,
    }


def _write_evidence_manifest(tmp_path: Path) -> Path:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"ready": True}), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "bundle_report",
                        "path": "report.json",
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [{"path": "ready", "equals": True}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _write_sota_report(tmp_path: Path) -> Path:
    path = tmp_path / "sota.json"
    path.write_text(
        json.dumps(
            {
                "sota_claim_ready": False,
                "supported_scope_sota_gate_ready": True,
                "claim_gates": {
                    "api_compat_gate_ready": True,
                    "current_fidelity_gate_ready": True,
                    "openpyxl_performance_gate_ready": True,
                    "rust_competitor_gate_ready": True,
                    "rust_competitor_set_gate_ready": True,
                    "supported_scope_sota_gate_ready": True,
                },
                "rust_competitors": {
                    "competitor_versions": _versions(),
                    "missing_competitors": [],
                    "missing_version_competitors": [],
                    "missing_required_case_family_count": 0,
                    "missing_required_case_families": [],
                    "source_relevance_ready": True,
                    "source_relevance_blockers": [],
                    "source_relevance_dirty_relevant_paths": [],
                    "source_relevance_relevant_changed_path_count": 0,
                },
                "rust_watchlist": {
                    "benchmark_present": True,
                    "min_observed_speedup": 2.4,
                    "memory_comparison_count": 1,
                    "max_observed_memory_ratio": 0.8,
                    "weak_memory_case_count": 0,
                    "near_parity_memory_case_count": 0,
                    "source_relevance_ready": True,
                    "source_relevance_blockers": [],
                },
                "rust_competitor_set": {
                    "main_rust_competitor_set_ready": True,
                    "benchmark_present": True,
                    "report_present": True,
                    "report": "rust-set.json",
                    "report_timestamp_utc": "2026-06-02T12:13:07Z",
                    "report_age_days": 0.0,
                    "report_fresh": True,
                    "max_age_days": 14.0,
                    "portable_report_path": True,
                    "registry_metadata_fetched": True,
                    "crates_io_discovery_fetched": True,
                    "pypi_discovery_fetched": True,
                    "required_competitors": list(audit.REQUIRED_RUST_COMPETITORS),
                    "benchmark_competitors": list(audit.REQUIRED_RUST_COMPETITORS),
                    "report_required_competitors": list(audit.REQUIRED_RUST_COMPETITORS),
                    "required_competitor_aliases": {"xlsxwriter": ["xlsxwriter-rs"]},
                    "benchmark_competitor_versions": _versions(),
                    "benchmark_competitor_api_surfaces": _api_surfaces(),
                    "required_competitor_version_evidence": _version_evidence(),
                    "missing_from_benchmark": [],
                    "missing_benchmark_versions": [],
                    "stale_benchmark_versions": [],
                    "missing_required_from_report": [],
                    "freshness_blockers": [],
                    "blockers": [],
                    "discovery_error_queries": [],
                    "pypi_discovery_error_queries": [],
                    "unclassified_discovery_hit_count": 0,
                    "unclassified_pypi_discovery_hit_count": 0,
                    "unclassified_relevant_below_threshold_hit_count": 1,
                    "unclassified_relevant_below_threshold_hits": [
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
                    "watchlist_promotion_review_ready": True,
                    "watchlist_promotion_review_count": 9,
                    "watchlist_packages_requiring_promotion": [],
                    "watchlist_promotion_adoption_missing_count": 0,
                    "watchlist_promotion_adoption_missing": [],
                    "watchlist_promotion_adoption_complete": True,
                    "watchlist_promotion_adoption_caveat": None,
                    "requested_competitor_name_resolutions": [
                        {
                            "requested_name": "xlsxwriter-rs",
                            "resolution": "required_competitor_alias",
                            "resolves_to_competitor": "xlsxwriter",
                            "benchmarked_package": "xlsxwriter",
                            "benchmarked_version": "0.6.1",
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
                    ],
                    "requested_competitor_name_resolution_count": 1,
                    "requested_competitor_name_resolution_ready": True,
                    "requested_competitor_name_resolution_blockers": [],
                    "missing_required_case_family_count": 0,
                    "missing_required_case_families": [],
                },
                "evidence": {
                    "finite_evidence_frontiers_ready": True,
                    "finite_evidence_frontier_blocker_ids": [],
                    "missing_report_count": 0,
                    "missing_requirement_ids": list(audit.UNBOUNDED_BOUNDARY_IDS),
                    "unbounded_claim_boundary_ids": list(audit.UNBOUNDED_BOUNDARY_IDS),
                    "missing_requirements": [
                        {
                            "id": "feature_specific_intentional_render_equivalence",
                            "evidence_summary": {
                                "ready_report_count": 74,
                                "excel_report_count": 70,
                                "passed_count": 832,
                                "failure_count": 0,
                                "frontier_evidence_ready": True,
                                "frontier_missing_report_count": 0,
                                "coverage_matrix": {
                                    "current_target_ready": True,
                                    "expected_mutation_count": 7,
                                    "observed_expected_mutation_count": 7,
                                    "missing_expected_mutation_count": 0,
                                    "unpassed_expected_mutation_count": 0,
                                },
                            },
                        },
                        {
                            "id": "broader_click_level_interaction_variants",
                            "evidence_summary": {
                                "probe_report_count": 242,
                                "ready_gate_report_count": 107,
                                "completed_probe_report_count": 135,
                                "raw_result_count": 318,
                                "raw_failure_count": 4,
                                "known_boundary_failure_count": 4,
                                "unresolved_non_boundary_failure_count": 0,
                                "frontier_evidence_ready": True,
                                "frontier_missing_report_count": 0,
                            },
                        },
                        {
                            "id": "future_surface_exhaustiveness",
                            "evidence_summary": {
                                "fixture_count": 783,
                                "required_gap_radar_report_count": 50,
                                "present_gap_radar_report_count": 50,
                                "clear_gap_radar_report_count": 50,
                                "unknown_part_family_count": 0,
                                "unknown_relationship_type_count": 0,
                                "unknown_content_type_count": 0,
                                "unknown_extension_uri_count": 0,
                            },
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_dimensions_report(tmp_path: Path) -> Path:
    path = tmp_path / "dimensions.json"
    path.write_text(
        json.dumps(
            {
                "supported_scope_ready": True,
                "broad_no_reason_claim_ready": False,
                "proven_today": [
                    "api_compatibility",
                    "openpyxl_speed",
                    "openpyxl_memory",
                    "python_public_api_vs_direct_rust_speed",
                    "rust_competitor_memory",
                ],
                "not_proven": [
                    "cross_platform_release_artifact_coverage",
                    "ecosystem_maturity_and_long_tail_workflows",
                    "all_high_risk_render_variants",
                    "all_click_level_interaction_variants",
                    "future_real_world_excel_surfaces",
                ],
                "promising_but_not_fully_proven": [
                    "cross_platform_release_artifact_coverage",
                ],
                "known_limitations": [
                    "ecosystem_maturity_and_long_tail_workflows",
                    "all_high_risk_render_variants",
                    "all_click_level_interaction_variants",
                    "future_real_world_excel_surfaces",
                ],
                "expected_broad_claim_boundaries": [
                    "all_click_level_interaction_variants",
                    "all_high_risk_render_variants",
                    "cross_platform_release_artifact_coverage",
                    "ecosystem_maturity_and_long_tail_workflows",
                    "future_real_world_excel_surfaces",
                ],
                "expected_broad_claim_boundary_gap_count": 0,
                "expected_broad_claim_boundary_gaps": [],
                "supported_scope_caveats": [
                    {
                        "id": "fixture_supported_caveat",
                        "label": "fixture supported caveat",
                        "source": "docs/example.md",
                        "note": "fixture supported caveat note",
                        "blocks_supported_scope": False,
                    }
                ],
                "rust_competitor_scope_caveats": [
                    {
                        "id": "fixture_rust_caveat",
                        "label": "fixture Rust caveat",
                        "source": "docs/rust.md",
                        "note": "fixture Rust caveat note",
                        "blocks_competitor_gate": False,
                    }
                ],
                "dimensions": [
                    {
                        "id": "openpyxl_speed",
                        "status": "proven_today",
                        "ready": True,
                        "blocker": None,
                        "evidence": {"source_relevance_ready": True},
                    },
                    {
                        "id": "openpyxl_memory",
                        "status": "proven_today",
                        "ready": True,
                        "blocker": None,
                        "evidence": {"source_relevance_ready": True},
                    },
                    {
                        "id": "python_public_api_vs_direct_rust_speed",
                        "ready": True,
                        "blocker": None,
                        "evidence": {
                            "public_cross_surface_weak_case_count": 0,
                        },
                    },
                    {
                        "id": "rust_competitor_memory",
                        "status": "proven_today",
                        "ready": True,
                        "blocker": None,
                        "evidence": {
                            "sota_weak_memory_case_count": 0,
                            "release_artifact_weak_memory_case_count": 0,
                        },
                    },
                    {
                        "id": "cross_platform_release_artifact_coverage",
                        "status": "promising_but_not_fully_proven",
                        "ready": False,
                        "blocker": (
                            "registered release-artifact lanes are proven today, "
                            "but broader release claims remain bounded"
                        ),
                        "evidence": {
                            "supported_scope_impact": False,
                            "unproven_release_family_count": 4,
                            "unproven_release_family_ids": [
                                "unregistered_future_wheel_lanes",
                                "installer_and_resolver_contexts",
                                "alternate_distribution_channels",
                                "workflow_topology_and_trigger_paths",
                            ],
                        },
                    },
                    {
                        "id": "ecosystem_maturity_and_long_tail_workflows",
                        "status": "known_limitation",
                        "ready": False,
                        "blocker": "openpyxl still has ecosystem maturity",
                        "evidence": {
                            "supported_scope_impact": False,
                            "still_reasonable_use_case_count": 5,
                            "still_reasonable_use_case_ids": [
                                "unsupported_openpyxl_api",
                                "unvalidated_business_template",
                                "olap_external_cache_or_pivot_visuals",
                                "adjacent_spreadsheet_surfaces",
                                "organizational_dependency_familiarity",
                            ],
                        },
                    },
                    {
                        "id": "all_high_risk_render_variants",
                        "status": "known_limitation",
                        "ready": False,
                        "blocker": "high-risk render variant space remains open-ended",
                        "evidence": {
                            "unexhausted_boundary_family_count": 3,
                            "unexhausted_boundary_family_ids": [
                                "unseen_feature_edit_combinations",
                                "template_specific_visual_acceptance",
                                "excel_renderer_version_variants",
                            ],
                        },
                    },
                    {
                        "id": "all_click_level_interaction_variants",
                        "status": "known_limitation",
                        "ready": False,
                        "blocker": "click-level Excel interaction variant space remains open-ended",
                        "evidence": {
                            "unexhausted_boundary_family_count": 3,
                            "unexhausted_boundary_family_ids": [
                                "slicer_timeline_control_variants",
                                "prompt_and_dialog_variants",
                                "destructive_axis_external_tool_boundaries",
                            ],
                        },
                    },
                    {
                        "id": "future_real_world_excel_surfaces",
                        "status": "known_limitation",
                        "ready": False,
                        "blocker": (
                            "no finite corpus can prove that unseen future Excel "
                            "surfaces do not exist"
                        ),
                        "evidence": {
                            "unexhausted_boundary_family_count": 3,
                            "unexhausted_boundary_family_ids": [
                                "unseen_ooxml_part_families",
                                "unseen_relationship_or_content_types",
                                "future_excel_feature_extensions",
                            ],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_proof_flow_report(tmp_path: Path) -> Path:
    path = tmp_path / "proof-flow.json"
    path.write_text(
        json.dumps(
            {
                "current_phase": "final_sota_audit_blockers",
                "ready": False,
                "headless_work_available": False,
                "excel_approval_required": False,
                "sota": {
                    "evidence": {
                        "finite_evidence_frontiers_ready": True,
                        "finite_evidence_frontier_blocker_ids": [],
                        "missing_report_count": 0,
                        "remaining_direct_headless_step_count": 0,
                        "remaining_deferred_excel_step_count": 0,
                        "next_required_proof_mode": "none",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_release_rerun(tmp_path: Path) -> Path:
    path = tmp_path / "release-rerun.json"
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "source_git_sha": "abc123",
                "source_git_dirty": False,
                "report_repo_git_sha": "report123",
                "report_repo_git_dirty": False,
                "source_relevance_ready": True,
                "source_relevance_status": "fixture_checked",
                "source_relevance_base_git_commit": "abc123",
                "source_relevance_current_git_commit": "abc123",
                "source_relevance_changed_path_count": 0,
                "source_relevance_relevant_changed_path_count": 0,
                "source_relevance_relevant_changed_paths": [],
                "source_relevance_dirty_relevant_paths": [],
                "source_relevance_blockers": [],
                "generator_script_source": "fixture generator",
                "full_release_artifact_rerun_ready": True,
                "openpyxl_sota_speed_ready": True,
                "openpyxl_memory_ready": True,
                "rust_superiority_ready": True,
                "rust_memory_ready": True,
                "broad_speed_superiority_ready": True,
                "wheel": {
                    "filename": "wolfxl-2.0.0-cp312-cp312-macosx_11_0_arm64.whl",
                    "metadata_name": "wolfxl",
                    "metadata_version": "2.0.0",
                    "sha256": "c" * 64,
                    "size_bytes": 1234,
                    "wheel_tag": "cp312-cp312-macosx_11_0_arm64",
                },
                "openpyxl_benchmark_summary": {
                    "metadata": {"platform": "fixture-platform"},
                    "comparison_count": 20,
                    "weak_sota_case_count": 0,
                    "memory_comparison_count": 8,
                    "weak_memory_case_count": 0,
                },
                "rust_benchmark_summary": {
                    "comparison_count": 14,
                    "weak_case_count": 0,
                    "memory_comparison_count": 14,
                    "weak_memory_case_count": 0,
                    "competitor_versions": _versions(),
                    "missing_competitors": [],
                    "missing_version_competitors": [],
                    "skipped_required_competitors": [],
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _versions() -> dict[str, str]:
    return {
        "rust_xlsxwriter": "0.95.0",
        "xlsxwriter": "0.6.1",
        "calamine": "0.35.0",
        "umya-spreadsheet": "2.3.3",
        "fastexcel": "0.20.2",
        "python-calamine": "0.6.2",
    }


def _api_surfaces() -> dict[str, list[str]]:
    return {
        "rust_xlsxwriter": ["direct_rust_api"],
        "xlsxwriter": ["direct_rust_api"],
        "calamine": ["direct_rust_api"],
        "umya-spreadsheet": ["direct_rust_api"],
        "fastexcel": ["python_binding_api"],
        "python-calamine": ["python_binding_api"],
    }


def _version_evidence() -> list[dict[str, object]]:
    package_sources = {
        "rust_xlsxwriter": ("rust_xlsxwriter", "crates.io", []),
        "xlsxwriter": ("xlsxwriter", "crates.io", ["xlsxwriter-rs"]),
        "calamine": ("calamine", "crates.io", []),
        "umya-spreadsheet": ("umya-spreadsheet", "crates.io", []),
        "fastexcel": ("fastexcel", "crates.io", []),
        "python-calamine": ("python-calamine", "pypi", []),
    }
    versions = _versions()
    return [
        {
            "competitor": competitor,
            "package": package,
            "source": source,
            "aliases": aliases,
            "benchmark_version": versions[competitor],
            "benchmark_api_surfaces": _api_surfaces()[competitor],
            "registry_version": versions[competitor],
            "release_artifact_version": versions[competitor],
            "version_captured": True,
            "evidence_source": "fixture_registry",
        }
        for competitor, (package, source, aliases) in package_sources.items()
    ]
