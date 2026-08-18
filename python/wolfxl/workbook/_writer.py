"""Workbook writer compatibility helpers used by openpyxl-shaped callers."""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.packaging.relationship import Relationship, RelationshipList
from wolfxl.utils import absolute_coordinate, quote_sheetname
from wolfxl.utils.datetime import CALENDAR_MAC_1904
from wolfxl.workbook.defined_name import DefinedName
from wolfxl.workbook.properties import WorkbookProperties
from wolfxl.xml.constants import (
    ARC_APP,
    ARC_CORE,
    ARC_CUSTOM,
    ARC_WORKBOOK,
    CUSTOMUI_NS,
    PKG_REL_NS,
    REL_NS,
    SHEET_MAIN_NS,
)
from wolfxl.xml.functions import Element, fromstring, tostring


def _workbook_root() -> Element:
    try:
        return Element("workbook", nsmap={None: SHEET_MAIN_NS, "r": REL_NS})
    except TypeError:  # pragma: no cover - stdlib ElementTree fallback
        return Element("workbook", {"xmlns": SHEET_MAIN_NS})


def _simple_tree(tagname: str, attrs=()) -> Element:
    node = Element(tagname)
    for key, value in attrs:
        if value is None:
            continue
        if isinstance(value, bool):
            value = "1" if value else "0"
        node.set(key, str(value))
    return node


def get_active_sheet(wb):
    """Return the active visible sheet index, matching openpyxl's helper."""
    sheets = list(getattr(wb, "worksheets", []))
    visible_sheets = [
        idx for idx, sheet in enumerate(sheets) if sheet.sheet_state == "visible"
    ]
    if not visible_sheets:
        raise IndexError("At least one sheet must be visible")

    idx = getattr(wb, "_active_sheet_index", 0)
    sheet = wb.active
    if sheet and sheet.sheet_state == "visible":
        return idx

    for visible_idx in visible_sheets[idx:]:
        wb.active = visible_idx
        return visible_idx

    return None


class WorkbookWriter:
    """Small compatibility facade for workbook-level package XML helpers."""

    def __init__(self, wb: object) -> None:
        self.wb = wb
        self.rels = RelationshipList()

    def write_properties(self) -> Element:
        props = WorkbookProperties()
        if getattr(self.wb, "code_name", None) is not None:
            props.codeName = self.wb.code_name
        if getattr(self.wb, "excel_base_date", None) == CALENDAR_MAC_1904:
            props.date1904 = True
        return props.to_tree()

    def write_protection(self) -> Element:
        security = getattr(self.wb, "security", None)
        return _simple_tree("workbookProtection", dict(security).items() if security else ())

    def write_views(self) -> Element:
        active = get_active_sheet(self.wb)
        views = getattr(self.wb, "views", None) or []
        if views:
            views[0].activeTab = active
        node = Element("bookViews")
        for view in views:
            node.append(_simple_tree("workbookView", dict(view).items()))
        return node

    def write_worksheets(self) -> Element:
        node = Element("sheets")
        sheets = list(getattr(self.wb, "worksheets", []))
        for idx, sheet in enumerate(sheets, 1):
            rel = Relationship(type="worksheet", Target=sheet.path)
            self.rels.append(rel)
            attrs = {
                "name": sheet.title,
                "sheetId": str(idx),
                "state": sheet.sheet_state,
                f"{{{REL_NS}}}id": rel.id,
            }
            if sheet.sheet_state != "visible" and len(sheets) == 1:
                raise ValueError("The only worksheet of a workbook cannot be hidden")
            node.append(Element("sheet", attrs))
        return node

    def write_names(self) -> Element:
        names = list(getattr(self.wb, "defined_names", {}).values())
        for idx, sheet in enumerate(getattr(self.wb, "worksheets", [])):
            quoted = quote_sheetname(sheet.title)

            sheet_names = getattr(sheet, "defined_names", None)
            if sheet_names:
                for defined_name in sheet_names.values():
                    defined_name.localSheetId = idx
                    names.append(defined_name)

            auto_filter = getattr(sheet, "auto_filter", None)
            if auto_filter and getattr(auto_filter, "ref", None):
                names.append(
                    DefinedName(
                        name="_xlnm._FilterDatabase",
                        localSheetId=idx,
                        hidden=True,
                        value=f"{quoted}!{absolute_coordinate(auto_filter.ref)}",
                    )
                )

            if sheet.print_titles:
                names.append(
                    DefinedName(
                        name="_xlnm.Print_Titles",
                        localSheetId=idx,
                        value=sheet.print_titles,
                    )
                )

            if sheet.print_area:
                names.append(
                    DefinedName(
                        name="_xlnm.Print_Area",
                        localSheetId=idx,
                        value=sheet.print_area,
                    )
                )

        node = Element("definedNames")
        for defined_name in names:
            node.append(defined_name.to_tree())
        return node

    def write_calc_pr(self) -> Element:
        return Element("calcPr", {"calcId": "124519", "fullCalcOnLoad": "1"})

    def write(self) -> bytes:
        """Write the core workbook XML."""
        root = _workbook_root()
        root.append(self.write_properties())
        root.append(self.write_protection())
        root.append(self.write_views())
        root.append(self.write_worksheets())
        root.append(self.write_names())
        root.append(self.write_calc_pr())
        return tostring(root)

    def write_rels(self) -> bytes:
        """Write workbook relationships XML."""
        rels = RelationshipList()
        rels.append(Relationship(type="styles", Target="styles.xml"))
        rels.append(Relationship(type="theme", Target="theme/theme1.xml"))

        if getattr(self.wb, "vba_archive", None) or getattr(
            self.wb, "_vba_archive_override", None
        ):
            vba = Relationship(
                Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject",
                Target="vbaProject.bin",
            )
            rels.append(vba)

        return tostring(rels.to_tree())

    def write_root_rels(self) -> bytes:
        root = RelationshipList()
        root.append(Relationship(type="officeDocument", Target=ARC_WORKBOOK))
        root.append(Relationship(Type=f"{PKG_REL_NS}/metadata/core-properties", Target=ARC_CORE))
        root.append(Relationship(type="extended-properties", Target=ARC_APP))
        custom_props = getattr(self.wb, "custom_doc_props", None)
        if custom_props is not None and len(custom_props) >= 1:
            root.append(Relationship(type="custom-properties", Target=ARC_CUSTOM))

        vba_archive = getattr(self.wb, "vba_archive", None) or getattr(
            self.wb, "_vba_archive_override", None
        )
        if vba_archive is not None:
            try:
                xml = fromstring(vba_archive.read("_rels/.rels"))
            except Exception:
                xml = None
            if xml is not None:
                root_rels = RelationshipList.from_tree(xml)
                for rel in root_rels.find(CUSTOMUI_NS):
                    root.append(rel)

        return tostring(root.to_tree())


__all__ = ["CALENDAR_MAC_1904", "WorkbookWriter", "get_active_sheet"]

__getattr__ = _openpyxl_name_fallback(globals())
