"""Post-save package-shape normalization for openpyxl-compatible saves."""

from __future__ import annotations

import copy
import os
import posixpath
import re
import tempfile
import zipfile
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET


CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

CT_TAG_OVERRIDE = f"{{{CT_NS}}}Override"
CT_TAG_DEFAULT = f"{{{CT_NS}}}Default"
REL_TAG_REL = f"{{{PKG_REL_NS}}}Relationship"
MAIN_TAG_CELL = f"{{{MAIN_NS}}}c"
MAIN_TAG_IS = f"{{{MAIN_NS}}}is"
MAIN_TAG_V = f"{{{MAIN_NS}}}v"
MAIN_TAG_DRAWING = f"{{{MAIN_NS}}}drawing"
MAIN_TAG_LEGACY_DRAWING = f"{{{MAIN_NS}}}legacyDrawing"
RID_ATTR = f"{{{REL_NS}}}id"

REL_TYPE_SHARED_STRINGS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"
)
REL_TYPE_DRAWING = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
)
REL_TYPE_COMMENTS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
)
REL_TYPE_VML_DRAWING = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"
)
REL_TYPE_VBA_PROJECT = "http://schemas.microsoft.com/office/2006/relationships/vbaProject"

SHEET_MAIN = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
SHEET_MACRO = "application/vnd.ms-excel.sheet.macroEnabled.main+xml"


def normalize_openpyxl_package_shape(filename: str, *, keep_vba: bool) -> None:
    """Normalize a saved OOXML package to openpyxl's VBA save shape."""
    try:
        with zipfile.ZipFile(filename, "r") as src:
            infos = src.infolist()
            parts = {info.filename: src.read(info.filename) for info in infos}
    except (OSError, zipfile.BadZipFile):
        return

    if "[Content_Types].xml" not in parts:
        return

    changed = False
    removed: set[str] = set()
    renames: dict[str, str] = {}

    has_vba_project = "xl/vbaProject.bin" in parts or _workbook_has_vba_rel(parts)
    if not (keep_vba or has_vba_project):
        return

    if keep_vba:
        changed |= _inline_shared_strings(parts)
        if "xl/sharedStrings.xml" in parts and not _worksheets_use_shared_strings(parts):
            removed.add("xl/sharedStrings.xml")
            changed = True
        changed |= _normalize_root_comment_parts(parts, renames)
        changed |= _prune_legacy_control_drawings(parts, removed)
        changed |= _normalize_vml_relationship_ids(parts)
    else:
        changed |= _inline_shared_strings(parts)
        if "xl/sharedStrings.xml" in parts and not _worksheets_use_shared_strings(parts):
            removed.add("xl/sharedStrings.xml")
            changed = True
        changed |= _normalize_root_comment_parts(parts, renames)
        changed |= _prune_legacy_control_drawings(parts, removed)
        changed |= _drop_vba_only_parts(parts, removed)
        if has_vba_project:
            changed = True

    if removed or renames or (not keep_vba and has_vba_project):
        changed |= _rewrite_rels(parts, removed, renames, keep_vba=keep_vba)
        changed |= _rewrite_content_types(parts, removed, renames, keep_vba=keep_vba)

    if not changed:
        return

    _rewrite_zip(filename, infos, parts, removed, renames)


def _workbook_has_vba_rel(parts: dict[str, bytes]) -> bool:
    rels = parts.get("xl/_rels/workbook.xml.rels")
    return bool(rels and REL_TYPE_VBA_PROJECT.encode("ascii") in rels)


def _inline_shared_strings(parts: dict[str, bytes]) -> bool:
    if "xl/sharedStrings.xml" not in parts:
        return False
    try:
        sst = ET.fromstring(parts["xl/sharedStrings.xml"])
    except ET.ParseError:
        return False
    strings = [si for si in sst if _local_name(si.tag) == "si"]
    if not strings:
        return False

    changed = False
    for name in _worksheet_parts(parts):
        try:
            root = ET.fromstring(parts[name])
        except ET.ParseError:
            continue
        sheet_changed = False
        for cell in root.iter(MAIN_TAG_CELL):
            if cell.get("t") != "s":
                continue
            value = cell.find(MAIN_TAG_V)
            if value is None or value.text is None:
                continue
            try:
                idx = int(value.text)
                si = strings[idx]
            except (ValueError, IndexError):
                continue
            cell.remove(value)
            for old_inline in list(cell.findall(MAIN_TAG_IS)):
                cell.remove(old_inline)
            inline = ET.Element(MAIN_TAG_IS)
            for child in list(si):
                inline.append(copy.deepcopy(child))
            cell.append(inline)
            cell.set("t", "inlineStr")
            sheet_changed = True
        if sheet_changed:
            parts[name] = _xml_bytes(root)
            changed = True
    return changed


def _worksheet_parts(parts: dict[str, bytes]) -> list[str]:
    return sorted(
        name
        for name in parts
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
    )


def _worksheets_use_shared_strings(parts: dict[str, bytes]) -> bool:
    return any(
        re.search(rb"\bt\s*=\s*['\"]s['\"]", parts[name]) is not None
        for name in _worksheet_parts(parts)
    )


def _normalize_root_comment_parts(parts: dict[str, bytes], renames: dict[str, str]) -> bool:
    changed = False
    for name in sorted(parts):
        match = re.fullmatch(r"xl/comments(\d+)\.xml", name)
        if not match:
            continue
        dst = f"xl/comments/comment{match.group(1)}.xml"
        if dst not in parts:
            renames[name] = dst
            changed = True
    return changed


def _prune_legacy_control_drawings(parts: dict[str, bytes], removed: set[str]) -> bool:
    changed = False
    for rels_name in sorted(name for name in parts if name.startswith("xl/worksheets/_rels/")):
        try:
            root = ET.fromstring(parts[rels_name])
        except ET.ParseError:
            continue
        rels = list(root)
        drawing_rels = [
            rel
            for rel in rels
            if rel.get("Type") == REL_TYPE_DRAWING
            and _drawing_is_legacy_control_shape(
                parts.get(_resolve_rel_target(_rels_owner_part(rels_name), rel.get("Target", "")))
            )
        ]
        if not drawing_rels:
            continue
        legacy_rels = [rel for rel in rels if rel.get("Type") == REL_TYPE_VML_DRAWING]
        macro_control_rels = [
            rel
            for rel in rels
            if rel.get("Type", "").endswith(("/control", "/ctrlProp", "/image", "/printerSettings"))
        ]
        if not legacy_rels or not macro_control_rels:
            continue

        pruned_ids = {rel.get("Id") for rel in drawing_rels if rel.get("Id")}
        for rel in drawing_rels:
            target = _resolve_rel_target(_rels_owner_part(rels_name), rel.get("Target", ""))
            if target:
                removed.add(target)
                rels_part = _part_rels_path(target)
                if rels_part in parts:
                    removed.add(rels_part)
            root.remove(rel)
        for rel in macro_control_rels:
            if rel.get("Type", "").endswith(("/control", "/ctrlProp", "/image", "/printerSettings")):
                root.remove(rel)
                target = _resolve_rel_target(_rels_owner_part(rels_name), rel.get("Target", ""))
                if target.endswith(".bin") and "printerSettings" in target:
                    removed.add(target)

        parts[rels_name] = _xml_bytes(root)
        sheet_name = _rels_owner_part(rels_name)
        if _remove_sheet_drawing_elements(parts, sheet_name, pruned_ids):
            changed = True
        changed = True
    return changed


def _drawing_is_legacy_control_shape(data: bytes | None) -> bool:
    if not data:
        return False
    # Ordinary charts/images must survive; legacy form-control drawings in the
    # openpyxl VBA fixtures are shape-only drawingML AlternateContent blocks.
    return (
        b"<xdr:sp" in data
        and b"<xdr:pic" not in data
        and b"<xdr:graphicFrame" not in data
    )


def _normalize_vml_relationship_ids(parts: dict[str, bytes]) -> bool:
    changed = False
    for rels_name in sorted(name for name in parts if name.startswith("xl/worksheets/_rels/")):
        try:
            root = ET.fromstring(parts[rels_name])
        except ET.ParseError:
            continue
        vml_rels = [rel for rel in root if rel.get("Type") == REL_TYPE_VML_DRAWING]
        if len(vml_rels) != 1:
            continue
        rel = vml_rels[0]
        old_id = rel.get("Id")
        owner = _rels_owner_part(rels_name)
        old_target = rel.get("Target", "")
        target = _resolve_rel_target(owner, old_target)
        if not target:
            continue
        rel_changed = old_id != "anysvml" or old_target != "/" + target
        rel.set("Id", "anysvml")
        rel.set("Target", "/" + target)
        changed |= rel_changed
        if _update_legacy_drawing_id(parts, owner, old_id, "anysvml"):
            changed = True
        if rel_changed:
            parts[rels_name] = _xml_bytes(root)
    return changed


def _remove_sheet_drawing_elements(
    parts: dict[str, bytes],
    sheet_name: str,
    pruned_ids: set[str | None],
) -> bool:
    if sheet_name not in parts:
        return False
    try:
        root = ET.fromstring(parts[sheet_name])
    except ET.ParseError:
        return False
    changed = False
    for drawing in list(root.findall(MAIN_TAG_DRAWING)):
        if drawing.get(RID_ATTR) in pruned_ids:
            root.remove(drawing)
            changed = True
    if changed:
        parts[sheet_name] = _xml_bytes(root)
    return changed


def _update_legacy_drawing_id(
    parts: dict[str, bytes],
    sheet_name: str,
    old_id: str | None,
    new_id: str,
) -> bool:
    if sheet_name not in parts:
        return False
    try:
        root = ET.fromstring(parts[sheet_name])
    except ET.ParseError:
        return False
    changed = False
    for legacy in root.findall(MAIN_TAG_LEGACY_DRAWING):
        if old_id is None or legacy.get(RID_ATTR) == old_id:
            legacy.set(RID_ATTR, new_id)
            changed = True
    if changed:
        parts[sheet_name] = _xml_bytes(root)
    return changed


def _drop_vba_only_parts(parts: dict[str, bytes], removed: set[str]) -> bool:
    before = len(removed)
    for name in parts:
        if (
            name == "xl/vbaProject.bin"
            or name.startswith("xl/activeX/")
            or name.startswith("xl/ctrlProps/")
            or name.startswith("customUI/")
        ):
            removed.add(name)
    return len(removed) != before


def _rewrite_rels(
    parts: dict[str, bytes],
    removed: set[str],
    renames: dict[str, str],
    *,
    keep_vba: bool,
) -> bool:
    changed = False
    for rels_name in sorted(name for name in parts if name.endswith(".rels")):
        if rels_name in removed:
            continue
        try:
            root = ET.fromstring(parts[rels_name])
        except ET.ParseError:
            continue
        owner = _rels_owner_part(rels_name)
        rel_changed = False
        for rel in list(root):
            target = rel.get("Target", "")
            part = _resolve_rel_target(owner, target)
            rel_type = rel.get("Type", "")
            if part in renames:
                new_part = renames[part]
                rel.set("Target", "/" + new_part)
                rel_changed = True
            elif part in removed or (keep_vba and rel_type == REL_TYPE_SHARED_STRINGS):
                root.remove(rel)
                rel_changed = True
            elif not keep_vba and rel_type == REL_TYPE_VBA_PROJECT:
                root.remove(rel)
                rel_changed = True
        if rel_changed:
            if len(root) == 0 and rels_name.startswith("xl/worksheets/_rels/"):
                removed.add(rels_name)
            else:
                parts[rels_name] = _xml_bytes(root)
            changed = True
    return changed


def _rewrite_content_types(
    parts: dict[str, bytes],
    removed: set[str],
    renames: dict[str, str],
    *,
    keep_vba: bool,
) -> bool:
    try:
        root = ET.fromstring(parts["[Content_Types].xml"])
    except ET.ParseError:
        return False

    changed = False
    seen: set[str] = set()
    for child in list(root):
        if child.tag == CT_TAG_DEFAULT:
            if (
                not keep_vba
                and child.get("Extension") == "bin"
                and child.get("ContentType") == "application/vnd.ms-office.vbaProject"
            ):
                root.remove(child)
                changed = True
            continue
        if child.tag != CT_TAG_OVERRIDE:
            continue
        part_name = child.get("PartName", "")
        part = part_name.lstrip("/")
        if part in renames:
            part = renames[part]
            child.set("PartName", "/" + part)
            changed = True
        content_type = child.get("ContentType", "")
        if (
            part in removed
            or (keep_vba and part == "xl/sharedStrings.xml")
            or (not keep_vba and content_type == SHEET_MACRO)
        ):
            if not keep_vba and content_type == SHEET_MACRO and part == "xl/workbook.xml":
                child.set("ContentType", SHEET_MAIN)
                changed = True
            else:
                root.remove(child)
                changed = True
                continue
        part_name = child.get("PartName", "")
        if part_name in seen:
            root.remove(child)
            changed = True
            continue
        seen.add(part_name)

    if changed:
        parts["[Content_Types].xml"] = _xml_bytes(root)
    return changed


def _rewrite_zip(
    filename: str,
    infos: list[zipfile.ZipInfo],
    parts: dict[str, bytes],
    removed: set[str],
    renames: dict[str, str],
) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix="wolfxl-package-shape-", suffix=".xlsx")
    os.close(fd)
    emitted: set[str] = set()
    try:
        with zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in infos:
                name = info.filename
                if name in removed:
                    continue
                out_name = renames.get(name, name)
                if out_name in emitted:
                    continue
                data = parts.get(name)
                if data is None:
                    continue
                info.filename = out_name
                dst.writestr(info, data)
                emitted.add(out_name)
        os.replace(tmp_name, filename)
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def _rels_owner_part(rels_name: str) -> str:
    if rels_name == "_rels/.rels":
        return ""
    path = PurePosixPath(rels_name)
    if path.parent.name != "_rels":
        return rels_name
    return str(path.parent.parent / path.name.removesuffix(".rels"))


def _part_rels_path(part_name: str) -> str:
    part = PurePosixPath(part_name)
    return str(part.parent / "_rels" / f"{part.name}.rels")


def _resolve_rel_target(owner_part: str, target: str) -> str:
    if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return ""
    if target.startswith("/"):
        return target.lstrip("/")
    base = posixpath.dirname(owner_part)
    return posixpath.normpath(posixpath.join(base, target)).lstrip("/")


def _xml_bytes(root: ET.Element) -> bytes:
    if root.tag.startswith("{"):
        ET.register_namespace("", root.tag[1:].split("}", 1)[0])
    ET.register_namespace("r", REL_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=False)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
