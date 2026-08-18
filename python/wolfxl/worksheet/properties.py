"""Worksheet properties (RFC-055 §2.x — Pod 2 re-export targets).

Provides ``WorksheetProperties``, ``PageSetupProperties``, ``Outline``
classes that mirror openpyxl's
``openpyxl.worksheet.properties.{WorksheetProperties, PageSetupProperties, Outline}``.

These are container classes; the actual page-setup contract lives in
``wolfxl.worksheet.page_setup``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from wolfxl._compat import _iter_openpyxl_attrs, _openpyxl_name_fallback
from wolfxl.styles.colors import Color
from wolfxl.xml.functions import Element, localname


@dataclass
class Outline:
    """Outline display properties for sheet rows/columns."""

    tagname: ClassVar[str] = "outlinePr"
    __attrs__: ClassVar[tuple[str, ...]] = (
        "applyStyles",
        "summaryBelow",
        "summaryRight",
        "showOutlineSymbols",
    )

    summaryBelow: bool | None = None  # noqa: N815
    summaryRight: bool | None = None  # noqa: N815
    applyStyles: bool | None = None  # noqa: N815
    showOutlineSymbols: bool | None = None  # noqa: N815

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        return _attrs_to_tree(self, tagname or self.tagname)

    @classmethod
    def from_tree(cls, node: Any) -> "Outline":
        return cls(**_parse_bool_attrs(node.attrib))


@dataclass
class PageSetupProperties:
    """`<pageSetUpPr>` toggles inside `<sheetPr>`."""

    tagname: ClassVar[str] = "pageSetUpPr"
    __attrs__: ClassVar[tuple[str, ...]] = ("autoPageBreaks", "fitToPage")

    autoPageBreaks: bool | None = None  # noqa: N815
    fitToPage: bool | None = None  # noqa: N815

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        return _attrs_to_tree(self, tagname or self.tagname)

    @classmethod
    def from_tree(cls, node: Any) -> "PageSetupProperties":
        return cls(**_parse_bool_attrs(node.attrib))


@dataclass
class WorksheetProperties:
    """Container for `<sheetPr>` child elements (CT_SheetPr)."""

    tagname: ClassVar[str] = "sheetPr"
    __attrs__: ClassVar[tuple[str, ...]] = (
        "codeName",
        "enableFormatConditionsCalculation",
        "filterMode",
        "published",
        "syncHorizontal",
        "syncRef",
        "syncVertical",
        "transitionEvaluation",
        "transitionEntry",
    )
    __elements__: ClassVar[tuple[str, ...]] = ("tabColor", "outlinePr", "pageSetUpPr")

    codeName: str | None = None  # noqa: N815
    enableFormatConditionsCalculation: bool | None = None  # noqa: N815
    filterMode: bool | None = None  # noqa: N815
    published: bool | None = None
    syncHorizontal: bool | None = None  # noqa: N815
    syncRef: str | None = None  # noqa: N815
    syncVertical: bool | None = None  # noqa: N815
    transitionEvaluation: bool | None = None  # noqa: N815
    transitionEntry: bool | None = None  # noqa: N815
    tabColor: Color | str | None = None  # noqa: N815  - "RRGGBB" hex
    outlinePr: Outline = field(  # noqa: N815
        default_factory=lambda: Outline(summaryBelow=True, summaryRight=True)
    )
    pageSetUpPr: PageSetupProperties = field(default_factory=PageSetupProperties)  # noqa: N815

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "tabColor" and isinstance(value, str):
            value = Color(rgb=value)
        super().__setattr__(name, value)

    def __post_init__(self) -> None:
        if self.outlinePr is None:
            self.outlinePr = Outline(summaryBelow=True, summaryRight=True)
        if self.pageSetUpPr is None:
            self.pageSetUpPr = PageSetupProperties()

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = _attrs_to_tree(self, tagname or self.tagname)
        for name in self.__elements__:
            value = getattr(self, name)
            if value is None:
                continue
            if name == "tabColor":
                node.append(value.to_tree("tabColor"))
            elif name == "pageSetUpPr":
                node.append(value.to_tree())
            elif dict(value):
                node.append(value.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "WorksheetProperties":
        attrs = _parse_bool_attrs(node.attrib)
        for name in ("codeName", "syncRef"):
            if name in node.attrib:
                attrs[name] = node.attrib[name]
        props = cls(**attrs)
        for child in node:
            name = localname(child)
            if name == "tabColor":
                props.tabColor = Color.from_tree(child)
            elif name == "outlinePr":
                props.outlinePr = Outline.from_tree(child)
            elif name == "pageSetUpPr":
                props.pageSetUpPr = PageSetupProperties.from_tree(child)
        return props


def _attrs_to_tree(obj: Any, tagname: str) -> Any:
    node = Element(tagname)
    for name, value in obj:
        node.set(name, value)
    return node


def _parse_bool_attrs(attrs: dict[str, str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in attrs.items():
        parsed[key] = value not in {"0", "false", "False"}
    return parsed


__all__ = [
    "WorksheetProperties",
    "PageSetupProperties",
    "Outline",
]

__getattr__ = _openpyxl_name_fallback(globals())
