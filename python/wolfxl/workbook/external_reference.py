"""External reference compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable
from wolfxl.packaging.relationship import Relationship
from wolfxl.xml.constants import REL_NS
from wolfxl.xml.functions import Element


@dataclass
class ExternalReference:
    tagname = "externalReference"
    __attrs__ = ("id",)

    id: str | None = None

    def __iter__(self):
        if self.id is not None:
            yield "id", self.id

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> Any:
        node = Element(tagname or self.tagname)
        if self.id is not None:
            node.set(f"{{{REL_NS}}}id", self.id)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "ExternalReference":
        return cls(id=node.get(f"{{{REL_NS}}}id") or node.get("r:id") or node.get("id"))


Relation = Sequence = Serialisable = _OpenpyxlSerialisable

__all__ = ["ExternalReference", "Relation", "Relationship", "Sequence", "Serialisable"]
