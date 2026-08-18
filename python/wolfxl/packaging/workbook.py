"""Workbook package model compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _install_openpyxl_iter
from wolfxl.workbook.defined_name import DefinedNameList
from wolfxl.workbook.external_reference import ExternalReference
from wolfxl.workbook.properties import CalcProperties, WorkbookProperties
from wolfxl.workbook.protection import WorkbookProtection
from wolfxl.workbook.views import BookView
from wolfxl.xml.constants import REL_NS, SHEET_MAIN_NS
from wolfxl.xml.functions import Element, localname


@dataclass
class FileVersion:
    appName: str | None = None  # noqa: N815
    lastEdited: str | None = None  # noqa: N815
    lowestEdited: str | None = None  # noqa: N815
    rupBuild: str | None = None  # noqa: N815
    codeName: str | None = None  # noqa: N815


@dataclass
class ChildSheet:
    name: str | None = None
    sheetId: int | None = None  # noqa: N815
    id: str | None = None
    state: str = "visible"


@dataclass(init=False)
class WorkbookPackage:
    workbookPr: WorkbookProperties | None = None  # noqa: N815
    workbookProtection: WorkbookProtection | None = None  # noqa: N815
    bookViews: list[BookView] = field(default_factory=list)  # noqa: N815
    sheets: list[ChildSheet] = field(default_factory=list)
    externalReferences: list[ExternalReference] = field(default_factory=list)  # noqa: N815
    definedNames: DefinedNameList | None = None  # noqa: N815
    calcPr: CalcProperties | None = None  # noqa: N815

    def __init__(
        self,
        workbookPr: WorkbookProperties | None = None,  # noqa: N803
        workbookProtection: WorkbookProtection | None = None,  # noqa: N803
        bookViews: list[BookView] | None = None,  # noqa: N803
        sheets: list[ChildSheet] | None = None,
        externalReferences: list[ExternalReference] | None = None,  # noqa: N803
        definedNames: DefinedNameList | None = None,  # noqa: N803
        calcPr: CalcProperties | None = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.workbookPr = workbookPr if workbookPr is not None else WorkbookProperties()
        self.workbookProtection = workbookProtection
        self.bookViews = list(bookViews or [])
        self.sheets = list(sheets or [])
        self.externalReferences = list(externalReferences or [])
        self.definedNames = definedNames
        self.calcPr = calcPr
        for name, value in kw.items():
            setattr(self, name, value)

    @property
    def active(self) -> int:
        if not self.bookViews:
            return 0
        return int(getattr(self.bookViews[0], "activeTab", 0) or 0)

    @active.setter
    def active(self, value: int) -> None:
        if not self.bookViews:
            self.bookViews.append(BookView())
        self.bookViews[0].activeTab = int(value)

    @property
    def properties(self) -> WorkbookProperties | None:
        return self.workbookPr

    @properties.setter
    def properties(self, value: WorkbookProperties | None) -> None:
        self.workbookPr = value

    def to_tree(self) -> Any:
        root = Element("workbook", {"xmlns": SHEET_MAIN_NS})
        if self.workbookPr is not None:
            root.append(self.workbookPr.to_tree())
        return root

    @classmethod
    def from_tree(cls, node: Any) -> "WorkbookPackage":
        workbook_pr = None
        workbook_protection = None
        book_views: list[BookView] = []
        sheets: list[ChildSheet] = []
        external_references: list[ExternalReference] = []
        defined_names = None
        calc_pr = None
        pivot_caches: list[PivotCache] = []
        for child in node:
            tag = localname(child)
            if tag == "workbookPr":
                workbook_pr = WorkbookProperties.from_tree(child)
            elif tag == "workbookProtection":
                workbook_protection = WorkbookProtection.from_tree(child)
            elif tag == "bookViews":
                book_views = [
                    BookView.from_tree(view)
                    for view in child
                    if localname(view) == "workbookView"
                ]
            elif tag == "sheets":
                sheets = [
                    ChildSheet(
                        name=sheet.get("name"),
                        sheetId=_optional_int(sheet.get("sheetId")),
                        id=sheet.get(f"{{{REL_NS}}}id") or sheet.get("r:id") or sheet.get("id"),
                        state=sheet.get("state", "visible"),
                    )
                    for sheet in child
                    if localname(sheet) == "sheet"
                ]
            elif tag == "externalReferences":
                external_references = [
                    ExternalReference.from_tree(ref)
                    for ref in child
                    if localname(ref) == "externalReference"
                ]
            elif tag == "definedNames":
                defined_names = DefinedNameList.from_tree(child)
            elif tag == "calcPr":
                calc_pr = CalcProperties.from_tree(child)
            elif tag == "pivotCaches":
                pivot_caches = [
                    PivotCache.from_tree(cache)
                    for cache in child
                    if localname(cache) == "pivotCache"
                ]
        return cls(
            workbookPr=workbook_pr,
            workbookProtection=workbook_protection,
            bookViews=book_views,
            sheets=sheets,
            externalReferences=external_references,
            definedNames=defined_names,
            calcPr=calc_pr,
            pivotCaches=pivot_caches,
        )


def _optional_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    return int(value)


class FileRecoveryProperties(_OpenpyxlSerialisable):
    pass


class FileSharing(_OpenpyxlSerialisable):
    pass


class CustomWorkbookView(_OpenpyxlSerialisable):
    pass


@dataclass
class PivotCache:
    cacheId: int | None = None  # noqa: N815
    id: str | None = None

    def to_tree(self) -> Any:
        attrs = {}
        if self.cacheId is not None:
            attrs["cacheId"] = str(self.cacheId)
        if self.id is not None:
            attrs[f"{{{REL_NS}}}id"] = self.id
        return Element("pivotCache", attrs)

    @classmethod
    def from_tree(cls, node: Any) -> "PivotCache":
        cache_id = node.get("cacheId")
        rel_id = node.get(f"{{{REL_NS}}}id") or node.get("id")
        return cls(cacheId=int(cache_id) if cache_id is not None else None, id=rel_id)


class WebPublishObjectList(_OpenpyxlSerialisable):
    pass


_install_openpyxl_iter(FileVersion, WorkbookPackage)


Alias = Bool = ExtensionList = FunctionGroupList = Integer = NestedSequence = NestedString = NoneSet = Relation = Serialisable = SmartTagList = SmartTagProperties = String = Typed = WebPublishing = _OpenpyxlSerialisable

__all__ = [
    "Alias",
    "BookView",
    "Bool",
    "CalcProperties",
    "ChildSheet",
    "CustomWorkbookView",
    "DefinedNameList",
    "ExtensionList",
    "ExternalReference",
    "FileRecoveryProperties",
    "FileSharing",
    "FileVersion",
    "FunctionGroupList",
    "Integer",
    "NestedSequence",
    "NestedString",
    "NoneSet",
    "PivotCache",
    "Relation",
    "SHEET_MAIN_NS",
    "Serialisable",
    "SmartTagList",
    "SmartTagProperties",
    "String",
    "Typed",
    "WebPublishObjectList",
    "WebPublishing",
    "WorkbookPackage",
    "WorkbookProperties",
    "WorkbookProtection",
]
