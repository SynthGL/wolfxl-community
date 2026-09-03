"""Per-feature semantic fingerprints for the OOXML package fidelity audit.

Internal to the OOXML fidelity audit. The public surface stays
``wolfxl.operations._ooxml_fidelity``.
"""

from __future__ import annotations

import hashlib
import zipfile

from ._ooxml_fidelity_constants import (
    CF_EXTENSION_NAMES,
    CONDITIONAL_FORMATTING_MARKERS,
    DATA_VALIDATION_MARKERS,
    EXTENSION_MARKERS,
    FORMULA_MARKERS,
    PAGE_SETUP_MARKERS,
    SLICER_EXTENSION_NAMES,
    TIMELINE_EXTENSION_NAMES,
)
from ._ooxml_fidelity_extract import (
    _chart_axes,
    _chart_axis_ids,
    _chart_series,
    _chart_types,
    _defined_name_refs,
    _external_sheet_data,
    _external_sheet_names,
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
from ._ooxml_fidelity_package import (
    _feature_xml_parts,
    _is_chart_style_part,
    _read_content_defaults,
    _relationships_by_owner,
    _rels_target_lookup,
    _worksheet_parts,
)
from ._ooxml_fidelity_progress import _run_audit_phase
from ._ooxml_fidelity_xml import (
    _all_stable_attrs,
    _attr,
    _children_by_local,
    _extension_fingerprints,
    _first_child_by_local,
    _first_node_by_local,
    _local_name,
    _nodes_by_local,
    _part_contains_any,
    _read_xml_or_none,
    _relationship_id,
    _stable_attrs,
    _text,
    _texts_by_local,
    _vals_by_path,
    _xml_extensions,
    _xml_tree_fingerprint,
)


def _read_semantic_fingerprints(
    archive: zipfile.ZipFile,
    *,
    compact: bool = False,
    progress_label: str | None = None,
    phase_prefix: str = "semantic_fingerprints",
    phase_timings: dict[str, float] | None = None,
) -> dict[str, dict[str, object]]:
    parts = set(archive.namelist())
    fingerprints: dict[str, dict[str, object]] = {}

    def read_feature(name: str, func):
        value = _run_audit_phase(
            progress_label,
            phase_timings,
            f"{phase_prefix}.{name}",
            func,
        )
        fingerprints[name] = value
        return value

    read_feature("charts", lambda: _chart_fingerprint(archive, parts))
    read_feature("chart_sheets", lambda: _chart_sheet_fingerprint(archive, parts))
    read_feature("chart_styles", lambda: _chart_style_fingerprint(archive, parts))
    read_feature(
        "conditional_formatting",
        lambda: _conditional_formatting_fingerprint(archive, parts),
    )
    read_feature("connections", lambda: _connection_fingerprint(archive, parts))
    read_feature("data_model", lambda: _data_model_fingerprint(archive, parts))
    read_feature("data_validations", lambda: _data_validation_fingerprint(archive, parts))
    read_feature("drawing_objects", lambda: _drawing_object_fingerprint(archive, parts))
    read_feature("extensions", lambda: _extension_payload_fingerprint(archive, parts))
    worksheet_formulas = read_feature(
        "worksheet_formulas",
        lambda: _worksheet_formula_fingerprint(archive, parts),
    )
    read_feature(
        "external_links",
        lambda: _external_link_fingerprint(
            archive,
            parts,
            worksheet_formulas=worksheet_formulas,
        ),
    )
    read_feature(
        "named_sheet_views",
        lambda: _xml_part_fingerprint(
            archive,
            parts,
            tuple(sorted(part for part in parts if part.startswith("xl/namedSheetViews/"))),
        ),
    )
    read_feature("page_setup", lambda: _page_setup_fingerprint(archive, parts))
    read_feature("pivots", lambda: _pivot_fingerprint(archive, parts))
    read_feature("python", lambda: _xml_part_fingerprint(archive, parts, ("xl/python.xml",)))
    read_feature(
        "sheet_metadata",
        lambda: _xml_part_fingerprint(archive, parts, ("xl/metadata.xml",)),
    )
    read_feature("slicers", lambda: _slicer_fingerprint(archive, parts))
    read_feature(
        "style_theme",
        lambda: _style_theme_fingerprint(archive, parts, compact=compact),
    )
    read_feature(
        "structured_references",
        lambda: _structured_reference_fingerprint(
            archive,
            parts,
            worksheet_formulas=worksheet_formulas,
        ),
    )
    read_feature("timelines", lambda: _timeline_fingerprint(archive, parts))
    read_feature("workbook_globals", lambda: _workbook_global_fingerprint(archive, parts))
    return fingerprints


def _chart_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    rels_by_owner = _relationships_by_owner(archive)
    for part in sorted(_feature_xml_parts(parts, "xl/charts/", ".xml")):
        if _is_chart_style_part(part):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        out[part] = [
            ("formulas", _texts_by_local(root, "f")),
            ("pivot_sources", _pivot_source_names(root)),
            ("dPt_count", len(_nodes_by_local(root, "dPt"))),
            ("style_vals", _vals_by_path(root, ("style",))),
            ("chart_types", _chart_types(root)),
            ("axis_ids", _chart_axis_ids(root)),
            ("axes", _chart_axes(root)),
            ("manual_layouts", _manual_layouts(root)),
            ("series", _chart_series(root)),
            ("rels", rels_by_owner.get(part, [])),
        ]
    return out


def _chart_sheet_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    rels_by_owner = _relationships_by_owner(archive)
    for part in sorted(_feature_xml_parts(parts, "xl/chartsheets/", ".xml")):
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        out[part] = [
            ("rels", rels_by_owner.get(part, [])),
            (
                "drawing_ids",
                [
                    _relationship_id(node)
                    for node in _nodes_by_local(root, "drawing")
                    + _nodes_by_local(root, "chartsheetDrawing")
                ],
            ),
            ("views", [_all_stable_attrs(node) for node in _nodes_by_local(root, "sheetView")]),
            (
                "protection",
                _stable_attrs(
                    _first_node_by_local(root, "sheetProtection"),
                    ("sheet", "objects", "scenarios"),
                ),
            ),
            ("extensions", _xml_extensions(root)),
        ]
    return out


def _chart_style_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    for part in sorted(_feature_xml_parts(parts, "xl/charts/", ".xml")):
        if not _is_chart_style_part(part):
            continue
        root = _read_xml_or_none(archive, part)
        if root is not None:
            out[part] = _xml_tree_fingerprint(root)
    return out


def _conditional_formatting_fingerprint(
    archive: zipfile.ZipFile, parts: set[str]
) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    for part in sorted(_worksheet_parts(parts)):
        if not _part_contains_any(archive, part, CONDITIONAL_FORMATTING_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        blocks: list[object] = []
        for block in _nodes_by_local(root, "conditionalFormatting"):
            rules: list[object] = []
            for rule in _children_by_local(block, "cfRule"):
                rules.append(
                    (
                        _stable_attrs(rule, ("type", "priority", "operator", "dxfId")),
                        _texts_by_local(rule, "formula"),
                    )
                )
            blocks.append(
                (
                    _attr(block, "sqref"),
                    rules,
                    _extension_fingerprints(block, CF_EXTENSION_NAMES),
                )
            )
        extensions = _extension_fingerprints(root, CF_EXTENSION_NAMES)
        if blocks or extensions:
            out[part] = [("blocks", blocks), ("extensions", extensions)]
    return out


def _data_validation_fingerprint(
    archive: zipfile.ZipFile, parts: set[str]
) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    for part in sorted(_worksheet_parts(parts)):
        if not _part_contains_any(archive, part, DATA_VALIDATION_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        validations: list[object] = []
        for validation in _nodes_by_local(root, "dataValidation"):
            validations.append(
                (
                    _stable_attrs(
                        validation,
                        (
                            "type",
                            "operator",
                            "allowBlank",
                            "showErrorMessage",
                            "showInputMessage",
                            "sqref",
                        ),
                    ),
                    _texts_by_local(validation, "formula1"),
                    _texts_by_local(validation, "formula2"),
                )
            )
        if validations:
            out[part] = validations
    return out


def _connection_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    rels_by_owner = _relationships_by_owner(archive)
    for part in sorted(_feature_xml_parts(parts, "xl/connections", ".xml")):
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        connections: list[object] = []
        for connection in _nodes_by_local(root, "connection"):
            connections.append(
                (
                    _stable_attrs(
                        connection,
                        (
                            "id",
                            "name",
                            "description",
                            "type",
                            "refreshedVersion",
                            "background",
                            "saveData",
                            "deleted",
                        ),
                    ),
                    [
                        _stable_attrs(
                            node,
                            ("connection", "command", "commandType", "serverCommand"),
                        )
                        for node in _nodes_by_local(connection, "dbPr")
                    ],
                    [_xml_tree_fingerprint(node) for node in _nodes_by_local(connection, "extLst")],
                )
            )
        out[part] = [
            ("attrs", _stable_attrs(root, ("count",))),
            ("rels", rels_by_owner.get(part, [])),
            ("connections", connections),
        ]
    return out


def _data_model_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, object]:
    model_parts = sorted(part for part in parts if part.startswith("xl/model/"))
    if not model_parts:
        return {}

    defaults = _read_content_defaults(archive)
    rels_by_owner = _relationships_by_owner(archive)
    out: dict[str, object] = {
        "xl/workbook.xml": [
            (
                "rels",
                [
                    rel
                    for rel in rels_by_owner.get("xl/workbook.xml", [])
                    if rel[1].endswith("/powerPivotData")
                    or rel[1].endswith("/model")
                    or str(rel[2]).startswith("model/")
                ],
            )
        ],
        "content_defaults": {
            ext: content_type
            for ext, content_type in sorted(defaults.items())
            if any(part.rsplit(".", 1)[-1] == ext for part in model_parts)
        },
        "parts": [
            (
                part,
                len(payload := archive.read(part)),
                hashlib.sha256(payload).hexdigest(),
            )
            for part in model_parts
        ],
    }
    return out


def _drawing_object_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    rels_by_owner = _relationships_by_owner(archive)
    for part in sorted(parts):
        if not part.startswith(
            (
                "xl/drawings/",
                "xl/comments",
                "xl/threadedComments/",
                "xl/persons/",
                "xl/media/",
                "xl/embeddings/",
                "xl/ctrlProps/",
                "xl/activeX/",
            )
        ):
            continue
        if part.endswith(".rels"):
            continue
        if part.endswith((".xml", ".vml")):
            root = _read_xml_or_none(archive, part)
            if root is None:
                continue
            out[part] = [
                ("xml", _xml_tree_fingerprint(root)),
                ("rels", rels_by_owner.get(part, [])),
            ]
        else:
            payload = archive.read(part)
            out[part] = [
                ("bytes", len(payload), hashlib.sha256(payload).hexdigest()),
                ("rels", rels_by_owner.get(part, [])),
            ]
    return out


def _external_link_fingerprint(
    archive: zipfile.ZipFile,
    parts: set[str],
    *,
    worksheet_formulas: dict[str, list[object]] | None = None,
) -> dict[str, object]:
    out: dict[str, object] = {}
    rel_targets = _rels_target_lookup(archive)
    for part in sorted(_feature_xml_parts(parts, "xl/externalLinks/", ".xml")):
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        external_books: list[object] = []
        for book in _nodes_by_local(root, "externalBook"):
            rid = _relationship_id(book)
            external_books.append(
                (
                    rid,
                    rel_targets.get((part, rid)) if rid is not None else None,
                    _external_sheet_names(book),
                    _defined_name_refs(book),
                    _external_sheet_data(book),
                )
            )
        out[part] = external_books
    if worksheet_formulas is None:
        workbook_formulas = _worksheet_formulas(archive, parts, external_only=True)
    else:
        workbook_formulas = _worksheet_formula_texts(
            worksheet_formulas,
            external_only=True,
        )
    if workbook_formulas:
        out["worksheet_formulas"] = workbook_formulas
    return out


def _extension_payload_fingerprint(
    archive: zipfile.ZipFile, parts: set[str]
) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    for part in sorted(p for p in parts if p.endswith(".xml")):
        if part == "xl/workbook.xml":
            continue
        if not _part_contains_any(archive, part, EXTENSION_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        extensions = _xml_extensions(root)
        if extensions:
            out[part] = extensions
    return out


def _xml_part_fingerprint(
    archive: zipfile.ZipFile, parts: set[str], part_names: tuple[str, ...]
) -> dict[str, object]:
    rels_by_owner = _relationships_by_owner(archive)
    out: dict[str, object] = {}
    for part in part_names:
        if part not in parts:
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        out[part] = [
            ("xml", _xml_tree_fingerprint(root)),
            ("rels", rels_by_owner.get(part, [])),
        ]
    return out


def _style_theme_fingerprint(
    archive: zipfile.ZipFile, parts: set[str], *, compact: bool = False
) -> dict[str, object]:
    out: dict[str, object] = {}
    rels_by_owner = _relationships_by_owner(archive)
    for part in sorted(p for p in parts if p == "xl/styles.xml" or p.startswith("xl/theme/theme")):
        if compact:
            payload = archive.read(part)
            out[part] = [
                ("bytes", len(payload), hashlib.sha256(payload).hexdigest()),
                ("rels", rels_by_owner.get(part, [])),
            ]
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        out[part] = [
            ("xml", _xml_tree_fingerprint(root)),
            ("rels", rels_by_owner.get(part, [])),
        ]
    return out


def _pivot_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    rels_by_owner = _relationships_by_owner(archive)
    for part in sorted(_feature_xml_parts(parts, "xl/pivotTables/", ".xml")):
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        out[part] = [
            ("attrs", _stable_attrs(root, ("name", "cacheId", "dataOnRows"))),
            ("rels", rels_by_owner.get(part, [])),
            ("data_fields", _pivot_data_fields(root)),
            ("row_fields", _pivot_field_indices(root, "rowFields", "field")),
            ("col_fields", _pivot_field_indices(root, "colFields", "field")),
            ("page_fields", _pivot_field_indices(root, "pageFields", "pageField")),
            ("calculated_items", _pivot_calculated_items(root)),
            ("formats", _pivot_formats(root)),
            ("conditional_formats", _pivot_conditional_formats(root)),
        ]
    for part in sorted(_feature_xml_parts(parts, "xl/pivotCache/", ".xml")):
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        source = _first_node_by_local(root, "worksheetSource")
        out[part] = [
            ("cacheSource", _stable_attrs(source, ("ref", "sheet", "name"))),
            ("refreshOnLoad", _attr(root, "refreshOnLoad")),
            ("rels", rels_by_owner.get(part, [])),
            ("fields", _pivot_cache_fields(root)),
            ("calculated_fields", _pivot_calculated_fields(root)),
            ("field_groups", _pivot_field_groups(root)),
        ]
    return out


def _slicer_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    rels_by_owner = _relationships_by_owner(archive)
    workbook_root = _read_xml_or_none(archive, "xl/workbook.xml")
    if workbook_root is not None:
        extensions = _extension_fingerprints(workbook_root, SLICER_EXTENSION_NAMES)
        if extensions:
            out["xl/workbook.xml"] = [("extensions", extensions)]
    for part in sorted(_worksheet_parts(parts)):
        if not _part_contains_any(archive, part, EXTENSION_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        extensions = _extension_fingerprints(root, SLICER_EXTENSION_NAMES)
        if extensions:
            out[part] = [("extensions", extensions)]
    for part in sorted(_feature_xml_parts(parts, "xl/slicerCaches/", ".xml")):
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        out[part] = [
            ("attrs", _stable_attrs(root, ("name", "pivotCacheId"))),
            ("rels", rels_by_owner.get(part, [])),
            ("data", _stable_attrs(_first_node_by_local(root, "data"), ("pivotCacheId",))),
            ("items", _slicer_items(root)),
        ]
    for part in sorted(_feature_xml_parts(parts, "xl/slicers/", ".xml")):
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        out[part] = [
            ("attrs", _stable_attrs(root, ("name", "cache", "caption", "style"))),
            ("rels", rels_by_owner.get(part, [])),
            (
                "slicers",
                [
                    _stable_attrs(node, ("name", "cache", "caption"))
                    for node in _nodes_by_local(root, "slicer")
                ],
            ),
        ]
    return out


def _timeline_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    rels_by_owner = _relationships_by_owner(archive)
    workbook_root = _read_xml_or_none(archive, "xl/workbook.xml")
    if workbook_root is not None:
        extensions = _extension_fingerprints(workbook_root, TIMELINE_EXTENSION_NAMES)
        if extensions:
            out["xl/workbook.xml"] = [("extensions", extensions)]
    for part in sorted(_worksheet_parts(parts)):
        if not _part_contains_any(archive, part, EXTENSION_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        extensions = _extension_fingerprints(root, TIMELINE_EXTENSION_NAMES)
        if extensions:
            out[part] = [("extensions", extensions)]
    for prefix in ("xl/timelineCaches/", "xl/timelines/"):
        for part in sorted(_feature_xml_parts(parts, prefix, ".xml")):
            root = _read_xml_or_none(archive, part)
            if root is not None:
                out[part] = [
                    ("attrs", _stable_attrs(root, ("name", "pivotCacheId", "cache"))),
                    ("rels", rels_by_owner.get(part, [])),
                    ("xml", _xml_tree_fingerprint(root)),
                ]
    return out


def _worksheet_formula_fingerprint(
    archive: zipfile.ZipFile, parts: set[str]
) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    for part in sorted(_worksheet_parts(parts)):
        if not _part_contains_any(archive, part, FORMULA_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        formulas: list[object] = []
        for cell in root.iter():
            if _local_name(cell.tag) != "c":
                continue
            formula = _first_child_by_local(cell, "f")
            if formula is None:
                continue
            formulas.append(
                (
                    _stable_attrs(cell, ("r",)),
                    _stable_attrs(formula, ("t", "ref", "si", "ca", "bx")),
                    _text(formula),
                )
            )
        if formulas:
            out[part] = formulas
    return out


def _page_setup_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    for part in sorted(_worksheet_parts(parts)):
        if not _part_contains_any(archive, part, PAGE_SETUP_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        page_margins: list[tuple[tuple[str, str | None], ...]] = []
        page_setups: list[tuple[tuple[str, str | None], ...]] = []
        print_options: list[tuple[tuple[str, str | None], ...]] = []
        header_footers: list[object] = []
        for node in root.iter():
            local = _local_name(node.tag)
            if local == "pageMargins":
                page_margins.append(_all_stable_attrs(node))
            elif local == "pageSetup":
                page_setups.append(_all_stable_attrs(node))
            elif local == "printOptions":
                print_options.append(_all_stable_attrs(node))
            elif local == "headerFooter":
                header_footers.append(_xml_tree_fingerprint(node))
        entries = [
            ("page_margins", page_margins),
            ("page_setup", page_setups),
            ("print_options", print_options),
            ("header_footer", header_footers),
        ]
        entries = [(label, value) for label, value in entries if value]
        if entries:
            out[part] = entries
    return out


def _structured_reference_fingerprint(
    archive: zipfile.ZipFile,
    parts: set[str],
    *,
    worksheet_formulas: dict[str, list[object]] | None = None,
) -> dict[str, object]:
    out: dict[str, object] = {}
    formulas_by_part = worksheet_formulas
    if formulas_by_part is None:
        formulas_by_part = _worksheet_formula_fingerprint(archive, parts)
    for part, formulas in formulas_by_part.items():
        structured = [
            formula
            for formula in formulas
            if isinstance(formula, tuple)
            and len(formula) == 3
            and isinstance(formula[2], str)
            and _is_structured_reference_formula(formula[2])
        ]
        if structured:
            out[part] = structured
    return out


def _workbook_global_fingerprint(archive: zipfile.ZipFile, parts: set[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    workbook_root = _read_xml_or_none(archive, "xl/workbook.xml")
    if workbook_root is not None:
        defined_names = [
            (
                _stable_attrs(
                    node,
                    ("name", "localSheetId", "hidden", "function", "vbProcedure"),
                ),
                _text(node),
            )
            for node in _nodes_by_local(workbook_root, "definedName")
        ]
        protection = _first_node_by_local(workbook_root, "workbookProtection")
        calc_pr = _first_node_by_local(workbook_root, "calcPr")
        extensions = _xml_extensions(workbook_root)
        workbook_entries = [
            ("defined_names", defined_names),
            ("workbook_protection", _all_stable_attrs(protection)),
            ("calc_pr", _all_stable_attrs(calc_pr)),
            ("extensions", extensions),
        ]
        if any(value for _, value in workbook_entries):
            out["xl/workbook.xml"] = workbook_entries
    global_parts = sorted(
        part
        for part in parts
        if part == "xl/vbaProject.bin"
        or part.startswith("customXml/")
        or part.startswith("xl/customXml/")
        or part.startswith("xl/customProperty")
        or part.startswith("xl/printerSettings/")
    )
    if global_parts:
        out["package_parts"] = global_parts
        out["package_payloads"] = {
            part: _global_package_part_fingerprint(archive, part)
            for part in global_parts
            if not part.endswith(".rels")
        }
    return out


def _global_package_part_fingerprint(archive: zipfile.ZipFile, part: str) -> object:
    if part.endswith(".xml"):
        root = _read_xml_or_none(archive, part)
        if root is not None:
            return ("xml", _xml_tree_fingerprint(root))
    payload = archive.read(part)
    return ("bytes", len(payload), hashlib.sha256(payload).hexdigest())
