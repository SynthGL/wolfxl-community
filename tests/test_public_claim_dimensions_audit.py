from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_public_claim_dimensions.py"
    spec = importlib.util.spec_from_file_location("audit_public_claim_dimensions", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_public_claim_dimensions_current_repo_keeps_broad_claim_gated() -> None:
    report = audit.audit_claim_dimensions()

    assert report["supported_scope_ready"] is True
    assert report["broad_no_reason_claim_ready"] is False
    assert report["ready"] is False
    assert report["promising_but_not_fully_proven"] == [
        "cross_platform_release_artifact_coverage",
    ]
    assert report["blocked_on_excel_evidence"] == []
    assert report["blocked_on_other_required_evidence"] == []
    assert report["known_limitations"] == [
        "ecosystem_maturity_and_long_tail_workflows",
        "all_high_risk_render_variants",
        "all_click_level_interaction_variants",
        "future_real_world_excel_surfaces",
    ]
    assert report["expected_broad_claim_boundaries"] == [
        "all_click_level_interaction_variants",
        "all_high_risk_render_variants",
        "cross_platform_release_artifact_coverage",
        "ecosystem_maturity_and_long_tail_workflows",
        "future_real_world_excel_surfaces",
    ]
    assert report["expected_broad_claim_boundary_gap_count"] == 0
    assert report["expected_broad_claim_boundary_gaps"] == []
    assert "api_compatibility" in report["proven_today"]
    assert "public_claim_wording" in report["proven_today"]
    assert "openpyxl_speed" in report["proven_today"]
    assert "openpyxl_memory" in report["proven_today"]
    assert "rust_and_rust_backed_competitors" in report["proven_today"]
    assert "rust_and_rust_backed_competitors" not in report["not_proven"]
    assert "rust_competitor_memory" in report["proven_today"]
    assert "rust_competitor_memory" not in report["not_proven"]
    assert "release_artifact_install_smoke" in report["proven_today"]
    assert "release_artifact_benchmark_smoke" in report["proven_today"]
    assert "release_artifact_install_smoke" not in report["not_proven"]
    assert "release_artifact_benchmark_smoke" not in report["not_proven"]
    assert "release_artifact_benchmark_rerun" in report["proven_today"]
    assert "release_artifact_benchmark_rerun" not in report["not_proven"]
    assert "python_public_api_vs_direct_rust_speed" in report["proven_today"]
    assert "python_public_api_vs_direct_rust_speed" not in report["not_proven"]
    assert {row["name"] for row in report["input_reports"]} == {
        "sota_report",
        "public_claim_report",
        "release_artifact_smoke",
        "release_artifact_benchmark_smoke",
        "release_artifact_benchmark_rerun",
        "release_artifact_coverage",
        "release_artifact_proof_workflow",
        "release_artifact_trigger_readiness",
        "proof_flow_report",
    }
    assert all(row["exists"] for row in report["input_reports"])
    assert all(row["sha256"] for row in report["input_reports"])
    assert "future_real_world_excel_surfaces" in report["not_proven"]
    assert "all_high_risk_render_variants" in report["not_proven"]
    assert "all_click_level_interaction_variants" in report["not_proven"]
    assert "cross_platform_release_artifact_coverage" in report["not_proven"]
    assert "ecosystem_maturity_and_long_tail_workflows" in report["not_proven"]
    assert report["supported_scope_caveat_count"] == 7
    assert report["rust_competitor_scope_caveat_count"] == 6
    assert report["rust_competitor_summary"]["ready"] is True
    assert report["rust_competitor_summary"]["speed_ready"] is True
    assert report["rust_competitor_summary"]["memory_ready"] is True
    assert report["rust_competitor_summary"]["same_surface_basis_ready"] is True
    assert report["rust_competitor_summary"]["required_competitors"] == [
        "rust_xlsxwriter",
        "xlsxwriter",
        "calamine",
        "umya-spreadsheet",
        "fastexcel",
        "python-calamine",
    ]
    assert report["rust_competitor_summary"]["competitor_versions"] == {
        "rust_xlsxwriter": "0.95.0",
        "xlsxwriter": "0.6.1",
        "calamine": "0.35.0",
        "umya-spreadsheet": "3.0.0",
        "fastexcel": "0.20.2",
        "python-calamine": "0.6.2",
    }
    assert report["rust_competitor_summary"]["benchmark_api_surfaces"] == {
        "rust_xlsxwriter": ["direct_rust_api"],
        "xlsxwriter": ["direct_rust_api"],
        "calamine": ["direct_rust_api"],
        "umya-spreadsheet": ["direct_rust_api"],
        "fastexcel": ["python_binding_api"],
        "python-calamine": ["python_binding_api"],
    }
    assert report["rust_competitor_summary"]["missing_competitors"] == []
    assert report["rust_competitor_summary"]["missing_version_competitors"] == []
    assert report["rust_competitor_summary"]["watchlist_packages_requiring_promotion"] == []
    assert (
        report["rust_competitor_summary"][
            "competitor_set_watchlist_adoption_attention_review_count"
        ]
        == 4
    )
    assert report["rust_competitor_summary"][
        "competitor_set_watchlist_adoption_attention_reviews"
    ][0]["id"] == "python-calamine-reducto"
    assert report["rust_competitor_summary"]["requested_competitor_names"] == [
        "xlsxwriter-rs"
    ]
    assert report["rust_competitor_summary"][
        "satisfied_requested_competitor_names"
    ] == ["xlsxwriter-rs"]
    assert report["rust_competitor_summary"][
        "unsatisfied_requested_competitor_names"
    ] == []
    assert report["rust_competitor_summary"]["public_rows_replaced_by_same_surface_count"] == 18
    assert report["rust_competitor_summary"]["scope_caveat_count"] == 6
    render = _dimension(report, "all_high_risk_render_variants")
    assert render["evidence"]["unexhausted_boundary_family_ids"] == [
        "unseen_feature_edit_combinations",
        "template_specific_visual_acceptance",
        "excel_renderer_version_variants",
    ]
    click = _dimension(report, "all_click_level_interaction_variants")
    assert click["evidence"]["unexhausted_boundary_family_ids"] == [
        "slicer_timeline_control_variants",
        "prompt_and_dialog_variants",
        "destructive_axis_external_tool_boundaries",
    ]
    future = _dimension(report, "future_real_world_excel_surfaces")
    assert future["evidence"]["unexhausted_boundary_family_ids"] == [
        "unseen_ooxml_part_families",
        "unseen_relationship_or_content_types",
        "future_excel_feature_extensions",
    ]
    assert {item["id"] for item in report["supported_scope_caveats"]} == {
        "pivot_cache_records_refresh_on_open",
        "pivot_table_styling_beyond_pivotarea_pivot_cf",
        "olap_external_pivot_caches_out_of_scope",
        "external_links_cached_data_not_dereferenced",
        "powerview_app_unsupported_prompt",
        "chart_cached_values_rebuilt_by_excel",
        "non_openpyxl_extra_exclusions",
    }
    assert {item["id"] for item in report["rust_competitor_scope_caveats"]} == {
        "rust_case_families_are_bounded",
        "pypi_rust_backed_discovery_bounded",
        "rust_memory_uses_absolute_noise_tolerance",
        "rust_same_surface_claim_basis",
        "rust_memory_claim_path_specific",
        "release_rust_benchmark_small_synthetic_shape",
    }
    assert all(
        item["blocks_supported_scope"] is False
        for item in report["supported_scope_caveats"]
    )
    assert all(
        item["blocks_competitor_gate"] is False
        for item in report["rust_competitor_scope_caveats"]
    )
    repo_root = Path(__file__).resolve().parents[1]
    for item in (
        report["supported_scope_caveats"] + report["rust_competitor_scope_caveats"]
    ):
        source = item["source"]
        if source.startswith(("docs/", "Plans/")) or source in {"pyproject.toml"}:
            assert (repo_root / source).exists(), source
    assert "openpyxl_speed" in report["proven_today"]
    assert "openpyxl_memory" in report["proven_today"]
    assert "openpyxl_speed" not in report["not_proven"]
    assert "openpyxl_memory" not in report["not_proven"]
    openpyxl_speed = _dimension(report, "openpyxl_speed")
    assert openpyxl_speed["status"] == "proven_today"
    assert openpyxl_speed["blocker"] is None
    assert openpyxl_speed["evidence"]["source_relevance_ready"] is True
    openpyxl_memory = _dimension(report, "openpyxl_memory")
    assert openpyxl_memory["status"] == "proven_today"
    assert openpyxl_memory["blocker"] is None
    assert openpyxl_memory["evidence"]["source_relevance_ready"] is True
    assert openpyxl_memory["evidence"]["weak_memory_case_count"] == 0
    rust_memory = _dimension(report, "rust_competitor_memory")
    assert rust_memory["status"] == "proven_today"
    assert rust_memory["blocker"] is None
    assert rust_memory["evidence"]["sota_memory_comparison_count"] == 18
    assert rust_memory["evidence"]["sota_weak_memory_case_count"] == 0
    assert rust_memory["evidence"]["sota_near_parity_memory_case_count"] >= 0
    assert rust_memory["evidence"]["memory_noise_tolerance_bytes"] == 3145728
    assert "memory rows are present" in rust_memory["evidence"]["note"]
    assert rust_memory["evidence"]["release_artifact_memory_comparison_count"] > 0
    assert rust_memory["evidence"]["release_artifact_weak_memory_case_count"] == 0
    rust_competitors = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust_competitors["ready"] is True
    assert rust_competitors["status"] == "proven_today"
    assert rust_competitors["blocker"] is None
    assert rust_competitors["evidence"]["source_relevance_ready"] is True
    assert rust_competitors["evidence"]["rust_watchlist_min_observed_speedup"] > 1.0
    assert rust_competitors["evidence"]["rust_watchlist_memory_comparison_count"] == 0
    assert rust_competitors["evidence"]["rust_watchlist_max_observed_memory_ratio"] is None
    assert rust_competitors["evidence"]["rust_watchlist_weak_memory_case_count"] == 0
    assert (
        rust_competitors["evidence"][
            "competitor_set_unclassified_relevant_below_threshold_hit_count"
        ]
        == 0
    )
    assert rust_competitors["evidence"][
        "competitor_set_unclassified_relevant_below_threshold_hit_ids"
    ] == []
    assert report["rust_competitor_summary"]["below_threshold_hit_ids"] == []
    public_vs_rust = _dimension(report, "python_public_api_vs_direct_rust_speed")
    assert public_vs_rust["status"] == "proven_today"
    assert (
        public_vs_rust["evidence"]["public_cross_surface_weak_case_count"] == 0
    )
    assert public_vs_rust["evidence"]["public_cross_surface_weak_cases"] == []
    repro_reports = public_vs_rust["evidence"]["focused_repro_reports"]
    assert {
        item["path"]
        for item in repro_reports
    } == {
        "docs/performance/baselines/2026-06-01-after-merged-border-open-skip-reader-repro.json",
        "docs/performance/baselines/2026-06-01-write-styled-rows-fast-path.json",
    }
    assert all(item["exists"] for item in repro_reports)
    ecosystem = _dimension(report, "ecosystem_maturity_and_long_tail_workflows")
    assert ecosystem["status"] == "known_limitation"
    assert ecosystem["blocks_broad_claim"] is True
    assert ecosystem["evidence"]["supported_scope_impact"] is False
    assert (
        "familiar dependency"
        in ecosystem["evidence"]["why_openpyxl_can_still_be_reasonable"]
    )
    assert ecosystem["evidence"]["still_reasonable_use_case_count"] == 5
    assert ecosystem["evidence"]["still_reasonable_use_case_ids"] == [
        "unsupported_openpyxl_api",
        "unvalidated_business_template",
        "olap_external_cache_or_pivot_visuals",
        "adjacent_spreadsheet_surfaces",
        "organizational_dependency_familiarity",
    ]
    assert {
        item["source"] for item in ecosystem["evidence"]["still_reasonable_use_cases"]
    } == {
        "docs/trust/launch-claim-brief.md",
        "docs/trust/public-evidence.md",
    }
    platform_release = _dimension(report, "cross_platform_release_artifact_coverage")
    assert platform_release["status"] == "promising_but_not_fully_proven"
    assert platform_release["blocks_broad_claim"] is True
    assert platform_release["reason"] == platform_release["blocker"]
    if platform_release["evidence"]["trigger_readiness_mode"] == "push_required":
        assert "Push the current branch" in platform_release["next_action"]
        assert "resulting release lane reports" in platform_release["next_action"]
    else:
        assert "Keep registered release-artifact lane proof current" in (
            platform_release["next_action"]
        )
        assert "missing lanes" not in platform_release["next_action"]
    assert "registered release-artifact lanes are proven today" in platform_release["blocker"]
    assert platform_release["evidence"]["supported_scope_impact"] is False
    assert platform_release["evidence"]["current_durable_wheel_tag"].endswith(
        "macosx_11_0_arm64"
    )
    assert platform_release["evidence"]["current_durable_platform"]
    assert platform_release["evidence"]["coverage_ready"] is True
    assert platform_release["evidence"]["release_lane_currentness_ready"] is True
    assert platform_release["evidence"]["current_head_proven_release_lane_count"] == 26
    assert platform_release["evidence"]["expected_release_lane_count"] == 26
    assert platform_release["evidence"]["proven_release_lane_count"] == 26
    assert platform_release["evidence"]["missing_release_lane_count"] == 0
    assert platform_release["evidence"]["stale_release_lane_count"] == 0
    assert platform_release["evidence"]["stale_release_lane_ids"] == []
    assert platform_release["evidence"]["unproven_release_family_count"] == 4
    assert platform_release["evidence"]["unproven_release_family_ids"] == [
        "unregistered_future_wheel_lanes",
        "installer_and_resolver_contexts",
        "alternate_distribution_channels",
        "workflow_topology_and_trigger_paths",
    ]
    assert platform_release["evidence"]["proven_release_lane_ids"] == [
        "wheel:linux:x86_64:cp39",
        "wheel:linux:x86_64:cp310",
        "wheel:linux:x86_64:cp311",
        "wheel:linux:x86_64:cp312",
        "wheel:linux:x86_64:cp313",
        "wheel:linux:aarch64:cp39",
        "wheel:linux:aarch64:cp310",
        "wheel:linux:aarch64:cp311",
        "wheel:linux:aarch64:cp312",
        "wheel:linux:aarch64:cp313",
        "wheel:macos:x86_64:cp39",
        "wheel:macos:x86_64:cp310",
        "wheel:macos:x86_64:cp311",
        "wheel:macos:x86_64:cp312",
        "wheel:macos:x86_64:cp313",
        "wheel:macos:aarch64:cp39",
        "wheel:macos:aarch64:cp310",
        "wheel:macos:aarch64:cp311",
        "wheel:macos:aarch64:cp312",
        "wheel:macos:aarch64:cp313",
        "wheel:windows:x86_64:cp39",
        "wheel:windows:x86_64:cp310",
        "wheel:windows:x86_64:cp311",
        "wheel:windows:x86_64:cp312",
        "wheel:windows:x86_64:cp313",
        "sdist:source",
    ]
    assert "sdist:source" not in platform_release["evidence"]["missing_release_lane_ids"]
    rerun = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun["ready"] is True
    assert rerun["status"] == "proven_today"
    assert rerun["evidence"]["full_release_artifact_rerun_ready"] is True
    assert rerun["evidence"]["source_relevance_relevant_changed_path_count"] == 0
    assert "zero benchmark-relevant committed changes" in rerun["evidence"][
        "source_relevance_acceptance_rule"
    ]
    assert rerun["evidence"]["openpyxl_sota_speed_ready"] is True
    assert rerun["evidence"]["openpyxl_memory_ready"] is True
    assert rerun["evidence"]["openpyxl_weak_memory_case_count"] == 0
    assert rerun["evidence"]["rust_superiority_ready"] is True
    assert rerun["evidence"]["rust_memory_ready"] is True
    assert rerun["evidence"]["rust_weak_case_count"] == 0
    assert rerun["evidence"]["rust_memory_comparison_count"] > 0
    assert rerun["evidence"]["rust_weak_memory_case_count"] == 0
    assert rerun["blocker"] is None
    assert "passes the OpenPyXL speed, OpenPyXL memory" in rerun["evidence"][
        "public_claim_note"
    ]
    assert "competitor speed thresholds" in rerun["evidence"]["public_claim_note"]
    install_smoke = _dimension(report, "release_artifact_install_smoke")
    assert install_smoke["status"] == "proven_today"
    assert install_smoke["reason"] is None
    assert install_smoke["blocker"] is None
    assert install_smoke["next_action"] is None
    assert install_smoke["evidence"]["source_relevance_ready"] is True
    assert install_smoke["evidence"]["source_relevance_blockers"] == []
    benchmark_smoke = _dimension(report, "release_artifact_benchmark_smoke")
    assert benchmark_smoke["status"] == "proven_today"
    assert benchmark_smoke["reason"] is None
    assert benchmark_smoke["blocker"] is None
    assert benchmark_smoke["next_action"] is None
    assert benchmark_smoke["evidence"]["source_relevance_ready"] is True
    assert benchmark_smoke["evidence"]["source_relevance_blockers"] == []
    assert any("future Excel surfaces" in blocker for blocker in report["blockers"])


def test_public_claim_dimensions_blocks_when_rust_version_missing(tmp_path: Path) -> None:
    sota_report = _write_sota_report(tmp_path)
    payload = json.loads(sota_report.read_text(encoding="utf-8"))
    del payload["rust_competitors"]["competitor_versions"]["calamine"]
    sota_report.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=sota_report,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert "rust_and_rust_backed_competitors" in report["not_proven"]
    assert report["rust_competitor_summary"]["ready"] is False
    assert "calamine" in report["rust_competitor_summary"]["missing_version_competitors"]


def test_release_artifact_platform_falls_back_to_benchmark_metadata() -> None:
    assert (
        audit._release_artifact_platform(
            {"openpyxl_benchmark_summary": {"metadata": {"platform": "fixture-platform"}}}
        )
        == "fixture-platform"
    )


def test_expected_broad_claim_boundary_gaps_catch_missing_boundary() -> None:
    report = audit.audit_claim_dimensions()
    dimensions = [
        row
        for row in report["dimensions"]
        if row["id"] != "future_real_world_excel_surfaces"
    ]

    gaps = audit._expected_broad_claim_boundary_gaps(dimensions)

    assert gaps == [
        {
            "id": "future_real_world_excel_surfaces",
            "issues": ["dimension is missing"],
        }
    ]


def test_expected_broad_claim_boundary_gaps_catch_misclassified_boundary() -> None:
    report = audit.audit_claim_dimensions()
    dimensions = [dict(row) for row in report["dimensions"]]
    for row in dimensions:
        if row["id"] == "ecosystem_maturity_and_long_tail_workflows":
            row["ready"] = True
            row["blocks_broad_claim"] = False
            row["status"] = "proven_today"
            row["blocker"] = None

    gaps = audit._expected_broad_claim_boundary_gaps(dimensions)

    assert gaps == [
        {
            "id": "ecosystem_maturity_and_long_tail_workflows",
            "issues": [
                "dimension is marked ready",
                "dimension does not block broad claim",
                "dimension status is 'proven_today', expected one of ['known_limitation']",
                "dimension has no blocker explanation",
            ],
        }
    ]


def test_cross_platform_release_artifact_coverage_uses_lane_audit(
    tmp_path: Path,
) -> None:
    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(
            tmp_path,
            ready=True,
        ),
        release_artifact_coverage=_write_release_artifact_coverage(tmp_path),
        release_artifact_proof_workflow=_write_release_artifact_proof_workflow(tmp_path),
        release_artifact_trigger_readiness=_write_release_artifact_trigger_readiness(
            tmp_path
        ),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    platform_release = _dimension(report, "cross_platform_release_artifact_coverage")
    assert platform_release["ready"] is False
    assert platform_release["status"] == "promising_but_not_fully_proven"
    assert platform_release["evidence"]["coverage_ready"] is False
    assert platform_release["evidence"]["expected_release_lane_count"] == 4
    assert platform_release["evidence"]["proven_release_lane_count"] == 2
    assert platform_release["evidence"]["missing_release_lane_count"] == 2
    assert platform_release["evidence"]["proven_release_lane_ids"] == [
        "wheel:linux:x86_64:cp39",
        "wheel:macos:aarch64:cp39",
    ]
    assert platform_release["evidence"]["missing_release_lane_ids"] == [
        "wheel:windows:x86_64:cp39",
        "sdist:source",
    ]
    assert platform_release["evidence"]["proof_workflow_ready"] is True
    assert platform_release["evidence"]["proof_workflow_planned_lane_count"] == 2
    assert platform_release["evidence"]["proof_workflow_missing_not_planned_count"] == 0
    assert platform_release["evidence"]["proof_workflow_planned_not_missing_count"] == 0
    assert platform_release["evidence"]["proof_workflow_duplicate_lane_count"] == 0
    assert platform_release["evidence"]["trigger_readiness_ready"] is True
    assert platform_release["evidence"]["trigger_readiness_mode"] == "branch_push"
    assert (
        platform_release["evidence"]["trigger_readiness_workflow_on_default_branch"]
        is False
    )
    assert platform_release["evidence"]["trigger_readiness_branch_push_ready_now"] is True
    assert (
        platform_release["evidence"]["trigger_readiness_manual_dispatch_ready_now"]
        is False
    )
    assert platform_release["reason"] == platform_release["blocker"]
    assert "missing lanes" in platform_release["next_action"]


def test_public_claim_dimensions_blocks_when_rust_case_family_missing(
    tmp_path: Path,
) -> None:
    sota_report = _write_sota_report(tmp_path)
    payload = json.loads(sota_report.read_text(encoding="utf-8"))
    payload["rust_competitors"]["missing_required_case_family_count"] = 1
    payload["rust_competitors"]["missing_required_case_families"] = ["read_formula"]
    sota_report.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=sota_report,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert rust["evidence"]["missing_required_case_family_count"] == 1
    assert "rust_and_rust_backed_competitors" in report["not_proven"]


def test_public_claim_dimensions_blocks_when_competitor_set_case_family_missing(
    tmp_path: Path,
) -> None:
    sota_report = _write_sota_report(tmp_path)
    payload = json.loads(sota_report.read_text(encoding="utf-8"))
    payload["rust_competitor_set"]["missing_required_case_family_count"] = 1
    payload["rust_competitor_set"]["missing_required_case_families"] = ["modify"]
    sota_report.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=sota_report,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert rust["evidence"]["competitor_set_missing_required_case_family_count"] == 1
    assert "rust_and_rust_backed_competitors" in report["not_proven"]


def test_public_claim_dimensions_blocks_when_competitor_set_benchmark_missing(
    tmp_path: Path,
) -> None:
    sota_report = _write_sota_report(tmp_path)
    payload = json.loads(sota_report.read_text(encoding="utf-8"))
    payload["rust_competitor_set"]["benchmark_competitors"].remove("fastexcel")
    payload["rust_competitor_set"]["missing_from_benchmark"] = ["fastexcel"]
    sota_report.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=sota_report,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert rust["evidence"]["competitor_set_missing_from_benchmark"] == ["fastexcel"]
    assert "rust_and_rust_backed_competitors" in report["not_proven"]


def test_public_claim_dimensions_blocks_when_competitor_set_version_missing(
    tmp_path: Path,
) -> None:
    sota_report = _write_sota_report(tmp_path)
    payload = json.loads(sota_report.read_text(encoding="utf-8"))
    del payload["rust_competitor_set"]["benchmark_competitor_versions"][
        "python-calamine"
    ]
    payload["rust_competitor_set"]["missing_benchmark_versions"] = ["python-calamine"]
    sota_report.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=sota_report,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert rust["evidence"]["competitor_set_missing_benchmark_versions"] == [
        "python-calamine"
    ]
    assert "rust_and_rust_backed_competitors" in report["not_proven"]


def test_public_claim_dimensions_blocks_when_competitor_set_report_stale(
    tmp_path: Path,
) -> None:
    sota_report = _write_sota_report(tmp_path)
    payload = json.loads(sota_report.read_text(encoding="utf-8"))
    payload["rust_competitor_set"]["report_fresh"] = False
    payload["rust_competitor_set"]["freshness_blockers"] = [
        "Rust competitor set audit is stale"
    ]
    sota_report.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=sota_report,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert rust["evidence"]["competitor_set_report_fresh"] is False
    assert rust["evidence"]["competitor_set_freshness_blockers"] == [
        "Rust competitor set audit is stale"
    ]
    assert "rust_and_rust_backed_competitors" in report["not_proven"]


def test_public_claim_dimensions_blocks_when_competitor_set_discovery_unclassified(
    tmp_path: Path,
) -> None:
    sota_report = _write_sota_report(tmp_path)
    payload = json.loads(sota_report.read_text(encoding="utf-8"))
    payload["rust_competitor_set"]["unclassified_discovery_hit_count"] = 1
    sota_report.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=sota_report,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert rust["evidence"]["competitor_set_unclassified_discovery_hit_count"] == 1
    assert "rust_and_rust_backed_competitors" in report["not_proven"]


def test_public_claim_dimensions_blocks_when_watchlist_adoption_evidence_missing(
    tmp_path: Path,
) -> None:
    sota_report = _write_sota_report(tmp_path)
    payload = json.loads(sota_report.read_text(encoding="utf-8"))
    payload["rust_competitor_set"]["watchlist_promotion_adoption_complete"] = False
    payload["rust_competitor_set"]["watchlist_promotion_adoption_missing_count"] = 1
    payload["rust_competitor_set"]["watchlist_promotion_adoption_missing"] = [
        "rustypyxl"
    ]
    payload["rust_competitor_set"]["watchlist_promotion_adoption_caveat"] = (
        "Objective watchlist promotion can be applied where registry adoption "
        "data exists; watchlist packages without adoption data remain reviewed "
        "caveats."
    )
    sota_report.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=sota_report,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert (
        rust["evidence"]["competitor_set_watchlist_promotion_adoption_complete"]
        is False
    )
    assert rust["evidence"]["competitor_set_watchlist_promotion_adoption_missing"] == [
        "rustypyxl"
    ]
    assert "rust_and_rust_backed_competitors" in report["not_proven"]
    assert any(
        item["id"] == "rust_watchlist_pypi_adoption_unmeasured"
        for item in report["rust_competitor_scope_caveats"]
    )


def test_public_claim_dimensions_blocks_missing_required_rust_alias(
    tmp_path: Path,
) -> None:
    report_path = _write_sota_report(tmp_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["rust_competitor_set"]["required_competitor_aliases"] = {}
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=report_path,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert "rust_and_rust_backed_competitors" in report["not_proven"]


def test_public_claim_dimensions_blocks_requested_competitor_name_gap(
    tmp_path: Path,
) -> None:
    report_path = _write_sota_report(tmp_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    row = payload["rust_competitor_set"]["requested_competitor_name_resolutions"][0]
    row["requirement_satisfied"] = False
    payload["rust_competitor_set"][
        "requested_competitor_name_resolution_ready"
    ] = False
    payload["rust_competitor_set"][
        "requested_competitor_name_resolution_blockers"
    ] = ["xlsxwriter-rs"]
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=report_path,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert rust["evidence"][
        "requested_competitor_name_resolution_blockers"
    ] == ["xlsxwriter-rs"]
    assert report["rust_competitor_summary"][
        "requested_competitor_names"
    ] == ["xlsxwriter-rs"]
    assert report["rust_competitor_summary"][
        "satisfied_requested_competitor_names"
    ] == []
    assert report["rust_competitor_summary"][
        "unsatisfied_requested_competitor_names"
    ] == ["xlsxwriter-rs"]
    assert "rust_and_rust_backed_competitors" in report["not_proven"]


def test_public_claim_dimensions_blocks_rust_source_relevance_gap(
    tmp_path: Path,
) -> None:
    report_path = _write_sota_report(tmp_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["rust_competitors"]["source_relevance_ready"] = False
    payload["rust_competitors"]["source_relevance_blockers"] = [
        "benchmark-relevant source changed after benchmark"
    ]
    payload["rust_competitors"]["source_relevance_dirty_relevant_paths"] = [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=report_path,
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rust = _dimension(report, "rust_and_rust_backed_competitors")
    assert rust["ready"] is False
    assert rust["blocker"] == "required Rust competitor evidence is incomplete"
    assert rust["evidence"]["source_relevance_ready"] is False
    assert rust["evidence"]["source_relevance_blockers"] == [
        "benchmark-relevant source changed after benchmark"
    ]
    assert rust["evidence"]["source_relevance_dirty_relevant_paths"] == [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    assert "rust_and_rust_backed_competitors" in report["not_proven"]


def test_public_claim_dimensions_blocks_public_claim_wording_gap(
    tmp_path: Path,
) -> None:
    public_claim = _write_public_claim_report(tmp_path)
    payload = json.loads(public_claim.read_text(encoding="utf-8"))
    payload["ready"] = False
    payload["issue_count"] = 1
    payload["issues"] = [
        {
            "path": "README.md",
            "line": 1,
            "reason": "unsupported absolute claim",
        }
    ]
    public_claim.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=public_claim,
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    public_dimension = _dimension(report, "public_claim_wording")
    assert public_dimension["ready"] is False
    assert public_dimension["evidence"]["issue_count"] == 1
    assert "public claim wording issues remain" in public_dimension["blocker"]
    assert "public_claim_wording" in report["not_proven"]


def test_public_claim_dimensions_markdown_lists_blockers(tmp_path: Path) -> None:
    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    markdown = audit.format_markdown(report)

    assert "# Public Claim Dimensions Audit" in markdown
    assert "| Supported-scope ready | false |" in markdown
    assert "| Promising but not fully proven | 3 |" in markdown
    assert "| Blocked on Excel evidence | 0 |" in markdown
    assert "| Blocked on other required evidence | 1 |" in markdown
    assert "| Known limitations | 5 |" in markdown
    assert "| Supported-scope caveats | 7 |" in markdown
    assert "| Rust competitor scope caveats | 6 |" in markdown
    assert "| Expected broad claim boundaries | 5 |" in markdown
    assert "| Expected broad claim boundary gaps | 0 |" in markdown
    assert (
        "| Expected broad claim boundary ids | all_click_level_interaction_variants, "
        "all_high_risk_render_variants, cross_platform_release_artifact_coverage, "
        "ecosystem_maturity_and_long_tail_workflows, future_real_world_excel_surfaces |"
    ) in markdown
    assert "## Input Reports" in markdown
    assert "| sota_report |" in markdown
    assert "| public_claim_report |" in markdown
    assert (
        "| installable release artifact smoke currentness | "
        "proven_today | false | none | none |"
    ) in markdown
    assert (
        "| release-artifact benchmark smoke currentness | "
        "proven_today | false | none | none |"
    ) in markdown
    assert (
        "| ecosystem maturity and long-tail workflow familiarity | known_limitation | "
        "true | openpyxl still has ecosystem maturity"
    ) in markdown
    assert "## Ecosystem Boundary Details" in markdown
    assert (
        "| unsupported_openpyxl_api | The workflow relies on an openpyxl API "
        "that is not listed as supported in the compatibility matrix. | "
        "`docs/trust/launch-claim-brief.md` |"
    ) in markdown
    assert "## Release Boundary Details" in markdown
    assert (
        "| installer_and_resolver_contexts | The current lane proof builds and "
        "smokes artifacts, but does not exhaust every pip, uv, conda-style, "
        "editable-install, cache, or dependency resolver environment a user "
        "might install through. |"
    ) in markdown
    assert "## Unbounded Boundary Details" in markdown
    assert (
        "| all_click_level_interaction_variants | prompt_and_dialog_variants | "
        "Excel prompt, repair, warning, and confirmation dialogs vary by "
        "file shape, version, tenant policy, and user action. |"
    ) in markdown
    assert (
        "| cross-platform and Python-version release artifact coverage | promising_but_not_fully_proven | "
        "true | registered release-artifact lanes are proven today"
    ) in markdown
    assert "## Rust Competitor Evidence" in markdown
    assert (
        "| xlsxwriter lane | crates.io package `xlsxwriter` 0.6.1; "
        "repository alias `xlsxwriter-rs`; separate crates.io package "
        "`xlsxwriter-rs` 0.1.0 is not the benchmarked lane |"
    ) in markdown
    assert "| Required aliases | xlsxwriter: xlsxwriter-rs |" in markdown
    assert "| Current audit competitor versions | rust_xlsxwriter 0.95.0" in markdown
    assert "| Competitor-set report | docs/performance/baselines/rust.json |" in markdown
    assert "| Competitor-set versions | rust_xlsxwriter 0.95.0" in markdown
    assert "| Missing required case families | 0 |" in markdown
    assert "| Competitor-set missing required case families | 0 |" in markdown
    assert "| Competitor-set missing benchmark competitors | none |" in markdown
    assert "| Competitor-set missing benchmark versions | none |" in markdown
    assert "| Competitor-set unclassified discovery hits | 0 |" in markdown
    assert "| Competitor-set unclassified low-adoption relevant hits | 1 |" in markdown
    assert "| Requested competitor name resolution ready | true |" in markdown
    assert (
        "| xlsxwriter-rs | watchlist | 0.1.0 | remain_watchlist | "
        "xlsxwriter | 0.6.1 | true |"
    ) in markdown
    assert "## Rust Below-Threshold Discovery Hits" in markdown
    assert (
        "| tiny-ooxml | ooxml | 7 | 0.0.1 | 12 | 3 | "
        "relevant discovery hit, but below the review/adoption threshold |"
    ) in markdown
    assert "## Supported-Scope Caveats" in markdown
    assert "pivot cache records after layout edits" in markdown
    assert "pivot table styling beyond PivotArea and pivot-CF" in markdown
    assert "external-link cached data is not dereferenced" in markdown
    assert "native writer rich-feature pytest marker wording" not in markdown
    assert "## Rust Competitor Scope Caveats" in markdown
    assert "Rust competitor case families are bounded" in markdown
    assert "Rust competitor gate uses same-surface rows when available" in markdown
    assert "Rust memory result is benchmark-path specific" in markdown
    assert "PyPI Rust-backed discovery is bounded" in markdown
    assert "## Python Public API vs Direct Rust" in markdown
    assert "| Public cross-surface weak cases | 4 |" in markdown
    assert "| Claim basis counts | direct_rust_same_surface=4, public_api=2 |" in markdown
    assert "## Rust Memory Evidence" in markdown
    assert "| Current audit Rust memory comparison rows | 0 |" in markdown
    assert "| Release-artifact Rust memory comparison rows | 0 |" in markdown
    assert "literal better-in-every-dimension claim" in markdown
    assert "## Release Artifact Evidence" in markdown
    assert "| Full release-artifact rerun ready | false |" in markdown
    assert "| Wheel metadata ready | true |" in markdown
    assert f"| Wheel SHA-256 | {'c' * 64} |" in markdown
    assert "| Wheel size bytes | 1234 |" in markdown
    assert "| Source git dirty | false |" in markdown
    assert "| Report repo git SHA | report123 |" in markdown
    assert "| Report repo git dirty | false |" in markdown
    assert "| Generator script source | fixture generator |" in markdown
    assert "| OpenPyXL speed ready | true |" in markdown
    assert "| OpenPyXL memory ready | true |" in markdown
    assert "| OpenPyXL weak memory cases | 0 |" in markdown
    assert "| Rust memory ready | false |" in markdown
    assert "| Rust memory comparison rows | 0 |" in markdown
    assert "| Rust weak memory rows | 0 |" in markdown
    assert "| Rust skipped required competitors | none |" in markdown
    assert (
        "fresh release-artifact benchmark rerun found: Rust competitor threshold miss"
        in markdown
    )
    assert "Rust competitor memory threshold miss" in markdown


def test_public_claim_dimensions_blocks_incomplete_benchmark_smoke(tmp_path: Path) -> None:
    benchmark_smoke = _write_release_artifact_benchmark_smoke(tmp_path)
    payload = json.loads(benchmark_smoke.read_text(encoding="utf-8"))
    del payload["rust_benchmark_summary"]["competitor_versions"]["fastexcel"]
    payload["rust_benchmark_summary"]["missing_version_competitors"] = ["fastexcel"]
    benchmark_smoke.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=benchmark_smoke,
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    benchmark = _dimension(report, "release_artifact_benchmark_smoke")
    assert benchmark["ready"] is False
    assert "Rust competitor version missing from smoke" in benchmark["blocker"]
    assert "required Rust competitor versions incomplete in smoke" in benchmark["blocker"]
    assert "release_artifact_benchmark_smoke" in report["not_proven"]


def test_public_claim_dimensions_names_install_smoke_failures(tmp_path: Path) -> None:
    smoke = _write_release_artifact_smoke(tmp_path)
    payload = json.loads(smoke.read_text(encoding="utf-8"))
    payload["source_git_dirty"] = True
    payload["venv_smoke"]["openpyxl_read_modified_a2"] = "old"
    smoke.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=smoke,
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    install = _dimension(report, "release_artifact_install_smoke")
    assert install["ready"] is False
    assert "source worktree was dirty" in install["blocker"]
    assert "OpenPyXL did not read the modified cell" in install["blocker"]
    assert install["evidence"]["source_git_dirty"] is True
    assert install["evidence"]["openpyxl_read_modified_a2"] == "old"
    assert "release_artifact_install_smoke" in report["not_proven"]


def test_public_claim_dimensions_blocks_install_smoke_source_relevance_gap(
    tmp_path: Path,
) -> None:
    smoke = _write_release_artifact_smoke(tmp_path)
    payload = json.loads(smoke.read_text(encoding="utf-8"))
    payload["source_relevance_ready"] = False
    payload["source_relevance_status"] = "blocked"
    payload["source_relevance_blockers"] = [
        "release-artifact install smoke has benchmark-relevant source changes"
    ]
    payload["source_relevance_dirty_relevant_paths"] = [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    smoke.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=smoke,
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    install = _dimension(report, "release_artifact_install_smoke")
    assert install["ready"] is False
    assert "benchmark-relevant source changes" in install["blocker"]
    assert install["evidence"]["source_relevance_ready"] is False
    assert install["evidence"]["source_relevance_dirty_relevant_paths"] == [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    assert "release_artifact_install_smoke" in report["not_proven"]


def test_public_claim_dimensions_names_benchmark_smoke_openpyxl_failures(
    tmp_path: Path,
) -> None:
    benchmark_smoke = _write_release_artifact_benchmark_smoke(tmp_path)
    payload = json.loads(benchmark_smoke.read_text(encoding="utf-8"))
    payload["openpyxl_benchmark_summary"]["comparison_count"] = 0
    payload["openpyxl_benchmark_summary"]["weak_case_count"] = 1
    benchmark_smoke.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=benchmark_smoke,
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    benchmark = _dimension(report, "release_artifact_benchmark_smoke")
    assert benchmark["ready"] is False
    assert "OpenPyXL comparison rows missing" in benchmark["blocker"]
    assert "OpenPyXL weak smoke cases present" in benchmark["blocker"]
    assert benchmark["evidence"]["openpyxl_comparison_count"] == 0
    assert benchmark["evidence"]["openpyxl_weak_case_count"] == 1
    assert "release_artifact_benchmark_smoke" in report["not_proven"]


def test_public_claim_dimensions_blocks_benchmark_smoke_source_relevance_gap(
    tmp_path: Path,
) -> None:
    benchmark_smoke = _write_release_artifact_benchmark_smoke(tmp_path)
    payload = json.loads(benchmark_smoke.read_text(encoding="utf-8"))
    payload["source_relevance_ready"] = False
    payload["source_relevance_status"] = "blocked"
    payload["source_relevance_blockers"] = [
        "release-artifact benchmark smoke has benchmark-relevant source changes"
    ]
    payload["source_relevance_dirty_relevant_paths"] = [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    benchmark_smoke.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=benchmark_smoke,
        release_artifact_benchmark_rerun=_write_release_artifact_benchmark_rerun(tmp_path),
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    benchmark = _dimension(report, "release_artifact_benchmark_smoke")
    assert benchmark["ready"] is False
    assert "benchmark-relevant source changes" in benchmark["blocker"]
    assert benchmark["evidence"]["source_relevance_ready"] is False
    assert benchmark["evidence"]["source_relevance_dirty_relevant_paths"] == [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    assert "release_artifact_benchmark_smoke" in report["not_proven"]


def test_public_claim_dimensions_blocks_dirty_release_artifact_rerun(
    tmp_path: Path,
) -> None:
    rerun = _write_release_artifact_benchmark_rerun(tmp_path, ready=True)
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    payload["source_git_dirty"] = True
    rerun.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=rerun,
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rerun_dimension = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun_dimension["ready"] is False
    assert "source worktree was dirty" in rerun_dimension["blocker"]
    assert rerun_dimension["evidence"]["source_git_dirty"] is True
    assert "release_artifact_benchmark_rerun" in report["not_proven"]


def test_public_claim_dimensions_blocks_dirty_release_report_generator(
    tmp_path: Path,
) -> None:
    rerun = _write_release_artifact_benchmark_rerun(tmp_path, ready=True)
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    payload["report_repo_git_dirty"] = True
    rerun.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=rerun,
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rerun_dimension = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun_dimension["ready"] is False
    assert "report generator worktree was dirty" in rerun_dimension["blocker"]
    assert rerun_dimension["evidence"]["report_repo_git_dirty"] is True
    assert "release_artifact_benchmark_rerun" in report["not_proven"]


def test_public_claim_dimensions_blocks_release_source_relevance_gap(
    tmp_path: Path,
) -> None:
    rerun = _write_release_artifact_benchmark_rerun(tmp_path, ready=True)
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    payload["source_relevance_ready"] = False
    payload["source_relevance_status"] = "blocked"
    payload["source_relevance_blockers"] = [
        "release-artifact benchmark rerun has benchmark-relevant source changes"
    ]
    payload["source_relevance_dirty_relevant_paths"] = [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    rerun.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=rerun,
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rerun_dimension = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun_dimension["ready"] is False
    assert "benchmark-relevant source changes" in rerun_dimension["blocker"]
    assert rerun_dimension["evidence"]["source_relevance_ready"] is False
    assert rerun_dimension["evidence"]["source_relevance_dirty_relevant_paths"] == [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    assert "release_artifact_benchmark_rerun" in report["not_proven"]


def test_public_claim_dimensions_blocks_release_rerun_missing_rust_version(
    tmp_path: Path,
) -> None:
    rerun = _write_release_artifact_benchmark_rerun(tmp_path, ready=True)
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    del payload["rust_benchmark_summary"]["competitor_versions"]["calamine"]
    payload["rust_benchmark_summary"]["missing_version_competitors"] = ["calamine"]
    rerun.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=rerun,
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rerun_dimension = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun_dimension["ready"] is False
    assert "Rust competitor version missing from rerun" in rerun_dimension["blocker"]
    assert rerun_dimension["evidence"]["rust_missing_version_competitors"] == [
        "calamine"
    ]
    assert "release_artifact_benchmark_rerun" in report["not_proven"]


def test_public_claim_dimensions_blocks_release_rerun_skipped_required_rust(
    tmp_path: Path,
) -> None:
    rerun = _write_release_artifact_benchmark_rerun(tmp_path, ready=True)
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    payload["rust_benchmark_summary"]["skipped_required_competitors"] = [
        "rust_xlsxwriter"
    ]
    rerun.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=rerun,
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rerun_dimension = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun_dimension["ready"] is False
    assert "required Rust competitor skipped in rerun" in rerun_dimension["blocker"]
    assert rerun_dimension["evidence"]["rust_skipped_required_competitors"] == [
        "rust_xlsxwriter"
    ]
    assert "release_artifact_benchmark_rerun" in report["not_proven"]


def test_public_claim_dimensions_blocks_release_rerun_missing_wheel_metadata(
    tmp_path: Path,
) -> None:
    rerun = _write_release_artifact_benchmark_rerun(tmp_path, ready=True)
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    del payload["wheel"]["sha256"]
    rerun.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=rerun,
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rerun_dimension = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun_dimension["ready"] is False
    assert "wheel metadata incomplete" in rerun_dimension["blocker"]
    assert rerun_dimension["evidence"]["wheel_metadata_ready"] is False
    assert "release_artifact_benchmark_rerun" in report["not_proven"]


def test_public_claim_dimensions_names_release_rerun_openpyxl_weak_cases(
    tmp_path: Path,
) -> None:
    rerun = _write_release_artifact_benchmark_rerun(tmp_path, ready=True)
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    payload["openpyxl_benchmark_summary"]["weak_sota_case_count"] = 1
    payload["openpyxl_benchmark_summary"]["weak_memory_case_count"] = 1
    rerun.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=rerun,
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rerun_dimension = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun_dimension["ready"] is False
    assert "OpenPyXL weak speed cases present" in rerun_dimension["blocker"]
    assert "OpenPyXL weak memory cases present" in rerun_dimension["blocker"]
    assert rerun_dimension["evidence"]["openpyxl_weak_sota_case_count"] == 1
    assert rerun_dimension["evidence"]["openpyxl_weak_memory_case_count"] == 1
    assert "release_artifact_benchmark_rerun" in report["not_proven"]


def test_public_claim_dimensions_names_release_rerun_rust_weak_cases(
    tmp_path: Path,
) -> None:
    rerun = _write_release_artifact_benchmark_rerun(tmp_path, ready=True)
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    payload["rust_benchmark_summary"]["weak_case_count"] = 1
    rerun.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=rerun,
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rerun_dimension = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun_dimension["ready"] is False
    assert "Rust weak cases present" in rerun_dimension["blocker"]
    assert rerun_dimension["evidence"]["rust_weak_case_count"] == 1
    assert "release_artifact_benchmark_rerun" in report["not_proven"]


def test_public_claim_dimensions_blocks_release_rerun_missing_rust_memory(
    tmp_path: Path,
) -> None:
    rerun = _write_release_artifact_benchmark_rerun(tmp_path, ready=True)
    payload = json.loads(rerun.read_text(encoding="utf-8"))
    payload["rust_memory_ready"] = False
    payload["rust_benchmark_summary"]["memory_comparison_count"] = 0
    payload["rust_benchmark_summary"]["weak_memory_case_count"] = 0
    rerun.write_text(json.dumps(payload), encoding="utf-8")

    report = audit.audit_claim_dimensions(
        sota_report=_write_sota_report(tmp_path),
        public_claim_report=_write_public_claim_report(tmp_path),
        release_artifact_smoke=_write_release_artifact_smoke(tmp_path),
        release_artifact_benchmark_smoke=_write_release_artifact_benchmark_smoke(tmp_path),
        release_artifact_benchmark_rerun=rerun,
        proof_flow_report=_write_proof_flow_report(tmp_path),
    )

    rerun_dimension = _dimension(report, "release_artifact_benchmark_rerun")
    assert rerun_dimension["ready"] is False
    assert "Rust competitor memory threshold miss" in rerun_dimension["blocker"]
    assert "Rust memory comparison rows missing" in rerun_dimension["blocker"]
    assert rerun_dimension["evidence"]["rust_memory_ready"] is False
    assert rerun_dimension["evidence"]["rust_memory_comparison_count"] == 0
    assert "release_artifact_benchmark_rerun" in report["not_proven"]


def _dimension(report: dict, id: str) -> dict:
    return next(item for item in report["dimensions"] if item["id"] == id)


def _write_sota_report(tmp_path: Path) -> Path:
    path = tmp_path / "sota.json"
    path.write_text(
        json.dumps(
            {
                "claim_gates": {
                    "api_compat_gate_ready": True,
                    "current_fidelity_gate_ready": True,
                    "openpyxl_performance_gate_ready": True,
                    "rust_competitor_gate_ready": True,
                    "finite_evidence_frontiers_ready": True,
                },
                "compat": {
                    "compat_spec_gap_count": 0,
                    "surface_known_gap_count": 0,
                    "out_of_scope_openpyxl_advantage_count": 0,
                    "status_totals": {"supported": 76, "out_of_scope": 7},
                },
                "performance": {
                    "comparison_count": 4,
                    "min_observed_speedup": 2.5,
                    "weak_case_count": 0,
                    "weak_memory_case_count": 0,
                    "max_observed_memory_ratio": 0.9,
                    "benchmark": "docs/performance/baselines/example.json",
                },
                "rust_competitors": {
                    "competitor_versions": {
                        "rust_xlsxwriter": "0.95.0",
                        "xlsxwriter": "0.6.1",
                        "calamine": "0.35.0",
                        "umya-spreadsheet": "2.3.3",
                        "fastexcel": "0.20.2",
                        "python-calamine": "0.6.2",
                    },
                    "missing_competitors": [],
                    "missing_version_competitors": [],
                    "missing_required_case_family_count": 0,
                    "missing_required_case_families": [],
                    "raw_public_comparison_count": 6,
                    "same_surface_direct_comparison_count": 4,
                    "public_rows_replaced_by_same_surface_count": 6,
                    "claim_basis_counts": {
                        "direct_rust_same_surface": 4,
                        "public_api": 2,
                    },
                    "public_rows_replaced_by_same_surface": [
                        {
                            "competitor": "calamine",
                            "case": "read_formula_text",
                            "speedup_vs_competitor": 0.75,
                            "wolfxl_api_surface": "python_public_api",
                            "competitor_api_surface": "direct_rust_api",
                        },
                        {
                            "competitor": "calamine",
                            "case": "read_values_plain",
                            "speedup_vs_competitor": 0.8,
                            "wolfxl_api_surface": "python_public_api",
                            "competitor_api_surface": "direct_rust_api",
                        },
                        {
                            "competitor": "rust_xlsxwriter",
                            "case": "write_formula_cells",
                            "speedup_vs_competitor": 1.16,
                            "wolfxl_api_surface": "python_public_api",
                            "competitor_api_surface": "direct_rust_api",
                        },
                        {
                            "competitor": "rust_xlsxwriter",
                            "case": "write_multi_sheet_plain",
                            "speedup_vs_competitor": 0.9,
                            "wolfxl_api_surface": "python_public_api",
                            "competitor_api_surface": "direct_rust_api",
                        },
                        {
                            "competitor": "rust_xlsxwriter",
                            "case": "write_styled_cells",
                            "speedup_vs_competitor": 0.26,
                            "wolfxl_api_surface": "python_public_api",
                            "competitor_api_surface": "direct_rust_api",
                        },
                        {
                            "competitor": "xlsxwriter",
                            "case": "write_formula_cells",
                            "speedup_vs_competitor": 2.02,
                            "wolfxl_api_surface": "python_public_api",
                            "competitor_api_surface": "direct_rust_api",
                        },
                    ],
                },
                "rust_watchlist": {
                    "min_observed_speedup": 2.4,
                    "memory_comparison_count": 1,
                    "max_observed_memory_ratio": 0.8,
                    "weak_memory_case_count": 0,
                    "near_parity_memory_case_count": 0,
                },
                "rust_competitor_set": {
                    "main_rust_competitor_set_ready": True,
                    "benchmark_present": True,
                    "report_present": True,
                    "report": "docs/performance/baselines/rust.json",
                    "report_fresh": True,
                    "portable_report_path": True,
                    "registry_metadata_fetched": True,
                    "crates_io_discovery_fetched": True,
                    "required_competitors": [
                        "rust_xlsxwriter",
                        "xlsxwriter",
                        "calamine",
                        "umya-spreadsheet",
                        "fastexcel",
                        "python-calamine",
                    ],
                    "benchmark_competitors": [
                        "calamine",
                        "fastexcel",
                        "python-calamine",
                        "rust_xlsxwriter",
                        "umya-spreadsheet",
                        "xlsxwriter",
                    ],
                    "report_required_competitors": [
                        "rust_xlsxwriter",
                        "xlsxwriter",
                        "calamine",
                        "umya-spreadsheet",
                        "fastexcel",
                        "python-calamine",
                    ],
                    "required_competitor_aliases": {
                        "xlsxwriter": ["xlsxwriter-rs"]
                    },
                    "benchmark_competitor_versions": {
                        "rust_xlsxwriter": "0.95.0",
                        "xlsxwriter": "0.6.1",
                        "calamine": "0.35.0",
                        "umya-spreadsheet": "2.3.3",
                        "fastexcel": "0.20.2",
                        "python-calamine": "0.6.2",
                    },
                    "missing_from_benchmark": [],
                    "missing_benchmark_versions": [],
                    "stale_benchmark_versions": [],
                    "missing_required_from_report": [],
                    "missing_required_version_evidence": [],
                    "missing_required_case_family_count": 0,
                    "missing_required_case_families": [],
                    "blockers": [],
                    "freshness_blockers": [],
                    "discovery_error_queries": [],
                    "unclassified_discovery_hit_count": 0,
                    "pypi_discovery_fetched": True,
                    "pypi_discovery_error_queries": [],
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
                            "exact_package_related_required_competitors": [
                                "xlsxwriter"
                            ],
                            "exact_package_reviewed": True,
                            "requirement_satisfied": True,
                        }
                    ],
                    "requested_competitor_name_resolution_count": 1,
                    "requested_competitor_name_resolution_ready": True,
                    "requested_competitor_name_resolution_blockers": [],
                },
                "inputs": {
                    "max_memory_ratio": 1.0,
                    "memory_noise_tolerance_bytes": 3145728,
                },
                "evidence": {
                    "bundle_ready": True,
                    "bundle_issue_count": 0,
                    "current_supported_claim_ready": True,
                    "finite_evidence_frontiers_ready": True,
                    "finite_evidence_frontier_blocker_ids": [],
                    "missing_requirement_ids": [
                        "feature_specific_intentional_render_equivalence",
                        "broader_click_level_interaction_variants",
                        "future_surface_exhaustiveness",
                    ],
                    "unbounded_claim_boundary_ids": [
                        "feature_specific_intentional_render_equivalence",
                        "broader_click_level_interaction_variants",
                        "future_surface_exhaustiveness",
                    ],
                    "missing_requirements": [
                        {
                            "id": "feature_specific_intentional_render_equivalence",
                            "status": "open",
                            "reason": "render variants remain open-ended",
                        },
                        {
                            "id": "future_surface_exhaustiveness",
                            "status": "open",
                            "reason": "future surfaces remain open-ended",
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_public_claim_report(tmp_path: Path) -> Path:
    path = tmp_path / "public-claim.json"
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "issue_count": 0,
                "scanned_files": ["README.md"],
                "scanned_context_files": ["docs/trust/public-evidence.md"],
            }
        ),
        encoding="utf-8",
    )
    return path


def _source_relevance_fields() -> dict[str, object]:
    return {
        "source_relevance_ready": True,
        "source_relevance_status": "fixture_checked",
        "source_relevance_base_git_commit": "abc123",
        "source_relevance_current_git_commit": "abc123",
        "source_relevance_changed_path_count": 0,
        "source_relevance_relevant_changed_path_count": 0,
        "source_relevance_relevant_changed_paths": [],
        "source_relevance_dirty_relevant_paths": [],
        "source_relevance_blockers": [],
    }


def _write_release_artifact_smoke(tmp_path: Path) -> Path:
    path = tmp_path / "release-artifact-smoke.json"
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "source_git_sha": "abc123",
                "source_git_dirty": False,
                "report_repo_git_sha": "report123",
                "report_repo_git_dirty": False,
                "generator_script_source": "fixture generator",
                **_source_relevance_fields(),
                "wheel": {
                    "filename": "wolfxl-2.0.0-cp312-cp312-macosx_11_0_arm64.whl",
                    "metadata_name": "wolfxl",
                    "metadata_version": "2.0.0",
                    "sha256": "a" * 64,
                    "size_bytes": 1234,
                    "wheel_tag": "cp312-cp312-macosx_11_0_arm64",
                },
                "venv_smoke": {
                    "wolfxl_version": "2.0.0",
                    "openpyxl_version": "3.1.5",
                    "write_workbook_exists": True,
                    "modified_workbook_exists": True,
                    "required_zip_parts_present": True,
                    "openpyxl_read_modified_a2": "modified",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_release_artifact_benchmark_smoke(tmp_path: Path) -> Path:
    path = tmp_path / "release-artifact-benchmark-smoke.json"
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "source_git_sha": "abc123",
                "source_git_dirty": False,
                "report_repo_git_sha": "report123",
                "report_repo_git_dirty": False,
                "generator_script_source": "fixture generator",
                **_source_relevance_fields(),
                "wheel": {
                    "filename": "wolfxl-2.0.0-cp312-cp312-macosx_11_0_arm64.whl",
                    "metadata_name": "wolfxl",
                    "metadata_version": "2.0.0",
                    "sha256": "b" * 64,
                    "size_bytes": 1234,
                    "wheel_tag": "cp312-cp312-macosx_11_0_arm64",
                },
                "parameters": {
                    "rows": 500,
                    "cols": 5,
                    "rounds": 3,
                },
                "openpyxl_benchmark_summary": {
                    "comparison_count": 3,
                    "min_observed_speedup": 1.5,
                    "weak_case_count": 0,
                },
                "rust_benchmark_summary": {
                    "comparison_count": 14,
                    "min_observed_speedup": 0.5,
                    "weak_case_count": 4,
                    "missing_competitors": [],
                    "missing_version_competitors": [],
                    "skipped_required_competitors": [],
                    "competitor_versions": {
                        "rust_xlsxwriter": "0.95.0",
                        "xlsxwriter": "0.6.1",
                        "calamine": "0.35.0",
                        "umya-spreadsheet": "2.3.3",
                        "fastexcel": "0.20.2",
                        "python-calamine": "0.6.2",
                    },
                },
                "broad_speed_superiority_ready": False,
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_release_artifact_benchmark_rerun(
    tmp_path: Path,
    *,
    ready: bool = False,
) -> Path:
    path = tmp_path / "release-artifact-benchmark-rerun.json"
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "full_release_artifact_rerun_ready": ready,
                "openpyxl_sota_speed_ready": True,
                "openpyxl_memory_ready": True,
                "rust_superiority_ready": ready,
                "rust_memory_ready": ready,
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
                    "min_observed_speedup": 2.5,
                    "weak_sota_case_count": 0,
                    "memory_comparison_count": 8,
                    "max_observed_memory_ratio": 0.95,
                    "weak_memory_case_count": 0,
                },
                "rust_benchmark_summary": {
                    "comparison_count": 14,
                    "min_observed_speedup": 1.2 if ready else 0.8,
                    "weak_case_count": 0 if ready else 1,
                    "memory_comparison_count": 16 if ready else 0,
                    "max_observed_memory_ratio": 0.95 if ready else None,
                    "weak_memory_case_count": 0,
                    "missing_competitors": [],
                    "missing_version_competitors": [],
                    "skipped_required_competitors": [],
                    "competitor_versions": {
                        "rust_xlsxwriter": "0.95.0",
                        "xlsxwriter": "0.6.1",
                        "calamine": "0.35.0",
                        "umya-spreadsheet": "2.3.3",
                        "fastexcel": "0.20.2",
                        "python-calamine": "0.6.2",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_release_artifact_coverage(tmp_path: Path) -> Path:
    path = tmp_path / "release-artifact-coverage.json"
    path.write_text(
        json.dumps(
            {
                "ready": False,
                "coverage_ready": False,
                "audit_ready": True,
                "expected_lane_count": 4,
                "proven_lane_count": 2,
                "missing_lane_count": 2,
                "proven_lanes": [
                    {
                        "id": "wheel:linux:x86_64:cp39",
                        "artifact_type": "wheel",
                        "os": "linux",
                        "arch": "x86_64",
                        "python": "3.9",
                        "abi": "cp39",
                    },
                    {
                        "id": "wheel:macos:aarch64:cp39",
                        "artifact_type": "wheel",
                        "os": "macos",
                        "arch": "aarch64",
                        "python": "3.9",
                        "abi": "cp39",
                    },
                ],
                "missing_lanes": [
                    {
                        "id": "wheel:windows:x86_64:cp39",
                        "artifact_type": "wheel",
                        "os": "windows",
                        "arch": "x86_64",
                        "python": "3.9",
                        "abi": "cp39",
                    },
                    {
                        "id": "sdist:source",
                        "artifact_type": "sdist",
                        "os": "source",
                        "arch": "source",
                        "python": "any",
                        "abi": "source",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_release_artifact_proof_workflow(tmp_path: Path) -> Path:
    path = tmp_path / "release-artifact-proof-workflow.json"
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "current_missing_lane_count": 2,
                "planned_lane_count": 2,
                "missing_not_planned_count": 0,
                "planned_not_missing_count": 0,
                "duplicate_lane_count": 0,
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_release_artifact_trigger_readiness(tmp_path: Path) -> Path:
    path = tmp_path / "release-artifact-trigger-readiness.json"
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "trigger_mode": "branch_push",
                "workflow_on_default_branch": False,
                "branch_push_ready_now": True,
                "manual_dispatch_ready_now": False,
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
                "headless_work_available": False,
            }
        ),
        encoding="utf-8",
    )
    return path
