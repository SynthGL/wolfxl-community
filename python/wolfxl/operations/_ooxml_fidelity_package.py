"""Package inspection: content types, relationships, and part classification.

Internal to the OOXML fidelity audit. The public surface stays
``wolfxl.operations._ooxml_fidelity``.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from typing import Iterable
from xml.etree import ElementTree

from ._ooxml_fidelity_constants import CT_NS, FEATURE_PART_PREFIXES, REL_NS
from ._ooxml_fidelity_models import Relationship
from ._ooxml_fidelity_xml import _read_part_bytes_or_none, _read_xml_or_none


def _read_content_overrides(archive: zipfile.ZipFile) -> dict[str, str]:
    try:
        xml = archive.read("[Content_Types].xml")
    except KeyError:
        return {}
    root = ElementTree.fromstring(xml)
    overrides: dict[str, str] = {}
    for node in root.findall(f"{CT_NS}Override"):
        part_name = node.attrib.get("PartName", "").lstrip("/")
        content_type = node.attrib.get("ContentType")
        if part_name and content_type:
            overrides[part_name] = content_type
    return overrides


def _read_content_defaults(archive: zipfile.ZipFile) -> dict[str, str]:
    try:
        xml = archive.read("[Content_Types].xml")
    except KeyError:
        return {}
    root = ElementTree.fromstring(xml)
    defaults: dict[str, str] = {}
    for node in root.findall(f"{CT_NS}Default"):
        extension = node.attrib.get("Extension")
        content_type = node.attrib.get("ContentType")
        if extension and content_type:
            defaults[extension] = content_type
    return defaults


def _read_xml_parse_errors(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    xml_cache = getattr(archive, "_wolfxl_ooxml_xml_cache", None)
    if xml_cache is None:
        xml_cache = {}
        setattr(archive, "_wolfxl_ooxml_xml_cache", xml_cache)
    for part in sorted(name for name in archive.namelist() if name.endswith((".xml", ".rels"))):
        if part in xml_cache:
            continue
        payload = _read_part_bytes_or_none(archive, part)
        if payload is None:
            xml_cache[part] = None
            continue
        try:
            xml_cache[part] = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            xml_cache[part] = None
            errors.append((part, str(exc)))
    return errors


def _read_relationships(archive: zipfile.ZipFile) -> list[Relationship]:
    out: list[Relationship] = []
    for rels_part in sorted(p for p in archive.namelist() if p.endswith(".rels")):
        root = _read_xml_or_none(archive, rels_part)
        if root is None:
            continue
        seen_ids: set[str] = set()
        for node in root.findall(f"{REL_NS}Relationship"):
            rel_id = node.attrib.get("Id", "")
            rel_type = node.attrib.get("Type", "")
            target = node.attrib.get("Target", "")
            target_mode = node.attrib.get("TargetMode")
            resolved = _resolve_relationship_target(rels_part, target, target_mode)
            if rel_id in seen_ids:
                rel_id = f"{rel_id}#duplicate"
            seen_ids.add(rel_id)
            out.append(
                Relationship(
                    rels_part=rels_part,
                    rel_id=rel_id,
                    rel_type=rel_type,
                    target=target,
                    target_mode=target_mode,
                    resolved_target=resolved,
                )
            )
    return out


def _resolve_relationship_target(
    rels_part: str, target: str, target_mode: str | None
) -> str | None:
    if not target or target_mode == "External" or target.startswith("#"):
        return None
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))

    source_part = _source_part_for_rels(rels_part)
    source_dir = posixpath.dirname(source_part)
    return posixpath.normpath(posixpath.join(source_dir, target))


def _source_part_for_rels(rels_part: str) -> str:
    if rels_part == "_rels/.rels":
        return ""
    if "\\" in rels_part or rels_part.startswith("/") or "/_rels/" not in rels_part:
        raise ValueError(f"unsafe OOXML package part path: {rels_part}")
    prefix, name = rels_part.rsplit("/_rels/", 1)
    return posixpath.join(prefix, name.removesuffix(".rels"))


def _relationships_by_owner(
    archive: zipfile.ZipFile,
) -> dict[str, list[tuple[str, str, str, str | None]]]:
    lookup: dict[str, list[tuple[str, str, str, str | None]]] = {}
    for rel in _read_relationships(archive):
        owner = _source_part_for_rels(rel.rels_part)
        if owner:
            lookup.setdefault(owner, []).append(
                (rel.rel_id, rel.rel_type, rel.target, rel.target_mode)
            )
    return lookup


def _rels_target_lookup(archive: zipfile.ZipFile) -> dict[tuple[str, str], str]:
    lookup: dict[tuple[str, str], str] = {}
    for rel in _read_relationships(archive):
        owner = _source_part_for_rels(rel.rels_part)
        if owner:
            lookup[(owner, rel.rel_id)] = rel.target
    return lookup


def _relationship_key(rel: Relationship) -> tuple[str, str, str, str | None]:
    return (rel.rels_part, rel.rel_type, rel.target, rel.target_mode)


def _feature_xml_parts(parts: set[str], prefix: str, suffix: str) -> Iterable[str]:
    return (part for part in parts if part.startswith(prefix) and part.endswith(suffix))


def _is_chart_style_part(part: str) -> bool:
    name = posixpath.basename(part)
    return name.startswith("style") or name.startswith("colors")


def _worksheet_parts(parts: Iterable[str]) -> Iterable[str]:
    pattern = re.compile(r"^xl/worksheets/sheet\d+\.xml$")
    return (part for part in parts if pattern.match(part))


def _classify_feature_parts(parts: set[str]) -> dict[str, list[str]]:
    classified: dict[str, list[str]] = {}
    for feature, prefixes in FEATURE_PART_PREFIXES.items():
        classified[feature] = sorted(
            part for part in parts if any(part.startswith(prefix) for prefix in prefixes)
        )
    return classified
