"""Workbook web publishing compatibility."""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable
from wolfxl.xml.functions import localname

Bool = Float = Integer = NoneSet = Sequence = Serialisable = String = Typed = (
    _OpenpyxlSerialisable
)


class _WebSerialisable(_OpenpyxlSerialisable):
    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return False
        return self.__dict__ == other.__dict__


class WebPublishObject(_WebSerialisable):
    tagname = "webPublishingObject"
    __attrs__ = (
        "id",
        "divId",
        "sourceObject",
        "destinationFile",
        "title",
        "autoRepublish",
    )

    def __init__(
        self,
        id: int,  # noqa: A002
        divId: str | None = None,  # noqa: N803
        sourceObject: str | None = None,  # noqa: N803
        destinationFile: str | None = None,  # noqa: N803
        title: str | None = None,
        autoRepublish: bool | None = None,  # noqa: N803
    ) -> None:
        self.id = int(id)
        self.divId = divId
        self.sourceObject = sourceObject
        self.destinationFile = destinationFile
        self.title = title
        self.autoRepublish = autoRepublish

    @classmethod
    def from_tree(cls, node: Any) -> "WebPublishObject":
        attrs = _attrs_from_node(node, cls.__attrs__)
        return cls(**attrs)


class WebPublishObjectList(_WebSerialisable):
    tagname = "webPublishingObjects"
    __elements__ = ("webPublishObject",)

    def __init__(
        self,
        count: int | None = None,  # noqa: ARG002
        webPublishObject: tuple[WebPublishObject, ...] | list[WebPublishObject] = (),  # noqa: N803
    ) -> None:
        self.webPublishObject = list(webPublishObject)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = super().to_tree(tagname)
        for item in self.webPublishObject:
            node.append(item.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "WebPublishObjectList":
        objects = [
            WebPublishObject.from_tree(child)
            for child in node
            if localname(child) == WebPublishObject.tagname
        ]
        return cls(webPublishObject=objects)


class WebPublishing(_WebSerialisable):
    tagname = "webPublishing"
    __attrs__ = (
        "css",
        "thicket",
        "longFileNames",
        "vml",
        "allowPng",
        "targetScreenSize",
        "dpi",
        "codePage",
        "characterSet",
    )

    def __init__(
        self,
        css: bool | None = None,
        thicket: bool | None = None,
        longFileNames: bool | None = None,  # noqa: N803
        vml: bool | None = None,
        allowPng: bool | None = None,  # noqa: N803
        targetScreenSize: str | None = "800x600",  # noqa: N803
        dpi: int | None = None,
        codePage: int | None = None,  # noqa: N803
        characterSet: str | None = None,  # noqa: N803
    ) -> None:
        self.css = css
        self.thicket = thicket
        self.longFileNames = longFileNames
        self.vml = vml
        self.allowPng = allowPng
        self.targetScreenSize = targetScreenSize
        self.dpi = dpi
        self.codePage = codePage
        self.characterSet = characterSet

    @classmethod
    def from_tree(cls, node: Any) -> "WebPublishing":
        attrs = _attrs_from_node(node, cls.__attrs__)
        return cls(**attrs)


def _attrs_from_node(node: Any, names: tuple[str, ...]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for name in names:
        value = node.get(name)
        if value is None:
            continue
        attrs[name] = _typed_attr(name, value)
    return attrs


def _typed_attr(name: str, value: str) -> Any:
    if name in {"id", "dpi", "codePage"}:
        return int(value)
    if name in {
        "autoRepublish",
        "css",
        "thicket",
        "longFileNames",
        "vml",
        "allowPng",
    }:
        return value.lower() in {"1", "true"}
    return value


__all__ = [
    "Bool",
    "Float",
    "Integer",
    "NoneSet",
    "Sequence",
    "Serialisable",
    "String",
    "Typed",
    "WebPublishObject",
    "WebPublishObjectList",
    "WebPublishing",
]
