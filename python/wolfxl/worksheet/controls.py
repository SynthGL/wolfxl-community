"""Worksheet controls compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _iter_openpyxl_attrs, _make_serialisable
from wolfxl.worksheet.ole import ObjectAnchor as _ObjectAnchor
from wolfxl.xml.constants import REL_NS
from wolfxl.xml.functions import Element, localname

Control = _make_serialisable("Control")


@dataclass
class ControlProperty:
    """ActiveX/control property payload with openpyxl-compatible XML shape."""

    tagname = "controlPr"
    __attrs__ = (
        "locked",
        "defaultSize",
        "_print",
        "disabled",
        "recalcAlways",
        "uiObject",
        "autoFill",
        "autoLine",
        "autoPict",
        "macro",
        "altText",
        "linkedCell",
        "listFillRange",
        "cf",
        "id",
    )
    __elements__ = ("anchor",)

    anchor: _ObjectAnchor | None = None
    locked: bool = True
    defaultSize: bool = True  # noqa: N815
    _print: bool = True
    disabled: bool = False
    recalcAlways: bool = False  # noqa: N815
    uiObject: bool = False  # noqa: N815
    autoFill: bool = True  # noqa: N815
    autoLine: bool = True  # noqa: N815
    autoPict: bool = True  # noqa: N815
    macro: str | None = None
    altText: str | None = None  # noqa: N815
    linkedCell: str | None = None  # noqa: N815
    listFillRange: str | None = None  # noqa: N815
    cf: str | None = "pict"
    id: str | None = None

    def __iter__(self):
        for name, value in _iter_openpyxl_attrs(self, self.__attrs__):
            if name == "_print":
                name = "print"
            yield name, value

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for name, value in self:
            if name == "id":
                node.set(f"{{{REL_NS}}}id", value)
            else:
                node.set(name, value)
        if self.anchor is not None:
            node.append(self.anchor.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "ControlProperty":
        attrs: dict[str, Any] = {}
        for key, value in node.attrib.items():
            name = _local_name(key)
            if name == "print":
                name = "_print"
            elif name == "id":
                name = "id"
            if name in cls.__attrs__:
                attrs[name] = _coerce_attr(name, value)
        anchor = None
        for child in node:
            if localname(child) == "anchor":
                anchor = _ObjectAnchor.from_tree(child)
                break
        return cls(anchor=anchor, **attrs)


Controls = _make_serialisable("Controls")
ObjectAnchor = _ObjectAnchor
Bool = Integer = Relation = Sequence = Serialisable = String = Typed = (
    _OpenpyxlSerialisable
)


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1] if "}" in name else name


def _coerce_attr(name: str, value: str) -> Any:
    if name in {
        "locked",
        "defaultSize",
        "_print",
        "disabled",
        "recalcAlways",
        "uiObject",
        "autoFill",
        "autoLine",
        "autoPict",
    }:
        return value.lower() in {"1", "true"}
    return value

__all__ = [
    "Bool",
    "Control",
    "ControlProperty",
    "Controls",
    "Integer",
    "ObjectAnchor",
    "Relation",
    "Sequence",
    "Serialisable",
    "String",
    "Typed",
]
