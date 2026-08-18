"""Workbook smart-tag compatibility."""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable
from wolfxl.xml.functions import localname

Bool = NoneSet = Sequence = Serialisable = String = _OpenpyxlSerialisable


class _SmartTagSerialisable(_OpenpyxlSerialisable):
    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return False
        return self.__dict__ == other.__dict__


class SmartTag(_SmartTagSerialisable):
    tagname = "smartTagType"
    __attrs__ = ("namespaceUri", "name", "url")


class SmartTagList(_SmartTagSerialisable):
    tagname = "smartTagTypes"
    __elements__ = ("smartTagType",)

    def __init__(self, smartTagType: tuple[SmartTag, ...] | list[SmartTag] = ()):  # noqa: N803
        self.smartTagType = list(smartTagType)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = super().to_tree(tagname)
        for tag in self.smartTagType:
            node.append(tag.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "SmartTagList":
        tags = [
            SmartTag.from_tree(child)
            for child in node
            if localname(child) == SmartTag.tagname
        ]
        return cls(smartTagType=tags)


class SmartTagProperties(_SmartTagSerialisable):
    tagname = "smartTagPr"
    __attrs__ = ("embed", "show")


__all__ = [
    "Bool",
    "NoneSet",
    "Sequence",
    "Serialisable",
    "SmartTag",
    "SmartTagList",
    "SmartTagProperties",
    "String",
]
