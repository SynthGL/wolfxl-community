"""Worksheet OLE object compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _iter_openpyxl_attrs, _make_serialisable
from wolfxl.drawing.spreadsheet_drawing import AnchorMarker
from wolfxl.xml.constants import SHEET_DRAWING_NS
from wolfxl.xml.functions import Element, localname


@dataclass
class ObjectAnchor:
    """OLE/control anchor with openpyxl-compatible XML shape."""

    tagname = "anchor"
    __attrs__ = ("moveWithCells", "sizeWithCells", "z_order")
    __elements__ = ("_from", "to")

    _from: AnchorMarker
    to: AnchorMarker
    moveWithCells: bool = False  # noqa: N815
    sizeWithCells: bool = False  # noqa: N815
    z_order: int | None = None

    def __iter__(self):
        for name, value in _iter_openpyxl_attrs(self, self.__attrs__):
            if name == "z_order":
                name = "z-order"
            yield name, value

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for name, value in self:
            node.set(name, value)
        node.append(_marker_to_tree(self._from, "from"))
        node.append(_marker_to_tree(self.to, "to"))
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "ObjectAnchor":
        kwargs: dict[str, Any] = {
            "moveWithCells": _to_bool(node.get("moveWithCells")),
            "sizeWithCells": _to_bool(node.get("sizeWithCells")),
            "z_order": _to_int(node.get("z-order")),
        }
        markers: dict[str, AnchorMarker] = {}
        for child in node:
            name = localname(child)
            if name in {"from", "to"}:
                markers["_from" if name == "from" else "to"] = _marker_from_tree(child)
        return cls(
            _from=markers.get("_from", AnchorMarker()),
            to=markers.get("to", AnchorMarker()),
            **kwargs,
        )


ObjectPr = _make_serialisable("ObjectPr")
OleObject = _make_serialisable("OleObject")
OleObjects = _make_serialisable("OleObjects")
Bool = Integer = Sequence = Serialisable = Set = String = Typed = _OpenpyxlSerialisable


def _marker_to_tree(marker: AnchorMarker, tagname: str) -> Any:
    node = Element(f"{{{SHEET_DRAWING_NS}}}{tagname}")
    for name in ("col", "colOff", "row", "rowOff"):
        child = Element(f"{{{SHEET_DRAWING_NS}}}{name}")
        child.text = str(getattr(marker, name))
        node.append(child)
    return node


def _marker_from_tree(node: Any) -> AnchorMarker:
    values: dict[str, int] = {}
    for child in node:
        name = localname(child)
        if name in {"col", "colOff", "row", "rowOff"}:
            values[name] = _to_int(child.text) or 0
    return AnchorMarker(**values)


def _to_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true"}


def _to_int(value: Any) -> int | None:
    return int(value) if value not in {None, ""} else None

__all__ = [
    "AnchorMarker",
    "Bool",
    "Integer",
    "ObjectAnchor",
    "ObjectPr",
    "OleObject",
    "OleObjects",
    "SHEET_DRAWING_NS",
    "Sequence",
    "Serialisable",
    "Set",
    "String",
    "Typed",
]
