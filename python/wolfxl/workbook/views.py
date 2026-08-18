"""Workbook view containers compatible with ``openpyxl.workbook.views``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from wolfxl._compat import _iter_openpyxl_attrs, _openpyxl_name_fallback
from wolfxl.xml.functions import Element


@dataclass
class BookView:
    """Workbook window view metadata from ``<workbookView>``."""

    tagname: ClassVar[str] = "workbookView"
    __attrs__: ClassVar[tuple[str, ...]] = (
        "visibility",
        "minimized",
        "showHorizontalScroll",
        "showVerticalScroll",
        "showSheetTabs",
        "xWindow",
        "yWindow",
        "windowWidth",
        "windowHeight",
        "tabRatio",
        "firstSheet",
        "activeTab",
        "autoFilterDateGrouping",
    )

    visibility: str = "visible"
    minimized: bool = False
    showHorizontalScroll: bool = True  # noqa: N815
    showVerticalScroll: bool = True  # noqa: N815
    showSheetTabs: bool = True  # noqa: N815
    xWindow: int | None = None  # noqa: N815
    yWindow: int | None = None  # noqa: N815
    windowWidth: int | None = None  # noqa: N815
    windowHeight: int | None = None  # noqa: N815
    tabRatio: int = 600  # noqa: N815
    firstSheet: int = 0  # noqa: N815
    activeTab: int = 0  # noqa: N815
    autoFilterDateGrouping: bool = True  # noqa: N815
    extLst: Any = None  # noqa: N815

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        return _attrs_to_tree(self, tagname or self.tagname)

    @classmethod
    def from_tree(cls, node: Any) -> "BookView":
        attrs = {
            key: value
            for key, value in _typed_attrs(node.attrib).items()
            if key in cls.__attrs__
        }
        return cls(**attrs)


@dataclass
class CustomWorkbookView:
    """Custom workbook view metadata from ``<customWorkbookView>``."""

    tagname: ClassVar[str] = "customWorkbookView"
    __attrs__: ClassVar[tuple[str, ...]] = (
        "name",
        "guid",
        "autoUpdate",
        "mergeInterval",
        "changesSavedWin",
        "onlySync",
        "personalView",
        "includePrintSettings",
        "includeHiddenRowCol",
        "maximized",
        "minimized",
        "showHorizontalScroll",
        "showVerticalScroll",
        "showSheetTabs",
        "xWindow",
        "yWindow",
        "windowWidth",
        "windowHeight",
        "tabRatio",
        "activeSheetId",
        "showFormulaBar",
        "showStatusbar",
        "showComments",
        "showObjects",
    )

    name: str | None = None
    guid: str | None = None
    autoUpdate: bool | None = None  # noqa: N815
    mergeInterval: int | None = None  # noqa: N815
    changesSavedWin: bool | None = None  # noqa: N815
    onlySync: bool | None = None  # noqa: N815
    personalView: bool | None = None  # noqa: N815
    includePrintSettings: bool | None = None  # noqa: N815
    includeHiddenRowCol: bool | None = None  # noqa: N815
    maximized: bool | None = None
    minimized: bool | None = None
    showHorizontalScroll: bool | None = None  # noqa: N815
    showVerticalScroll: bool | None = None  # noqa: N815
    showSheetTabs: bool | None = None  # noqa: N815
    xWindow: int | None = None  # noqa: N815
    yWindow: int | None = None  # noqa: N815
    windowWidth: int | None = None  # noqa: N815
    windowHeight: int | None = None  # noqa: N815
    tabRatio: int | None = None  # noqa: N815
    activeSheetId: int | None = None  # noqa: N815
    showFormulaBar: bool | None = None  # noqa: N815
    showStatusbar: bool | None = None  # noqa: N815
    showComments: str | None = "commIndicator"  # noqa: N815
    showObjects: str | None = "all"  # noqa: N815
    extLst: Any = None  # noqa: N815

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        return _attrs_to_tree(self, tagname or self.tagname)

    @classmethod
    def from_tree(cls, node: Any) -> "CustomWorkbookView":
        attrs = {
            key: value
            for key, value in _typed_attrs(node.attrib).items()
            if key in cls.__attrs__
        }
        return cls(**attrs)


def _attrs_to_tree(obj: Any, tagname: str) -> Any:
    node = Element(tagname)
    for name, value in obj:
        node.set(name, value)
    return node


def _typed_attrs(attrs: dict[str, str]) -> dict[str, Any]:
    typed: dict[str, Any] = {}
    for name, value in attrs.items():
        if name in _BOOL_ATTRS:
            typed[name] = value.lower() in {"1", "true"}
        elif name in _INT_ATTRS:
            typed[name] = int(value)
        else:
            typed[name] = value
    return typed


_BOOL_ATTRS = {
    "minimized",
    "showHorizontalScroll",
    "showVerticalScroll",
    "showSheetTabs",
    "autoFilterDateGrouping",
    "autoUpdate",
    "changesSavedWin",
    "onlySync",
    "personalView",
    "includePrintSettings",
    "includeHiddenRowCol",
    "maximized",
    "showFormulaBar",
    "showStatusbar",
}

_INT_ATTRS = {
    "xWindow",
    "yWindow",
    "windowWidth",
    "windowHeight",
    "tabRatio",
    "firstSheet",
    "activeTab",
    "mergeInterval",
    "activeSheetId",
}


__all__ = ["BookView", "CustomWorkbookView"]

__getattr__ = _openpyxl_name_fallback(globals())
