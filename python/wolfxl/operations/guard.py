#!/usr/bin/env python3
"""Compare two local workbooks for bounded OOXML fidelity regressions.

The optional API default is the strict five-dimension policy. An explicit
policy object may set any dimension to ``null`` (unassessed), use
``{"mode": "unchanged"}``, or provide bounded inventory counts. The CLI
requires the same object in a JSON file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import posixpath
import re
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile
from . import _ooxml_fidelity as fidelity_audit
from wolfxl.comparison import WorkbookComparison, WorkbookIdentity


SCHEMA_VERSION = 1
EXIT_PASSED = 0
EXIT_REGRESSION = 1
EXIT_INVALID_INPUT = 2
EXIT_INTERNAL_ERROR = 3
_SUPPORTED_SUFFIXES = frozenset({".xlsx", ".xlsm"})
_FIDELITY_DIMENSION_FEATURES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "charts": (("charts", "chart_sheets", "chart_styles"), ("chart", "chart_sheet", "chart_style")),
    "conditional_formatting": (("conditional_formatting",), ("conditional_formatting",)),
    "comments": ((), ("comment",)),
    "connections": (("connections",), ("connection",)),
    "data_model": (("data_model",), ("data_model",)),
    "data_validations": (("data_validations",), ()),
    "drawing_objects": (("drawing_objects",), ("drawing", "image_media")),
    "extensions": (("extensions",), ()),
    "named_sheet_views": (("named_sheet_views",), ("named_sheet_view",)),
    "page_setup": (("page_setup",), ("printer_settings",)),
    "pivots": (("pivots",), ("pivot",)),
    "python": (("python",), ("python",)),
    "sheet_metadata": (("sheet_metadata",), ("sheet_metadata",)),
    "slicers": (("slicers",), ("slicer",)),
    "style_theme": (("style_theme",), ()),
    "structured_references": (("structured_references",), ("table",)),
    "timelines": (("timelines",), ("timeline",)),
    "workbook_globals": (("workbook_globals",), ("custom_property", "custom_xml", "vba")),
}
_POLICY_DIMENSIONS = (
    "macro_inventory",
    "external_link_inventory",
    "worksheet_inventory",
    "formula_integrity",
    "package_integrity",
)
_POLICY_ALIASES = {"ooxml_package_integrity": "package_integrity"}
_INVENTORY_POLICY_KEYS = frozenset({"mode", "max_count", "expected_count"})
_WORKSHEET_POLICY_KEYS = frozenset({"mode", "max_count", "expected_count", "expected_names"})
_INTEGRITY_POLICY_KEYS = frozenset({"mode"})
_MODE_ALIASES = {"preserve": "unchanged", "strict": "unchanged", "unchanged": "unchanged"}
_DEFAULT_POLICY = {
    **{dimension: {"mode": "unchanged"} for dimension in _POLICY_DIMENSIONS},
    **{dimension: {"mode": "unchanged"} for dimension in _FIDELITY_DIMENSION_FEATURES},
}

SUPPORT_BUNDLE_SCHEMA_VERSION = 2
SUPPORT_BUNDLE_EXIT_PASSED = 0
SUPPORT_BUNDLE_EXIT_UNACCEPTABLE = 5
_SAFE_DECISION_EVIDENCE_KEYS = frozenset(
    {
        "after_count",
        "after_formula_count",
        "before_count",
        "before_formula_count",
        "issue_count",
    }
)

_ERROR_DUPLICATE_MEMBERS = "OOXML package contains duplicate ZIP members"
_ERROR_WORKSHEET_INVENTORY_UNREADABLE = "workbook worksheet inventory could not be read"
_ERROR_WORKSHEET_INVENTORY_UNAVAILABLE = "workbook worksheet inventory is unavailable"
_ERROR_WORKSHEET_NAME_MAPPING = "worksheet name mapping is incomplete"
_ERROR_WORKSHEET_INVENTORY_EMPTY = "worksheet inventory is empty"
_ERROR_WORKSHEET_NAMES_DUPLICATED = "worksheet inventory contains duplicate names"
_ERROR_RELATIONSHIPS_UNAVAILABLE = "workbook worksheet relationships are unavailable"
_ERROR_RELATIONSHIPS_INCOMPLETE = "workbook worksheet relationships are incomplete"
_ERROR_RELATIONSHIPS_UNREADABLE = "workbook worksheet relationships could not be read"
_ERROR_RELATIONSHIP_SHEET_MAPPING = "worksheet relationship/sheet mapping is incomplete"
_ERROR_WORKSHEET_XML_UNREADABLE = "worksheet XML could not be read"
_ERROR_FORMULA_INVENTORY_UNREADABLE = "worksheet formula inventory could not be read"
_ERROR_WORKSHEET_DUPLICATE_MEMBERS = "worksheet evidence contains duplicate ZIP members"
_ERROR_MACRO_DUPLICATE_MEMBERS = "macro evidence contains duplicate ZIP members"
_ERROR_EXTERNAL_DUPLICATE_MEMBERS = "external-link evidence contains duplicate ZIP members"
_ERROR_EXTERNAL_XML_UNREADABLE = "external-link XML inventory could not be read"
_ERROR_FORMULA_EVIDENCE_INCOMPLETE = "worksheet/formula evidence is incomplete"
_ERROR_FORMULA_INVENTORY_UNAVAILABLE = "worksheet formula inventory is unavailable"

_RELATIONSHIPS_MISSING = "workbook_relationships_missing"
_RELATIONSHIPS_UNREADABLE = "workbook_relationships_unreadable"
_RELATIONSHIPS_INCOMPLETE = "workbook_relationships_incomplete"
_RELATIONSHIP_MAPPING_INCOMPLETE = "worksheet_relationship_mapping_incomplete"

# Every inventory diagnostic maps to one stable, value-free code so a support
# bundle can name a failure without echoing a package message.
_INVENTORY_ERROR_CODES: dict[str, str] = {
    _ERROR_DUPLICATE_MEMBERS: "package_duplicate_members",
    _ERROR_WORKSHEET_INVENTORY_UNREADABLE: "workbook_part_unreadable",
    _ERROR_WORKSHEET_INVENTORY_UNAVAILABLE: "workbook_part_missing",
    _ERROR_WORKSHEET_NAME_MAPPING: "worksheet_name_mapping_incomplete",
    _ERROR_WORKSHEET_INVENTORY_EMPTY: "worksheet_inventory_empty",
    _ERROR_WORKSHEET_NAMES_DUPLICATED: "worksheet_names_duplicated",
    _ERROR_RELATIONSHIPS_UNAVAILABLE: _RELATIONSHIPS_MISSING,
    _ERROR_RELATIONSHIPS_INCOMPLETE: _RELATIONSHIPS_INCOMPLETE,
    _ERROR_RELATIONSHIPS_UNREADABLE: _RELATIONSHIPS_UNREADABLE,
    _ERROR_RELATIONSHIP_SHEET_MAPPING: _RELATIONSHIP_MAPPING_INCOMPLETE,
    _ERROR_WORKSHEET_XML_UNREADABLE: "worksheet_xml_unreadable",
    _ERROR_FORMULA_INVENTORY_UNREADABLE: "formula_inventory_unreadable",
    _ERROR_WORKSHEET_DUPLICATE_MEMBERS: "worksheet_duplicate_members",
    _ERROR_MACRO_DUPLICATE_MEMBERS: "macro_duplicate_members",
    _ERROR_EXTERNAL_DUPLICATE_MEMBERS: "external_link_duplicate_members",
    _ERROR_EXTERNAL_XML_UNREADABLE: "external_link_xml_unreadable",
    _ERROR_FORMULA_EVIDENCE_INCOMPLETE: "formula_evidence_incomplete",
    _ERROR_FORMULA_INVENTORY_UNAVAILABLE: "formula_inventory_unavailable",
}
_UNCLASSIFIED_ERROR_CODE = "unclassified_inventory_error"

# Most specific relationship defect wins, so one malformed package reports one
# deterministic classification.
_RELATIONSHIP_CLASSIFICATIONS: tuple[tuple[str, str], ...] = (
    (_RELATIONSHIPS_MISSING, "relationships_missing"),
    (_RELATIONSHIPS_UNREADABLE, "relationships_unreadable"),
    (_RELATIONSHIPS_INCOMPLETE, "relationships_incomplete"),
    (_RELATIONSHIP_MAPPING_INCOMPLETE, "relationship_sheet_mapping_incomplete"),
)
_RELATIONSHIPS_WELL_FORMED = "well_formed"

# Part paths are reduced to a bounded vocabulary of kinds; a bundle never
# carries a part name, only a kind and a count.
_PART_KIND_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\[Content_Types\]\.xml"), "content_types"),
    (re.compile(r"_rels/\.rels"), "package_relationships"),
    (re.compile(r"(?:.*/)?_rels/[^/]+\.rels"), "part_relationships"),
    (re.compile(r"docProps/.+"), "document_properties"),
    (re.compile(r"customXml/.+"), "custom_xml"),
    (re.compile(r"customUI/.+"), "custom_ui"),
    (re.compile(r"_xmlsignatures/.+"), "digital_signature"),
    (re.compile(r"xl/workbook\.xml"), "workbook"),
    (re.compile(r"xl/worksheets/[^/]+"), "worksheet"),
    (re.compile(r"xl/chartsheets/[^/]+"), "chartsheet"),
    (re.compile(r"xl/dialogsheets/[^/]+"), "dialogsheet"),
    (re.compile(r"xl/macrosheets/[^/]+"), "macrosheet"),
    (re.compile(r"xl/sharedStrings\.xml"), "shared_strings"),
    (re.compile(r"xl/styles\.xml"), "styles"),
    (re.compile(r"xl/calcChain\.xml"), "calculation_chain"),
    (re.compile(r"xl/theme/[^/]+"), "theme"),
    (re.compile(r"xl/vbaProject\.bin"), "vba_project"),
    (re.compile(r"xl/vbaData\.xml"), "vba_data"),
    (re.compile(r"xl/externalLinks/[^/]+"), "external_link"),
    (re.compile(r"xl/connections\.xml"), "connections"),
    (re.compile(r"xl/queryTables/[^/]+"), "query_table"),
    (re.compile(r"xl/pivotTables/[^/]+"), "pivot_table"),
    (re.compile(r"xl/pivotCache/[^/]+"), "pivot_cache"),
    (re.compile(r"xl/tables/[^/]+"), "table"),
    (re.compile(r"xl/charts/[^/]+"), "chart"),
    (re.compile(r"xl/drawings/[^/]+"), "drawing"),
    (re.compile(r"xl/media/[^/]+"), "media"),
    (re.compile(r"xl/embeddings/[^/]+"), "embedding"),
    (re.compile(r"xl/activeX/[^/]+"), "activex"),
    (re.compile(r"xl/printerSettings/[^/]+"), "printer_settings"),
    (re.compile(r"xl/richData/[^/]+"), "rich_data"),
    (re.compile(r"xl/metadata\.xml"), "cell_metadata"),
)
_OTHER_PART_KIND = "other"


class GuardInputError(ValueError):
    """Raised when Guard cannot safely compare the requested files."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_workbook(path: Path, *, label: str) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise GuardInputError(f"{label} workbook is not a readable file") from exc
    if not resolved.is_file() or resolved.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise GuardInputError(f"{label} workbook must be an .xlsx or .xlsm file")
    return resolved


def _validated_workbook_source(source: str | os.PathLike[str], *, label: str) -> Path:
    try:
        raw_path = os.fspath(source)
    except TypeError as exc:
        raise GuardInputError(f"{label} workbook must be a path") from exc
    if isinstance(raw_path, bytes):
        raise GuardInputError(f"{label} workbook must be a path")
    return _validated_workbook(Path(raw_path), label=label)


def _validated_output(path: Path, *, before: Path, after: Path) -> Path:
    if path.suffix.lower() != ".json":
        raise GuardInputError("output must be a .json file")
    output = path.expanduser().resolve(strict=False)
    if output in {before, after}:
        raise GuardInputError("output must not replace either workbook")
    return output


def _validated_policy_path(path: Path) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise GuardInputError("policy file is not a readable file") from exc
    if not resolved.is_file():
        raise GuardInputError("policy file is not a readable file")
    return resolved


def _artifact_summary(path: Path) -> dict[str, Any]:
    return {
        "filename": path.name,
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


_POLICY_DEFAULT = object()


def _normalized_policy(policy: object) -> dict[str, dict[str, Any] | None]:
    if policy is _POLICY_DEFAULT or policy is None:
        policy = _DEFAULT_POLICY
    if not isinstance(policy, Mapping):
        raise GuardInputError("policy must be a JSON object")

    raw_policy = dict(policy)
    invalid_keys = sorted(
        str(key)
        for key in raw_policy
        if not isinstance(key, str)
        or (
            key not in _POLICY_DIMENSIONS
            and key not in _FIDELITY_DIMENSION_FEATURES
            and key not in _POLICY_ALIASES
        )
    )
    if invalid_keys:
        raise GuardInputError(f"policy has unknown key(s): {', '.join(invalid_keys)}")

    normalized: dict[str, dict[str, Any] | None] = {}
    for key, value in raw_policy.items():
        canonical = _POLICY_ALIASES.get(key, key)
        if canonical in normalized:
            raise GuardInputError(f"policy specifies {canonical!r} more than once")
        if value is None:
            normalized[canonical] = None
            continue
        if not isinstance(value, Mapping):
            raise GuardInputError(f"policy.{canonical} must be null or an object")
        allowed = (
            _WORKSHEET_POLICY_KEYS
            if canonical == "worksheet_inventory"
            else _INTEGRITY_POLICY_KEYS
            if canonical
            in {"formula_integrity", "package_integrity", *_FIDELITY_DIMENSION_FEATURES}
            else _INVENTORY_POLICY_KEYS
        )
        dimension_policy = dict(value)
        unknown = sorted(str(field) for field in dimension_policy if field not in allowed)
        if unknown:
            raise GuardInputError(f"policy.{canonical} has unknown key(s): {', '.join(unknown)}")
        normalized_dimension: dict[str, Any] = {}
        if "mode" in dimension_policy:
            mode = dimension_policy["mode"]
            if not isinstance(mode, str) or mode not in _MODE_ALIASES:
                raise GuardInputError(f"policy.{canonical}.mode must be 'unchanged' or 'preserve'")
            normalized_dimension["mode"] = _MODE_ALIASES[mode]
        for field in ("max_count", "expected_count"):
            if field not in dimension_policy:
                continue
            count = dimension_policy[field]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise GuardInputError(f"policy.{canonical}.{field} must be a non-negative integer")
            normalized_dimension[field] = count
        if "expected_names" in dimension_policy:
            names = dimension_policy["expected_names"]
            if (
                not isinstance(names, list)
                or any(not isinstance(name, str) for name in names)
                or len(set(names)) != len(names)
            ):
                raise GuardInputError(
                    f"policy.{canonical}.expected_names must be a list of unique strings"
                )
            normalized_dimension["expected_names"] = list(names)
        if not normalized_dimension:
            normalized_dimension["mode"] = "unchanged"
        if canonical in {
            "formula_integrity",
            "package_integrity",
            *_FIDELITY_DIMENSION_FEATURES,
        } and set(normalized_dimension) != {"mode"}:
            raise GuardInputError(f"policy.{canonical} only accepts the mode field")
        normalized[canonical] = normalized_dimension

    # Package fidelity is the core Guard check. It remains assessed unless a
    # caller explicitly sets package_integrity to null.
    normalized.setdefault("package_integrity", {"mode": "unchanged"})
    for dimension in _POLICY_DIMENSIONS:
        normalized.setdefault(dimension, None)
    return normalized


def _load_policy(path: Path) -> dict[str, dict[str, Any] | None]:
    policy_path = _validated_policy_path(path)
    try:
        text = policy_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise GuardInputError("policy file is not valid UTF-8 JSON") from exc
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GuardInputError("policy file contains malformed JSON") from exc
    return _normalized_policy(parsed)


def load_guard_policy(path: Path) -> dict[str, dict[str, Any] | None]:
    """Load and validate a Guard policy JSON file."""
    return _load_policy(path)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


_EXTERNAL_UNQUOTED_SHEET = re.compile(r"[^!\s\[\]\(\)\+\-\*/,:;]+!")
_EXTERNAL_QUOTED_SHEET = re.compile(r"[^']*'!")


def _contains_external_workbook_reference(formula: str) -> bool:
    """Return whether a formula contains an external-workbook reference.

    A workbook token is a bracketed token at a formula boundary followed by a
    sheet reference and ``!``. Structured table references have an identifier
    immediately before their bracket and are excluded. Double-quoted Excel
    string literals are removed before scanning.
    """
    cleaned: list[str] = []
    in_string = False
    index = 0
    while index < len(formula):
        char = formula[index]
        if char == '"':
            if in_string and index + 1 < len(formula) and formula[index + 1] == '"':
                cleaned.extend((" ", " "))
                index += 2
                continue
            in_string = not in_string
            cleaned.append(" ")
        elif in_string:
            cleaned.append(" ")
        else:
            cleaned.append(char)
        index += 1

    text = "".join(cleaned)
    search_from = 0
    while True:
        opening = text.find("[", search_from)
        if opening < 0:
            return False
        closing = text.find("]", opening + 1)
        if closing < 0 or closing == opening + 1:
            return False
        before = opening - 1
        while before >= 0 and text[before].isspace():
            before -= 1
        if before >= 0 and (text[before].isalnum() or text[before] in "_.$"):
            search_from = closing + 1
            continue
        after = text[closing + 1 :]
        if _EXTERNAL_QUOTED_SHEET.match(after) or _EXTERNAL_UNQUOTED_SHEET.match(after):
            return True
        search_from = closing + 1


def _resolve_relationship_target(source: str, target: str) -> str:
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def _part_kind(part: str) -> str:
    for pattern, kind in _PART_KIND_RULES:
        if pattern.fullmatch(part):
            return kind
    return _OTHER_PART_KIND


def _package_inventory(path: Path) -> dict[str, Any]:
    with ZipFile(path) as archive:
        diagnostics: list[str] = []

        def note(message: str) -> str:
            # Each single-valued error slot keeps its historical winner while
            # every observed diagnostic stays available for typed reporting.
            if message not in diagnostics:
                diagnostics.append(message)
            return message

        members = archive.infolist()
        counts: dict[str, int] = {}
        for member in members:
            counts[member.filename] = counts.get(member.filename, 0) + 1
        duplicate_parts = sorted(part for part, count in counts.items() if count > 1)
        parts = sorted(counts)
        member_identity = hashlib.sha256()
        for member in sorted(
            members, key=lambda entry: (entry.filename, entry.file_size, entry.CRC)
        ):
            member_identity.update(
                f"{member.filename}\x00{member.file_size}\x00{member.CRC}\n".encode()
            )
        part_kind_counts = Counter(_part_kind(part) for part in parts)
        inventory_error = note(_ERROR_DUPLICATE_MEMBERS) if duplicate_parts else None
        macro_parts = [
            part for part in parts if part == "xl/vbaProject.bin" or part == "xl/vbaData.xml"
        ]
        external_link_parts = sorted(
            part for part in parts if re.fullmatch(r"xl/externalLinks/externalLink\d+\.xml", part)
        )
        macro_signatures = {
            part: hashlib.sha256(archive.read(part)).hexdigest() for part in macro_parts
        }
        external_link_signatures = {
            part: hashlib.sha256(archive.read(part)).hexdigest() for part in external_link_parts
        }
        worksheet_parts = sorted(
            part for part in parts if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", part)
        )
        worksheet_names: list[str] | None = None
        worksheet_error: str | None = None
        workbook_root: ElementTree.Element | None = None
        if "xl/workbook.xml" in parts:
            try:
                workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            except ElementTree.ParseError:
                worksheet_error = note(_ERROR_WORKSHEET_INVENTORY_UNREADABLE)
        else:
            worksheet_error = note(_ERROR_WORKSHEET_INVENTORY_UNAVAILABLE)

        sheet_nodes: list[ElementTree.Element] = []
        if workbook_root is not None:
            sheet_nodes = [
                sheet for sheet in workbook_root.iter() if _local_name(sheet.tag) == "sheet"
            ]
            worksheet_names = [
                str(sheet.attrib["name"]) for sheet in sheet_nodes if "name" in sheet.attrib
            ]
            if len(worksheet_names) != len(sheet_nodes):
                worksheet_error = note(_ERROR_WORKSHEET_NAME_MAPPING)
            elif not worksheet_names or not worksheet_parts:
                worksheet_error = note(_ERROR_WORKSHEET_INVENTORY_EMPTY)
            elif len(set(worksheet_names)) != len(worksheet_names):
                worksheet_error = note(_ERROR_WORKSHEET_NAMES_DUPLICATED)

            rels_by_id: dict[str, str] = {}
            rels_path = "xl/_rels/workbook.xml.rels"
            if rels_path not in parts:
                worksheet_error = note(_ERROR_RELATIONSHIPS_UNAVAILABLE)
            else:
                try:
                    rels_root = ElementTree.fromstring(archive.read(rels_path))
                    for relationship in rels_root.iter():
                        if _local_name(relationship.tag) != "Relationship":
                            continue
                        rel_id = relationship.attrib.get("Id")
                        target = relationship.attrib.get("Target")
                        if not rel_id or not target or rel_id in rels_by_id:
                            worksheet_error = note(_ERROR_RELATIONSHIPS_INCOMPLETE)
                            continue
                        rels_by_id[rel_id] = _resolve_relationship_target("xl/workbook.xml", target)
                except ElementTree.ParseError:
                    worksheet_error = note(_ERROR_RELATIONSHIPS_UNREADABLE)

            mapped_parts: set[str] = set()
            for sheet in sheet_nodes:
                relationship_id = next(
                    (value for key, value in sheet.attrib.items() if _local_name(key) == "id"),
                    None,
                )
                target = rels_by_id.get(relationship_id or "")
                if target is None or target not in worksheet_parts:
                    worksheet_error = note(_ERROR_RELATIONSHIP_SHEET_MAPPING)
                else:
                    mapped_parts.add(target)
            if set(worksheet_parts) != mapped_parts:
                worksheet_error = note(_ERROR_RELATIONSHIP_SHEET_MAPPING)

        formulas: dict[str, list[list[object]]] | None = {}
        formula_error: str | None = None
        for part in worksheet_parts:
            try:
                root = ElementTree.fromstring(archive.read(part))
            except ElementTree.ParseError:
                formula_error = note(_ERROR_FORMULA_INVENTORY_UNREADABLE)
                worksheet_error = worksheet_error or note(_ERROR_WORKSHEET_XML_UNREADABLE)
                continue
            if _local_name(root.tag) != "worksheet":
                formula_error = note(_ERROR_FORMULA_INVENTORY_UNREADABLE)
                worksheet_error = worksheet_error or note(_ERROR_WORKSHEET_XML_UNREADABLE)
                continue
            entries: list[list[object]] = []
            for cell in root.iter():
                if _local_name(cell.tag) != "c":
                    continue
                formula = next(
                    (child for child in cell if _local_name(child.tag) == "f"),
                    None,
                )
                if formula is None:
                    continue
                attrs = [
                    (name, formula.attrib[name])
                    for name in ("t", "ref", "si", "ca", "bx")
                    if name in formula.attrib
                ]
                entries.append(
                    [
                        cell.attrib.get("r", ""),
                        attrs,
                        (formula.text or "").strip() or None,
                    ]
                )
            if entries:
                formulas[part] = entries

        external_error: str | None = None
        for part in external_link_parts:
            try:
                ElementTree.fromstring(archive.read(part))
            except ElementTree.ParseError:
                external_error = note(_ERROR_EXTERNAL_XML_UNREADABLE)
                break
        macro_error: str | None = None
        duplicate_worksheet = any(
            part in {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"} or part in worksheet_parts
            for part in duplicate_parts
        )
        duplicate_macro = any(part in macro_parts for part in duplicate_parts)
        duplicate_external = any(part in external_link_parts for part in duplicate_parts)
        if duplicate_worksheet:
            worksheet_error = worksheet_error or note(_ERROR_WORKSHEET_DUPLICATE_MEMBERS)
        if duplicate_macro:
            macro_error = note(_ERROR_MACRO_DUPLICATE_MEMBERS)
        if duplicate_external:
            external_error = note(_ERROR_EXTERNAL_DUPLICATE_MEMBERS)
        if worksheet_error is not None:
            formula_error = formula_error or note(_ERROR_FORMULA_EVIDENCE_INCOMPLETE)
        if formula_error is not None:
            formulas = None
        if formulas is not None:
            for part, entries in formulas.items():
                for cell, _attrs, formula_text in entries:
                    if isinstance(formula_text, str) and _contains_external_workbook_reference(
                        formula_text
                    ):
                        label = f"{part}:{cell}"
                        external_link_parts.append(label)
                        external_link_signatures[label] = hashlib.sha256(
                            formula_text.encode("utf-8")
                        ).hexdigest()
            external_link_parts = sorted(set(external_link_parts))

        if not worksheet_parts:
            worksheet_error = worksheet_error or note(_ERROR_WORKSHEET_INVENTORY_EMPTY)
            formula_error = formula_error or note(_ERROR_FORMULA_INVENTORY_UNAVAILABLE)
            formulas = None
        return {
            "parts": parts,
            "diagnostics": diagnostics,
            "member_digest": member_identity.hexdigest(),
            "part_count": len(parts),
            "duplicate_part_count": len(duplicate_parts),
            "part_kind_counts": dict(part_kind_counts),
            "duplicate_parts": duplicate_parts,
            "inventory_error": inventory_error,
            "macro_parts": macro_parts,
            "external_link_parts": external_link_parts,
            "macro_signatures": macro_signatures,
            "external_link_signatures": external_link_signatures,
            "worksheet_parts": worksheet_parts,
            "worksheet_names": worksheet_names,
            "worksheet_error": worksheet_error,
            "formulas": formulas,
            "formula_error": formula_error,
            "macro_error": macro_error,
            "external_error": external_error,
        }


def _not_assessed(dimension: str) -> dict[str, Any]:
    return {
        "status": "unassessed",
        "findings": [
            {
                "kind": "not_assessed",
                "message": f"{dimension} is not assessed by policy",
            }
        ],
    }


def _inventory_decision(
    dimension: str,
    config: dict[str, Any] | None,
    before_values: list[str] | None,
    after_values: list[str] | None,
    *,
    before_error: str | None = None,
    after_error: str | None = None,
    before_signatures: Mapping[str, str] | None = None,
    after_signatures: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if config is None:
        return _not_assessed(dimension)
    if (
        before_values is None
        or after_values is None
        or before_error is not None
        or after_error is not None
    ):
        return {
            "status": "unassessed",
            "findings": [
                {
                    "kind": "evidence_unavailable",
                    "message": before_error or after_error or "inventory evidence is unavailable",
                }
            ],
        }
    before_count = len(before_values)
    after_count = len(after_values)
    evidence = {
        "before_count": before_count,
        "after_count": after_count,
        "before_items": list(before_values),
        "after_items": list(after_values),
    }
    findings: list[dict[str, Any]] = []
    if "max_count" in config and after_count > config["max_count"]:
        findings.append(
            {
                "kind": "max_count_exceeded",
                "message": (
                    f"{dimension} after count {after_count} exceeds max_count {config['max_count']}"
                ),
                "max_count": config["max_count"],
                "after_count": after_count,
            }
        )
    if "expected_count" in config and after_count != config["expected_count"]:
        findings.append(
            {
                "kind": "unexpected_count",
                "message": (
                    f"{dimension} after count {after_count} does not equal "
                    f"expected_count {config['expected_count']}"
                ),
                "expected_count": config["expected_count"],
                "after_count": after_count,
            }
        )
    if "expected_names" in config and after_values != config["expected_names"]:
        findings.append(
            {
                "kind": "unexpected_items",
                "message": f"{dimension} after inventory differs from expected items",
                "expected_items": list(config["expected_names"]),
                "after_items": list(after_values),
            }
        )
    signatures_changed = (
        before_signatures is not None
        and after_signatures is not None
        and dict(before_signatures) != dict(after_signatures)
    )
    if config.get("mode") == "unchanged" and (before_values != after_values or signatures_changed):
        findings.append(
            {
                "kind": "inventory_changed",
                "message": f"{dimension} changed between before and after workbooks",
                "before_items": list(before_values),
                "after_items": list(after_values),
            }
        )
    return {
        "status": "failed" if findings else "passed",
        "evidence": evidence,
        "findings": findings,
    }


def _formula_decision(
    config: dict[str, Any] | None, before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    if config is None:
        return _not_assessed("formula_integrity")
    before_formulas = before["formulas"]
    after_formulas = after["formulas"]
    if before_formulas is None or after_formulas is None:
        return {
            "status": "unassessed",
            "findings": [
                {
                    "kind": "evidence_unavailable",
                    "message": before["formula_error"]
                    or after["formula_error"]
                    or "formula evidence is unavailable",
                }
            ],
        }
    evidence = {
        "before_formula_count": sum(len(entries) for entries in before_formulas.values()),
        "after_formula_count": sum(len(entries) for entries in after_formulas.values()),
    }
    if before_formulas != after_formulas:
        return {
            "status": "failed",
            "evidence": evidence,
            "findings": [
                {
                    "kind": "formula_changed",
                    "message": "worksheet formulas changed between before and after workbooks",
                }
            ],
        }

    return {"status": "passed", "evidence": evidence, "findings": []}
def _fidelity_dimension_decision(
    dimension: str,
    config: dict[str, Any] | None,
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    if config is None:
        return _not_assessed(dimension)
    semantic_features, part_features = _FIDELITY_DIMENSION_FEATURES[dimension]
    before = audit["before"]
    after = audit["after"]
    evidence = {
        "before": {
            "semantic_fingerprint_counts": {
                feature: before["semantic_fingerprint_counts"].get(feature, 0)
                for feature in semantic_features
            },
            "feature_part_counts": {
                feature: before["feature_part_counts"].get(feature, 0)
                for feature in part_features
            },
        },
        "after": {
            "semantic_fingerprint_counts": {
                feature: after["semantic_fingerprint_counts"].get(feature, 0)
                for feature in semantic_features
            },
            "feature_part_counts": {
                feature: after["feature_part_counts"].get(feature, 0)
                for feature in part_features
            },
        },
    }
    semantic_prefixes = tuple(f"{feature}_" for feature in semantic_features)
    related_issues = [
        {"kind": issue.get("kind"), "part": issue.get("part")}
        for issue in audit["issues"]
        if (
            str(issue.get("kind", "")).startswith(semantic_prefixes)
            or (
                issue.get("kind") == "feature_part_loss"
                and issue.get("part") in part_features
            )
        )
    ]
    findings: list[dict[str, Any]] = []
    if evidence["before"] != evidence["after"]:
        findings.append({"kind": "fidelity_inventory_changed"})
    if related_issues:
        findings.append({"kind": "fidelity_drift", "issues": related_issues})
    return {"status": "failed" if findings else "passed", "evidence": evidence, "findings": findings}


def _package_decision(
    config: dict[str, Any] | None,
    audit: dict[str, Any],
    before_inventory: dict[str, Any],
    after_inventory: dict[str, Any],
) -> dict[str, Any]:
    if config is None:
        return _not_assessed("package_integrity")
    issues = [
        {key: issue[key] for key in ("kind", "part", "message") if key in issue}
        for issue in audit.get("issues", [])
    ]
    seen_messages = {str(issue.get("message", "")) for issue in issues}
    for label, inventory in (
        ("before", before_inventory),
        ("after", after_inventory),
    ):
        for error_key in ("inventory_error", "worksheet_error", "formula_error"):
            message = inventory.get(error_key)
            if not message or message in seen_messages:
                continue
            seen_messages.add(message)
            issues.append(
                {
                    "kind": "package_evidence_incomplete",
                    "part": "package",
                    "message": f"{label} workbook: {message}",
                }
            )
    issues.sort(
        key=lambda issue: (
            str(issue.get("kind", "")),
            str(issue.get("part", "")),
            str(issue.get("message", "")),
        )
    )
    return {
        "status": "failed" if issues else "passed",
        "evidence": {"issue_count": len(issues)},
        "findings": issues,
    }


def _guard_evaluation(
    before_path: Path,
    after_path: Path,
    normalized_policy: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Audit both packages once and return the report plus both inventories."""
    try:
        audit = fidelity_audit.audit(
            before_path,
            after_path,
            compact_semantic_drift=True,
        )
        before_inventory = _package_inventory(before_path)
        after_inventory = _package_inventory(after_path)
    except BadZipFile as exc:
        raise GuardInputError("workbook is not a valid OOXML package") from exc
    audit["before"]["path"] = before_path.name
    audit["after"]["path"] = after_path.name
    policy_decisions = {
        "macro_inventory": _inventory_decision(
            "macro_inventory",
            normalized_policy["macro_inventory"],
            before_inventory["macro_parts"],
            after_inventory["macro_parts"],
            before_error=before_inventory["macro_error"],
            after_error=after_inventory["macro_error"],
            before_signatures=before_inventory["macro_signatures"],
            after_signatures=after_inventory["macro_signatures"],
        ),
        "external_link_inventory": _inventory_decision(
            "external_link_inventory",
            normalized_policy["external_link_inventory"],
            before_inventory["external_link_parts"],
            after_inventory["external_link_parts"],
            before_error=(
                before_inventory["external_error"]
                or before_inventory["worksheet_error"]
                or before_inventory["formula_error"]
            ),
            after_error=(
                after_inventory["external_error"]
                or after_inventory["worksheet_error"]
                or after_inventory["formula_error"]
            ),
            before_signatures=before_inventory["external_link_signatures"],
            after_signatures=after_inventory["external_link_signatures"],
        ),
        "worksheet_inventory": _inventory_decision(
            "worksheet_inventory",
            normalized_policy["worksheet_inventory"],
            before_inventory["worksheet_names"],
            after_inventory["worksheet_names"],
            before_error=before_inventory["worksheet_error"],
            after_error=after_inventory["worksheet_error"],
        ),
        "formula_integrity": _formula_decision(
            normalized_policy["formula_integrity"], before_inventory, after_inventory
        ),
        "package_integrity": _package_decision(
            normalized_policy["package_integrity"],
            audit,
            before_inventory,
            after_inventory,
        ),
    }
    policy_decisions.update(
        {
            dimension: _fidelity_dimension_decision(
                dimension,
                normalized_policy[dimension],
                audit,
            )
            for dimension in _FIDELITY_DIMENSION_FEATURES
            if dimension in normalized_policy
        }
    )
    statuses = [decision["status"] for decision in policy_decisions.values()]
    if "failed" in statuses:
        status = "failed"
    elif "unassessed" in statuses:
        status = "unassessed"
    else:
        status = "passed"
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "before": _artifact_summary(before_path),
        "after": _artifact_summary(after_path),
        "policy": normalized_policy,
        "policy_decisions": policy_decisions,
        "fidelity_audit": audit,
        "not_assessed": [
            "intended change authorization",
            "calculation correctness",
            "rendered appearance",
            "macro execution",
        ],
    }
    return report, before_inventory, after_inventory


def _workbook_comparison(report: Mapping[str, Any]) -> WorkbookComparison:
    """Reduce the complete Guard report to the stable public summary."""
    decisions = report["policy_decisions"]
    issue_codes: set[str] = set()
    issue_categories: list[str] = []
    issue_count = 0
    for category in _POLICY_DIMENSIONS:
        decision = decisions[category]
        if decision["status"] != "failed":
            continue
        issue_categories.append(category)
        findings = decision.get("findings", [])
        issue_count += len(findings)
        issue_codes.update(
            finding["kind"]
            for finding in findings
            if isinstance(finding, Mapping) and isinstance(finding.get("kind"), str)
        )
    before = report["before"]
    after = report["after"]
    return WorkbookComparison(
        status=report["status"],
        passed=report["status"] == "passed",
        issue_count=issue_count,
        issue_codes=tuple(sorted(issue_codes)),
        issue_categories=tuple(issue_categories),
        before=WorkbookIdentity(
            filename=before["filename"],
            sha256=before["sha256"],
            size_bytes=before["size_bytes"],
        ),
        after=WorkbookIdentity(
            filename=after["filename"],
            sha256=after["sha256"],
            size_bytes=after["size_bytes"],
        ),
    )


def compare_workbooks(
    before: str | os.PathLike[str],
    after: str | os.PathLike[str],
    *,
    policy: Mapping[str, Any] | None = None,
) -> WorkbookComparison:
    """Compare two OOXML workbooks using Guard without writing a report file."""
    before_path = _validated_workbook_source(before, label="before")
    after_path = _validated_workbook_source(after, label="after")
    if before_path == after_path:
        raise GuardInputError("before and after must be different files")
    normalized_policy = _normalized_policy(_POLICY_DEFAULT if policy is None else policy)
    report, _, _ = _guard_evaluation(before_path, after_path, normalized_policy)
    return _workbook_comparison(report)


def run_guard(
    *,
    before: str | os.PathLike[str],
    after: str | os.PathLike[str],
    output: Path | None = None,
    policy: Mapping[str, Any] | None | object = _POLICY_DEFAULT,
) -> dict[str, Any]:
    """Run the fidelity audit and evaluate one explicit bounded policy."""
    before_path = _validated_workbook_source(before, label="before")
    after_path = _validated_workbook_source(after, label="after")
    if before_path == after_path:
        raise GuardInputError("before and after must be different files")
    report, _, _ = _guard_evaluation(before_path, after_path, _normalized_policy(policy))
    if output is not None:
        output_path = _validated_output(output, before=before_path, after=after_path)
        _atomic_write_json(output_path, report)
    return report

def _compact_policy_decisions(
    decisions: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Keep only status, numeric evidence, and stable finding categories."""
    compact: dict[str, dict[str, Any]] = {}
    for dimension in _POLICY_DIMENSIONS:
        decision = decisions[dimension]
        evidence = decision.get("evidence", {})
        numeric_evidence = (
            {
                key: value
                for key, value in evidence.items()
                if key in _SAFE_DECISION_EVIDENCE_KEYS
                and isinstance(value, int)
                and not isinstance(value, bool)
            }
            if isinstance(evidence, Mapping)
            else {}
        )
        finding_kinds = sorted(
            {
                finding["kind"]
                for finding in decision.get("findings", [])
                if isinstance(finding, Mapping) and isinstance(finding.get("kind"), str)
            }
        )
        compact[dimension] = {
            "status": decision["status"],
            "evidence": numeric_evidence,
            "finding_count": len(decision.get("findings", [])),
            "finding_kinds": finding_kinds,
        }
    return compact


def _package_finding_summary(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize Guard package findings without serializing part details."""
    kinds = Counter(
        issue["kind"]
        for issue in audit.get("issues", [])
        if isinstance(issue, Mapping) and isinstance(issue.get("kind"), str)
    )
    return {
        "issue_count": int(audit["issue_count"]),
        "by_kind": [{"kind": kind, "count": count} for kind, count in sorted(kinds.items())],
    }


def _support_bundle_exit_status(status: str) -> dict[str, Any]:
    """Map Guard's tri-state result to the operations CLI's exit contract."""
    if status == "passed":
        return {"code": SUPPORT_BUNDLE_EXIT_PASSED, "category": "success"}
    return {
        "code": SUPPORT_BUNDLE_EXIT_UNACCEPTABLE,
        "category": "guard_unacceptable",
    }


def _environment() -> dict[str, str]:
    """Report the runtime that produced the bundle, with no host identity."""
    from wolfxl import __version__ as wolfxl_version

    return {
        "wolfxl_version": str(wolfxl_version),
        "python_version": platform.python_version(),
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
    }


def _package_identity(summary: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    """Identify one package by digest and redacted part-kind counts only."""
    return {
        "sha256": summary["sha256"],
        "size_bytes": summary["size_bytes"],
        "member_digest": inventory["member_digest"],
        "part_count": inventory["part_count"],
        "duplicate_part_count": inventory["duplicate_part_count"],
        "part_kinds": [
            {"kind": kind, "count": count}
            for kind, count in sorted(inventory["part_kind_counts"].items())
        ],
    }


def _policy_snapshot(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Snapshot the active bounds, counting expected worksheet names only.

    The digest covers this redacted snapshot rather than the policy object, so
    the bundle cannot be used to confirm a guessed worksheet-name list.
    """
    dimensions: dict[str, dict[str, Any]] = {}
    for dimension in _POLICY_DIMENSIONS:
        config = policy[dimension]
        if config is None:
            dimensions[dimension] = {"assessed": False}
            continue
        snapshot: dict[str, Any] = {"assessed": True}
        if "mode" in config:
            snapshot["mode"] = config["mode"]
        for field in ("max_count", "expected_count"):
            if field in config:
                snapshot[field] = int(config[field])
        if "expected_names" in config:
            snapshot["expected_name_count"] = len(config["expected_names"])
        dimensions[dimension] = snapshot
    digest = hashlib.sha256(
        json.dumps(dimensions, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {"sha256": digest, "dimensions": dimensions}


def _typed_failure_codes(inventory: Mapping[str, Any]) -> list[str]:
    """Normalize one package's inventory diagnostics to stable typed codes."""
    return sorted(
        {
            _INVENTORY_ERROR_CODES.get(message, _UNCLASSIFIED_ERROR_CODE)
            for message in inventory["diagnostics"]
        }
    )


def _relationship_classification(codes: Sequence[str]) -> str:
    for code, classification in _RELATIONSHIP_CLASSIFICATIONS:
        if code in codes:
            return classification
    return _RELATIONSHIPS_WELL_FORMED


def _support_bundle(
    report: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    before_inventory: Mapping[str, Any],
    after_inventory: Mapping[str, Any],
) -> dict[str, Any]:
    status = str(report["status"])
    source_failures = _typed_failure_codes(before_inventory)
    target_failures = _typed_failure_codes(after_inventory)
    return {
        "schema_version": SUPPORT_BUNDLE_SCHEMA_VERSION,
        "bundle_type": "workbook_guard_pilot_support",
        "guard": {
            "schema_version": report["schema_version"],
            "status": status,
            "issue_count": report["fidelity_audit"]["issue_count"],
        },
        "environment": _environment(),
        "content_identities": {
            "source": _package_identity(report["before"], before_inventory),
            "target": _package_identity(report["after"], after_inventory),
        },
        "policy": _policy_snapshot(policy),
        "policy_decisions": _compact_policy_decisions(report["policy_decisions"]),
        "package_findings": _package_finding_summary(report["fidelity_audit"]),
        "reproduction": {
            "argv": [
                "wolfxl-ops",
                "guard-bundle",
                "--before",
                "<source.xlsx>",
                "--after",
                "<target.xlsx>",
                "--output",
                "<support.json>",
                "--policy",
                "<policy.json>",
            ],
            "typed_failures": [
                {"scope": scope, "code": code}
                for scope, failures in (("source", source_failures), ("target", target_failures))
                for code in failures
            ],
            "relationship_classification": {
                "source": _relationship_classification(source_failures),
                "target": _relationship_classification(target_failures),
            },
        },
        "exit_status": _support_bundle_exit_status(status),
    }


def run_guard_support_bundle(
    *,
    before: Path,
    after: Path,
    output: Path,
    policy: Path,
) -> dict[str, Any]:
    """Write a privacy-safe, deterministic support bundle for one Guard run."""
    before_path = _validated_workbook(before, label="before")
    after_path = _validated_workbook(after, label="after")
    if before_path == after_path:
        raise GuardInputError("before and after must be different files")
    output_path = _validated_output(output, before=before_path, after=after_path)
    policy_path = _validated_policy_path(policy)
    if output_path == policy_path:
        raise GuardInputError("output must not replace the policy input")
    if output_path.exists() and output_path.is_dir():
        raise GuardInputError("output must be a JSON file")
    normalized_policy = _load_policy(policy_path)

    report, before_inventory, after_inventory = _guard_evaluation(
        before_path, after_path, normalized_policy
    )
    bundle = _support_bundle(
        report,
        policy=normalized_policy,
        before_inventory=before_inventory,
        after_inventory=after_inventory,
    )
    _atomic_write_json(output_path, bundle)
    return bundle


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--policy",
        type=Path,
        help="JSON policy object describing bounded Guard checks",
    )
    return parser.parse_args(argv)


def _error_document(category: str, message: str, *, exception: str | None = None) -> str:
    error: dict[str, Any] = {"category": category, "message": message}
    if exception is not None:
        error["exception"] = exception
    return json.dumps(
        {"schema_version": SCHEMA_VERSION, "status": "error", "error": error},
        sort_keys=True,
        separators=(",", ":"),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.policy is None:
            raise GuardInputError("policy input is required")
        policy = load_guard_policy(args.policy)
        report = run_guard(
            before=args.before,
            after=args.after,
            output=args.output,
            policy=policy,
        )
    except (GuardInputError, BadZipFile) as exc:
        print(_error_document("invalid_input", str(exc)), file=sys.stderr)
        return EXIT_INVALID_INPUT
    except OSError as exc:
        print(
            _error_document(
                "io_error",
                "workbook comparison could not be read or written",
                exception=type(exc).__name__,
            ),
            file=sys.stderr,
        )
        return EXIT_INVALID_INPUT
    except Exception as exc:
        print(
            _error_document(
                "internal_error",
                "workbook comparison failed unexpectedly",
                exception=type(exc).__name__,
            ),
            file=sys.stderr,
        )
        return EXIT_INTERNAL_ERROR

    summary = {
        "status": report["status"],
        "issue_count": report["fidelity_audit"]["issue_count"],
        "output": args.output.name,
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return EXIT_PASSED if report["status"] == "passed" else EXIT_REGRESSION


if __name__ == "__main__":
    raise SystemExit(main())
