"""Snapshot-time reference-integrity checks over a single OOXML package.

Internal to the OOXML fidelity audit. The public surface stays
``wolfxl.operations._ooxml_fidelity``.
"""

from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree

from ._ooxml_fidelity_constants import (
    CONDITIONAL_FORMATTING_MARKERS,
    FORMULA_MARKERS,
    MAIN_NS,
)
from ._ooxml_fidelity_extract import _pivot_source_names
from ._ooxml_fidelity_models import AuditIssue
from ._ooxml_fidelity_package import (
    _feature_xml_parts,
    _is_chart_style_part,
    _worksheet_parts,
)
from ._ooxml_fidelity_xml import (
    _attr,
    _children_by_local,
    _first_child_by_local,
    _local_name,
    _nodes_by_local,
    _part_contains_any,
    _read_xml_or_none,
    _text,
    _texts_by_local,
)


def _read_dxfs_count(archive: zipfile.ZipFile) -> int:
    root = _read_xml_or_none(archive, "xl/styles.xml")
    if root is None:
        return 0
    dxfs = root.find(f"{MAIN_NS}dxfs")
    if dxfs is None:
        return 0
    return len(dxfs.findall(f"{MAIN_NS}dxf"))


def _read_cf_dxf_refs(archive: zipfile.ZipFile) -> list[tuple[str, int]]:
    refs: list[tuple[str, int]] = []
    for part in sorted(_worksheet_parts(archive.namelist())):
        if not _part_contains_any(archive, part, CONDITIONAL_FORMATTING_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        for cf_rule in root.findall(f".//{MAIN_NS}cfRule"):
            raw = cf_rule.attrib.get("dxfId")
            if raw is not None and raw.isdigit():
                refs.append((part, int(raw)))
    return refs


def _read_table_integrity_issues(archive: zipfile.ZipFile) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    for part in sorted(_feature_xml_parts(set(archive.namelist()), "xl/tables/", ".xml")):
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        ref = _attr(root, "ref")
        ref_width = _range_width(ref) if ref else None
        columns = _first_child_by_local(root, "tableColumns")
        child_count = len(_children_by_local(columns, "tableColumn")) if columns is not None else 0
        declared_count_raw = _attr(columns, "count") if columns is not None else None
        declared_count = (
            int(declared_count_raw)
            if declared_count_raw is not None and declared_count_raw.isdigit()
            else None
        )
        mismatches: list[str] = []
        if ref_width is not None and child_count != ref_width:
            mismatches.append(f"ref width={ref_width}, tableColumn children={child_count}")
        if declared_count is not None and declared_count != child_count:
            mismatches.append(f"count={declared_count}, tableColumn children={child_count}")
        if declared_count is not None and ref_width is not None and declared_count != ref_width:
            mismatches.append(f"count={declared_count}, ref width={ref_width}")
        if mismatches:
            mismatch_text = "; ".join(mismatches)
            issues.append(
                {
                    "severity": "error",
                    "kind": "table_column_count_mismatch",
                    "part": part,
                    "message": (
                        f"{part} table metadata is internally inconsistent: {mismatch_text}"
                    ),
                }
            )
    return issues


def _read_chart_sheet_ref_issues(
    archive: zipfile.ZipFile,
) -> list[AuditIssue]:
    sheet_names = _workbook_sheet_names(archive)
    if not sheet_names:
        return []

    parts = set(archive.namelist())
    issues: list[AuditIssue] = []
    for part in sorted(_feature_xml_parts(parts, "xl/charts/", ".xml")):
        if _is_chart_style_part(part):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        for formula in _texts_by_local(root, "f"):
            refs = _formula_sheet_reference_names(formula)
            missing = sorted(ref for ref in refs if ref not in sheet_names)
            if missing:
                issues.append(
                    {
                        "severity": "error",
                        "kind": "chart_formula_missing_sheet",
                        "part": part,
                        "message": (
                            f"{part} chart formula {formula!r} references missing "
                            f"sheet(s): {missing}"
                        ),
                    }
                )
        for name in _pivot_source_names(root):
            sheet_name = _pivot_source_sheet_reference_name(name)
            if sheet_name is not None and sheet_name not in sheet_names:
                issues.append(
                    {
                        "severity": "error",
                        "kind": "chart_pivot_source_missing_sheet",
                        "part": part,
                        "message": (
                            f"{part} pivot source {name!r} references missing sheet: {sheet_name!r}"
                        ),
                    }
                )
    return issues


def _read_workbook_sheet_ref_issues(
    archive: zipfile.ZipFile,
) -> list[AuditIssue]:
    sheet_names = _workbook_sheet_names(archive)
    if not sheet_names:
        return []

    root = _read_xml_or_none(archive, "xl/workbook.xml")
    if root is None:
        return []

    issues: list[AuditIssue] = []
    for node in _nodes_by_local(root, "definedName"):
        formula = _text(node)
        refs = _formula_sheet_reference_names(formula) if formula is not None else set()
        missing = sorted(ref for ref in refs if ref not in sheet_names)
        if missing:
            name = _attr(node, "name") or "<unnamed>"
            issues.append(
                {
                    "severity": "error",
                    "kind": "workbook_defined_name_missing_sheet",
                    "part": "xl/workbook.xml",
                    "message": (
                        f"defined name {name!r} formula {formula!r} references "
                        f"missing sheet(s): {missing}"
                    ),
                }
            )
    return issues


def _read_worksheet_sheet_ref_issues(archive: zipfile.ZipFile, parts: set[str]) -> list[AuditIssue]:
    sheet_names = _workbook_sheet_names(archive)
    if not sheet_names:
        return []

    issues: list[AuditIssue] = []
    for part in sorted(_worksheet_parts(parts)):
        if not _part_contains_any(archive, part, FORMULA_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        for element_name, formula in _worksheet_formula_reference_texts(root):
            refs = _formula_sheet_reference_names(formula)
            missing = sorted(ref for ref in refs if ref not in sheet_names)
            if missing:
                issues.append(
                    {
                        "severity": "error",
                        "kind": "worksheet_formula_missing_sheet",
                        "part": part,
                        "message": (
                            f"{part} {element_name} formula {formula!r} references "
                            f"missing sheet(s): {missing}"
                        ),
                    }
                )
    return issues


def _read_pivot_sheet_ref_issues(archive: zipfile.ZipFile, parts: set[str]) -> list[AuditIssue]:
    sheet_names = _workbook_sheet_names(archive)
    if not sheet_names:
        return []

    issues: list[AuditIssue] = []
    for part in sorted(_feature_xml_parts(parts, "xl/pivotCache/", ".xml")):
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        for source in _nodes_by_local(root, "worksheetSource"):
            sheet_name = _attr(source, "sheet")
            if not sheet_name or sheet_name in sheet_names:
                continue
            issues.append(
                {
                    "severity": "error",
                    "kind": "pivot_cache_source_missing_sheet",
                    "part": part,
                    "message": (
                        f"{part} worksheetSource sheet {sheet_name!r} references a missing sheet"
                    ),
                }
            )
    return issues


def _worksheet_formula_reference_texts(
    root: ElementTree.Element,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    formula_node_names = {"f", "formula", "formula1", "formula2"}
    for node in root.iter():
        element_name = _local_name(node.tag)
        if element_name not in formula_node_names:
            continue
        if (
            element_name in {"formula1", "formula2"}
            and _first_child_by_local(node, "f") is not None
        ):
            continue
        if formula := _text(node):
            out.append((element_name, formula))
    return out


def _workbook_sheet_names(archive: zipfile.ZipFile) -> set[str]:
    root = _read_xml_or_none(archive, "xl/workbook.xml")
    if root is None:
        return set()
    return {name for sheet in _nodes_by_local(root, "sheet") if (name := _attr(sheet, "name"))}


def _formula_sheet_reference_names(formula: str) -> set[str]:
    refs: set[str] = set()
    consumed_ranges: list[tuple[int, int]] = []

    for match in re.finditer(r'"(?:[^"]|"")*"', formula):
        consumed_ranges.append(match.span())

    for match in re.finditer(r"'((?:[^']|'')+)'!", formula):
        consumed_ranges.append(match.span())
        refs.update(_local_sheet_names_from_token(match.group(1).replace("''", "'")))

    for match in re.finditer(r"(?<![\]\w'])((?:[A-Za-z0-9_][A-Za-z0-9_ .:]*)!)", formula):
        if any(start <= match.start() < end for start, end in consumed_ranges):
            continue
        refs.update(_local_sheet_names_from_token(match.group(1)[:-1].strip()))

    return refs


def _local_sheet_names_from_token(token: str) -> set[str]:
    if "[" in token or "]" in token:
        return set()
    return {
        name for name in token.split(":") if name and not _is_formula_error_reference_token(name)
    }


def _is_formula_error_reference_token(token: str) -> bool:
    return token.lstrip("#").upper() in {
        "REF",
        "VALUE",
        "DIV/0",
        "NAME?",
        "N/A",
        "NULL",
        "NUM",
    }


def _pivot_source_sheet_reference_name(name: str) -> str | None:
    if "!" not in name:
        return None
    left, _, _ = name.partition("!")
    if "]" in left:
        left = left.rsplit("]", 1)[1]
    left = left.strip("'").replace("''", "'")
    return left or None


def _range_width(ref: str) -> int | None:
    first, _, last = ref.partition(":")
    last = last or first
    first_col = _cell_col_index(first)
    last_col = _cell_col_index(last)
    if first_col is None or last_col is None:
        return None
    return abs(last_col - first_col) + 1


def _cell_col_index(cell: str) -> int | None:
    match = re.match(r"^\$?([A-Za-z]+)\$?\d+$", cell)
    if match is None:
        return None
    value = 0
    for char in match.group(1).upper():
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value
