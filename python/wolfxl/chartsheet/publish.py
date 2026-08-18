"""Chartsheet web publish compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable
from wolfxl.xml.functions import Element, localname


@dataclass
class WebPublishItem:
    tagname = "webPublishItem"
    __attrs__ = (
        "id",
        "divId",
        "sourceType",
        "sourceRef",
        "sourceObject",
        "destinationFile",
        "title",
        "autoRepublish",
    )

    id: int | None = None
    divId: str | None = None  # noqa: N815
    sourceType: str | None = None  # noqa: N815
    sourceRef: str | None = None  # noqa: N815
    sourceObject: str | None = None  # noqa: N815
    destinationFile: str | None = None  # noqa: N815
    title: str | None = None
    autoRepublish: bool | None = None  # noqa: N815

    def to_tree(self, tagname: str | None = None, idx: Any = None) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for attr in self.__attrs__:
            value = getattr(self, attr)
            if value is None:
                continue
            node.set(attr, _serialise_value(value))
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "WebPublishItem":
        return cls(
            id=_to_int(node.get("id")),
            divId=node.get("divId"),
            sourceType=node.get("sourceType"),
            sourceRef=node.get("sourceRef"),
            sourceObject=node.get("sourceObject"),
            destinationFile=node.get("destinationFile"),
            title=node.get("title"),
            autoRepublish=_to_bool(node.get("autoRepublish")),
        )


class WebPublishItems:
    tagname = "WebPublishItems"
    __attrs__ = ("count",)
    __elements__ = ("webPublishItem",)

    def __init__(
        self,
        count: int | None = None,
        webPublishItem: list[WebPublishItem] | None = None,  # noqa: N803
    ) -> None:
        self.webPublishItem = list(webPublishItem or [])
        self.count = len(self.webPublishItem) if count is None else count

    def to_tree(self, tagname: str | None = None, idx: Any = None) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        node.set("count", str(len(self.webPublishItem)))
        for item in self.webPublishItem:
            node.append(item.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "WebPublishItems":
        items = [
            WebPublishItem.from_tree(child)
            for child in list(node)
            if localname(child) == "webPublishItem"
        ]
        return cls(count=_to_int(node.get("count")), webPublishItem=items)


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


Bool = Integer = Sequence = Serialisable = Set = String = _OpenpyxlSerialisable

__all__ = [
    "Bool",
    "Integer",
    "Sequence",
    "Serialisable",
    "Set",
    "String",
    "WebPublishItem",
    "WebPublishItems",
]
