"""Feature-level element extractors used to build semantic fingerprints.

Internal to the OOXML fidelity audit. The public surface stays
``wolfxl.operations._ooxml_fidelity``.
"""

from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree

from ._ooxml_fidelity_constants import CF_EXTENSION_NAMES, FORMULA_MARKERS
from ._ooxml_fidelity_package import _worksheet_parts
from ._ooxml_fidelity_xml import (
    _attr,
    _children_by_local,
    _extension_fingerprints,
    _first_node_by_local,
    _local_name,
    _nodes_by_local,
    _part_contains_any,
    _read_xml_or_none,
    _stable_attrs,
    _texts_by_local,
    _xml_tree_fingerprint,
)


def _pivot_source_names(root: ElementTree.Element) -> list[str]:
    names: list[str] = []
    for pivot_source in _nodes_by_local(root, "pivotSource"):
        names.extend(_texts_by_local(pivot_source, "name"))
    return names


def _chart_types(root: ElementTree.Element) -> list[str]:
    plot_area = _first_node_by_local(root, "plotArea")
    if plot_area is None:
        return []
    return [
        _local_name(node.tag) for node in list(plot_area) if _local_name(node.tag).endswith("Chart")
    ]


def _chart_axis_ids(root: ElementTree.Element) -> list[str | None]:
    return [_attr(node, "val") for node in _nodes_by_local(root, "axId")]


def _chart_axes(root: ElementTree.Element) -> list[object]:
    axes: list[object] = []
    for node in root.iter():
        local = _local_name(node.tag)
        if local not in {"catAx", "valAx", "dateAx", "serAx"}:
            continue
        axes.append(
            (
                local,
                _axis_child_val(node, "axId"),
                _axis_child_val(node, "crossAx"),
                _axis_child_val(node, "axPos"),
                _axis_child_val(node, "orientation"),
                _axis_child_val(node, "crosses"),
                _axis_child_val(node, "crossBetween"),
                _stable_attrs(_first_node_by_local(node, "numFmt"), ("formatCode", "sourceLinked")),
                _texts_by_local(node, "t"),
            )
        )
    return axes


def _manual_layouts(root: ElementTree.Element) -> list[object]:
    return [_xml_tree_fingerprint(node) for node in _nodes_by_local(root, "manualLayout")]


def _chart_series(root: ElementTree.Element) -> list[object]:
    return [
        (
            _axis_child_val(node, "idx"),
            _axis_child_val(node, "order"),
            _texts_by_local(node, "f"),
            len(_nodes_by_local(node, "dPt")),
        )
        for node in _nodes_by_local(root, "ser")
    ]


def _axis_child_val(root: ElementTree.Element, name: str) -> str | None:
    node = _first_node_by_local(root, name)
    return _attr(node, "val")


def _defined_name_refs(root: ElementTree.Element) -> list[tuple[str | None, str | None]]:
    return [
        (_attr(node, "name"), _attr(node, "refersTo"))
        for node in _nodes_by_local(root, "definedName")
    ]


def _external_sheet_names(root: ElementTree.Element) -> list[str | None]:
    return [_attr(node, "val") for node in _nodes_by_local(root, "sheetName")]


def _external_sheet_data(root: ElementTree.Element) -> list[object]:
    sheets: list[object] = []
    for sheet_data in _nodes_by_local(root, "sheetData"):
        rows: list[object] = []
        for row in _children_by_local(sheet_data, "row"):
            cells = [
                (_stable_attrs(cell, ("r", "t", "vm")), _texts_by_local(cell, "v"))
                for cell in _children_by_local(row, "cell")
            ]
            rows.append((_stable_attrs(row, ("r",)), cells))
        sheets.append(
            (
                _stable_attrs(sheet_data, ("sheetId", "refreshError")),
                rows,
            )
        )
    return sheets


def _worksheet_formulas(
    archive: zipfile.ZipFile, parts: set[str], *, external_only: bool = False
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in sorted(_worksheet_parts(parts)):
        if not _part_contains_any(archive, part, FORMULA_MARKERS):
            continue
        root = _read_xml_or_none(archive, part)
        if root is None:
            continue
        formulas = _texts_by_local(root, "f")
        if external_only:
            formulas = [formula for formula in formulas if _is_external_workbook_formula(formula)]
        if formulas:
            out[part] = formulas
    return out


def _worksheet_formula_texts(
    formulas_by_part: dict[str, list[object]],
    *,
    external_only: bool = False,
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part, formulas in formulas_by_part.items():
        texts: list[str] = []
        for formula in formulas:
            if not (
                isinstance(formula, tuple) and len(formula) == 3 and isinstance(formula[2], str)
            ):
                continue
            text = formula[2]
            if external_only and not _is_external_workbook_formula(text):
                continue
            texts.append(text)
        if texts:
            out[part] = texts
    return out


def _is_external_workbook_formula(formula: str) -> bool:
    # External workbook refs look like [Book.xlsx]Sheet!A1 or
    # '[Book.xlsx]Sheet 1'!A1. Structured table refs also use brackets
    # (Table1[Column]) but do not carry a sheet bang after the closing bracket.
    return bool(re.search(r"\[[^\]]+\][^!]*!", formula))


def _is_structured_reference_formula(formula: str) -> bool:
    return "[" in formula and "]" in formula and not _is_external_workbook_formula(formula)


def _pivot_data_fields(root: ElementTree.Element) -> list[tuple[tuple[str, str | None], ...]]:
    return [
        _stable_attrs(node, ("name", "fld", "subtotal", "baseField", "baseItem"))
        for node in _nodes_by_local(root, "dataField")
    ]


def _pivot_field_indices(
    root: ElementTree.Element, container_name: str, child_name: str
) -> list[str | None]:
    container = _first_node_by_local(root, container_name)
    if container is None:
        return []
    return [
        _attr(child, "x") or _attr(child, "fld")
        for child in _children_by_local(container, child_name)
    ]


def _pivot_cache_fields(root: ElementTree.Element) -> list[tuple[tuple[str, str | None], ...]]:
    return [
        _stable_attrs(node, ("name", "numFmtId", "databaseField", "formula"))
        for node in _nodes_by_local(root, "cacheField")
    ]


def _pivot_calculated_fields(
    root: ElementTree.Element,
) -> list[tuple[tuple[str, str | None], ...]]:
    return [
        _stable_attrs(node, ("name", "formula", "hierarchy", "memberName", "mdx", "solveOrder"))
        for node in _nodes_by_local(root, "calculatedField")
    ]


def _pivot_calculated_items(root: ElementTree.Element) -> list[object]:
    return [
        (
            _stable_attrs(node, ("field", "formula")),
            _extension_fingerprints(node, CF_EXTENSION_NAMES),
        )
        for node in _nodes_by_local(root, "calculatedItem")
    ]


def _pivot_formats(root: ElementTree.Element) -> list[object]:
    return [
        (
            _stable_attrs(node, ("action", "dxfId")),
            [
                _stable_attrs(area, ("type", "field", "fieldPosition"))
                for area in _nodes_by_local(node, "pivotArea")
            ],
        )
        for node in _nodes_by_local(root, "format")
    ]


def _pivot_conditional_formats(root: ElementTree.Element) -> list[object]:
    return [
        (
            _stable_attrs(node, ("scope", "type", "priority")),
            [
                _stable_attrs(area, ("type", "field", "fieldPosition"))
                for area in _nodes_by_local(node, "pivotArea")
            ],
            _extension_fingerprints(node, CF_EXTENSION_NAMES),
        )
        for node in _nodes_by_local(root, "conditionalFormat")
    ]


def _pivot_field_groups(root: ElementTree.Element) -> list[object]:
    groups: list[object] = []
    for node in _nodes_by_local(root, "fieldGroup"):
        groups.append(_xml_tree_fingerprint(node))
    return groups


def _slicer_items(root: ElementTree.Element) -> list[tuple[tuple[str, str | None], ...]]:
    return [_stable_attrs(node, ("n", "c", "x", "s")) for node in _nodes_by_local(root, "i")]
