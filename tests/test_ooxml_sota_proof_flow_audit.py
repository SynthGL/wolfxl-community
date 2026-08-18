from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "audit_ooxml_sota_proof_flow.py"
    spec = importlib.util.spec_from_file_location("audit_ooxml_sota_proof_flow", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_default_rust_inputs_point_at_current_green_evidence() -> None:
    assert (
        audit.DEFAULT_RUST_BENCHMARK.name
        == "2026-06-10-required-rust-10k-with-memory-clean.json"
    )
    assert (
        audit.DEFAULT_RUST_COMPETITOR_SET_REPORT.name
        == "2026-06-05-rust-competitor-set-live-recheck.json"
    )


def test_proof_flow_reports_first_excel_batch_phase(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=False)
    worker_status = _write_worker_status(tmp_path, clean_preflights=True)
    worker_dispatch = _write_worker_dispatch_board(tmp_path)
    handoff_report = _write_subagent_handoff_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=False),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_status=worker_status,
        worker_dispatch_board=worker_dispatch,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
        subagent_handoff_report=handoff_report,
    )

    assert report["ready"] is False
    assert report["current_phase"] == "phase_1_excel_batch"
    assert report["worker_readiness"]["all_preflights_clean"] is True
    assert report["worker_readiness"]["clean_preflight_status_report_count"] == 2
    assert report["worker_readiness"]["missing_execute_status_report_count"] == 2
    assert report["worker_readiness"]["durable_reports_missing_for_worker_execute_count"] == 1
    assert report["worker_readiness"]["worker_execute_reports_needed_for_current_evidence"] is True
    assert report["worker_readiness"]["missing_execute_reports_block_current_proof"] is True
    assert (
        report["worker_readiness"]["missing_execute_reports_superseded_by_durable_reports"] is False
    )
    assert report["worker_readiness"]["accepted_handoff_shard_count"] == 0
    assert report["worker_readiness"]["handoff_mismatch_count"] == 0
    assert report["worker_readiness"]["rejected_handoff_shard_count"] == 0
    assert report["worker_readiness"]["handoff_status_counts"] == {"not_ready": 2}
    assert report["worker_readiness"]["no_rejected_or_mismatched_handoffs"] is True
    assert report["worker_dispatch"]["ready_group_count"] == 2
    assert report["worker_dispatch"]["ready_shard_count"] == 3
    assert report["worker_dispatch"]["ready_report_count"] == 11
    assert report["worker_dispatch"]["dispatch_groups_actionable_for_current_phase"] is True
    assert report["worker_dispatch"]["ready_dispatch_groups_superseded_by_durable_reports"] is False
    assert report["worker_dispatch"]["execution_groups"][0] == {
        "name": "unattended_off_desktop_excel",
        "worker_kind": "Off-desktop Excel worker or VM",
        "where_to_run": "approved off-desktop Excel machine only",
        "can_run_now": True,
        "shard_count": 2,
        "expected_report_count": 10,
        "suggested_wave_count": 1,
        "requires_excel_approval": True,
        "local_desktop_safe": False,
    }
    assert report["excel_approval_required"] is True
    assert report["headless_work_available"] is False
    assert report["ready_excel_batch"]["missing_durable_report_count"] == 1
    assert report["current_batch_control"] == {
        "approved_first_chunk_command": (
            "WOLFXL_ALLOW_EXCEL_FOCUS=1 "
            "uv run --no-sync python scripts/run_ooxml_evidence_plan.py "
            f"{ready_plan} --execute --allow-excel-focus --skip-existing "
            "--limit 1 --status-report "
            "/tmp/wolfxl-ready-excel-batch-chunk-001-status.json"
        ),
        "chunk_count": 1,
        "chunk_manifest": str(ready_plan.with_name("ready-plan-chunks.json")),
        "chunk_manifest_command": (
            "uv run --no-sync python scripts/run_ooxml_evidence_plan.py "
            f"{ready_plan} --skip-existing --strict-existing --strict-commands "
            "--chunk-size 10 --chunk-manifest-output "
            f"{ready_plan.with_name('ready-plan-chunks.json')} --summary-only"
        ),
        "chunk_preview_command": (
            "uv run --no-sync python scripts/run_ooxml_evidence_plan.py "
            f"{ready_plan} --skip-existing --strict-existing --strict-commands "
            "--shell-script-dir /tmp/wolfxl-ready-excel-batch-chunks "
            "--chunk-size 10 --summary-only"
        ),
        "chunk_size": 10,
        "first_chunk_limit": 1,
        "first_chunk_start_at": 1,
        "first_missing_step_lane": "render",
        "first_missing_step_name": "ready_excel",
        "label": "ready_excel_batch",
        "plan": str(ready_plan),
        "preflight_command": (
            "uv run --no-sync python scripts/run_ooxml_evidence_plan.py "
            f"{ready_plan} --skip-existing --strict-existing --strict-commands "
            "--chunk-size 10 --summary-only"
        ),
    }
    assert report["sota"]["evidence"]["missing_requirement_ids"] == [
        "current_evidence_bundle_ready",
        "feature_specific_intentional_render_equivalence",
    ]
    assert report["sota"]["openpyxl_compat"] == {
        "openpyxl_gap_count": 0,
        "compat_spec_gap_count": 0,
        "surface_known_gap_count": 0,
        "surface_entry_count": 66,
        "out_of_scope_count": 7,
        "out_of_scope_openpyxl_advantage_count": 0,
        "status_totals": {"supported": 76, "out_of_scope": 7},
    }
    assert report["sota"]["rust_coverage"] == {
        "competitor_set_ready": True,
        "competitor_benchmark": "docs/performance/baselines/rust-required.json",
        "competitor_benchmark_fresh": True,
        "competitor_benchmark_metadata_ready": True,
        "competitor_benchmark_metadata_missing_fields": [],
        "competitor_benchmark_age_days": 0.0,
        "competitor_benchmark_max_age_days": 14.0,
        "competitor_benchmark_freshness_blockers": [],
        "competitor_benchmark_source_relevance_ready": None,
        "competitor_benchmark_source_relevance_status": None,
        "competitor_benchmark_source_relevance_blockers": [],
        "competitor_benchmark_source_relevance_changed_paths": [],
        "competitor_benchmark_source_relevance_dirty_paths": [],
        "competitor_set_report": "docs/performance/baselines/rust-set.json",
        "report_timestamp_utc": "2026-06-01T00:00:00Z",
        "report_age_days": 0.0,
        "max_age_days": 14.0,
        "report_fresh": True,
        "freshness_blockers": [],
        "registry_metadata_fetched": True,
        "crates_io_discovery_fetched": True,
        "pypi_discovery_fetched": True,
        "discovery_queries": ["xlsx", "excel", "spreadsheet"],
        "discovery_per_page": 50,
        "discovery_min_downloads": 1000,
        "discovery_min_recent_downloads": 50,
        "watchlist_promotion_min_downloads": None,
        "watchlist_promotion_min_recent_downloads": None,
        "discovery_error_queries": [],
        "pypi_discovery_name_terms": ["xlsx", "excel", "calamine"],
        "pypi_discovery_rust_hint_terms": ["rust", "maturin", "pyo3"],
        "pypi_discovery_candidate_limit": 250,
        "pypi_discovery_error_queries": [],
        "required_competitors": ["calamine", "rust_xlsxwriter"],
        "required_competitor_aliases": {"xlsxwriter": ["xlsxwriter-rs"]},
        "requested_competitor_name_resolutions": [
            {
                "requested_name": "xlsxwriter-rs",
                "exact_package_gate_status": "watchlist",
                "exact_package_version": "0.1.0",
                "exact_package_decision": "remain_watchlist",
                "resolves_to_competitor": "xlsxwriter",
                "benchmarked_version": "0.6.1",
                "requirement_satisfied": True,
            }
        ],
        "requested_competitor_name_resolution_count": 1,
        "requested_competitor_name_resolution_ready": True,
        "requested_competitor_name_resolution_blockers": [],
        "benchmark_competitors": ["calamine", "rust_xlsxwriter"],
        "benchmark_competitor_versions": {
            "calamine": "0.35.0",
            "rust_xlsxwriter": "0.95.0",
        },
        "benchmark_competitor_api_surfaces": {
            "calamine": ["direct_rust_api"],
            "rust_xlsxwriter": ["direct_rust_api"],
        },
        "status_counts": {"required": 2, "watchlist": 3},
        "watchlist_count": 3,
        "missing_from_benchmark": [],
        "missing_benchmark_versions": [],
        "stale_benchmark_versions": [],
        "unclassified_discovery_hit_count": 0,
        "unclassified_pypi_discovery_hit_count": 0,
        "unclassified_relevant_below_threshold_hit_count": 0,
        "watchlist_promotion_adoption_missing_count": 1,
        "watchlist_promotion_adoption_missing": ["rustypyxl"],
        "watchlist_promotion_adoption_complete": False,
        "watchlist_promotion_adoption_caveat": (
            "Objective watchlist promotion can be applied where registry adoption "
            "data exists; watchlist packages without adoption data remain reviewed "
            "caveats."
        ),
        "watchlist_adoption_attention_review_count": 1,
        "watchlist_adoption_attention_reviews": [
            {
                "id": "python-calamine-reducto",
                "source": "pypi",
                "promotion_risk": "medium",
                "adoption_recent_downloads": 47565,
                "max_promotion_ratio": 0.9513,
                "positioning_handling": "covered_by_required_lanes",
                "related_required_competitors": ["python-calamine", "calamine"],
                "basis": "Fork of the required python-calamine lane.",
                "next_trigger": "Promote if it becomes the main package.",
            }
        ],
        "set_blockers": [],
        "set_missing_required_case_family_count": 0,
        "set_missing_required_case_families": [],
        "missing_required_case_family_count": 0,
        "missing_required_case_families": [],
        "required_min_observed_speedup": 1.2,
        "watchlist_benchmark": "docs/performance/baselines/rust-watchlist.json",
        "watchlist_benchmark_fresh": True,
        "watchlist_benchmark_metadata_ready": True,
        "watchlist_benchmark_metadata_missing_fields": [],
        "watchlist_benchmark_age_days": 0.0,
        "watchlist_benchmark_max_age_days": 14.0,
        "watchlist_benchmark_freshness_blockers": [],
        "watchlist_benchmark_source_relevance_ready": None,
        "watchlist_benchmark_source_relevance_status": None,
        "watchlist_benchmark_source_relevance_blockers": [],
        "watchlist_benchmark_source_relevance_changed_paths": [],
        "watchlist_benchmark_source_relevance_dirty_paths": [],
        "watchlist_min_observed_speedup": 1.5,
        "watchlist_memory_comparison_count": 1,
        "watchlist_max_observed_memory_ratio": 0.8,
        "watchlist_weak_memory_case_count": 0,
        "watchlist_near_parity_memory_case_count": 0,
    }
    assert report["sota"]["evidence"]["missing_requirements"][0]["evidence_summary"] == {
        "issue_count": 1,
        "missing_report_lane_counts": {"render": 1},
    }
    assert (
        _missing_requirement_key_evidence(
            report,
            "feature_specific_intentional_render_equivalence",
        )
        == "0/7 expected mutations; 7 missing; 2/3 frontier reports; 1 missing"
    )
    assert "unattended_off_desktop_excel=2 shards/10 reports" in report["next_action"]
    assert "supervised_excel=1 shards/1 reports" in report["next_action"]
    assert "ready_excel" in report["next_action"]


def test_proof_flow_reports_complete_when_all_gates_are_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=True),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
    )

    assert report["ready"] is True
    assert report["current_phase"] == "complete"
    assert report["excel_approval_required"] is False
    assert report["repin"]["ready"] is True
    assert report["sota"]["sota_confidence_ready"] is True
    assert report["sota"]["supported_scope_sota_gate_ready"] is True
    assert report["sota"]["claim_gates"]["current_fidelity_gate_ready"] is True
    assert report["sota"]["claim_gates"]["rust_competitor_gate_ready"] is True
    assert report["sota"]["claim_gates"]["finite_evidence_frontiers_ready"] is True
    assert report["public_claim"]["ready"] is True
    assert report["public_claim"]["scanned_context_file_count"] == 1
    assert report["release_artifact_benchmark_rerun"]["ready"] is True
    assert report["release_artifact_benchmark_rerun"]["wheel_metadata_ready"] is True
    assert report["release_artifact_benchmark_rerun"][
        "rust_required_versions_complete"
    ] is True


def test_proof_flow_reports_release_artifact_rerun_detail(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    payload = json.loads(release_rerun.read_text(encoding="utf-8"))
    payload["openpyxl_benchmark_summary"]["weak_memory_case_count"] = 1
    payload["rust_benchmark_summary"]["skipped_required_competitors"] = [
        "rust_xlsxwriter"
    ]
    release_rerun.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=True),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
    )

    assert report["ready"] is False
    assert report["current_phase"] == "fix_release_artifact_benchmark_rerun"
    assert report["headless_work_available"] is True
    assert "OpenPyXL weak memory cases present" in report["next_action"]
    assert "required Rust competitors skipped" in report["next_action"]
    rerun = report["release_artifact_benchmark_rerun"]
    assert rerun["available"] is True
    assert rerun["ready"] is False
    assert rerun["openpyxl_weak_memory_case_count"] == 1
    assert rerun["rust_skipped_required_competitors"] == ["rust_xlsxwriter"]
    assert rerun["rust_required_versions_complete"] is True


def test_proof_flow_blocks_on_public_claim_wording_audit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=False)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=True),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
    )

    assert report["ready"] is False
    assert report["current_phase"] == "fix_public_claim_wording"
    assert report["headless_work_available"] is True
    assert report["public_claim"]["issue_count"] == 1
    assert "Resolve public-claim wording audit issues" in report["next_action"]


def test_proof_flow_blocks_on_subagent_handoff_audit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    handoff_report = _write_subagent_handoff_report(tmp_path, ready=False)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=True),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
        subagent_handoff_report=handoff_report,
    )

    assert report["ready"] is False
    assert report["current_phase"] == "fix_subagent_handoff_audit"
    assert report["headless_work_available"] is True
    assert report["subagent_handoffs"]["unexpected_rejection_count"] == 1
    assert "Resolve subagent handoff audit issues" in report["next_action"]


def test_proof_flow_blocks_on_current_worker_handoff_audit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    subagent_handoff_report = _write_subagent_handoff_report(
        tmp_path,
        ready=True,
        name="subagent-handoff-audit.json",
    )
    current_worker_handoff_report = _write_subagent_handoff_report(
        tmp_path,
        ready=False,
        name="current-worker-handoff-audit.json",
    )
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=True),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
        subagent_handoff_report=subagent_handoff_report,
        current_worker_handoff_report=current_worker_handoff_report,
    )

    assert report["ready"] is False
    assert report["current_phase"] == "fix_current_worker_handoff_audit"
    assert report["headless_work_available"] is True
    assert report["current_worker_handoffs"]["unexpected_rejection_count"] == 1
    assert "Resolve current worker handoff audit issues" in report["next_action"]


def test_proof_flow_marks_old_worker_execute_gaps_superseded_by_durable_reports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    worker_status = _write_worker_status(tmp_path, clean_preflights=True)
    worker_dispatch = _write_worker_dispatch_board(tmp_path)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=False),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_status=worker_status,
        worker_dispatch_board=worker_dispatch,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
    )

    assert report["current_phase"] == "final_sota_audit_blockers"
    assert report["excel_approval_required"] is False
    assert report["ready_excel_batch"]["missing_durable_report_count"] == 0
    assert report["worker_readiness"]["missing_execute_status_report_count"] == 2
    assert report["worker_readiness"]["durable_reports_missing_for_worker_execute_count"] == 0
    assert report["worker_readiness"]["worker_execute_reports_needed_for_current_evidence"] is False
    assert report["worker_readiness"]["missing_execute_reports_block_current_proof"] is False
    assert (
        report["worker_readiness"]["missing_execute_reports_superseded_by_durable_reports"] is True
    )
    assert report["worker_readiness"]["next_shard_is_current_proof_step"] is False
    assert report["worker_readiness"]["excel_approval_required_for_next"] is False
    assert report["worker_readiness"]["next_shard"] is None
    superseded_next = report["worker_readiness"]["superseded_next_shard"]
    assert superseded_next["phase"] == "phase_1_ready_excel_batch"
    assert superseded_next["lane"] == "render"
    assert superseded_next["shard"] == 1
    assert report["worker_dispatch"]["dispatch_groups_actionable_for_current_phase"] is False
    assert report["worker_dispatch"]["ready_dispatch_groups_superseded_by_durable_reports"] is True


def test_proof_flow_ignores_bad_stale_worker_status_after_durable_reports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    worker_status = _write_worker_status(tmp_path, clean_preflights=True)
    payload = json.loads(worker_status.read_text(encoding="utf-8"))
    payload.update(
        {
            "status_audit_ready": False,
            "no_rejected_or_mismatched_handoffs": False,
            "handoff_mismatch_count": 1,
            "rejected_handoff_shard_count": 0,
            "handoff_status_counts": {
                "execute_complete_but_reports_incomplete": 1,
                "not_ready": 1,
            },
        }
    )
    worker_status.write_text(json.dumps(payload), encoding="utf-8")
    worker_dispatch = _write_worker_dispatch_board(tmp_path)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    handoff_report = _write_subagent_handoff_report(tmp_path, ready=True)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=False),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_status=worker_status,
        worker_dispatch_board=worker_dispatch,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
        subagent_handoff_report=handoff_report,
    )

    assert report["ready"] is False
    assert report["current_phase"] == "final_sota_audit_blockers"
    assert report["excel_approval_required"] is False
    assert report["headless_work_available"] is False
    assert report["worker_readiness"]["status_audit_ready"] is False
    assert report["worker_readiness"]["handoff_mismatch_count"] == 1
    assert report["worker_readiness"]["durable_reports_missing_for_worker_execute_count"] == 0
    assert report["worker_readiness"]["worker_execute_reports_needed_for_current_evidence"] is False
    assert report["worker_readiness"]["missing_execute_reports_block_current_proof"] is False
    assert (
        report["worker_readiness"]["missing_execute_reports_superseded_by_durable_reports"] is True
    )
    assert report["worker_dispatch"]["dispatch_groups_actionable_for_current_phase"] is False
    assert report["worker_dispatch"]["ready_dispatch_groups_superseded_by_durable_reports"] is True
    assert "Resolve final SOTA audit blockers" in report["next_action"]


def test_proof_flow_explains_supported_scope_ready_but_broad_sota_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    handoff_report = _write_subagent_handoff_report(tmp_path, ready=True)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_supported_scope_ready_broad_sota_blocked_report(),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
        subagent_handoff_report=handoff_report,
    )

    assert report["ready"] is False
    assert report["current_phase"] == "final_sota_audit_blockers"
    assert report["excel_approval_required"] is False
    assert report["headless_work_available"] is False
    assert report["sota"]["supported_scope_sota_gate_ready"] is True
    assert report["sota"]["sota_claim_ready"] is False
    assert report["sota"]["evidence"]["remaining_direct_headless_step_count"] == 0
    assert report["sota"]["evidence"]["remaining_deferred_excel_step_count"] == 0
    assert report["sota"]["evidence"]["next_required_proof_mode"] == "none"
    assert "Keep the broad all-future-surface SOTA claim gated" in report["next_action"]
    assert "missing headless or Excel batch" in report["next_action"]


def test_proof_flow_counts_missing_release_lanes_as_headless_work(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    release_coverage = _write_release_artifact_coverage(tmp_path)
    handoff_report = _write_subagent_handoff_report(tmp_path, ready=True)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_supported_scope_ready_broad_sota_blocked_report(),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
        release_artifact_coverage=release_coverage,
        subagent_handoff_report=handoff_report,
    )

    assert report["current_phase"] == "final_sota_audit_blockers"
    assert report["headless_work_available"] is True
    assert report["excel_approval_required"] is False
    assert report["release_artifact_coverage"]["ready"] is False
    assert report["release_artifact_coverage"]["missing_lane_count"] == 2
    assert report["sota"]["evidence"]["remaining_direct_headless_step_count"] == 2
    assert (
        report["sota"]["evidence"]["next_required_proof_mode"]
        == "cross_platform_release_artifact_batch"
    )
    assert "cross_platform_release_artifact_coverage" in report["sota"]["evidence"][
        "missing_requirement_ids"
    ]
    assert "Run the cross-platform release artifact proof batch" in report["next_action"]
    assert "2 release workflow lanes" in report["next_action"]


def test_proof_flow_counts_dirty_release_content_as_headless_work(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    release_coverage = _write_release_artifact_coverage(
        tmp_path,
        coverage_ready=True,
        currentness_ready=False,
        missing_lane_count=0,
        missing_lanes=[],
        content_dirty_paths=["crates/wolfxl-writer/src/lib.rs"],
    )
    handoff_report = _write_subagent_handoff_report(tmp_path, ready=True)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_supported_scope_ready_broad_sota_blocked_report(),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
        release_artifact_coverage=release_coverage,
        subagent_handoff_report=handoff_report,
    )

    assert report["headless_work_available"] is True
    assert report["release_artifact_coverage"]["ready"] is False
    assert report["release_artifact_coverage"]["content_dirty_path_count"] == 1
    assert report["sota"]["evidence"]["remaining_direct_headless_step_count"] == 1
    assert report["sota"]["evidence"]["release_artifact_content_dirty_paths"] == [
        "crates/wolfxl-writer/src/lib.rs"
    ]
    assert (
        report["sota"]["evidence"]["next_required_proof_mode"]
        == "cross_platform_release_artifact_batch"
    )
    assert "cross_platform_release_artifact_coverage" in report["sota"]["evidence"][
        "missing_requirement_ids"
    ]


def test_proof_flow_counts_stale_benchmark_sources_as_headless_work(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    handoff_report = _write_subagent_handoff_report(tmp_path, ready=True)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_stale_benchmark_source_report(),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
        subagent_handoff_report=handoff_report,
    )

    evidence = report["sota"]["evidence"]
    assert report["current_phase"] == "final_sota_audit_blockers"
    assert report["headless_work_available"] is True
    assert evidence["remaining_direct_headless_step_count"] == 3
    assert evidence["benchmark_source_relevance_missing_task_count"] == 3
    assert evidence["benchmark_source_relevance_missing_task_ids"] == [
        "openpyxl_performance_benchmark_source_relevance",
        "rust_competitor_benchmark_source_relevance",
        "rust_watchlist_benchmark_source_relevance",
    ]
    assert "benchmark_rerun" == evidence["next_required_proof_mode"]
    assert "Rerun stale benchmark evidence" in report["next_action"]
    assert "3 benchmark reruns" in report["next_action"]
    assert report["sota"]["openpyxl_benchmark_source_relevance_ready"] is False
    assert report["sota"]["rust_coverage"][
        "competitor_benchmark_source_relevance_ready"
    ] is False
    assert report["sota"]["rust_coverage"][
        "watchlist_benchmark_source_relevance_ready"
    ] is False


def test_proof_flow_names_push_required_before_release_proof_batch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=True)
    public_claim_report = _write_public_claim_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    release_coverage = _write_release_artifact_coverage(tmp_path)
    release_trigger = _write_release_artifact_trigger_readiness(tmp_path)
    handoff_report = _write_subagent_handoff_report(tmp_path, ready=True)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_supported_scope_ready_broad_sota_blocked_report(),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_dispatch_board=None,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        public_claim_report=public_claim_report,
        release_artifact_benchmark_rerun=release_rerun,
        release_artifact_coverage=release_coverage,
        release_artifact_trigger_readiness=release_trigger,
        subagent_handoff_report=handoff_report,
    )

    assert report["release_artifact_trigger_readiness"]["ready"] is False
    assert report["release_artifact_trigger_readiness"]["trigger_mode"] == "push_required"
    assert "Push the current branch" in report["next_action"]
    assert "then import the resulting reports" in report["next_action"]
    assert "2 release workflow lanes" in report["next_action"]


def test_proof_flow_blocks_on_bad_worker_handoff_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=False)
    worker_status = _write_worker_status(tmp_path, clean_preflights=True)
    payload = json.loads(worker_status.read_text(encoding="utf-8"))
    payload.update(
        {
            "status_audit_ready": False,
            "no_rejected_or_mismatched_handoffs": False,
            "handoff_mismatch_count": 1,
            "rejected_handoff_shard_count": 0,
            "handoff_status_counts": {
                "execute_complete_but_reports_incomplete": 1,
                "not_ready": 1,
            },
        }
    )
    worker_status.write_text(json.dumps(payload), encoding="utf-8")
    worker_dispatch = _write_worker_dispatch_board(tmp_path)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=False),
    )

    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_status=worker_status,
        worker_dispatch_board=worker_dispatch,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
    )

    assert report["ready"] is False
    assert report["current_phase"] == "fix_worker_handoff_status"
    assert report["excel_approval_required"] is False
    assert report["worker_readiness"]["status_audit_ready"] is False
    assert "1 mismatched" in report["next_action"]
    assert "running more Excel evidence" in report["next_action"]


def test_proof_flow_cli_writes_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=False)
    worker_dispatch = _write_worker_dispatch_board(tmp_path)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    output = tmp_path / "proof-flow.json"
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=False),
    )

    code = audit.main(
        [
            "--ready-plan",
            str(ready_plan),
            "--round-1-plan",
            str(round_plan),
            "--worker-dispatch-board",
            str(worker_dispatch),
            "--evidence-manifest",
            str(manifest),
            "--release-artifact-benchmark-rerun",
            str(release_rerun),
            "--output",
            str(output),
        ]
    )
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(output.read_text())

    assert code == 0
    assert printed["current_phase"] == "phase_1_excel_batch"
    assert written == printed


def test_markdown_report_summarizes_current_phase(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=False)
    worker_status = _write_worker_status(tmp_path, clean_preflights=True)
    worker_dispatch = _write_worker_dispatch_board(tmp_path)
    handoff_report = _write_subagent_handoff_report(tmp_path, ready=True)
    release_rerun = _write_release_artifact_benchmark_rerun(tmp_path)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=False),
    )
    report = audit.audit_proof_flow(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        worker_status=worker_status,
        worker_dispatch_board=worker_dispatch,
        evidence_manifest=manifest,
        openpyxl_benchmark=None,
        rust_benchmark=None,
        rust_watchlist_benchmark=None,
        rust_competitor_set_report=None,
        subagent_handoff_report=handoff_report,
        release_artifact_benchmark_rerun=release_rerun,
    )

    markdown = audit.format_markdown_report(report)

    assert "# WolfXL SOTA Proof Flow Status (Supported Scope Ready; Broad Claim Not Ready)" in markdown
    assert "| Current phase | phase_1_excel_batch |" in markdown
    assert "| Openpyxl min observed speedup | 2.5 |" in markdown
    assert "| Supported-scope SOTA gate ready | false |" in markdown
    assert "| Current fidelity gate ready | false |" in markdown
    assert "| Rust competitor gate ready | true |" in markdown
    assert "| Finite named-frontier evidence ready | false |" in markdown
    assert "| Exhaustive all-future-surface claim ready | false |" in markdown
    assert "| Openpyxl max observed memory ratio | 0.98 |" in markdown
    assert "| Openpyxl API gaps | 0 |" in markdown
    assert "| Openpyxl parity surface known gaps | 0 |" in markdown
    assert "| Out-of-scope openpyxl advantages | 0 |" in markdown
    assert "| Ready Excel batch | 1 | 0 | 1 | 0 | 0 | true |" in markdown
    assert "## Remaining Claim Requirements" in markdown
    assert "## Public Claim Wording" in markdown
    assert "| Ready | true |" in markdown
    assert "| Context files scanned |" in markdown
    assert "## Release Artifact Benchmark Rerun" in markdown
    assert "| Wheel metadata ready | true |" in markdown
    assert "| OpenPyXL weak memory cases | 0 |" in markdown
    assert "| Rust skipped required competitors | none |" in markdown
    assert "## Rust Coverage" in markdown
    assert "| Required competitors | calamine, rust_xlsxwriter |" in markdown
    assert "| crates.io discovery fetched | true |" in markdown
    assert "| PyPI Rust-backed discovery fetched | true |" in markdown
    assert "| Audit timestamp UTC | 2026-06-01T00:00:00Z |" in markdown
    assert "| Discovery download threshold | 1000 |" in markdown
    assert "| PyPI discovery name terms | xlsx, excel, calamine |" in markdown
    assert "| PyPI Rust hint terms | rust, maturin, pyo3 |" in markdown
    assert "| PyPI discovery candidate limit | 250 |" in markdown
    assert "| PyPI discovery errors | none |" in markdown
    assert "| Unclassified relevant discovery hits | 0 |" in markdown
    assert "| Unclassified PyPI Rust-backed discovery hits | 0 |" in markdown
    assert "| Requested competitor name resolution ready | true |" in markdown
    assert "| Requested competitor name resolution blockers | none |" in markdown
    assert (
        "| xlsxwriter-rs | watchlist | 0.1.0 | remain_watchlist | "
        "xlsxwriter | 0.6.1 | true |"
    ) in markdown
    assert "| Missing benchmark competitors | none |" in markdown
    assert "| Stale benchmark versions | none |" in markdown
    assert "Required Rust benchmark versions:" in markdown
    assert "| calamine | 0.35.0 |" in markdown
    assert "## Current Batch Control" in markdown
    assert "## Worker Readiness" in markdown
    assert "| Clean preflight reports | 2 |" in markdown
    assert "| All preflights clean | true |" in markdown
    assert "| Execute reports needed for current evidence | true |" in markdown
    assert "| Missing execute reports block current proof | true |" in markdown
    assert "| Accepted handoffs | 0 |" in markdown
    assert "| No rejected or mismatched handoffs | true |" in markdown
    assert "| Handoff mismatches | 0 |" in markdown
    assert "## Worker Dispatch Groups" in markdown
    assert "## Subagent Handoffs" in markdown
    assert "| Accepted handoffs | 2 |" in markdown
    assert "| Rejected handoffs | 1 |" in markdown
    assert "| Groups actionable for current phase | true |" in markdown
    assert "| Ready groups superseded by durable reports | false |" in markdown
    assert (
        "| unattended_off_desktop_excel | approved off-desktop Excel machine only | "
        "true | 2 | 10 | 1 | false |"
    ) in markdown
    assert (
        "| future_headless_after_phase_1 | headless worker after dependencies are "
        "complete | false | 2 | 7 | 1 | true |"
    ) in markdown
    assert "Approved first chunk command" in markdown
    assert "WOLFXL_ALLOW_EXCEL_FOCUS=1" in markdown
    assert "current_evidence_bundle_ready" in markdown
    assert "1 issues; lanes render=1" in markdown
    assert "Feature-specific Excel render equivalence" in markdown
    assert "| Missing evidence reports | 1 |" in markdown
    assert "## Blockers" in markdown


def test_proof_flow_cli_can_write_markdown_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    ready_plan, round_plan, manifest = _write_fixture(tmp_path, durable_ready=False)
    markdown_output = tmp_path / "proof-flow.md"
    worker_dispatch = _write_worker_dispatch_board(tmp_path)
    monkeypatch.setattr(
        audit.audit_wolfxl_sota_claim,
        "audit_sota_claim",
        lambda **_: _fake_sota_report(ready=False),
    )

    code = audit.main(
        [
            "--ready-plan",
            str(ready_plan),
            "--round-1-plan",
            str(round_plan),
            "--worker-dispatch-board",
            str(worker_dispatch),
            "--evidence-manifest",
            str(manifest),
            "--markdown-output",
            str(markdown_output),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["current_phase"] == "phase_1_excel_batch"
    assert markdown_output.read_text().startswith(
        "# WolfXL SOTA Proof Flow Status (Supported Scope Ready; Broad Claim Not Ready)"
    )


def _write_fixture(
    tmp_path: Path,
    *,
    durable_ready: bool,
) -> tuple[Path, Path, Path]:
    durable_report = tmp_path / "ready.json"
    if durable_ready:
        durable_report.write_text('{"ok": true}\n')
    ready_plan = tmp_path / "ready-plan.json"
    ready_plan.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "name": "ready_excel",
                        "lane": "render",
                        "action": "defer_excel_batch",
                        "durable_report_path": str(durable_report),
                        "durable_producer": "printf '{}\\n'",
                        "opens_excel_or_render_oracle": True,
                    }
                ]
            }
        )
    )
    round_plan = tmp_path / "round-plan.json"
    round_plan.write_text(json.dumps({"steps": []}))
    manifest = tmp_path / "Plans" / "ooxml-current-evidence-bundle.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "ready_excel",
                        "path": "old-ready.json",
                    }
                ]
            }
        )
    )
    return ready_plan, round_plan, manifest


def _write_worker_status(tmp_path: Path, *, clean_preflights: bool) -> Path:
    path = tmp_path / "worker-status.json"
    clean_count = 2 if clean_preflights else 1
    missing_count = 0 if clean_preflights else 1
    path.write_text(
        json.dumps(
            {
                "status_audit_ready": True,
                "no_rejected_or_mismatched_handoffs": True,
                "worker_shard_count": 2,
                "clean_preflight_status_report_count": clean_count,
                "missing_preflight_status_report_count": missing_count,
                "complete_execute_status_report_count": 0,
                "missing_execute_status_report_count": 2,
                "accepted_handoff_shard_count": 0,
                "handoff_mismatch_count": 0,
                "rejected_handoff_shard_count": 0,
                "handoff_status_counts": {"not_ready": 2},
                "preflight_status_counts": {"clean_preflight": clean_count},
                "execute_status_counts": {"missing": 2},
                "excel_approval_required_for_next": True,
                "next_shard": {
                    "phase": "phase_1_ready_excel_batch",
                    "lane": "render",
                    "shard": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_worker_dispatch_board(tmp_path: Path) -> Path:
    path = tmp_path / "worker-dispatch-board.json"
    path.write_text(
        json.dumps(
            {
                "execution_groups": {
                    "unattended_off_desktop_excel": {
                        "name": "unattended_off_desktop_excel",
                        "worker_kind": "Off-desktop Excel worker or VM",
                        "where_to_run": "approved off-desktop Excel machine only",
                        "can_run_now": True,
                        "shard_count": 2,
                        "expected_report_count": 10,
                        "suggested_wave_count": 1,
                        "requires_excel_approval": True,
                        "local_desktop_safe": False,
                    },
                    "supervised_excel": {
                        "name": "supervised_excel",
                        "worker_kind": "Manual or closely supervised Excel worker",
                        "where_to_run": "approved off-desktop Excel machine only",
                        "can_run_now": True,
                        "shard_count": 1,
                        "expected_report_count": 1,
                        "suggested_wave_count": 1,
                        "requires_excel_approval": True,
                        "local_desktop_safe": False,
                    },
                    "future_headless_after_phase_1": {
                        "name": "future_headless_after_phase_1",
                        "worker_kind": "Headless/package-level worker",
                        "where_to_run": ("headless worker after dependencies are complete"),
                        "can_run_now": False,
                        "shard_count": 2,
                        "expected_report_count": 7,
                        "suggested_wave_count": 1,
                        "requires_excel_approval": False,
                        "local_desktop_safe": True,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_public_claim_report(tmp_path: Path, *, ready: bool) -> Path:
    path = tmp_path / "public-claim-wording-audit.json"
    issue = {
        "file": "README.md",
        "line": 1,
        "phrase": "Full openpyxl replacement.",
        "reason": "full replacement wording is broader than the current audit",
    }
    path.write_text(
        json.dumps(
            {
                "ready": ready,
                "issue_count": 0 if ready else 1,
                "issues": [] if ready else [issue],
                "scanned_files": ["README.md"],
                "scanned_context_files": ["Plans/launch-posts.md"],
                "sota_alignment": {
                    "supported_scope_sota_gate_ready": True,
                    "sota_claim_ready": False,
                    "required_rust_competitors": ["calamine", "rust_xlsxwriter"],
                    "benchmark_competitor_versions": {
                        "calamine": "0.35.0",
                        "rust_xlsxwriter": "0.95.0",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_release_artifact_benchmark_rerun(tmp_path: Path) -> Path:
    path = tmp_path / "release-artifact-benchmark-rerun.json"
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "full_release_artifact_rerun_ready": True,
                "source_git_sha": "abc123",
                "source_git_dirty": False,
                "wheel": {
                    "filename": "wolfxl-2.0.0-cp312-cp312-macosx_11_0_arm64.whl",
                    "metadata_name": "wolfxl",
                    "metadata_version": "2.0.0",
                    "sha256": "c" * 64,
                    "size_bytes": 1234,
                    "wheel_tag": "cp312-cp312-macosx_11_0_arm64",
                },
                "openpyxl_sota_speed_ready": True,
                "openpyxl_memory_ready": True,
                "rust_superiority_ready": True,
                "rust_memory_ready": True,
                "openpyxl_benchmark_summary": {
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


def _write_release_artifact_coverage(
    tmp_path: Path,
    *,
    coverage_ready: bool = False,
    currentness_ready: bool = False,
    missing_lane_count: int = 2,
    missing_lanes: list[dict[str, str]] | None = None,
    stale_lanes: list[dict[str, str]] | None = None,
    content_dirty_paths: list[str] | None = None,
) -> Path:
    path = tmp_path / "release-artifact-coverage.json"
    if missing_lanes is None:
        missing_lanes = [
            {"id": "wheel:linux:aarch64:cp312"},
            {"id": "wheel:windows:x86_64:cp312"},
        ]
    if stale_lanes is None:
        stale_lanes = []
    if content_dirty_paths is None:
        content_dirty_paths = []
    path.write_text(
        json.dumps(
            {
                "ready": coverage_ready and currentness_ready and not content_dirty_paths,
                "coverage_ready": coverage_ready,
                "currentness_ready": currentness_ready,
                "expected_lane_count": 4,
                "proven_lane_count": 4 - missing_lane_count,
                "missing_lane_count": missing_lane_count,
                "missing_lanes": missing_lanes,
                "stale_proven_lane_count": len(stale_lanes),
                "stale_proven_lanes": stale_lanes,
                "current_worktree_release_relevant_content_dirty_path_count": len(
                    content_dirty_paths
                ),
                "current_worktree_release_relevant_content_dirty_paths": content_dirty_paths,
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
                "ready": False,
                "trigger_mode": "push_required",
                "branch_push_ready_now": False,
                "branch_push_requires_push": True,
                "manual_dispatch_ready_now": False,
                "current_branch_pushed": False,
                "current_branch_has_unpushed_commits": True,
                "workflow_on_default_branch": False,
                "local_workflow_ready": True,
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_subagent_handoff_report(
    tmp_path: Path,
    *,
    ready: bool,
    name: str = "subagent-handoff-audit.json",
) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "ready": ready,
                "accepted_count": 2 if ready else 1,
                "rejected_count": 1 if ready else 2,
                "unexpected_acceptance": [],
                "unexpected_rejection": [] if ready else ["worker_missing"],
                "handoffs": [
                    {
                        "name": "worker_b",
                        "expected": "accepted",
                        "accepted": True,
                        "issues": [],
                    },
                    {
                        "name": "worker_a",
                        "expected": "rejected",
                        "accepted": False,
                        "issues": ["missing JSON status report"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _fake_sota_report(*, ready: bool) -> dict[str, object]:
    return {
        "sota_claim_ready": ready,
        "sota_confidence_ready": ready,
        "supported_scope_sota_gate_ready": ready,
        "claim_gates": {
            "api_compat_gate_ready": True,
            "current_fidelity_gate_ready": ready,
            "openpyxl_performance_gate_ready": True,
            "rust_competitor_benchmark_gate_ready": True,
            "rust_competitor_set_gate_ready": True,
            "rust_watchlist_gate_ready": True,
            "rust_competitor_gate_ready": True,
            "finite_evidence_frontiers_ready": ready,
            "supported_scope_sota_gate_ready": ready,
            "exhaustive_claim_ready": ready,
        },
        "blockers": [] if ready else ["current supported-fidelity evidence bundle is not ready"],
        "confidence_warnings": [],
        "compat": {
            "openpyxl_gap_count": 0,
            "compat_spec_gap_count": 0,
            "surface_known_gap_count": 0,
            "surface_entry_count": 66,
            "out_of_scope_count": 7,
            "out_of_scope_openpyxl_advantage_count": 0,
            "status_totals": {"supported": 76, "out_of_scope": 7},
        },
        "rust_competitor_set": {
            "main_rust_competitor_set_ready": True,
            "report": "docs/performance/baselines/rust-set.json",
            "report_timestamp_utc": "2026-06-01T00:00:00Z",
            "report_age_days": 0.0,
            "max_age_days": 14.0,
            "report_fresh": True,
            "freshness_blockers": [],
            "registry_metadata_fetched": True,
            "crates_io_discovery_fetched": True,
            "pypi_discovery_fetched": True,
            "discovery_queries": ["xlsx", "excel", "spreadsheet"],
            "discovery_per_page": 50,
            "discovery_min_downloads": 1000,
            "discovery_min_recent_downloads": 50,
            "discovery_error_queries": [],
            "pypi_discovery_name_terms": ["xlsx", "excel", "calamine"],
            "pypi_discovery_rust_hint_terms": ["rust", "maturin", "pyo3"],
            "pypi_discovery_candidate_limit": 250,
            "pypi_discovery_error_queries": [],
            "required_competitors": ["calamine", "rust_xlsxwriter"],
            "required_competitor_aliases": {"xlsxwriter": ["xlsxwriter-rs"]},
            "requested_competitor_name_resolutions": [
                {
                    "requested_name": "xlsxwriter-rs",
                    "exact_package_gate_status": "watchlist",
                    "exact_package_version": "0.1.0",
                    "exact_package_decision": "remain_watchlist",
                    "resolves_to_competitor": "xlsxwriter",
                    "benchmarked_version": "0.6.1",
                    "requirement_satisfied": True,
                }
            ],
            "requested_competitor_name_resolution_count": 1,
            "requested_competitor_name_resolution_ready": True,
            "requested_competitor_name_resolution_blockers": [],
            "benchmark_competitors": ["calamine", "rust_xlsxwriter"],
            "benchmark_competitor_versions": {
                "calamine": "0.35.0",
                "rust_xlsxwriter": "0.95.0",
            },
            "benchmark_competitor_api_surfaces": {
                "calamine": ["direct_rust_api"],
                "rust_xlsxwriter": ["direct_rust_api"],
            },
            "status_counts": {"required": 2, "watchlist": 3},
            "watchlist_count": 3,
            "missing_from_benchmark": [],
            "missing_benchmark_versions": [],
            "stale_benchmark_versions": [],
            "unclassified_discovery_hit_count": 0,
            "unclassified_pypi_discovery_hit_count": 0,
            "unclassified_relevant_below_threshold_hit_count": 0,
            "watchlist_promotion_adoption_missing_count": 1,
            "watchlist_promotion_adoption_missing": ["rustypyxl"],
            "watchlist_promotion_adoption_complete": False,
            "watchlist_promotion_adoption_caveat": (
                "Objective watchlist promotion can be applied where registry "
                "adoption data exists; watchlist packages without adoption data "
                "remain reviewed caveats."
            ),
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
            "missing_required_case_family_count": 0,
            "missing_required_case_families": [],
            "blockers": [],
        },
        "rust_competitors": {
            "benchmark": "docs/performance/baselines/rust-required.json",
            "benchmark_fresh": True,
            "benchmark_metadata_ready": True,
            "benchmark_metadata_missing_fields": [],
            "benchmark_age_days": 0.0,
            "benchmark_max_age_days": 14.0,
            "freshness_blockers": [],
            "min_observed_speedup": 1.2,
            "missing_required_case_family_count": 0,
            "missing_required_case_families": [],
        },
        "rust_watchlist": {
            "benchmark": "docs/performance/baselines/rust-watchlist.json",
            "benchmark_fresh": True,
            "benchmark_metadata_ready": True,
            "benchmark_metadata_missing_fields": [],
            "benchmark_age_days": 0.0,
            "benchmark_max_age_days": 14.0,
            "freshness_blockers": [],
            "min_observed_speedup": 1.5,
            "memory_comparison_count": 1,
            "max_observed_memory_ratio": 0.8,
            "weak_memory_case_count": 0,
            "near_parity_memory_case_count": 0,
        },
        "performance": {
            "benchmark": "docs/performance/baselines/current.json",
            "benchmark_fresh": True,
            "benchmark_metadata_ready": True,
            "benchmark_metadata_missing_fields": [],
            "min_observed_speedup": 2.5,
            "max_observed_memory_ratio": 0.98,
        },
        "evidence": {
            "missing_requirement_ids": []
            if ready
            else [
                "current_evidence_bundle_ready",
                "feature_specific_intentional_render_equivalence",
            ],
            "finite_evidence_frontiers_ready": ready,
            "finite_evidence_frontier_blocker_ids": []
            if ready
            else [
                "current_evidence_bundle_ready",
                "feature_specific_intentional_render_equivalence",
            ],
            "unbounded_claim_boundary_ids": [],
            "missing_requirements": []
            if ready
            else [
                {
                    "id": "current_evidence_bundle_ready",
                    "status": "missing",
                    "evidence_summary": {
                        "issue_count": 1,
                        "missing_report_lane_counts": {"render": 1},
                    },
                },
                {
                    "id": "feature_specific_intentional_render_equivalence",
                    "status": "open",
                    "evidence_summary": {
                        "coverage_matrix": {
                            "expected_mutation_count": 7,
                            "observed_expected_mutation_count": 0,
                            "missing_expected_mutation_count": 7,
                        },
                        "frontier_candidate_count": 3,
                        "frontier_expected_report_count": 3,
                        "frontier_observed_report_count": 2,
                        "frontier_missing_report_count": 1,
                    },
                },
            ],
            "missing_report_count": 0 if ready else 1,
            "remaining_direct_headless_step_count": 0,
            "remaining_deferred_excel_step_count": 0 if ready else 1,
            "remaining_followup_coverage_gate_count": 0,
            "next_required_proof_mode": "complete" if ready else "explicit_excel_batch",
        },
    }


def _fake_supported_scope_ready_broad_sota_blocked_report() -> dict[str, object]:
    report = _fake_sota_report(ready=True)
    unbounded_ids = [
        "feature_specific_intentional_render_equivalence",
        "broader_click_level_interaction_variants",
        "future_surface_exhaustiveness",
    ]
    report["sota_claim_ready"] = False
    report["sota_confidence_ready"] = False
    report["claim_gates"]["exhaustive_claim_ready"] = False
    report["blockers"] = ["exhaustive no-gap claim is still unproven"]
    report["evidence"]["missing_requirement_ids"] = unbounded_ids
    report["evidence"]["unbounded_claim_boundary_ids"] = unbounded_ids
    report["evidence"]["missing_requirements"] = [
        {
            "id": requirement_id,
            "status": "open",
            "evidence_summary": {
                "boundary": "unbounded proof boundary",
            },
        }
        for requirement_id in unbounded_ids
    ]
    report["evidence"]["next_required_proof_mode"] = "none"
    return report


def _fake_stale_benchmark_source_report() -> dict[str, object]:
    report = _fake_supported_scope_ready_broad_sota_blocked_report()
    source_blocker = (
        "benchmark has benchmark-relevant source changes since metadata.git_commit: "
        "python/wolfxl/_worksheet_write_buffers.py"
    )
    for section_name in ("performance", "rust_competitors", "rust_watchlist"):
        section = report[section_name]
        section.update(
            {
                "source_relevance_ready": False,
                "source_relevance_status": "blocked",
                "source_relevance_blockers": [source_blocker],
                "source_relevance_relevant_changed_paths": [
                    "python/wolfxl/_worksheet_write_buffers.py"
                ],
                "source_relevance_dirty_relevant_paths": [],
            }
        )
    report["claim_gates"]["openpyxl_performance_gate_ready"] = False
    report["claim_gates"]["rust_competitor_benchmark_gate_ready"] = False
    report["claim_gates"]["rust_watchlist_gate_ready"] = False
    report["claim_gates"]["rust_competitor_gate_ready"] = False
    report["claim_gates"]["supported_scope_sota_gate_ready"] = False
    report["supported_scope_sota_gate_ready"] = False
    report["blockers"] = [
        "OpenPyXL performance benchmark has benchmark-relevant source changes",
        "Rust competitor benchmark has benchmark-relevant source changes",
        "Rust watchlist benchmark has benchmark-relevant source changes",
        "exhaustive no-gap claim is still unproven",
    ]
    return report


def _missing_requirement_key_evidence(report: dict, requirement_id: str) -> str:
    requirement = next(
        requirement
        for requirement in report["sota"]["evidence"]["missing_requirements"]
        if requirement["id"] == requirement_id
    )
    return audit._requirement_key_evidence(requirement)
