"""Operation models for the OOXML package fidelity audit.

Internal to the OOXML fidelity audit. The public surface stays
``wolfxl.operations._ooxml_fidelity``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class FingerprintStats(TypedDict):
    dicts: int
    lists: int
    tuples: int
    scalars: int
    top_level_keys: list[str]


class _OptionalAuditIssueFields(TypedDict, total=False):
    before_empty: bool
    after_empty: bool
    before_summary: FingerprintStats
    after_summary: FingerprintStats


class AuditIssue(_OptionalAuditIssueFields):
    severity: str
    kind: str
    part: str
    message: str


@dataclass(frozen=True)
class Relationship:
    rels_part: str
    rel_id: str
    rel_type: str
    target: str
    target_mode: str | None
    resolved_target: str | None


@dataclass
class Snapshot:
    path: str
    parts: set[str]
    xml_parse_errors: list[tuple[str, str]]
    content_overrides: dict[str, str]
    relationships: list[Relationship]
    dxfs_count: int
    cf_dxf_refs: list[tuple[str, int]]
    table_integrity_issues: list[AuditIssue]
    worksheet_sheet_ref_issues: list[AuditIssue]
    workbook_sheet_ref_issues: list[AuditIssue]
    chart_sheet_ref_issues: list[AuditIssue]
    pivot_sheet_ref_issues: list[AuditIssue]
    feature_parts: dict[str, list[str]]
    semantic_fingerprints: dict[str, dict[str, object]]
