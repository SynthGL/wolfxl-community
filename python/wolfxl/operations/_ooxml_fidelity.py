#!/usr/bin/env python3
"""Audit OOXML package fidelity between two workbook files.

This is intentionally package-level rather than API-level. It catches the
class of modify-save regressions where a workbook still opens, but an OOXML
dependency has been dropped, orphaned, or left pointing at a missing part.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from ._ooxml_fidelity_constants import MARKER_SENSITIVE_SEMANTIC_FEATURES
from ._ooxml_fidelity_fingerprints import _read_semantic_fingerprints
from ._ooxml_fidelity_models import AuditIssue, FingerprintStats, Snapshot
from ._ooxml_fidelity_package import (
    _classify_feature_parts,
    _read_content_overrides,
    _read_relationships,
    _read_xml_parse_errors,
    _relationship_key,
)
from ._ooxml_fidelity_progress import _emit_audit_progress, _run_audit_phase
from ._ooxml_fidelity_refs import (
    _read_cf_dxf_refs,
    _read_chart_sheet_ref_issues,
    _read_dxfs_count,
    _read_pivot_sheet_ref_issues,
    _read_table_integrity_issues,
    _read_workbook_sheet_ref_issues,
    _read_worksheet_sheet_ref_issues,
)

# This module is the import facade for the OOXML fidelity audit. Callers -- most
# notably `scripts/audit_ooxml_fidelity.py`, which republishes every public
# attribute of this module -- reach the internal helpers through here, so the
# names below stay reachable even though the orchestration code above does not
# call them directly.
from ._ooxml_fidelity_constants import (  # noqa: F401
    CF_EXTENSION_NAMES,
    CONDITIONAL_FORMATTING_MARKERS,
    CT_NS,
    DATA_VALIDATION_MARKERS,
    EXTENSION_MARKERS,
    FEATURE_PART_PREFIXES,
    FORMULA_MARKERS,
    MAIN_NS,
    PAGE_SETUP_MARKERS,
    REL_NS,
    SLICER_EXTENSION_NAMES,
    TIMELINE_EXTENSION_NAMES,
)
from ._ooxml_fidelity_extract import (  # noqa: F401
    _axis_child_val,
    _chart_axes,
    _chart_axis_ids,
    _chart_series,
    _chart_types,
    _defined_name_refs,
    _external_sheet_data,
    _external_sheet_names,
    _is_external_workbook_formula,
    _is_structured_reference_formula,
    _manual_layouts,
    _pivot_cache_fields,
    _pivot_calculated_fields,
    _pivot_calculated_items,
    _pivot_conditional_formats,
    _pivot_data_fields,
    _pivot_field_groups,
    _pivot_field_indices,
    _pivot_formats,
    _pivot_source_names,
    _slicer_items,
    _worksheet_formula_texts,
    _worksheet_formulas,
)
from ._ooxml_fidelity_fingerprints import (  # noqa: F401
    _chart_fingerprint,
    _chart_sheet_fingerprint,
    _chart_style_fingerprint,
    _conditional_formatting_fingerprint,
    _connection_fingerprint,
    _data_model_fingerprint,
    _data_validation_fingerprint,
    _drawing_object_fingerprint,
    _extension_payload_fingerprint,
    _external_link_fingerprint,
    _global_package_part_fingerprint,
    _page_setup_fingerprint,
    _pivot_fingerprint,
    _slicer_fingerprint,
    _structured_reference_fingerprint,
    _style_theme_fingerprint,
    _timeline_fingerprint,
    _workbook_global_fingerprint,
    _worksheet_formula_fingerprint,
    _xml_part_fingerprint,
)
from ._ooxml_fidelity_models import (  # noqa: F401
    Relationship,
    _OptionalAuditIssueFields,
)
from ._ooxml_fidelity_package import (  # noqa: F401
    _feature_xml_parts,
    _is_chart_style_part,
    _read_content_defaults,
    _relationships_by_owner,
    _rels_target_lookup,
    _resolve_relationship_target,
    _source_part_for_rels,
    _worksheet_parts,
)
from ._ooxml_fidelity_refs import (  # noqa: F401
    _cell_col_index,
    _formula_sheet_reference_names,
    _is_formula_error_reference_token,
    _local_sheet_names_from_token,
    _pivot_source_sheet_reference_name,
    _range_width,
    _workbook_sheet_names,
    _worksheet_formula_reference_texts,
)
from ._ooxml_fidelity_xml import (  # noqa: F401
    _all_stable_attrs,
    _attr,
    _children_by_local,
    _extension_fingerprints,
    _first_child_by_local,
    _first_node_by_local,
    _local_name,
    _nodes_by_local,
    _part_contains_any,
    _read_part_bytes_or_none,
    _read_xml_or_none,
    _relationship_id,
    _stable_attrs,
    _text,
    _texts_by_local,
    _vals_by_path,
    _xml_extensions,
    _xml_tree_fingerprint,
)

__all__ = [
    "AuditIssue",
    "FingerprintStats",
    "Relationship",
    "Snapshot",
    "audit",
    "main",
    "snapshot",
]


def snapshot(
    path: Path,
    *,
    compact_semantic_drift: bool = False,
    progress_label: str | None = None,
    phase_prefix: str = "snapshot",
    phase_timings: dict[str, float] | None = None,
) -> Snapshot:
    with zipfile.ZipFile(path) as archive:
        parts = set(archive.namelist())
        _emit_audit_progress(progress_label, phase_prefix, "parts", "done")
        return Snapshot(
            path=str(path),
            parts=parts,
            xml_parse_errors=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.xml_parse_errors",
                lambda: _read_xml_parse_errors(archive),
            ),
            content_overrides=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.content_overrides",
                lambda: _read_content_overrides(archive),
            ),
            relationships=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.relationships",
                lambda: _read_relationships(archive),
            ),
            dxfs_count=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.dxfs_count",
                lambda: _read_dxfs_count(archive),
            ),
            cf_dxf_refs=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.cf_dxf_refs",
                lambda: _read_cf_dxf_refs(archive),
            ),
            table_integrity_issues=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.table_integrity",
                lambda: _read_table_integrity_issues(archive),
            ),
            worksheet_sheet_ref_issues=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.worksheet_sheet_refs",
                lambda: _read_worksheet_sheet_ref_issues(archive, parts),
            ),
            workbook_sheet_ref_issues=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.workbook_sheet_refs",
                lambda: _read_workbook_sheet_ref_issues(archive),
            ),
            chart_sheet_ref_issues=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.chart_sheet_refs",
                lambda: _read_chart_sheet_ref_issues(archive),
            ),
            pivot_sheet_ref_issues=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.pivot_sheet_refs",
                lambda: _read_pivot_sheet_ref_issues(archive, parts),
            ),
            feature_parts=_classify_feature_parts(parts),
            semantic_fingerprints=_run_audit_phase(
                progress_label,
                phase_timings,
                f"{phase_prefix}.semantic_fingerprints",
                lambda: _read_semantic_fingerprints(
                    archive,
                    compact=compact_semantic_drift,
                    progress_label=progress_label,
                    phase_prefix=f"{phase_prefix}.semantic_fingerprints",
                    phase_timings=phase_timings,
                ),
            ),
        )


def audit(
    before: Path,
    after: Path,
    *,
    compact_semantic_drift: bool = False,
    phase_timings: bool = False,
    progress_label: str | None = None,
) -> dict:
    timings: dict[str, float] | None = {} if phase_timings else None
    before_snapshot = _run_audit_phase(
        progress_label,
        timings,
        "before_snapshot",
        lambda: snapshot(
            before,
            compact_semantic_drift=compact_semantic_drift,
            progress_label=progress_label,
            phase_prefix="before_snapshot",
            phase_timings=timings,
        ),
    )
    after_snapshot = _run_audit_phase(
        progress_label,
        timings,
        "after_snapshot",
        lambda: snapshot(
            after,
            compact_semantic_drift=compact_semantic_drift,
            progress_label=progress_label,
            phase_prefix="after_snapshot",
            phase_timings=timings,
        ),
    )
    issues: list[AuditIssue] = []

    missing_parts = _run_audit_phase(
        progress_label,
        timings,
        "compare.missing_parts",
        lambda: sorted(before_snapshot.parts - after_snapshot.parts),
    )
    for part in missing_parts:
        issues.append(
            {
                "severity": "error",
                "kind": "missing_part",
                "part": part,
                "message": f"Part existed before save and is missing after save: {part}",
            }
        )

    _run_audit_phase(
        progress_label,
        timings,
        "compare.relationship_preservation",
        lambda: _audit_relationship_preservation(before_snapshot, after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.xml_well_formed",
        lambda: _audit_xml_well_formed(before_snapshot, after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.dangling_relationships",
        lambda: _audit_dangling_relationships(after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.content_types",
        lambda: _audit_content_type_preservation(before_snapshot, after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.conditional_formatting_refs",
        lambda: _audit_conditional_formatting_refs(after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.table_integrity",
        lambda: _audit_table_integrity(before_snapshot, after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.worksheet_sheet_refs",
        lambda: _audit_worksheet_sheet_refs(before_snapshot, after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.workbook_sheet_refs",
        lambda: _audit_workbook_sheet_refs(before_snapshot, after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.chart_sheet_refs",
        lambda: _audit_chart_sheet_refs(before_snapshot, after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.pivot_sheet_refs",
        lambda: _audit_pivot_sheet_refs(before_snapshot, after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.feature_hotspots",
        lambda: _audit_feature_hotspots(before_snapshot, after_snapshot, issues),
    )
    _run_audit_phase(
        progress_label,
        timings,
        "compare.semantic_fingerprints",
        lambda: _audit_semantic_fingerprints(
            before_snapshot,
            after_snapshot,
            issues,
            compact=compact_semantic_drift,
        ),
    )

    report = {
        "before": _snapshot_summary(before_snapshot),
        "after": _snapshot_summary(after_snapshot),
        "issue_count": len(issues),
        "issues": issues,
    }
    if timings is not None:
        report["phase_timings"] = timings
    return report


def _audit_relationship_preservation(
    before: Snapshot, after: Snapshot, issues: list[AuditIssue]
) -> None:
    before_rels = {_relationship_key(rel): rel for rel in before.relationships}
    after_rels = {_relationship_key(rel): rel for rel in after.relationships}
    for key, rel in sorted(before_rels.items()):
        if key not in after_rels:
            issues.append(
                {
                    "severity": "error",
                    "kind": "missing_relationship",
                    "part": rel.rels_part,
                    "message": (
                        "Relationship existed before save and is missing after save: "
                        f"{rel.rels_part} {rel.rel_id} {rel.rel_type} -> {rel.target}"
                    ),
                }
            )


def _audit_xml_well_formed(before: Snapshot, after: Snapshot, issues: list[AuditIssue]) -> None:
    before_errors = set(before.xml_parse_errors)
    for part, error in after.xml_parse_errors:
        if (part, error) in before_errors:
            continue
        issues.append(
            {
                "severity": "error",
                "kind": "malformed_xml_part",
                "part": part,
                "message": f"{part} is not well-formed XML after save: {error}",
            }
        )


def _audit_dangling_relationships(snapshot_: Snapshot, issues: list[AuditIssue]) -> None:
    for rel in snapshot_.relationships:
        if rel.resolved_target is None:
            continue
        if not _has_part_case_insensitive(snapshot_.parts, rel.resolved_target):
            issues.append(
                {
                    "severity": "error",
                    "kind": "dangling_relationship",
                    "part": rel.rels_part,
                    "message": (
                        f"{rel.rels_part} {rel.rel_id} points to missing {rel.resolved_target}"
                    ),
                }
            )


def _has_part_case_insensitive(parts: set[str], target: str) -> bool:
    target_lc = target.lower()
    return any(part.lower() == target_lc for part in parts)


def _audit_content_type_preservation(
    before: Snapshot, after: Snapshot, issues: list[AuditIssue]
) -> None:
    for part, content_type in sorted(before.content_overrides.items()):
        if part not in after.parts:
            continue
        after_content_type = after.content_overrides.get(part)
        if after_content_type != content_type:
            issues.append(
                {
                    "severity": "error",
                    "kind": "content_type_changed",
                    "part": part,
                    "message": (
                        f"Content type for {part} changed from {content_type!r} "
                        f"to {after_content_type!r}"
                    ),
                }
            )


def _audit_conditional_formatting_refs(snapshot_: Snapshot, issues: list[AuditIssue]) -> None:
    for sheet_part, dxf_id in snapshot_.cf_dxf_refs:
        if dxf_id >= snapshot_.dxfs_count:
            issues.append(
                {
                    "severity": "error",
                    "kind": "conditional_formatting_dxf_out_of_range",
                    "part": sheet_part,
                    "message": (
                        f"{sheet_part} references dxfId={dxf_id}, but styles.xml "
                        f"only has {snapshot_.dxfs_count} <dxf> entries"
                    ),
                }
            )


def _audit_table_integrity(before: Snapshot, after: Snapshot, issues: list[AuditIssue]) -> None:
    _extend_new_issues(before.table_integrity_issues, after.table_integrity_issues, issues)


def _audit_worksheet_sheet_refs(
    before: Snapshot, after: Snapshot, issues: list[AuditIssue]
) -> None:
    _extend_new_issues(before.worksheet_sheet_ref_issues, after.worksheet_sheet_ref_issues, issues)


def _audit_workbook_sheet_refs(before: Snapshot, after: Snapshot, issues: list[AuditIssue]) -> None:
    _extend_new_issues(before.workbook_sheet_ref_issues, after.workbook_sheet_ref_issues, issues)


def _audit_chart_sheet_refs(before: Snapshot, after: Snapshot, issues: list[AuditIssue]) -> None:
    _extend_new_issues(before.chart_sheet_ref_issues, after.chart_sheet_ref_issues, issues)


def _audit_pivot_sheet_refs(before: Snapshot, after: Snapshot, issues: list[AuditIssue]) -> None:
    _extend_new_issues(before.pivot_sheet_ref_issues, after.pivot_sheet_ref_issues, issues)


def _extend_new_issues(
    before_issues: list[AuditIssue],
    after_issues: list[AuditIssue],
    issues: list[AuditIssue],
) -> None:
    before_keys = {_issue_key(issue) for issue in before_issues}
    issues.extend(issue for issue in after_issues if _issue_key(issue) not in before_keys)


def _issue_key(issue: AuditIssue) -> tuple[str, str, str]:
    return (
        issue.get("kind", ""),
        issue.get("part", ""),
        issue.get("message", ""),
    )


def _audit_feature_hotspots(before: Snapshot, after: Snapshot, issues: list[AuditIssue]) -> None:
    for feature, before_parts in sorted(before.feature_parts.items()):
        if not before_parts:
            continue
        after_parts = set(after.feature_parts.get(feature, []))
        missing = sorted(set(before_parts) - after_parts)
        if missing:
            issues.append(
                {
                    "severity": "error",
                    "kind": "feature_part_loss",
                    "part": feature,
                    "message": f"{feature} parts disappeared after save: {missing}",
                }
            )


def _audit_semantic_fingerprints(
    before: Snapshot,
    after: Snapshot,
    issues: list[AuditIssue],
    *,
    compact: bool = False,
) -> None:
    for feature, before_fingerprint in sorted(before.semantic_fingerprints.items()):
        if not before_fingerprint:
            continue
        after_fingerprint = after.semantic_fingerprints.get(feature, {})
        if feature in {"drawing_objects", "extensions"}:
            after_fingerprint = {
                part: after_fingerprint.get(part)
                for part in before_fingerprint
                if part in after.parts
            }
        if after_fingerprint != before_fingerprint:
            issues.append(
                _semantic_drift_issue(
                    feature,
                    before_fingerprint,
                    after_fingerprint,
                    compact=compact,
                )
            )


def _semantic_drift_issue(
    feature: str,
    before_fingerprint: dict[str, object],
    after_fingerprint: dict[str, object],
    *,
    compact: bool,
) -> AuditIssue:
    if compact and feature not in MARKER_SENSITIVE_SEMANTIC_FEATURES:
        before_summary = _fingerprint_summary(before_fingerprint)
        after_summary = _fingerprint_summary(after_fingerprint)
        return {
            "severity": "error",
            "kind": f"{feature}_semantic_drift",
            "part": feature,
            "before_empty": not bool(before_fingerprint),
            "after_empty": not bool(after_fingerprint),
            "before_summary": before_summary,
            "after_summary": after_summary,
            "message": (
                f"{feature} semantic fingerprint changed after save "
                f"(compact summary): before={before_summary} "
                f"after={after_summary}"
            ),
        }
    return {
        "severity": "error",
        "kind": f"{feature}_semantic_drift",
        "part": feature,
        "before_empty": not bool(before_fingerprint),
        "after_empty": not bool(after_fingerprint),
        "message": (
            f"{feature} semantic fingerprint changed after save: "
            f"before={before_fingerprint!r} after={after_fingerprint!r}"
        ),
    }


def _fingerprint_summary(value: object) -> FingerprintStats:
    stats = FingerprintStats(
        dicts=0,
        lists=0,
        tuples=0,
        scalars=0,
        top_level_keys=[],
    )
    if isinstance(value, dict):
        stats["top_level_keys"] = sorted(str(key) for key in value)[:20]
    _accumulate_fingerprint_stats(value, stats)
    return stats


def _accumulate_fingerprint_stats(value: object, stats: FingerprintStats) -> None:
    if isinstance(value, dict):
        stats["dicts"] += 1
        for item in value.values():
            _accumulate_fingerprint_stats(item, stats)
    elif isinstance(value, list):
        stats["lists"] += 1
        for item in value:
            _accumulate_fingerprint_stats(item, stats)
    elif isinstance(value, tuple):
        stats["tuples"] += 1
        for item in value:
            _accumulate_fingerprint_stats(item, stats)
    else:
        stats["scalars"] += 1


def _snapshot_summary(snapshot_: Snapshot) -> dict:
    return {
        "path": snapshot_.path,
        "part_count": len(snapshot_.parts),
        "xml_parse_error_count": len(snapshot_.xml_parse_errors),
        "relationship_count": len(snapshot_.relationships),
        "content_override_count": len(snapshot_.content_overrides),
        "dxfs_count": snapshot_.dxfs_count,
        "cf_dxf_ref_count": len(snapshot_.cf_dxf_refs),
        "table_integrity_issue_count": len(snapshot_.table_integrity_issues),
        "worksheet_sheet_ref_issue_count": len(snapshot_.worksheet_sheet_ref_issues),
        "workbook_sheet_ref_issue_count": len(snapshot_.workbook_sheet_ref_issues),
        "chart_sheet_ref_issue_count": len(snapshot_.chart_sheet_ref_issues),
        "pivot_sheet_ref_issue_count": len(snapshot_.pivot_sheet_ref_issues),
        "feature_part_counts": {
            feature: len(parts) for feature, parts in snapshot_.feature_parts.items()
        },
        "semantic_fingerprint_counts": {
            feature: len(fingerprint)
            for feature, fingerprint in snapshot_.semantic_fingerprints.items()
        },
    }


def _json_default(value: object) -> object:
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(cast(Any, value))
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="Workbook before modify-save")
    parser.add_argument("after", type=Path, help="Workbook after modify-save")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    report = audit(args.before, args.after)
    if args.json:
        print(json.dumps(report, indent=2, default=_json_default, sort_keys=True))
    else:
        _print_text_report(report)
    return 1 if report["issues"] else 0


def _print_text_report(report: dict) -> None:
    print(f"Before parts: {report['before']['part_count']}")
    print(f"After parts:  {report['after']['part_count']}")
    print(f"Issues:       {report['issue_count']}")
    for issue in report["issues"]:
        print(f"- [{issue['severity']}] {issue['kind']}: {issue['message']}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
