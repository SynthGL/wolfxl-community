"""Chartsheet authoring post-processor.

The native writer emits ordinary worksheet parts. Chartsheets are workbook-tab
parts that point at a drawing, which in turn points at a chart XML part. This
module keeps that wiring in Python so the existing chart serializer can be
reused without adding a second writer model.
"""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from wolfxl.chartsheet import Chartsheet

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"

RT_WORKSHEET = f"{REL_NS}/worksheet"
RT_CHARTSHEET = f"{REL_NS}/chartsheet"
RT_DRAWING = f"{REL_NS}/drawing"
RT_CHART = f"{REL_NS}/chart"

CT_CHARTSHEET = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.chartsheet+xml"
)
CT_DRAWING = "application/vnd.openxmlformats-officedocument.drawing+xml"
CT_CHART = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"


def create_chartsheet(wb: Any, title: str | None = None, index: int | None = None) -> Chartsheet:
    """Create a chartsheet tab in write or modify mode."""
    if wb._rust_writer is None and wb._rust_patcher is None:  # noqa: SLF001
        raise RuntimeError("create_chartsheet requires write or modify mode")
    base = title or "Chart"
    final = _unique_title(wb, base)
    cs = Chartsheet(wb, final)
    cs._source_chartsheet = False
    wb._chartsheets[final] = cs  # noqa: SLF001
    if index is None:
        wb._sheet_names.append(final)  # noqa: SLF001
    else:
        wb._sheet_names.insert(index, final)  # noqa: SLF001
    wb._chartsheets_dirty = True  # noqa: SLF001
    return cs


def apply_chartsheets_to_xlsx(path: str, wb: Any) -> None:
    """Rewrite ``path`` to include any authored chartsheets."""
    chartsheets = [
        wb._chartsheets[name]  # noqa: SLF001
        for name in wb._sheet_names  # noqa: SLF001
        if name in wb._chartsheets  # noqa: SLF001
        and not getattr(wb._chartsheets[name], "_source_chartsheet", False)  # noqa: SLF001
    ]
    if not chartsheets:
        return

    with zipfile.ZipFile(path, "r") as src:
        workbook_xml = src.read("xl/workbook.xml")
        workbook_rels_xml = src.read("xl/_rels/workbook.xml.rels")
        content_types_xml = src.read("[Content_Types].xml")
        names = src.namelist()

    next_chartsheet = _next_index(names, r"^xl/chartsheets/sheet(\d+)\.xml$")
    next_drawing = _next_index(names, r"^xl/drawings/drawing(\d+)\.xml$")
    next_chart = _next_index(names, r"^xl/charts/chart(\d+)\.xml$")
    workbook_xml_out, workbook_rels_out, rel_ids = _rewrite_workbook_parts(
        workbook_xml,
        workbook_rels_xml,
        wb,
        chartsheets,
        next_chartsheet,
    )

    generated: dict[str, bytes] = {
        "xl/workbook.xml": workbook_xml_out,
        "xl/_rels/workbook.xml.rels": workbook_rels_out,
    }
    content_type_overrides: dict[str, str] = {}

    for offset, cs in enumerate(chartsheets):
        chartsheet_n = next_chartsheet + offset
        drawing_n = next_drawing + offset
        chart_n = next_chart + offset
        has_chart = bool(cs._charts)
        generated[f"xl/chartsheets/sheet{chartsheet_n}.xml"] = _render_chartsheet_xml(
            has_drawing=has_chart
        )
        content_type_overrides[f"/xl/chartsheets/sheet{chartsheet_n}.xml"] = CT_CHARTSHEET
        if has_chart:
            generated[f"xl/chartsheets/_rels/sheet{chartsheet_n}.xml.rels"] = (
                _render_single_rel_xml(RT_DRAWING, f"/xl/drawings/drawing{drawing_n}.xml")
            )
            generated[f"xl/drawings/drawing{drawing_n}.xml"] = _render_chartsheet_drawing_xml()
            generated[f"xl/drawings/_rels/drawing{drawing_n}.xml.rels"] = _render_single_rel_xml(
                RT_CHART,
                f"/xl/charts/chart{chart_n}.xml",
            )
            generated[f"xl/charts/chart{chart_n}.xml"] = _serialize_chart(cs)
            content_type_overrides[f"/xl/drawings/drawing{drawing_n}.xml"] = CT_DRAWING
            content_type_overrides[f"/xl/charts/chart{chart_n}.xml"] = CT_CHART
        else:
            generated[f"xl/chartsheets/_rels/sheet{chartsheet_n}.xml.rels"] = (
                _render_empty_rels_xml()
            )
        # Keep the variable used so a mismatch between workbook rel ordering and
        # generated parts is caught by static checkers.
        assert rel_ids[offset]

    generated["[Content_Types].xml"] = _rewrite_content_types(
        content_types_xml,
        content_type_overrides,
    )

    fd, tmp_name = tempfile.mkstemp(prefix="wolfxl-chartsheets-", suffix=".xlsx")
    os.close(fd)
    try:
        with zipfile.ZipFile(path, "r") as src, zipfile.ZipFile(
            tmp_name, "w", zipfile.ZIP_DEFLATED
        ) as dst:
            for info in src.infolist():
                if info.filename in generated:
                    continue
                with src.open(info, "r") as handle:
                    dst.writestr(info, handle.read())
            for name in sorted(generated):
                dst.writestr(name, generated[name])
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    wb._chartsheets_dirty = False  # noqa: SLF001


def _unique_title(wb: Any, base: str) -> str:
    existing = set(wb._sheet_names)  # noqa: SLF001
    if base not in existing:
        return base
    i = 1
    while f"{base}{i}" in existing:
        i += 1
    return f"{base}{i}"


def _next_index(names: list[str], pattern: str) -> int:
    rx = re.compile(pattern)
    seen = [int(m.group(1)) for name in names if (m := rx.match(name))]
    return max(seen, default=0) + 1


def _rewrite_workbook_parts(
    workbook_xml: bytes,
    workbook_rels_xml: bytes,
    wb: Any,
    chartsheets: list[Chartsheet],
    first_chartsheet_n: int,
) -> tuple[bytes, bytes, list[str]]:
    ET.register_namespace("", MAIN_NS)
    ET.register_namespace("r", REL_NS)
    wb_root = ET.fromstring(workbook_xml)
    rels_root = ET.fromstring(workbook_rels_xml)
    sheets_el = wb_root.find(f"{{{MAIN_NS}}}sheets")
    if sheets_el is None:
        raise ValueError("workbook.xml has no <sheets> block")

    old_order = [
        sheet.attrib.get("name", "")
        for sheet in list(sheets_el)
        if sheet.attrib.get("name")
    ]
    existing_by_name = {
        sheet.attrib.get("name"): sheet
        for sheet in list(sheets_el)
        if sheet.attrib.get("name") not in {cs.title for cs in chartsheets}
    }
    existing_rel_ids = [
        rel.attrib.get("Id", "")
        for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
    ]
    next_rid_num = _next_rid_number(existing_rel_ids)

    rel_ids: list[str] = []
    chartsheet_by_name = {cs.title: cs for cs in chartsheets}
    for offset, cs in enumerate(chartsheets):
        rid = f"rId{next_rid_num + offset}"
        rel_ids.append(rid)
        rel = ET.Element(f"{{{PKG_REL_NS}}}Relationship")
        rel.set("Id", rid)
        rel.set("Type", RT_CHARTSHEET)
        rel.set("Target", f"/xl/chartsheets/sheet{first_chartsheet_n + offset}.xml")
        rels_root.append(rel)

    sheets_el.clear()
    max_sheet_id = _max_sheet_id(existing_by_name.values())
    chart_rid_by_name = {cs.title: rid for cs, rid in zip(chartsheets, rel_ids)}
    chart_sheet_id_by_name = {
        cs.title: str(max_sheet_id + idx + 1) for idx, cs in enumerate(chartsheets)
    }
    for name in wb._sheet_names:  # noqa: SLF001
        if name in existing_by_name:
            sheets_el.append(existing_by_name[name])
        elif name in chartsheet_by_name:
            sheet = ET.Element(f"{{{MAIN_NS}}}sheet")
            sheet.set("name", name)
            sheet.set("sheetId", chart_sheet_id_by_name[name])
            if chartsheet_by_name[name].sheet_state != "visible":
                sheet.set("state", chartsheet_by_name[name].sheet_state)
            sheet.set(f"{{{REL_NS}}}id", chart_rid_by_name[name])
            sheets_el.append(sheet)

    _remap_defined_name_local_sheet_ids(wb_root, old_order, list(wb._sheet_names))  # noqa: SLF001
    workbook_out = ET.tostring(wb_root, encoding="utf-8")
    ET.register_namespace("", PKG_REL_NS)
    rels_out = ET.tostring(rels_root, encoding="utf-8")
    return workbook_out, rels_out, rel_ids


def _remap_defined_name_local_sheet_ids(
    wb_root: ET.Element,
    old_order: list[str],
    new_order: list[str],
) -> None:
    defined_names_el = wb_root.find(f"{{{MAIN_NS}}}definedNames")
    if defined_names_el is None:
        return
    new_index_by_name = {name: idx for idx, name in enumerate(new_order)}
    for defined_name in defined_names_el.findall(f"{{{MAIN_NS}}}definedName"):
        raw = defined_name.attrib.get("localSheetId")
        if raw is None:
            continue
        try:
            old_index = int(raw)
        except ValueError:
            continue
        if old_index < 0 or old_index >= len(old_order):
            continue
        sheet_name = old_order[old_index]
        if sheet_name in new_index_by_name:
            defined_name.set("localSheetId", str(new_index_by_name[sheet_name]))


def _max_sheet_id(sheets: Any) -> int:
    values = []
    for sheet in sheets:
        try:
            values.append(int(sheet.attrib.get("sheetId", "0")))
        except ValueError:
            pass
    return max(values, default=0)


def _next_rid_number(ids: list[str]) -> int:
    nums = []
    for rid in ids:
        if rid.startswith("rId"):
            try:
                nums.append(int(rid[3:]))
            except ValueError:
                pass
    return max(nums, default=0) + 1


def _serialize_chart(cs: Chartsheet) -> bytes:
    from wolfxl._rust import serialize_chart_dict

    chart = cs._charts[0]
    return bytes(serialize_chart_dict(chart.to_rust_dict(), "A1"))


def _render_chartsheet_xml(*, has_drawing: bool = True) -> bytes:
    drawing = '<drawing r:id="rId1"/>' if has_drawing else ""
    xml = (
        f'<chartsheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">'
        '<sheetViews><sheetView workbookViewId="0" zoomToFit="1"/></sheetViews>'
        f"{drawing}"
        "</chartsheet>"
    )
    return xml.encode("utf-8")


def _render_chartsheet_drawing_xml() -> bytes:
    xml = (
        f'<wsDr xmlns="{DRAWING_NS}" xmlns:a="{A_NS}" xmlns:c="{C_NS}" xmlns:r="{REL_NS}">'
        '<absoluteAnchor><pos x="0" y="0"/><ext cx="0" cy="0"/>'
        '<graphicFrame><nvGraphicFramePr><cNvPr id="1" name="Chart 1"/>'
        "<cNvGraphicFramePr/></nvGraphicFramePr><xfrm/>"
        f'<a:graphic><a:graphicData uri="{C_NS}"><c:chart r:id="rId1"/>'
        "</a:graphicData></a:graphic></graphicFrame><clientData/></absoluteAnchor>"
        "</wsDr>"
    )
    return xml.encode("utf-8")


def _render_single_rel_xml(rel_type: str, target: str) -> bytes:
    xml = (
        f'<Relationships xmlns="{PKG_REL_NS}">'
        f'<Relationship Id="rId1" Type="{rel_type}" Target="{target}"/>'
        "</Relationships>"
    )
    return xml.encode("utf-8")


def _render_empty_rels_xml() -> bytes:
    return f'<Relationships xmlns="{PKG_REL_NS}"/>'.encode("utf-8")


def _rewrite_content_types(content_types_xml: bytes, overrides: dict[str, str]) -> bytes:
    ET.register_namespace("", CT_NS)
    root = ET.fromstring(content_types_xml)
    existing = {
        child.attrib.get("PartName"): child
        for child in root.findall(f"{{{CT_NS}}}Override")
    }
    for part_name, content_type in overrides.items():
        node = existing.get(part_name)
        if node is None:
            node = ET.Element(f"{{{CT_NS}}}Override")
            node.set("PartName", part_name)
            root.append(node)
        node.set("ContentType", content_type)
    return ET.tostring(root, encoding="utf-8")
