"""Chartsheet view compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _iter_openpyxl_attrs
from wolfxl.xml.functions import Element, localname


@dataclass
class ChartsheetView:
    tagname = "sheetView"
    __attrs__ = ("tabSelected", "zoomScale", "workbookViewId", "zoomToFit")

    tabSelected: bool | None = None  # noqa: N815
    zoomScale: int | None = None  # noqa: N815
    workbookViewId: int = 0  # noqa: N815
    zoomToFit: bool | None = True  # noqa: N815
    extLst: Any = None  # noqa: N815

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, idx: Any = None) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for attr in self.__attrs__:
            value = getattr(self, attr)
            if value is not None:
                node.set(attr, _serialise_value(value))
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "ChartsheetView":
        return cls(
            tabSelected=_to_bool(node.get("tabSelected")),
            zoomScale=_to_int(node.get("zoomScale")),
            workbookViewId=_to_int(node.get("workbookViewId")) or 0,
            zoomToFit=_to_bool(node.get("zoomToFit")),
        )


class ChartsheetViewList:
    tagname = "sheetViews"
    __elements__ = ("sheetView",)

    def __init__(
        self,
        sheetView: list[ChartsheetView] | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
    ) -> None:
        self.sheetView = list(sheetView or [ChartsheetView()])
        self.extLst = extLst

    def __iter__(self):
        return iter(())

    def to_tree(self, tagname: str | None = None, idx: Any = None) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for view in self.sheetView:
            node.append(view.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "ChartsheetViewList":
        views = [
            ChartsheetView.from_tree(child)
            for child in list(node)
            if localname(child) == "sheetView"
        ]
        return cls(sheetView=views)


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


Bool = ExtensionList = Integer = Sequence = Serialisable = Typed = _OpenpyxlSerialisable

__all__ = [
    "Bool",
    "ChartsheetView",
    "ChartsheetViewList",
    "ExtensionList",
    "Integer",
    "Sequence",
    "Serialisable",
    "Typed",
]
