"""Workbook function group compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _iter_openpyxl_attrs
from wolfxl.xml.functions import Element, localname

@dataclass
class FunctionGroup:
    tagname = "functionGroup"
    __attrs__ = ("name",)

    name: str | None = None

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for name, value in self:
            node.set(name, value)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "FunctionGroup":
        return cls(name=node.get("name"))


@dataclass
class FunctionGroupList:
    tagname = "functionGroups"
    __attrs__ = ("builtInGroupCount",)
    __elements__ = ("functionGroup",)

    functionGroup: list[FunctionGroup] = field(default_factory=list)  # noqa: N815
    builtInGroupCount: int | None = 16  # noqa: N815

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for name, value in self:
            node.set(name, value)
        for group in self.functionGroup:
            node.append(group.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "FunctionGroupList":
        groups = [
            FunctionGroup.from_tree(child)
            for child in node
            if localname(child) == "functionGroup"
        ]
        count = node.get("builtInGroupCount")
        return cls(
            functionGroup=groups,
            builtInGroupCount=int(count) if count is not None else 16,
        )


Integer = Sequence = Serialisable = String = _OpenpyxlSerialisable

__all__ = ["FunctionGroup", "FunctionGroupList", "Integer", "Sequence", "Serialisable", "String"]
