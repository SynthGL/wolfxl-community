"""Chartsheet relationship compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _iter_openpyxl_attrs
from wolfxl.xml.constants import REL_NS
from wolfxl.xml.functions import Element


@dataclass
class SheetBackgroundPicture:
    tagname = "picture"
    __attrs__ = ("id",)

    id: str | None = None

    def to_tree(self, tagname: str | None = None, idx: Any = None) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        if self.id is not None:
            node.set(f"{{{REL_NS}}}id", self.id)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "SheetBackgroundPicture":
        return cls(id=_relationship_id(node))


@dataclass
class DrawingHF:
    __attrs__ = (
        "id",
        "lho",
        "lhe",
        "lhf",
        "cho",
        "che",
        "chf",
        "rho",
        "rhe",
        "rhf",
        "lfo",
        "lfe",
        "lff",
        "cfo",
        "cfe",
        "cff",
        "rfo",
        "rfe",
        "rff",
    )

    id: str | None = None
    lho: int | None = None
    lhe: int | None = None
    lhf: int | None = None
    cho: int | None = None
    che: int | None = None
    chf: int | None = None
    rho: int | None = None
    rhe: int | None = None
    rhf: int | None = None
    lfo: int | None = None
    lfe: int | None = None
    lff: int | None = None
    cfo: int | None = None
    cfe: int | None = None
    cff: int | None = None
    rfo: int | None = None
    rfe: int | None = None
    rff: int | None = None

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, idx: Any = None) -> Any:  # noqa: ARG002
        node = Element(tagname or "drawingHF")
        if self.id is not None:
            node.set(f"{{{REL_NS}}}id", self.id)
        for attr in self.__attrs__[1:]:
            value = getattr(self, attr)
            if value is not None:
                node.set(attr, str(value))
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "DrawingHF":
        kwargs: dict[str, Any] = {"id": _relationship_id(node)}
        for attr in cls.__attrs__[1:]:
            value = node.get(attr)
            kwargs[attr] = int(value) if value is not None else None
        return cls(**kwargs)


def _relationship_id(node: Any) -> str | None:
    return node.get(f"{{{REL_NS}}}id") or node.get("r:id") or node.get("id")


Alias = Integer = Relation = Serialisable = object

__all__ = ["Alias", "DrawingHF", "Integer", "Relation", "Serialisable", "SheetBackgroundPicture"]
