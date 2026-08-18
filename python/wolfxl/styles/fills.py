"""``openpyxl.styles.fills`` — fill value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wolfxl._compat import _install_openpyxl_iter, _openpyxl_name_fallback
from wolfxl._styles import Color, PatternFill, _color_lxml_tree
from wolfxl.xml.constants import SHEET_MAIN_NS
from wolfxl.xml.functions import Element, localname

FILL_NONE = "none"
FILL_SOLID = "solid"
FILL_PATTERN_DARKDOWN = "darkDown"
FILL_PATTERN_DARKGRAY = "darkGray"
FILL_PATTERN_DARKGRID = "darkGrid"
FILL_PATTERN_DARKHORIZONTAL = "darkHorizontal"
FILL_PATTERN_DARKTRELLIS = "darkTrellis"
FILL_PATTERN_DARKUP = "darkUp"
FILL_PATTERN_DARKVERTICAL = "darkVertical"
FILL_PATTERN_GRAY0625 = "gray0625"
FILL_PATTERN_GRAY125 = "gray125"
FILL_PATTERN_LIGHTDOWN = "lightDown"
FILL_PATTERN_LIGHTGRAY = "lightGray"
FILL_PATTERN_LIGHTGRID = "lightGrid"
FILL_PATTERN_LIGHTHORIZONTAL = "lightHorizontal"
FILL_PATTERN_LIGHTTRELLIS = "lightTrellis"
FILL_PATTERN_LIGHTUP = "lightUp"
FILL_PATTERN_LIGHTVERTICAL = "lightVertical"
FILL_PATTERN_MEDIUMGRAY = "mediumGray"

DEFAULT_EMPTY_FILL = PatternFill(fill_type=None)
DEFAULT_GRAY_FILL = PatternFill(fill_type=FILL_PATTERN_GRAY125)

# Pattern-type vocabulary mirrored from openpyxl for callers that
# introspect against it (e.g. validation pre-processors).
fills = (
    "none",
    "solid",
    "darkGray",
    "mediumGray",
    "lightGray",
    "gray125",
    "gray0625",
    "darkHorizontal",
    "darkVertical",
    "darkDown",
    "darkUp",
    "darkGrid",
    "darkTrellis",
    "lightHorizontal",
    "lightVertical",
    "lightDown",
    "lightUp",
    "lightGrid",
    "lightTrellis",
)


@dataclass
class Fill:
    """Base fill container.

    openpyxl exposes ``Fill`` as the abstract base for pattern and gradient
    fills. WolfXL treats it as a passive value object so direct construction
    used by migration code no longer raises.
    """

    tagname: str | None = None

    def to_rust_dict(self) -> dict[str, Any]:
        return {"tagname": self.tagname}

    @classmethod
    def from_tree(cls, node: Any) -> "Fill | None":
        children = list(node)
        if not children:
            return None
        child = children[0]
        name = localname(child)
        if name == "patternFill":
            return PatternFill.from_tree(child)
        if name == "gradientFill":
            return GradientFill.from_tree(child)
        return None


@dataclass
class Stop:
    color: Color
    position: float

    tagname = "stop"

    def __init__(self, color: Color | str, position: float) -> None:
        if position is None:
            raise TypeError("expected <class 'float'>")
        if position < 0 or position > 1:
            raise ValueError("Max value is 1")
        if not isinstance(color, Color):
            raw = str(color).lstrip("#").upper()
            color = Color(rgb=f"00{raw}" if len(raw) == 6 else raw)
        self.color = color
        self.position = position

    def __getitem__(self, index: int) -> float | str:
        if index == 0:
            return self.position
        if index == 1:
            return self.color.rgb or ""
        raise IndexError(index)

    def to_tree(self, tagname: str | None = None, idx: int | None = None) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        node.set("position", str(self.position))
        node.append(_color_lxml_tree(self.color, "color"))
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "Stop":
        color = Color()
        for child in node:
            if localname(child) == "color":
                color = Color.from_tree(child)
                break
        return cls(color, float(node.attrib["position"]))


def _assign_position(values: list[Any] | tuple[Any, ...]) -> list[Stop]:
    """Assign evenly spaced gradient positions for color-only stop lists."""
    values = list(values)
    if all(
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], (int, float))
        for value in values
    ):
        values = [Stop(value[1], float(value[0])) for value in values]
    n_values = len(values)
    n_stops = sum(isinstance(value, Stop) for value in values)

    if n_stops == 0:
        interval = 1
        if n_values > 2:
            interval = 1 / (n_values - 1)
        values = [Stop(value, i * interval) for i, value in enumerate(values)]
    elif n_stops < n_values:
        raise ValueError("Cannot interpret mix of Stops and Colors in GradientFill")

    positions = set()
    for stop in values:
        if stop.position in positions:
            raise ValueError(f"Duplicate position {stop.position}")
        positions.add(stop.position)

    return values


def _stop_color_for_rust(stop: Stop) -> str:
    rgb = stop.color.rgb or ""
    return rgb[2:] if rgb.startswith("00") and len(rgb) == 8 else rgb


class StopList:
    expected_type = Stop

    def __init__(self, name: str | None = None, **kw: Any) -> None:
        self.name = name
        self.kw = kw

    def __set__(self, obj: Any, values: list[Any] | tuple[Any, ...]) -> None:
        obj.__dict__["stop"] = _assign_position(values)


@dataclass
class GradientFill(Fill):
    """Gradient fill value object mirroring openpyxl's public shape."""

    type: str = "linear"  # noqa: A003
    degree: float = 0.0
    left: float = 0.0
    right: float = 0.0
    top: float = 0.0
    bottom: float = 0.0
    stop: list[Any] = field(default_factory=list)
    __attrs__ = ("type", "degree", "left", "right", "top", "bottom")
    __elements__ = ("stop",)

    def __init__(
        self,
        type: str = "linear",  # noqa: A002
        degree: float = 0.0,
        left: float = 0.0,
        right: float = 0.0,
        top: float = 0.0,
        bottom: float = 0.0,
        stop: list[Any] | tuple[Any, ...] | None = None,
        *,
        fill_type: str | None = None,
    ) -> None:
        self.tagname = "gradientFill"
        self.type = fill_type if fill_type is not None else type
        self.degree = degree
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom
        self.stop = _assign_position(list(stop or [])) if stop else []

    @property
    def fill_type(self) -> str:
        return self.type

    def to_rust_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "degree": self.degree,
            "left": self.left,
            "right": self.right,
            "top": self.top,
            "bottom": self.bottom,
            "stop": [_stop_color_for_rust(stop) for stop in self.stop],
        }

    def __iter__(self):
        for attr in self.__attrs__:
            value = getattr(self, attr)
            if value:
                yield attr, str(value)

    def to_tree(
        self,
        tagname: str | None = None,
        namespace: str | None = None,  # noqa: ARG002
        idx: int | None = None,  # noqa: ARG002
    ) -> Any:
        parent = Element(tagname or "fill")
        node = Element(self.tagname)
        for key, value in self:
            node.set(key, value)
        for stop in self.stop:
            node.append(stop.to_tree())
        parent.append(node)
        return parent

    @classmethod
    def from_tree(cls, node: Any) -> "GradientFill":
        if localname(node) == "fill":
            children = list(node)
            node = children[0] if children else node
        kwargs: dict[str, Any] = dict(node.attrib)
        for key in ("degree", "left", "right", "top", "bottom"):
            if key in kwargs:
                kwargs[key] = float(kwargs[key])
        kwargs["stop"] = [Stop.from_tree(child) for child in node if localname(child) == "stop"]
        return cls(**kwargs)


_install_openpyxl_iter(Fill, GradientFill, PatternFill)

__all__ = [
    "DEFAULT_EMPTY_FILL",
    "DEFAULT_GRAY_FILL",
    "FILL_NONE",
    "FILL_PATTERN_DARKDOWN",
    "FILL_PATTERN_DARKGRAY",
    "FILL_PATTERN_DARKGRID",
    "FILL_PATTERN_DARKHORIZONTAL",
    "FILL_PATTERN_DARKTRELLIS",
    "FILL_PATTERN_DARKUP",
    "FILL_PATTERN_DARKVERTICAL",
    "FILL_PATTERN_GRAY0625",
    "FILL_PATTERN_GRAY125",
    "FILL_PATTERN_LIGHTDOWN",
    "FILL_PATTERN_LIGHTGRAY",
    "FILL_PATTERN_LIGHTGRID",
    "FILL_PATTERN_LIGHTHORIZONTAL",
    "FILL_PATTERN_LIGHTTRELLIS",
    "FILL_PATTERN_LIGHTUP",
    "FILL_PATTERN_LIGHTVERTICAL",
    "FILL_PATTERN_MEDIUMGRAY",
    "FILL_SOLID",
    "Fill",
    "GradientFill",
    "PatternFill",
    "SHEET_MAIN_NS",
    "Stop",
    "StopList",
    "_assign_position",
    "fills",
]

__getattr__ = _openpyxl_name_fallback(globals())
