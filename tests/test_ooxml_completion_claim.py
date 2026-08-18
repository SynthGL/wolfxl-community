from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType


def _load_completion_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_ooxml_completion_claim.py"
    spec = importlib.util.spec_from_file_location("audit_ooxml_completion_claim", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


completion = _load_completion_module()


def test_completion_claim_audit_supports_current_claim_but_not_exhaustive_claim(
    tmp_path: Path,
) -> None:
    manifest = _write_bundle_manifest(tmp_path, ready=True, include_required_reports=True)

    report = completion.audit_completion_claim(manifest)

    assert report["objective"] == "no real-world Excel fidelity gaps"
    assert report["current_supported_claim_ready"] is True
    assert report["exhaustive_claim_ready"] is False
    assert report["bundle_audit"]["ready"] is True
    assert report["missing_requirement_count"] == 4
    assert report["missing_requirement_ids"] == [
        "broader_real_world_corpus_diversity",
        "feature_specific_intentional_render_equivalence",
        "broader_click_level_interaction_variants",
        "future_surface_exhaustiveness",
    ]
    assert {
        requirement["id"] for requirement in report["missing_requirements"]
    } == {
        "broader_real_world_corpus_diversity",
        "feature_specific_intentional_render_equivalence",
        "broader_click_level_interaction_variants",
        "future_surface_exhaustiveness",
    }
    assert report["finite_evidence_frontiers_ready"] is False
    assert report["finite_evidence_frontier_blocker_ids"] == [
        "broader_real_world_corpus_diversity",
        "feature_specific_intentional_render_equivalence",
        "broader_click_level_interaction_variants",
    ]
    assert report["unbounded_claim_boundary_ids"] == [
        "future_surface_exhaustiveness"
    ]
    corpus_requirement = next(
        requirement
        for requirement in report["missing_requirements"]
        if requirement["id"] == "broader_real_world_corpus_diversity"
    )
    assert "11 unique readable workbooks across 3 source reports" in corpus_requirement["reason"]
    assert "below the customer-scale target" in corpus_requirement["reason"]
    assert corpus_requirement["evidence"] == {
        "actual_workbook_count": 11,
        "actual_source_count": 3,
        "customer_scale_min_workbooks": completion.CUSTOMER_SCALE_MIN_WORKBOOKS,
        "customer_scale_min_sources": completion.CUSTOMER_SCALE_MIN_SOURCES,
        "workbook_deficit": completion.CUSTOMER_SCALE_MIN_WORKBOOKS - 11,
        "source_deficit": completion.CUSTOMER_SCALE_MIN_SOURCES - 3,
    }
    render_requirement = next(
        requirement
        for requirement in report["missing_requirements"]
        if requirement["id"] == "feature_specific_intentional_render_equivalence"
    )
    assert render_requirement["evidence"]["ready_report_count"] > 0
    assert render_requirement["evidence"]["excel_report_count"] > 0
    assert render_requirement["evidence"]["passed_count"] > 0
    assert render_requirement["evidence"]["failure_count"] == 0
    assert render_requirement["evidence"]["target_status"] == (
        "open_unbounded_high_risk_feature_edit_universe"
    )
    assert render_requirement["evidence"]["frontier_candidate_count"] == len(
        completion.RENDER_EQUIVALENCE_FRONTIER_CANDIDATES
    )
    assert render_requirement["evidence"]["frontier_expected_report_count"] == 36
    assert render_requirement["evidence"]["frontier_observed_report_count"] == 36
    assert render_requirement["evidence"]["frontier_missing_report_count"] == 0
    assert render_requirement["evidence"]["frontier_missing_candidate_count"] == 0
    assert render_requirement["evidence"]["frontier_empty_candidate_count"] == 0
    assert render_requirement["evidence"]["frontier_missing_candidates"] == []
    assert render_requirement["evidence"]["frontier_empty_candidates"] == []
    assert render_requirement["evidence"]["frontier_evidence_ready"] is True
    assert {
        candidate["id"]
        for candidate in render_requirement["evidence"]["frontier_candidates"]
    } == {
        "pivot_slicer_structural_edits",
        "external_link_relationship_preserving_edits",
        "additional_high_risk_feature_edits",
    }
    render_frontier = {
        candidate["id"]: candidate
        for candidate in render_requirement["evidence"]["frontier_candidates"]
    }
    assert render_frontier["pivot_slicer_structural_edits"][
        "observed_report_count"
    ] == 14
    assert render_frontier["pivot_slicer_structural_edits"][
        "expected_report_count"
    ] == 14
    assert render_frontier["pivot_slicer_structural_edits"][
        "missing_report_count"
    ] == 0
    assert render_frontier["pivot_slicer_structural_edits"]["missing_reports"] == []
    assert render_frontier["pivot_slicer_structural_edits"]["observed_reports"] == [
        "pivot_slicer_structural_render_equivalence",
        "slicer_shared_two_pivots_sidecar_add_conditional_formatting_render_equivalence",
        "slicer_shared_two_pivots_sidecar_add_data_validation_render_equivalence",
        "slicer_shared_two_pivots_sidecar_copy_remove_sheet_render_equivalence",
        "slicer_shared_two_pivots_sidecar_move_formula_range_render_delta",
        "slicer_shared_two_pivots_sidecar_move_marker_range_render_delta",
        "slicer_shared_two_pivots_sidecar_neutral_feature_render_equivalence",
        "slicer_shared_two_pivots_sidecar_rename_sheet_render_equivalence",
        "timeline_slicer_add_conditional_formatting_render_equivalence",
        "timeline_slicer_copy_remove_sheet_render_equivalence",
        "timeline_slicer_move_formula_range_render_delta",
        "timeline_slicer_move_marker_range_render_delta",
        "timeline_slicer_neutral_feature_render_equivalence",
        "timeline_slicer_rename_sheet_render_equivalence",
    ]
    assert render_frontier["external_link_relationship_preserving_edits"][
        "observed_report_count"
    ] == 8
    assert render_frontier["external_link_relationship_preserving_edits"][
        "expected_report_count"
    ] == 8
    assert render_frontier["external_link_relationship_preserving_edits"][
        "missing_report_count"
    ] == 0
    assert render_frontier["external_link_relationship_preserving_edits"][
        "observed_reports"
    ] == [
        "external_link_add_conditional_formatting_render_equivalence",
        "external_link_add_data_validation_render_equivalence",
        "external_link_add_remove_chart_render_equivalence",
        "external_link_copy_first_sheet_native_excel_page_multiset_equivalence",
        "external_link_copy_remove_sheet_render_equivalence",
        "external_link_move_formula_range_render_delta",
        "external_link_move_marker_range_render_delta",
        "external_link_rename_sheet_render_equivalence",
    ]
    assert render_frontier["additional_high_risk_feature_edits"][
        "observed_report_count"
    ] == 14
    assert render_frontier["additional_high_risk_feature_edits"][
        "expected_report_count"
    ] == 14
    assert render_frontier["additional_high_risk_feature_edits"][
        "missing_report_count"
    ] == 0
    assert render_frontier["additional_high_risk_feature_edits"]["observed_reports"] == [
        "excel_render_delete_first_col_delta_full_pack_report",
        "excel_render_delete_first_row_delta_full_pack_report",
        "excel_render_delete_marker_tail_col_delta_full_pack_report",
        "excel_render_delete_marker_tail_row_delta_full_pack_report",
        "excel_render_insert_tail_col_delta_full_pack_report",
        "excel_render_insert_tail_row_delta_full_pack_report",
        "excel_render_marker_cell_delta_full_pack_report",
        "excel_render_move_formula_range_delta_full_pack_report",
        "excel_render_move_marker_range_delta_full_pack_report",
        "excel_render_style_cell_delta_full_pack_report",
        "slicer_shared_two_pivots_sidecar_delete_first_col_render_delta",
        "slicer_shared_two_pivots_sidecar_delete_first_row_render_delta",
        "timeline_slicer_delete_first_col_render_delta",
        "timeline_slicer_delete_first_row_render_delta",
    ]
    render_delta_evidence = render_requirement["evidence"]["render_delta_evidence"]
    assert render_delta_evidence["required_report_count"] == len(
        completion.RENDER_DELTA_EVIDENCE_REPORTS
    )
    assert render_delta_evidence["present_report_count"] == len(
        completion.RENDER_DELTA_EVIDENCE_REPORTS
    )
    assert render_delta_evidence["missing_reports"] == []
    assert render_delta_evidence["ready_report_count"] == len(
        completion.RENDER_DELTA_EVIDENCE_REPORTS
    )
    assert render_delta_evidence["excel_report_count"] == len(
        completion.RENDER_DELTA_EVIDENCE_REPORTS
    )
    assert render_delta_evidence["result_count"] == len(
        completion.RENDER_DELTA_EVIDENCE_REPORTS
    )
    assert render_delta_evidence["changed_count"] == len(
        completion.RENDER_DELTA_EVIDENCE_REPORTS
    )
    assert render_delta_evidence["unchanged_count"] == 0
    assert render_delta_evidence["failure_count"] == 0
    assert render_delta_evidence["inconclusive_count"] == 0
    assert render_delta_evidence["reports"] == sorted(
        completion.RENDER_DELTA_EVIDENCE_REPORTS
    )
    assert render_delta_evidence["observed_mutations"] == sorted(
        {
            _render_delta_mutation_for_report(report_name)
            for report_name in completion.RENDER_DELTA_EVIDENCE_REPORTS
        }
    )
    assert render_requirement["evidence"]["coverage_matrix"][
        "expected_mutation_count"
    ] == len(completion.EXPECTED_RENDER_EQUIVALENCE_MUTATIONS)
    assert render_requirement["evidence"]["coverage_matrix"][
        "observed_expected_mutation_count"
    ] == 1
    assert render_requirement["evidence"]["coverage_matrix"][
        "missing_expected_mutation_count"
    ] == len(completion.EXPECTED_RENDER_EQUIVALENCE_MUTATIONS) - 1
    assert render_requirement["evidence"]["coverage_matrix"][
        "unpassed_expected_mutation_count"
    ] == 0
    assert render_requirement["evidence"]["coverage_matrix"][
        "current_target_ready"
    ] is False
    assert "current render-equivalence target matrix covers 1 of" in (
        render_requirement["reason"]
    )
    assert "current target ready is False" in render_requirement["reason"]
    assert "pinned visual-delta render evidence" in render_requirement["reason"]
    assert (
        "next frontier ledger lists "
        f"{len(completion.RENDER_EQUIVALENCE_FRONTIER_CANDIDATES)} "
        "candidate evidence lanes"
    ) in render_requirement["reason"]
    assert "missing expected buckets" in render_requirement["reason"]
    interaction_requirement = next(
        requirement
        for requirement in report["missing_requirements"]
        if requirement["id"] == "broader_click_level_interaction_variants"
    )
    assert interaction_requirement["evidence"]["probe_report_count"] > 0
    assert interaction_requirement["evidence"]["raw_result_count"] > 0
    assert interaction_requirement["evidence"]["known_boundary_failure_count"] == len(
        completion.KNOWN_UI_INTERACTION_BOUNDARY_REPORTS
    )
    assert interaction_requirement["evidence"]["diagnostic_non_state_change_failure_count"] == 0
    assert interaction_requirement["evidence"]["unresolved_non_boundary_failure_count"] == 0
    assert interaction_requirement["evidence"]["non_boundary_failure_count"] == 0
    assert interaction_requirement["evidence"]["failed_raw_reports"] == sorted(
        completion.KNOWN_UI_INTERACTION_BOUNDARY_REPORTS
    )
    assert interaction_requirement["evidence"]["known_boundary_reports"] == sorted(
        completion.KNOWN_UI_INTERACTION_BOUNDARY_REPORTS
    )
    assert interaction_requirement["evidence"]["frontier_candidate_count"] == len(
        completion.UI_INTERACTION_FRONTIER_CANDIDATES
    )
    assert interaction_requirement["evidence"]["frontier_expected_report_count"] == 81
    assert interaction_requirement["evidence"]["frontier_observed_report_count"] == 81
    assert interaction_requirement["evidence"]["frontier_missing_report_count"] == 0
    assert interaction_requirement["evidence"]["frontier_missing_candidate_count"] == 0
    assert interaction_requirement["evidence"]["frontier_empty_candidate_count"] == 0
    assert interaction_requirement["evidence"]["frontier_missing_candidates"] == []
    assert interaction_requirement["evidence"]["frontier_empty_candidates"] == []
    assert interaction_requirement["evidence"]["frontier_evidence_ready"] is True
    assert {
        candidate["id"]
        for candidate in interaction_requirement["evidence"]["frontier_candidates"]
    } == {
        "broader_embedded_control_variants",
        "broader_slicer_timeline_variants",
        "broader_prompt_variants",
    }
    interaction_frontier = {
        candidate["id"]: candidate
        for candidate in interaction_requirement["evidence"]["frontier_candidates"]
    }
    assert interaction_frontier["broader_embedded_control_variants"][
        "observed_report_count"
    ] == 18
    assert interaction_frontier["broader_embedded_control_variants"][
        "expected_report_count"
    ] == 18
    assert interaction_frontier["broader_embedded_control_variants"][
        "missing_report_count"
    ] == 0
    assert interaction_frontier["broader_embedded_control_variants"][
        "missing_reports"
    ] == []
    assert interaction_frontier["broader_embedded_control_variants"][
        "observed_reports"
    ] == [
        "excel_ui_interaction_add_conditional_formatting_control_evidence",
        "excel_ui_interaction_add_data_validation_control_evidence",
        "excel_ui_interaction_add_data_validation_umya_listbox_control_evidence",
        "excel_ui_interaction_add_remove_chart_control_evidence",
        "excel_ui_interaction_copy_remove_button_control_evidence",
        "excel_ui_interaction_copy_remove_control_evidence",
        "excel_ui_interaction_copy_remove_umya_listbox_control_evidence",
        "excel_ui_interaction_marker_button_control_evidence",
        "excel_ui_interaction_marker_control_evidence",
        "excel_ui_interaction_marker_umya_listbox_control_evidence",
        "excel_ui_interaction_move_formula_range_control_evidence",
        "excel_ui_interaction_move_formula_range_umya_listbox_control_evidence",
        "excel_ui_interaction_move_marker_range_control_evidence",
        "excel_ui_interaction_move_marker_range_umya_listbox_control_evidence",
        "excel_ui_interaction_rename_external_oracle_prompt_control_evidence",
        "excel_ui_interaction_style_button_control_evidence",
        "excel_ui_interaction_style_control_evidence",
        "excel_ui_interaction_style_umya_listbox_control_evidence",
    ]
    assert interaction_frontier["broader_slicer_timeline_variants"][
        "observed_report_count"
    ] == 33
    assert interaction_frontier["broader_slicer_timeline_variants"][
        "expected_report_count"
    ] == 33
    assert interaction_frontier["broader_slicer_timeline_variants"][
        "missing_report_count"
    ] == 0
    assert interaction_frontier["broader_slicer_timeline_variants"][
        "observed_reports"
    ] == [
        "excel_ui_interaction_add_conditional_formatting_pivot_slicer_evidence",
        "excel_ui_interaction_add_conditional_formatting_shared_slicer_evidence",
        "excel_ui_interaction_add_conditional_formatting_timeline_evidence",
        "excel_ui_interaction_add_data_validation_pivot_slicer_evidence",
        "excel_ui_interaction_add_data_validation_shared_slicer_evidence",
        "excel_ui_interaction_add_data_validation_table_slicer_evidence",
        "excel_ui_interaction_add_data_validation_timeline_evidence",
        "excel_ui_interaction_add_remove_chart_shared_slicer_evidence",
        "excel_ui_interaction_add_remove_chart_timeline_evidence",
        "excel_ui_interaction_copy_remove_external_tool_pivot_slicer_evidence",
        "excel_ui_interaction_copy_remove_pivot_chart_slicer_evidence",
        "excel_ui_interaction_copy_remove_table_slicer_evidence",
        "excel_ui_interaction_copy_remove_timeline_evidence",
        "excel_ui_interaction_insert_tail_col_shared_slicer_evidence",
        "excel_ui_interaction_insert_tail_row_shared_slicer_evidence",
        "excel_ui_interaction_marker_external_tool_pivot_slicer_evidence",
        "excel_ui_interaction_marker_pivot_chart_slicer_evidence",
        "excel_ui_interaction_marker_table_slicer_evidence",
        "excel_ui_interaction_marker_timeline_evidence",
        "excel_ui_interaction_move_formula_range_shared_slicer_evidence",
        "excel_ui_interaction_move_formula_range_timeline_evidence",
        "excel_ui_interaction_move_marker_range_shared_slicer_evidence",
        "excel_ui_interaction_move_marker_range_timeline_evidence",
        "excel_ui_interaction_rename_external_oracle_pivot_slicer_timeline_evidence",
        "excel_ui_interaction_rename_shared_slicer_evidence",
        "excel_ui_interaction_style_external_tool_pivot_slicer_evidence",
        "excel_ui_interaction_style_pivot_chart_slicer_evidence",
        "excel_ui_interaction_style_table_slicer_evidence",
        "excel_ui_interaction_style_timeline_evidence",
        "slicer_shared_two_pivots_sidecar_copy_remove_ui_interaction_evidence",
        "slicer_shared_two_pivots_sidecar_marker_ui_interaction_evidence",
        "slicer_shared_two_pivots_sidecar_style_ui_interaction_evidence",
        "slicer_shared_two_pivots_sidecar_ui_interaction_evidence",
    ]
    assert interaction_frontier["broader_prompt_variants"][
        "observed_report_count"
    ] == 30
    assert interaction_frontier["broader_prompt_variants"][
        "expected_report_count"
    ] == 30
    assert interaction_frontier["broader_prompt_variants"]["missing_report_count"] == 0
    assert interaction_frontier["broader_prompt_variants"]["observed_reports"] == [
        "excel_ui_interaction_add_data_validation_external_link_current_prompt_evidence",
        "excel_ui_interaction_add_data_validation_external_link_forced_prompt_evidence",
        "excel_ui_interaction_add_data_validation_umya_external_link_forced_prompt_evidence",
        "excel_ui_interaction_add_remove_chart_external_link_current_setting_evidence",
        "excel_ui_interaction_add_remove_chart_external_link_forced_prompt_evidence",
        "excel_ui_interaction_add_remove_chart_macro_evidence",
        "excel_ui_interaction_add_remove_chart_umya_external_link_forced_prompt_evidence",
        "excel_ui_interaction_copy_remove_external_link_current_prompt_evidence",
        "excel_ui_interaction_copy_remove_external_link_forced_prompt_evidence",
        "excel_ui_interaction_copy_remove_umya_external_link_forced_prompt_evidence",
        "excel_ui_interaction_marker_external_link_current_prompt_evidence",
        "excel_ui_interaction_marker_umya_external_link_forced_prompt_evidence",
        "excel_ui_interaction_move_formula_range_external_link_current_prompt_evidence",
        "excel_ui_interaction_move_formula_range_external_link_forced_prompt_evidence",
        "excel_ui_interaction_move_formula_range_macro_evidence",
        "excel_ui_interaction_move_marker_range_external_link_current_prompt_evidence",
        "excel_ui_interaction_move_marker_range_external_link_forced_prompt_evidence",
        "excel_ui_interaction_move_marker_range_macro_evidence",
        "excel_ui_interaction_rename_external_oracle_prompt_control_evidence",
        "excel_ui_interaction_rename_powerview_evidence",
        "excel_ui_interaction_style_external_link_current_prompt_evidence",
        "excel_ui_interaction_style_umya_external_link_forced_prompt_evidence",
        "powerpivot_contoso_sidecar_add_data_validation_unsupported_content_prompt_evidence",
        "powerpivot_contoso_sidecar_add_remove_chart_unsupported_content_prompt_evidence",
        "powerpivot_contoso_sidecar_copy_remove_unsupported_content_prompt_evidence",
        "powerpivot_contoso_sidecar_marker_unsupported_content_prompt_evidence",
        "powerpivot_contoso_sidecar_move_formula_range_unsupported_content_prompt_evidence",
        "powerpivot_contoso_sidecar_move_marker_range_unsupported_content_prompt_evidence",
        "powerpivot_contoso_sidecar_style_unsupported_content_prompt_evidence",
        "powerpivot_contoso_sidecar_unsupported_content_prompt_evidence",
    ]
    assert interaction_requirement["evidence"]["diagnostic_non_state_change_reports"] == []
    assert interaction_requirement["evidence"]["unresolved_failed_raw_reports"] == []
    assert interaction_requirement["evidence"]["coverage_matrix"][
        "mutation_probe_pair_count"
    ] > 0
    assert interaction_requirement["evidence"]["coverage_matrix"][
        "mutation_probe_pairs_with_failures"
    ] == 2
    assert interaction_requirement["evidence"]["coverage_matrix"][
        "expected_mutation_probe_pair_count"
    ] == (
        len(completion.EXPECTED_UI_INTERACTION_MUTATIONS)
        * len(completion.EXPECTED_UI_INTERACTION_PROBES)
    )
    assert interaction_requirement["evidence"]["coverage_matrix"][
        "missing_expected_mutation_probe_pair_count"
    ] == (
        interaction_requirement["evidence"]["coverage_matrix"][
            "expected_mutation_probe_pair_count"
        ]
        - interaction_requirement["evidence"]["coverage_matrix"][
            "observed_expected_mutation_probe_pair_count"
        ]
    )
    assert interaction_requirement["evidence"]["coverage_matrix"][
        "current_target_ready"
    ] is False
    assert "current target ready is False" in interaction_requirement["reason"]
    assert (
        "next frontier ledger lists "
        f"{len(completion.UI_INTERACTION_FRONTIER_CANDIDATES)} "
        "candidate evidence lanes"
    ) in interaction_requirement["reason"]
    assert interaction_requirement["evidence"]["target_status"] == (
        "open_unbounded_click_level_variant_universe"
    )
    future_surface_requirement = next(
        requirement
        for requirement in report["missing_requirements"]
        if requirement["id"] == "future_surface_exhaustiveness"
    )
    assert future_surface_requirement["evidence"]["required_gap_radar_report_count"] == len(
        completion.FUTURE_SURFACE_GAP_RADAR_REPORTS
    )
    assert future_surface_requirement["evidence"]["present_gap_radar_report_count"] == len(
        completion.FUTURE_SURFACE_GAP_RADAR_REPORTS
    )
    assert future_surface_requirement["evidence"]["missing_gap_radar_reports"] == []
    assert future_surface_requirement["evidence"]["clear_gap_radar_report_count"] == len(
        completion.FUTURE_SURFACE_GAP_RADAR_REPORTS
    )
    assert future_surface_requirement["evidence"]["unclear_gap_radar_reports"] == []
    assert future_surface_requirement["evidence"]["missing_clear_status_reports"] == []
    assert future_surface_requirement["evidence"]["fixture_count"] == len(
        completion.FUTURE_SURFACE_GAP_RADAR_REPORTS
    )
    assert "wolfxl_repo_fixtures_gap_radar" in future_surface_requirement["evidence"][
        "gap_radar_reports"
    ]
    assert future_surface_requirement["evidence"]["unknown_part_family_count"] == 0
    assert future_surface_requirement["evidence"]["unknown_relationship_type_count"] == 0
    assert future_surface_requirement["evidence"]["unknown_content_type_count"] == 0
    assert future_surface_requirement["evidence"]["unknown_extension_uri_count"] == 0
    assert "required gap-radar reports present" in future_surface_requirement["reason"]
    assert "cannot prove that no unseen future real-world Excel surface exists" in (
        future_surface_requirement["reason"]
    )
    required_reports = next(
        criterion
        for criterion in report["criteria"]
        if criterion["id"] == "current_evidence_required_reports_present"
    )
    assert required_reports["evidence"]["missing_reports"] == []
    assert required_reports["evidence"]["required_report_count"] == len(
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "pivot_slicer_structural_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "local_project_holdouts_small_neutral_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "current_excel_16_108_delete_first_row_broad_external_tool_slicer_boundary" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "current_excel_16_108_delete_first_col_broad_external_tool_slicer_boundary" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_real_world_ingestion_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_ingest_confidence_sample_100_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_ingest_confidence_sample_100_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_ingest_confidence_sample_100_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_codex_spark_archive_71_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_codex_spark_archive_71_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "sec_investment_advisers_package_only_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_ingest_confidence_cohort_01_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_ingest_confidence_cohort_03_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_ingest_confidence_cohort_04_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_ingest_confidence_cohort_05_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_ingest_confidence_cohort_06_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "sec_commission_votes_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "sec_commission_votes_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "sec_commission_votes_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "sec_enforcement_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "sec_enforcement_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "sec_enforcement_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "domain_consolidation_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "domain_consolidation_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "domain_consolidation_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "domain_international_standards_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "domain_international_standards_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "domain_international_standards_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fed_asset_pricing_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fed_asset_pricing_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fed_asset_pricing_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fdic_qbp_timeseries_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fdic_qbp_timeseries_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fdic_qbp_timeseries_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "umya_result_files_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "calamine_reader_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "domain_ground_truth_valid_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "codexaudit_qoe_workbooks_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fed_aea_papers_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "vendored_openpyxl_corpus_buckets" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "synthgl_real_world_ingestion_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "wolfxl_repo_fixtures_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "vendored_openpyxl_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "powerpivot_contoso_sidecar_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "domain_ground_truth_valid_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "codexaudit_qoe_workbooks_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fed_aea_papers_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "irs_soi_public_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "bea_gdp_public_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "usda_ers_county_public_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "eia_energy_public_neutral_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "census_sitc_renderable_neutral_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fintech_hackathon_demo_neutral_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fed_aea_papers_neutral_render_smoke" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "fed_aea_papers_copy_chart_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "codexaudit_qoe_sample_add_dv_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_50" in completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    assert "random_corpus_holdout_50_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_50_gap_radar_selection" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_50_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_100_gap_radar" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_100_gap_radar_selection" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_100_excel_source_app_open" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_libre_excel_source_app_open_timeout_confirmation" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_100_risk_slice_10_selection" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_100_risk_slice_10_quick_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_20_render_boundary" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_20_renderable_18_neutral_render_smoke" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_20_renderable_18_neutral_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_10_smoke_mutation_report" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_10_add_data_validation_render_smoke" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_10_add_data_validation_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_10_add_conditional_formatting_render_smoke" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert (
        "random_corpus_holdout_10_add_conditional_formatting_render_equivalence"
        in completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_10_chart_copy_render_smoke" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "random_corpus_holdout_10_chart_copy_render_equivalence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "excel_ui_interaction_add_conditional_formatting_shared_slicer_evidence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "excel_ui_interaction_insert_tail_row_shared_slicer_evidence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "excel_ui_interaction_insert_tail_col_shared_slicer_evidence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "excel_ui_interaction_add_remove_chart_external_link_forced_prompt_evidence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "excel_ui_interaction_rename_external_oracle_pivot_slicer_timeline_evidence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "excel_ui_interaction_move_formula_range_external_oracle_evidence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert "excel_ui_interaction_delete_first_row_external_oracle_core_evidence" in (
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )


def test_render_equivalence_evidence_counts_scalar_mutation_reports() -> None:
    report = completion._render_equivalence_evidence(
        {
            "reports": [
                {
                    "name": "excel_render_copy_sheet_equivalence_full_pack_report",
                    "path": "/tmp/copy-sheet-render-equivalence.json",
                    "checks": [
                        {"path": "ready", "actual": True, "passed": True},
                        {"path": "render_engine", "actual": "excel", "passed": True},
                        {
                            "path": "mutation",
                            "actual": "copy_first_sheet",
                            "passed": True,
                        },
                        {"path": "result_count", "actual": 2, "passed": True},
                        {"path": "passed_count", "actual": 2, "passed": True},
                        {"path": "failure_count", "actual": 0, "passed": True},
                        {
                            "path": "inconclusive_count",
                            "actual": 0,
                            "passed": True,
                        },
                    ],
                },
                {
                    "name": "neutral_feature_render_equivalence",
                    "path": "/tmp/neutral-feature-render-equivalence.json",
                    "checks": [
                        {"path": "ready", "actual": True, "passed": True},
                        {"path": "render_engine", "actual": "excel", "passed": True},
                        {
                            "path": "observed_mutations",
                            "actual": ["add_data_validation"],
                            "passed": True,
                        },
                        {"path": "result_count", "actual": 3, "passed": True},
                        {"path": "passed_count", "actual": 3, "passed": True},
                        {"path": "failure_count", "actual": 0, "passed": True},
                        {
                            "path": "inconclusive_count",
                            "actual": 0,
                            "passed": True,
                        },
                    ],
                },
                {
                    "name": (
                        "slicer_shared_two_pivots_sidecar_move_formula_range_"
                        "render_delta"
                    ),
                    "path": "/tmp/pivot-slicer-move-formula-render-delta.json",
                    "checks": [
                        {"path": "ready", "actual": True, "passed": True},
                        {"path": "render_engine", "actual": "excel", "passed": True},
                        {
                            "path": "mutation",
                            "actual": "move_formula_range",
                            "passed": True,
                        },
                        {"path": "changed_count", "actual": 1, "passed": True},
                        {"path": "failure_count", "actual": 0, "passed": True},
                    ],
                },
                {
                    "name": "external_link_rename_sheet_render_equivalence",
                    "path": "/tmp/external-link-rename-sheet-render-equivalence.json",
                    "checks": [
                        {"path": "ready", "actual": True, "passed": True},
                        {"path": "render_engine", "actual": "excel", "passed": True},
                        {
                            "path": "observed_mutations",
                            "actual": ["rename_first_sheet"],
                            "passed": True,
                        },
                        {"path": "result_count", "actual": 1, "passed": True},
                        {"path": "passed_count", "actual": 1, "passed": True},
                        {"path": "failure_count", "actual": 0, "passed": True},
                        {
                            "path": "inconclusive_count",
                            "actual": 0,
                            "passed": True,
                        },
                        {"path": "skipped_count", "actual": 0, "passed": True},
                    ],
                },
                {
                    "name": "external_link_copy_remove_sheet_render_equivalence",
                    "path": "/tmp/external-link-copy-remove-render-equivalence.json",
                    "checks": [
                        {"path": "ready", "actual": True, "passed": True},
                        {"path": "render_engine", "actual": "excel", "passed": True},
                        {
                            "path": "observed_mutations",
                            "actual": ["copy_remove_sheet"],
                            "passed": True,
                        },
                        {"path": "result_count", "actual": 1, "passed": True},
                        {"path": "passed_count", "actual": 1, "passed": True},
                        {"path": "failure_count", "actual": 0, "passed": True},
                        {
                            "path": "inconclusive_count",
                            "actual": 0,
                            "passed": True,
                        },
                        {"path": "skipped_count", "actual": 0, "passed": True},
                    ],
                },
            ]
        }
    )

    assert report["ready_report_count"] == 4
    assert report["excel_report_count"] == 4
    assert report["result_count"] == 7
    assert report["passed_count"] == 7
    assert report["observed_mutations"] == [
        "add_data_validation",
        "copy_first_sheet",
        "copy_remove_sheet",
        "rename_first_sheet",
    ]
    assert report["coverage_matrix"]["observed_mutations"] == [
        "add_data_validation",
        "copy_first_sheet",
        "copy_remove_sheet",
        "rename_first_sheet",
    ]
    assert report["coverage_matrix"]["mutation_count"] == 4
    assert report["coverage_matrix"]["mutation_matrix"]["copy_first_sheet"][
        "single_mutation_result_count"
    ] == 2
    assert report["coverage_matrix"]["expected_mutation_count"] == len(
        completion.EXPECTED_RENDER_EQUIVALENCE_MUTATIONS
    )
    assert report["coverage_matrix"]["observed_expected_mutation_count"] == 4
    assert report["coverage_matrix"]["missing_expected_mutations"] == [
        "add_conditional_formatting",
        "add_remove_chart",
        "retarget_external_links",
    ]
    assert report["coverage_matrix"]["unpassed_expected_mutations"] == []
    pivot_frontier = next(
        candidate
        for candidate in report["frontier_candidates"]
        if candidate["id"] == "pivot_slicer_structural_edits"
    )
    assert pivot_frontier["observed_report_count"] == 1
    assert pivot_frontier["observed_reports"] == [
        "slicer_shared_two_pivots_sidecar_move_formula_range_render_delta"
    ]
    external_link_frontier = next(
        candidate
        for candidate in report["frontier_candidates"]
        if candidate["id"] == "external_link_relationship_preserving_edits"
    )
    assert external_link_frontier["observed_report_count"] == 2
    assert external_link_frontier["observed_reports"] == [
        "external_link_copy_remove_sheet_render_equivalence",
        "external_link_rename_sheet_render_equivalence"
    ]


def test_render_equivalence_coverage_matrix_keeps_multi_mutation_counts_separate() -> None:
    report = completion._render_equivalence_coverage_matrix(
        [
            {
                "name": "single_copy_remove_sheet_equivalence",
                "path": "/tmp/copy-remove-sheet-render-equivalence.json",
                "checks": [
                    {"path": "ready", "actual": True, "passed": True},
                    {"path": "render_engine", "actual": "excel", "passed": True},
                    {"path": "mutation", "actual": "copy_remove_sheet", "passed": True},
                    {"path": "result_count", "actual": 4, "passed": True},
                    {"path": "passed_count", "actual": 4, "passed": True},
                    {"path": "failure_count", "actual": 0, "passed": True},
                    {"path": "inconclusive_count", "actual": 0, "passed": True},
                    {"path": "skipped_count", "actual": 0, "passed": True},
                ],
            },
            {
                "name": "neutral_feature_equivalence",
                "path": "/tmp/neutral-feature-render-equivalence.json",
                "checks": [
                    {"path": "ready", "actual": True, "passed": True},
                    {"path": "render_engine", "actual": "excel", "passed": True},
                    {
                        "path": "observed_mutations",
                        "actual": ["add_data_validation", "add_remove_chart"],
                        "passed": True,
                    },
                    {
                        "path": "mutations",
                        "actual": [
                            "add_data_validation",
                            "add_remove_chart",
                            "missing_requested_mutation",
                        ],
                        "passed": True,
                    },
                    {
                        "path": "missing_mutations",
                        "actual": ["missing_requested_mutation"],
                        "passed": True,
                    },
                    {"path": "result_count", "actual": 6, "passed": True},
                    {"path": "passed_count", "actual": 5, "passed": True},
                    {"path": "failure_count", "actual": 0, "passed": True},
                    {"path": "inconclusive_count", "actual": 1, "passed": True},
                    {"path": "skipped_count", "actual": 0, "passed": True},
                ],
            },
        ]
    )

    assert report["observed_mutations"] == [
        "add_data_validation",
        "add_remove_chart",
        "copy_remove_sheet",
    ]
    assert "missing_requested_mutation" not in report["observed_mutations"]
    assert report["multi_mutation_report_count"] == 1
    assert report["issue_reports"] == ["neutral_feature_equivalence"]
    assert report["mutation_matrix"]["copy_remove_sheet"] == {
        "report_count": 1,
        "ready_report_count": 1,
        "excel_report_count": 1,
        "single_mutation_result_count": 4,
        "single_mutation_passed_count": 4,
        "single_mutation_failure_count": 0,
        "single_mutation_inconclusive_count": 0,
        "single_mutation_non_comparable_count": 0,
        "single_mutation_skipped_count": 0,
        "multi_mutation_report_count": 0,
        "ready_clean_report_count": 1,
        "excel_or_native_clean_report_count": 1,
        "issue_report_count": 0,
        "issue_reports": [],
    }
    assert report["mutation_matrix"]["add_data_validation"][
        "single_mutation_result_count"
    ] == 0
    assert report["mutation_matrix"]["add_data_validation"][
        "multi_mutation_report_count"
    ] == 1
    assert report["mutation_matrix"]["add_remove_chart"]["issue_reports"] == [
        "neutral_feature_equivalence"
    ]


def test_render_equivalence_coverage_matrix_uses_requested_minus_missing_fallback() -> None:
    report = completion._render_equivalence_coverage_matrix(
        [
            {
                "name": "legacy_requested_mutations_equivalence",
                "path": "/tmp/legacy-render-equivalence.json",
                "checks": [
                    {"path": "ready", "actual": True, "passed": True},
                    {"path": "render_engine", "actual": "excel", "passed": True},
                    {
                        "path": "mutations",
                        "actual": ["copy_remove_sheet", "missing_requested_mutation"],
                        "passed": True,
                    },
                    {
                        "path": "missing_mutations",
                        "actual": ["missing_requested_mutation"],
                        "passed": True,
                    },
                    {"path": "result_count", "actual": 3, "passed": True},
                    {"path": "passed_count", "actual": 3, "passed": True},
                    {"path": "failure_count", "actual": 0, "passed": True},
                    {"path": "inconclusive_count", "actual": 0, "passed": True},
                    {"path": "skipped_count", "actual": 0, "passed": True},
                ],
            }
        ]
    )

    assert report["observed_mutations"] == ["copy_remove_sheet"]
    assert "missing_requested_mutation" not in report["mutation_matrix"]
    assert report["mutation_matrix"]["copy_remove_sheet"]["single_mutation_result_count"] == 3


def test_render_equivalence_coverage_matrix_reports_current_target_gaps() -> None:
    report = completion._render_equivalence_coverage_matrix(
        [
            {
                "name": "single_ready_excel_equivalence",
                "path": "/tmp/single-ready-render-equivalence.json",
                "checks": [
                    {"path": "ready", "actual": True, "passed": True},
                    {"path": "render_engine", "actual": "excel", "passed": True},
                    {"path": "mutation", "actual": "copy_remove_sheet", "passed": True},
                    {"path": "result_count", "actual": 4, "passed": True},
                    {"path": "passed_count", "actual": 4, "passed": True},
                    {"path": "failure_count", "actual": 0, "passed": True},
                    {"path": "inconclusive_count", "actual": 0, "passed": True},
                    {"path": "non_comparable_count", "actual": 1, "passed": True},
                    {"path": "skipped_count", "actual": 0, "passed": True},
                ],
            },
            {
                "name": "copy_remove_sheet_native_excel_page_multiset_equivalence",
                "path": "/tmp/page-multiset-equivalence.json",
                "checks": [
                    {"path": "ready", "actual": True, "passed": True},
                    {
                        "path": "left_mutation",
                        "actual": "copy_remove_sheet",
                        "passed": True,
                    },
                    {"path": "right_mutation", "actual": "no_op", "passed": True},
                    {"path": "result_count", "actual": 1, "passed": True},
                    {"path": "passed_count", "actual": 1, "passed": True},
                    {"path": "failure_count", "actual": 0, "passed": True},
                    {"path": "inconclusive_count", "actual": 0, "passed": True},
                    {"path": "skipped_count", "actual": 0, "passed": True},
                ],
            },
            {
                "name": "single_issue_equivalence",
                "path": "/tmp/single-issue-render-equivalence.json",
                "checks": [
                    {"path": "ready", "actual": True, "passed": True},
                    {"path": "render_engine", "actual": "excel", "passed": True},
                    {"path": "mutation", "actual": "rename_first_sheet", "passed": True},
                    {"path": "result_count", "actual": 2, "passed": True},
                    {"path": "passed_count", "actual": 1, "passed": True},
                    {"path": "failure_count", "actual": 1, "passed": True},
                    {"path": "inconclusive_count", "actual": 0, "passed": True},
                    {"path": "skipped_count", "actual": 0, "passed": True},
                ],
            },
        ],
        expected_mutations=(
            "copy_remove_sheet",
            "rename_first_sheet",
            "retarget_external_links",
        ),
    )

    assert report["expected_mutations"] == [
        "copy_remove_sheet",
        "rename_first_sheet",
        "retarget_external_links",
    ]
    assert report["observed_expected_mutation_count"] == 2
    assert report["missing_expected_mutations"] == ["retarget_external_links"]
    assert report["mutation_matrix"]["copy_remove_sheet"]["issue_report_count"] == 1
    assert report["mutation_matrix"]["copy_remove_sheet"][
        "ready_clean_report_count"
    ] == 1
    assert report["mutation_matrix"]["copy_remove_sheet"][
        "excel_or_native_clean_report_count"
    ] == 1
    assert report["unpassed_expected_mutations"] == ["rename_first_sheet"]
    assert report["current_target_ready"] is False


def test_render_equivalence_coverage_matrix_marks_current_target_ready() -> None:
    report = completion._render_equivalence_coverage_matrix(
        [
            {
                "name": "copy_remove_sheet_render_equivalence",
                "path": "/tmp/copy-remove-sheet-render-equivalence.json",
                "checks": [
                    {"path": "ready", "actual": True, "passed": True},
                    {"path": "render_engine", "actual": "excel", "passed": True},
                    {"path": "mutation", "actual": "copy_remove_sheet", "passed": True},
                    {"path": "result_count", "actual": 4, "passed": True},
                    {"path": "passed_count", "actual": 4, "passed": True},
                    {"path": "failure_count", "actual": 0, "passed": True},
                    {"path": "inconclusive_count", "actual": 0, "passed": True},
                    {"path": "non_comparable_count", "actual": 0, "passed": True},
                    {"path": "skipped_count", "actual": 0, "passed": True},
                ],
            },
            {
                "name": "rename_first_sheet_render_equivalence",
                "path": "/tmp/rename-first-sheet-render-equivalence.json",
                "checks": [
                    {"path": "ready", "actual": True, "passed": True},
                    {"path": "render_engine", "actual": "excel", "passed": True},
                    {"path": "mutation", "actual": "rename_first_sheet", "passed": True},
                    {"path": "result_count", "actual": 2, "passed": True},
                    {"path": "passed_count", "actual": 2, "passed": True},
                    {"path": "failure_count", "actual": 0, "passed": True},
                    {"path": "inconclusive_count", "actual": 0, "passed": True},
                    {"path": "non_comparable_count", "actual": 0, "passed": True},
                    {"path": "skipped_count", "actual": 0, "passed": True},
                ],
            },
        ],
        expected_mutations=("copy_remove_sheet", "rename_first_sheet"),
    )

    assert report["observed_expected_mutation_count"] == 2
    assert report["missing_expected_mutations"] == []
    assert report["unpassed_expected_mutations"] == []
    assert report["current_target_ready"] is True


def test_render_equivalence_coverage_matrix_rejects_non_excel_clean_target() -> None:
    report = completion._render_equivalence_coverage_matrix(
        [
            {
                "name": "libreoffice_copy_remove_sheet_render_equivalence",
                "path": "/tmp/libreoffice-render-equivalence.json",
                "checks": [
                    {"path": "ready", "actual": True, "passed": True},
                    {"path": "render_engine", "actual": "libreoffice", "passed": True},
                    {"path": "mutation", "actual": "copy_remove_sheet", "passed": True},
                    {"path": "result_count", "actual": 1, "passed": True},
                    {"path": "passed_count", "actual": 1, "passed": True},
                    {"path": "failure_count", "actual": 0, "passed": True},
                    {"path": "inconclusive_count", "actual": 0, "passed": True},
                    {"path": "skipped_count", "actual": 0, "passed": True},
                ],
            }
        ],
        expected_mutations=("copy_remove_sheet",),
    )

    assert report["mutation_matrix"]["copy_remove_sheet"][
        "ready_clean_report_count"
    ] == 1
    assert report["mutation_matrix"]["copy_remove_sheet"][
        "excel_or_native_clean_report_count"
    ] == 0
    assert report["unpassed_expected_mutations"] == ["copy_remove_sheet"]
    assert report["current_target_ready"] is False


def test_ui_interaction_coverage_matrix_groups_mutations_and_probe_statuses() -> None:
    report = completion._ui_interaction_coverage_matrix(
        [
            {
                "name": "excel_ui_interaction_source_probe",
                "checks": [
                    {"path": "results.0.probe", "actual": "slicer_selection_state"},
                    {"path": "results.0.status", "actual": "passed"},
                    {"path": "results.1.probe", "actual": "pivot_refresh_state"},
                    {"path": "results.1.status", "actual": "passed"},
                ],
            },
            {
                "name": "known_boundary_report",
                "checks": [
                    {"path": "mutation", "actual": "delete_first_row"},
                    {"path": "results.0.probe", "actual": "slicer_selection_state"},
                    {"path": "results.0.status", "actual": "failed"},
                    {"path": "results.1.probe", "actual": "pivot_refresh_state"},
                    {"path": "results.1.status", "actual": "passed"},
                ],
            },
            {
                "name": "diagnostic_report",
                "checks": [
                    {"path": "results.0.probe", "actual": "timeline_selection_state"},
                    {"path": "results.0.status", "actual": "failed"},
                ],
            },
        ],
        known_boundary_reports={"known_boundary_report"},
        diagnostic_reports={"diagnostic_report"},
    )

    assert report["observed_mutations"] == ["delete_first_row", "source"]
    assert report["observed_probes"] == [
        "pivot_refresh_state",
        "slicer_selection_state",
        "timeline_selection_state",
    ]
    assert report["mutation_probe_pair_count"] == 5
    assert report["mutation_probe_pairs_with_failures"] == 2
    assert report["expected_mutation_probe_pair_count"] == (
        len(completion.EXPECTED_UI_INTERACTION_MUTATIONS)
        * len(completion.EXPECTED_UI_INTERACTION_PROBES)
    )
    assert report["observed_expected_mutation_probe_pair_count"] == 5
    assert report["missing_expected_mutation_probe_pair_count"] == (
        report["expected_mutation_probe_pair_count"] - 5
    )
    assert {
        (pair["mutation"], pair["probe"])
        for pair in report["unpassed_expected_mutation_probe_pairs"]
    } == {
        ("delete_first_row", "slicer_selection_state"),
        ("source", "timeline_selection_state"),
    }
    assert report["boundary_only_expected_mutation_probe_pair_count"] == 1
    assert report["diagnostic_only_expected_mutation_probe_pair_count"] == 1
    assert report["mutation_probe_matrix"]["delete_first_row"][
        "slicer_selection_state"
    ] == {
        "passed": 0,
        "failed": 1,
        "known_boundary_failed": 1,
        "diagnostic_failed": 0,
    }
    assert report["mutation_probe_matrix"]["source"]["timeline_selection_state"] == {
        "passed": 0,
        "failed": 1,
        "known_boundary_failed": 0,
        "diagnostic_failed": 1,
    }


def test_ui_interaction_coverage_matrix_infers_passed_status_from_clean_report() -> None:
    report = completion._ui_interaction_coverage_matrix(
        [
            {
                "name": "excel_ui_interaction_external_link_current_prompt_click",
                "checks": [
                    {"path": "failure_count", "actual": 0},
                    {"path": "results.0.probe", "actual": "external_link_update_prompt"},
                ],
            },
        ],
        known_boundary_reports=set(),
        diagnostic_reports=set(),
    )

    assert report["mutation_probe_matrix"]["source"][
        "external_link_update_prompt"
    ] == {
        "passed": 1,
        "failed": 0,
        "known_boundary_failed": 0,
        "diagnostic_failed": 0,
    }
    assert {
        "mutation": "source",
        "probe": "external_link_update_prompt",
    } not in report["unpassed_expected_mutation_probe_pairs"]


def test_ui_interaction_coverage_matrix_marks_current_target_ready() -> None:
    report = completion._ui_interaction_coverage_matrix(
        [
            {
                "name": "excel_ui_interaction_source_probe",
                "checks": [
                    {"path": "results.0.probe", "actual": "slicer_selection_state"},
                    {"path": "results.0.status", "actual": "passed"},
                    {"path": "results.1.probe", "actual": "pivot_refresh_state"},
                    {"path": "results.1.status", "actual": "passed"},
                ],
            },
            {
                "name": "excel_ui_interaction_copy_remove_sheet_probe",
                "checks": [
                    {"path": "mutation", "actual": "copy_remove_sheet"},
                    {"path": "results.0.probe", "actual": "slicer_selection_state"},
                    {"path": "results.0.status", "actual": "passed"},
                    {"path": "results.1.probe", "actual": "pivot_refresh_state"},
                    {"path": "results.1.status", "actual": "passed"},
                ],
            },
        ],
        known_boundary_reports=set(),
        diagnostic_reports=set(),
        expected_mutations=("source", "copy_remove_sheet"),
        expected_probes=("slicer_selection_state", "pivot_refresh_state"),
    )

    assert report["observed_expected_mutation_probe_pair_count"] == 4
    assert report["missing_expected_mutation_probe_pairs"] == []
    assert report["unpassed_expected_mutation_probe_pairs"] == []
    assert report["current_target_ready"] is True


def test_completion_claim_audit_requires_named_current_evidence_reports(
    tmp_path: Path,
) -> None:
    manifest = _write_bundle_manifest(tmp_path, ready=True, include_required_reports=False)

    report = completion.audit_completion_claim(manifest)

    assert report["current_supported_claim_ready"] is False
    assert report["exhaustive_claim_ready"] is False
    assert report["bundle_audit"]["ready"] is True
    required_reports = next(
        criterion
        for criterion in report["criteria"]
        if criterion["id"] == "current_evidence_required_reports_present"
    )
    assert required_reports["status"] == "missing"
    assert "combined_all_evidence_gate" in required_reports["evidence"]["missing_reports"]
    assert report["missing_requirement_count"] == 5


def test_completion_claim_audit_blocks_current_claim_when_bundle_is_stale(
    tmp_path: Path,
) -> None:
    manifest = _write_bundle_manifest(tmp_path, ready=False, include_required_reports=True)

    report = completion.audit_completion_claim(manifest)

    assert report["current_supported_claim_ready"] is False
    assert report["exhaustive_claim_ready"] is False
    stale_report_count = len(json.loads(manifest.read_text())["reports"])
    assert report["bundle_audit"]["issue_count"] == stale_report_count
    required_reports = next(
        criterion
        for criterion in report["criteria"]
        if criterion["id"] == "current_evidence_required_reports_present"
    )
    assert required_reports["status"] == "satisfied"
    assert required_reports["evidence"]["missing_reports"] == []
    assert report["missing_requirements"][0]["id"] == "current_evidence_bundle_ready"


def test_completion_claim_audit_summarizes_stale_bundle_lanes(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "missing_headless",
                        "path": "missing-headless.json",
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_fidelity_mutations.py fixtures "
                            "--compact-report --report-only"
                        ),
                        "expect": [{"path": "ready", "equals": True}],
                    },
                    {
                        "name": "missing_render",
                        "path": "missing-render.json",
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py --render-engine excel"
                        ),
                        "expect": [{"path": "ready", "equals": True}],
                    },
                    {
                        "name": "missing_interactive",
                        "path": "missing-interactive.json",
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_interactive_probe.py"
                        ),
                        "expect": [{"path": "ready", "equals": True}],
                    },
                ]
            }
        )
    )

    report = completion.audit_completion_claim(manifest)

    expected_lane_counts = {
        "excel_gui_interactive": 1,
        "headless": 1,
        "render": 1,
    }
    assert report["bundle_audit"]["ready"] is False
    assert report["bundle_audit"]["producer_lane_counts"] == expected_lane_counts
    assert report["bundle_audit"]["missing_report_lane_counts"] == expected_lane_counts
    assert report["bundle_audit"]["volatile_missing_report_lane_counts"] == {}
    assert report["bundle_audit"]["missing_report_action_counts"] == {
        "defer_excel_batch": 2,
        "rerun_headless": 1,
    }
    bundle_ready = next(
        criterion
        for criterion in report["criteria"]
        if criterion["id"] == "current_evidence_bundle_ready"
    )
    assert bundle_ready["evidence"]["producer_lane_counts"] == expected_lane_counts
    assert bundle_ready["evidence"]["missing_report_lane_counts"] == expected_lane_counts
    assert bundle_ready["evidence"]["volatile_missing_report_lane_counts"] == {}
    assert bundle_ready["evidence"]["missing_report_action_counts"] == {
        "defer_excel_batch": 2,
        "rerun_headless": 1,
    }


def test_completion_claim_strict_current_evidence_only_checks_bundle_freshness(
    tmp_path: Path,
    capsys,
) -> None:
    ready_manifest = _write_bundle_manifest(
        tmp_path / "ready", ready=True, include_required_reports=True
    )
    stale_manifest = _write_bundle_manifest(
        tmp_path / "stale", ready=False, include_required_reports=True
    )

    ready_code = completion.main([str(ready_manifest), "--strict-current-evidence"])
    ready_payload = json.loads(capsys.readouterr().out)
    stale_code = completion.main([str(stale_manifest), "--strict-current-evidence"])
    stale_payload = json.loads(capsys.readouterr().out)

    assert ready_code == 0
    assert ready_payload["current_supported_claim_ready"] is True
    assert ready_payload["exhaustive_claim_ready"] is False
    assert stale_code == 1
    assert stale_payload["current_supported_claim_ready"] is False


def test_completion_claim_can_require_portable_current_evidence(
    tmp_path: Path,
) -> None:
    report_path = (
        Path(tempfile.gettempdir())
        / f"wolfxl-current-claim-volatile-{tmp_path.name}.json"
    )
    report_path.write_text(json.dumps({"ready": True}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": name,
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py --strict",
                        "expect": [{"path": "ready", "equals": True}],
                    }
                    for name in completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
                ]
            }
        )
    )

    try:
        report = completion.audit_completion_claim(
            manifest,
            require_portable_paths=True,
        )
    finally:
        report_path.unlink(missing_ok=True)

    assert report["current_supported_claim_ready"] is False
    assert report["bundle_audit"]["ready"] is False
    assert report["bundle_audit"]["require_portable_paths"] is True
    assert report["bundle_audit"]["absolute_path_count"] == len(
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert report["bundle_audit"]["volatile_path_count"] == len(
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert report["bundle_audit"]["portable_paths_ready"] is False
    assert "current_evidence_bundle_ready" in report["missing_requirement_ids"]
    assert {
        issue["check"] for issue in report["bundle_audit"]["issues"]
    } == {
        "duplicate_path",
        "portable_path",
    }


def test_completion_claim_cli_can_require_portable_current_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    report_path = (
        Path(tempfile.gettempdir())
        / f"wolfxl-current-claim-cli-volatile-{tmp_path.name}.json"
    )
    report_path.write_text(json.dumps({"ready": True}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": name,
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py --strict",
                        "expect": [{"path": "ready", "equals": True}],
                    }
                    for name in completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
                ]
            }
        )
    )

    try:
        code = completion.main(
            [
                str(manifest),
                "--strict-current-evidence",
                "--require-portable-current-evidence",
            ]
        )
    finally:
        report_path.unlink(missing_ok=True)

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["current_supported_claim_ready"] is False
    assert payload["bundle_audit"]["require_portable_paths"] is True
    assert payload["bundle_audit"]["absolute_path_count"] == len(
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )
    assert payload["bundle_audit"]["volatile_path_count"] == len(
        completion.REQUIRED_CURRENT_EVIDENCE_REPORTS
    )


def test_completion_claim_strict_claim_fails_until_open_requirements_close(
    tmp_path: Path,
    capsys,
) -> None:
    manifest = _write_bundle_manifest(tmp_path, ready=True, include_required_reports=True)

    code = completion.main([str(manifest), "--strict-claim"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 1
    assert payload["current_supported_claim_ready"] is True
    assert payload["exhaustive_claim_ready"] is False


def test_completion_claim_marks_corpus_requirement_satisfied_at_customer_scale(
    tmp_path: Path,
) -> None:
    manifest = _write_bundle_manifest(
        tmp_path,
        ready=True,
        include_required_reports=True,
        corpus_source_count=completion.CUSTOMER_SCALE_MIN_SOURCES,
        corpus_workbook_count=completion.CUSTOMER_SCALE_MIN_WORKBOOKS,
    )

    report = completion.audit_completion_claim(manifest)

    corpus_requirement = next(
        requirement
        for requirement in report["criteria"]
        if requirement["id"] == "broader_real_world_corpus_diversity"
    )
    assert corpus_requirement["status"] == "satisfied"
    assert "satisfies the customer-scale corpus target" in corpus_requirement["reason"]
    assert "remains below" not in corpus_requirement["reason"]
    assert corpus_requirement["evidence"]["workbook_deficit"] == 0
    assert corpus_requirement["evidence"]["source_deficit"] == 0
    assert "broader_real_world_corpus_diversity" not in report["missing_requirement_ids"]


def test_completion_claim_classifies_paired_ui_diagnostic_non_state_change_rechecks(
    tmp_path: Path,
) -> None:
    manifest = _write_bundle_manifest(
        tmp_path,
        ready=True,
        include_required_reports=True,
        include_diagnostic_non_state_change_reports=True,
    )

    report = completion.audit_completion_claim(manifest)

    interaction_requirement = next(
        requirement
        for requirement in report["missing_requirements"]
        if requirement["id"] == "broader_click_level_interaction_variants"
    )
    evidence = interaction_requirement["evidence"]
    expected_diagnostics = sorted(
        completion.KNOWN_UI_INTERACTION_DIAGNOSTIC_NON_STATE_CHANGE_REPORTS
    )
    assert evidence["raw_failure_count"] == (
        len(completion.KNOWN_UI_INTERACTION_BOUNDARY_REPORTS) + 3
    )
    assert evidence["known_boundary_failure_count"] == len(
        completion.KNOWN_UI_INTERACTION_BOUNDARY_REPORTS
    )
    assert evidence["observed_non_boundary_failure_count"] == 3
    assert evidence["diagnostic_non_state_change_failure_count"] == 3
    assert evidence["diagnostic_non_state_change_reports"] == expected_diagnostics
    assert {
        pairing["diagnostic_report"]
        for pairing in evidence["diagnostic_non_state_change_pairings"]
    } == set(expected_diagnostics)
    assert evidence["unresolved_non_boundary_failure_count"] == 0
    assert evidence["non_boundary_failure_count"] == 0
    assert evidence["unresolved_failed_raw_reports"] == []
    assert evidence["failed_raw_reports"] == sorted(
        [
            *completion.KNOWN_UI_INTERACTION_BOUNDARY_REPORTS,
            *completion.KNOWN_UI_INTERACTION_DIAGNOSTIC_NON_STATE_CHANGE_REPORTS,
        ]
    )
    assert evidence["coverage_matrix"]["mutation_probe_pairs_with_failures"] == 5


def test_completion_claim_counts_unexpected_ui_failures_from_failed_expectations(
    tmp_path: Path,
) -> None:
    manifest = _write_bundle_manifest(
        tmp_path,
        ready=True,
        include_required_reports=True,
        include_unexpected_ui_failure_report=True,
    )

    report = completion.audit_completion_claim(manifest)

    interaction_requirement = next(
        requirement
        for requirement in report["missing_requirements"]
        if requirement["id"] == "broader_click_level_interaction_variants"
    )
    evidence = interaction_requirement["evidence"]
    assert report["bundle_audit"]["ready"] is False
    assert evidence["raw_failure_count"] == (
        len(completion.KNOWN_UI_INTERACTION_BOUNDARY_REPORTS) + 1
    )
    assert evidence["known_boundary_failure_count"] == len(
        completion.KNOWN_UI_INTERACTION_BOUNDARY_REPORTS
    )
    assert evidence["unresolved_non_boundary_failure_count"] == 1
    assert evidence["unresolved_failed_raw_reports"] == [
        "excel_ui_interaction_unexpected_failure_probe"
    ]
    assert "excel_ui_interaction_unexpected_failure_probe" in evidence["failed_raw_reports"]


def _diagnostic_probe_for_report(name: str) -> str:
    if "control" in name:
        return "embedded_control_openability"
    if "timeline" in name:
        return "timeline_selection_state"
    return "slicer_selection_state"


_RENDER_DELTA_MUTATION_TOKENS = (
    ("delete_marker_tail_col", "delete_marker_tail_col"),
    ("delete_marker_tail_row", "delete_marker_tail_row"),
    ("delete_first_col", "delete_first_col"),
    ("delete_first_row", "delete_first_row"),
    ("insert_tail_col", "insert_tail_col"),
    ("insert_tail_row", "insert_tail_row"),
    ("move_formula_range", "move_formula_range"),
    ("move_marker_range", "move_marker_range"),
    ("marker_cell", "marker_cell"),
    ("style_cell", "style_cell"),
)


def _render_delta_mutation_for_report(name: str) -> str:
    for token, mutation in _RENDER_DELTA_MUTATION_TOKENS:
        if token in name:
            return mutation
    raise AssertionError(f"Unhandled render-delta report mutation for {name!r}")


def _write_bundle_manifest(
    tmp_path: Path,
    *,
    ready: bool,
    include_required_reports: bool,
    include_diagnostic_non_state_change_reports: bool = False,
    include_unexpected_ui_failure_report: bool = False,
    corpus_source_count: int = 3,
    corpus_workbook_count: int = 11,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    reports = []
    names = ["current"]
    if include_required_reports:
        names.extend(completion.REQUIRED_CURRENT_EVIDENCE_REPORTS)
        names.extend(
            report_name
            for report_name in completion.RENDER_DELTA_EVIDENCE_REPORTS
            if report_name not in names
        )
        for frontier_reports in completion.RENDER_EQUIVALENCE_FRONTIER_EVIDENCE_REPORTS.values():
            names.extend(
                report_name for report_name in frontier_reports if report_name not in names
            )
    if include_diagnostic_non_state_change_reports:
        names.extend(completion.KNOWN_UI_INTERACTION_DIAGNOSTIC_NON_STATE_CHANGE_REPORTS)
        names.extend(
            completion.KNOWN_UI_INTERACTION_DIAGNOSTIC_NON_STATE_CHANGE_REPORTS.values()
        )
    if include_unexpected_ui_failure_report:
        names.append("excel_ui_interaction_unexpected_failure_probe")
    for index, name in enumerate(names):
        report_path = tmp_path / f"report-{index}.json"
        payload = {"ready": ready}
        expect = [{"path": "ready", "equals": True}]
        if name == "corpus_portfolio_diversity":
            payload.update(
                {
                    "source_count": corpus_source_count,
                    "workbook_count": corpus_workbook_count,
                }
            )
            expect.extend(
                [
                    {"path": "source_count", "equals": corpus_source_count},
                    {"path": "workbook_count", "equals": corpus_workbook_count},
                ]
            )
        if "render_equivalence" in name:
            payload.update(
                {
                    "render_engine": "excel",
                    "observed_mutations": ["add_data_validation"],
                    "result_count": 2,
                    "passed_count": 2,
                    "failure_count": 0,
                    "inconclusive_count": 0,
                    "skipped_count": 0,
                }
            )
            expect.extend(
                [
                    {"path": "render_engine", "equals": "excel"},
                    {"path": "observed_mutations", "equals": ["add_data_validation"]},
                    {"path": "result_count", "equals": 2},
                    {"path": "passed_count", "equals": 2},
                    {"path": "failure_count", "equals": 0},
                    {"path": "inconclusive_count", "equals": 0},
                    {"path": "skipped_count", "equals": 0},
                ]
            )
        if name in completion.FUTURE_SURFACE_GAP_RADAR_REPORTS:
            payload.update(
                {
                    "clear": True,
                    "fixture_count": 1,
                    "unknown_part_family_count": 0,
                    "unknown_relationship_type_count": 0,
                    "unknown_content_type_count": 0,
                    "unknown_extension_uri_count": 0,
                }
            )
            expect.extend(
                [
                    {"path": "clear", "equals": True},
                    {"path": "fixture_count", "equals": 1},
                    {"path": "unknown_part_family_count", "equals": 0},
                    {"path": "unknown_relationship_type_count", "equals": 0},
                    {"path": "unknown_content_type_count", "equals": 0},
                    {"path": "unknown_extension_uri_count", "equals": 0},
                ]
            )
        if name in completion.RENDER_DELTA_EVIDENCE_REPORTS:
            payload.update(
                {
                    "render_engine": "excel",
                    "mutation": _render_delta_mutation_for_report(name),
                    "missing_mutation": False,
                    "result_count": 1,
                    "changed_count": 1,
                    "unchanged_count": 0,
                    "failure_count": 0,
                    "inconclusive_count": 0,
                }
            )
            expect.extend(
                [
                    {"path": "render_engine", "equals": "excel"},
                    {"path": "mutation", "equals": payload["mutation"]},
                    {"path": "missing_mutation", "equals": False},
                    {"path": "result_count", "equals": 1},
                    {"path": "changed_count", "equals": 1},
                    {"path": "unchanged_count", "equals": 0},
                    {"path": "failure_count", "equals": 0},
                    {"path": "inconclusive_count", "equals": 0},
                ]
            )
        ui_frontier_reports = {
            report_name
            for report_names in completion.UI_INTERACTION_FRONTIER_EVIDENCE_REPORTS.values()
            for report_name in report_names
        }
        if name.startswith("excel_ui_interaction_") or name in ui_frontier_reports:
            payload.update({"probe_kind": "excel_ui_interaction", "report_count": 1})
            expect.extend(
                [
                    {"path": "probe_kind", "equals": "excel_ui_interaction"},
                    {"path": "report_count", "equals": 1},
                ]
            )
        if name in completion.KNOWN_UI_INTERACTION_BOUNDARY_REPORTS:
            mutation = (
                "delete_first_col" if "delete_first_col" in name else "delete_first_row"
            )
            payload.update(
                {
                    "probe_kind": "excel_ui_interaction",
                    "completed": True,
                    "mutation": mutation,
                    "result_count": 11,
                    "failure_count": 1,
                    "results": [
                        {"probe": "slicer_selection_state", "status": "failed"}
                    ],
                }
            )
            expect.extend(
                [
                    {"path": "probe_kind", "equals": "excel_ui_interaction"},
                    {"path": "completed", "equals": True},
                    {"path": "mutation", "equals": mutation},
                    {"path": "result_count", "equals": 11},
                    {"path": "failure_count", "equals": 1},
                    {"path": "results.0.probe", "equals": "slicer_selection_state"},
                    {"path": "results.0.status", "equals": "failed"},
                ]
            )
        if name in completion.KNOWN_UI_INTERACTION_DIAGNOSTIC_NON_STATE_CHANGE_REPORTS:
            probe = _diagnostic_probe_for_report(name)
            payload.update(
                {
                    "probe_kind": "excel_ui_interaction",
                    "completed": True,
                    "result_count": 1,
                    "failure_count": 1,
                    "results": [{"probe": probe, "status": "failed"}],
                }
            )
            expect.extend(
                [
                    {"path": "probe_kind", "equals": "excel_ui_interaction"},
                    {"path": "completed", "equals": True},
                    {"path": "result_count", "equals": 1},
                    {"path": "failure_count", "equals": 1},
                    {"path": "results.0.probe", "equals": probe},
                    {"path": "results.0.status", "equals": "failed"},
                ]
            )
        if name in completion.KNOWN_UI_INTERACTION_DIAGNOSTIC_NON_STATE_CHANGE_REPORTS.values():
            probe = _diagnostic_probe_for_report(name)
            payload.update(
                {
                    "probe_kind": "excel_ui_interaction",
                    "completed": True,
                    "result_count": 1,
                    "failure_count": 0,
                    "results": [{"probe": probe, "status": "passed"}],
                }
            )
            expect.extend(
                [
                    {"path": "probe_kind", "equals": "excel_ui_interaction"},
                    {"path": "completed", "equals": True},
                    {"path": "result_count", "equals": 1},
                    {"path": "failure_count", "equals": 0},
                    {"path": "results.0.probe", "equals": probe},
                    {"path": "results.0.status", "equals": "passed"},
                ]
            )
        if name == "excel_ui_interaction_unexpected_failure_probe":
            payload.update(
                {
                    "probe_kind": "excel_ui_interaction",
                    "completed": True,
                    "result_count": 1,
                    "failure_count": 1,
                    "results": [
                        {"probe": "slicer_selection_state", "status": "failed"}
                    ],
                }
            )
            expect.extend(
                [
                    {"path": "probe_kind", "equals": "excel_ui_interaction"},
                    {"path": "completed", "equals": True},
                    {"path": "result_count", "equals": 1},
                    {"path": "failure_count", "equals": 0},
                    {"path": "results.0.probe", "equals": "slicer_selection_state"},
                    {"path": "results.0.status", "equals": "failed"},
                ]
            )
        report_path.write_text(json.dumps(payload))
        reports.append(
            {
                "name": name,
                "path": str(report_path),
                "producer": "uv run --no-sync python scripts/example.py --strict",
                "expect": expect,
            }
        )
    manifest = tmp_path / "bundle.json"
    manifest.write_text(json.dumps({"reports": reports}))
    return manifest
