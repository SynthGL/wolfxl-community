"""Shim for ``openpyxl.styles.differential``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.styles import Border, Color, Font, PatternFill
from wolfxl.xml.functions import Element


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass
class DifferentialStyle:
    """Conditional-format differential style value object."""

    font: Any = None
    numFmt: Any = None  # noqa: N815
    fill: Any = None
    alignment: Any = None
    border: Any = None
    protection: Any = None
    extLst: Any = None  # noqa: N815

    @classmethod
    def from_tree(cls, node: ET.Element) -> "DifferentialStyle":
        style = cls()
        for child in node:
            child_name = _local_name(child.tag)
            if child_name == "font":
                style.font = Font.from_tree(_strip_namespace(child))
            elif child_name == "fill":
                style.fill = _pattern_fill_from_tree(child)
            elif child_name == "border":
                style.border = _border_from_tree(child)
        return style

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        node = Element(tagname or "dxf")
        for value, child_name in (
            (self.font, "font"),
            (self.numFmt, "numFmt"),
            (self.fill, "fill"),
            (self.alignment, "alignment"),
            (self.border, "border"),
            (self.protection, "protection"),
        ):
            if value is not None:
                node.append(_to_tree(value, child_name))
        return node

    def to_rust_dict(self) -> dict[str, Any]:
        return {
            "font": _style_to_dict(self.font),
            "num_fmt": _style_to_dict(self.numFmt),
            "fill": _style_to_dict(self.fill),
            "alignment": _style_to_dict(self.alignment),
            "border": _style_to_dict(self.border),
            "protection": _style_to_dict(self.protection),
        }


class DifferentialStyleList:
    tagname = "dxfs"

    def __init__(
        self,
        dxf: list[DifferentialStyle] | tuple[DifferentialStyle, ...] = (),
        count: int | None = None,  # noqa: ARG002
    ) -> None:
        self.dxf: list[DifferentialStyle] = []
        for style in dxf:
            self.append(style)

    @property
    def styles(self) -> list[DifferentialStyle]:
        return self.dxf

    @property
    def count(self) -> int:
        return len(self.dxf)

    def __iter__(self):
        return iter(self.dxf)

    def __contains__(self, value: object) -> bool:
        return value in self.dxf

    def append(self, style: DifferentialStyle) -> None:
        is_alias = any(
            cls.__name__ == "DifferentialStyle"
            and cls.__module__.endswith("styles.differential")
            for cls in type(style).__mro__
        )
        if not isinstance(style, DifferentialStyle) and not is_alias:
            raise TypeError(f"expected {DifferentialStyle}")
        self.dxf.append(style)

    def add(self, style: DifferentialStyle) -> int:
        self.append(style)
        return len(self.dxf) - 1

    @classmethod
    def from_tree(cls, node: ET.Element) -> "DifferentialStyleList":
        styles = [
            DifferentialStyle.from_tree(child)
            for child in node
            if _local_name(child.tag) == "dxf"
        ]
        return cls(dxf=styles)

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        node = Element(tagname or self.tagname)
        node.set("count", str(self.count))
        for style in self.dxf:
            node.append(style.to_tree())
        return node


def _style_to_dict(value: Any) -> dict[str, Any] | Any:
    if hasattr(value, "to_rust_dict"):
        return value.to_rust_dict()
    return value


def _pattern_fill_from_tree(node: ET.Element) -> PatternFill:
    pattern = next(
        (item for item in node if _local_name(item.tag) == "patternFill"),
        None,
    )
    if pattern is None:
        return PatternFill()
    fg_color = None
    bg_color = None
    for color_node in pattern:
        color_name = _local_name(color_node.tag)
        if color_name == "fgColor":
            fg_color = _color_from_tree(color_node)
        elif color_name == "bgColor":
            bg_color = _color_from_tree(color_node)
    return PatternFill(
        patternType=pattern.attrib.get("patternType"),
        fgColor=fg_color,
        bgColor=bg_color,
    )


def _color_from_tree(node: ET.Element) -> Any:
    color = Color.from_tree(_strip_namespace(node))
    return color.rgb if color.type == "rgb" else color


def _to_tree(value: Any, tagname: str) -> ET.Element:
    if isinstance(value, Border):
        return _border_to_tree(value, tagname)
    if hasattr(value, "to_tree"):
        return value.to_tree(tagname)
    node = Element(tagname)
    for key, attr_value in dict(value).items():
        node.set(key, str(attr_value))
    return node


def _border_from_tree(node: ET.Element) -> Border:
    from wolfxl.styles import Side

    border = Border.from_tree(_strip_namespace(node))
    if border.diagonal is None:
        object.__setattr__(border, "diagonal", Side())
    return border


def _border_to_tree(border: Border, tagname: str) -> ET.Element:
    from wolfxl.styles import Side

    node = Element(tagname)
    non_default = any(
        getattr(border, side_name) != Side()
        for side_name in ("left", "right", "top", "bottom", "diagonal")
    )
    for side_name in ("left", "right", "top", "bottom", "diagonal"):
        side = getattr(border, side_name)
        if side is None:
            continue
        if side == Side() and not (side_name == "left" and non_default):
            continue
        node.append(_side_to_tree(side, side_name))
    return node


def _side_to_tree(side: Any, tagname: str) -> ET.Element:
    node = Element(tagname)
    if side.style is not None:
        node.set("style", side.style)
    if side.color is not None:
        color = side.color if isinstance(side.color, Color) else Color(side.color)
        node.append(color.to_tree("color"))
    return node


def _strip_namespace(node: ET.Element) -> ET.Element:
    stripped = ET.Element(_local_name(node.tag), dict(node.attrib))
    for child in node:
        stripped.append(_strip_namespace(child))
    return stripped


__all__ = ["DifferentialStyle", "DifferentialStyleList"]

__getattr__ = _openpyxl_name_fallback(globals())
