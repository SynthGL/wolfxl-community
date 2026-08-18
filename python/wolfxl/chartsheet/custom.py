"""Chartsheet custom view compatibility."""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable
from wolfxl.worksheet.header_footer import HeaderFooter
from wolfxl.worksheet.page import PageMargins, PrintPageSetup
from wolfxl.xml.functions import Element, localname


class CustomChartsheetView(_OpenpyxlSerialisable):
    tagname = "customSheetView"
    __attrs__ = ("guid", "scale", "state", "zoomToFit")
    __elements__ = ("pageMargins", "pageSetup", "headerFooter")

    def __init__(
        self,
        guid: str | None = None,
        scale: int | None = None,
        state: str = "visible",
        zoomToFit: bool | int | None = None,  # noqa: N803
        pageMargins: Any = None,  # noqa: N803
        pageSetup: Any = None,  # noqa: N803
        headerFooter: Any = None,  # noqa: N803
    ) -> None:
        self.guid = guid
        self.scale = scale
        self.state = state
        self.zoomToFit = zoomToFit
        self.pageMargins = pageMargins
        self.pageSetup = pageSetup
        self.headerFooter = headerFooter

    @classmethod
    def from_tree(cls, node: Any) -> "CustomChartsheetView":
        view = cls(
            guid=node.get("guid"),
            scale=_to_int(node.get("scale")),
            state=node.get("state", "visible"),
            zoomToFit=_to_bool(node.get("zoomToFit")),
        )
        for child in list(node):
            child_name = localname(child)
            if child_name == "pageMargins":
                view.pageMargins = _page_margins_from_tree(child)
            elif child_name == "pageSetup":
                view.pageSetup = PrintPageSetup(**dict(child.attrib))
            elif child_name == "headerFooter":
                view.headerFooter = HeaderFooter.from_tree(child)
        return view

    def to_tree(self, tagname: str | None = None, idx: Any = None) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for name in self.__attrs__:
            value = getattr(self, name)
            if value is not None:
                node.set(name, _serialise_value(value))
        if self.pageMargins is not None:
            node.append(_to_tree(self.pageMargins, "pageMargins"))
        if self.pageSetup is not None:
            node.append(_to_tree(self.pageSetup, "pageSetup"))
        if self.headerFooter is not None:
            node.append(_to_tree(self.headerFooter, "headerFooter"))
        return node


class CustomChartsheetViews(_OpenpyxlSerialisable):
    tagname = "customSheetViews"
    __elements__ = ("customSheetView",)

    def __init__(self, customSheetView: list[CustomChartsheetView] | None = None) -> None:  # noqa: N803
        self.customSheetView = list(customSheetView or [])

    @classmethod
    def from_tree(cls, node: Any) -> "CustomChartsheetViews":
        return cls(
            customSheetView=[
                CustomChartsheetView.from_tree(child)
                for child in list(node)
                if localname(child) == "customSheetView"
            ]
        )

    def to_tree(self, tagname: str | None = None, idx: Any = None) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for view in self.customSheetView:
            node.append(view.to_tree())
        return node


Bool = Guid = Integer = Sequence = Serialisable = Set = Typed = _OpenpyxlSerialisable


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true"}


def _to_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _serialise_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _page_margins_from_tree(node: Any) -> PageMargins:
    return PageMargins(**{name: float(value) for name, value in node.attrib.items()})


def _to_tree(obj: Any, tagname: str) -> Any:
    if hasattr(obj, "to_tree"):
        return obj.to_tree(tagname)
    node = Element(tagname)
    for name, value in dict(obj).items():
        if value is not None:
            node.set(name, str(value))
    return node

__all__ = [
    "Bool",
    "CustomChartsheetView",
    "CustomChartsheetViews",
    "Guid",
    "HeaderFooter",
    "Integer",
    "PageMargins",
    "PrintPageSetup",
    "Sequence",
    "Serialisable",
    "Set",
    "Typed",
]
