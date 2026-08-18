"""``NamedStyle`` + ``_NamedStyleList`` registry — RFC-064 §2.1."""

from __future__ import annotations

from collections.abc import Iterator
from copy import copy
from dataclasses import dataclass, field
import inspect as _inspect
from typing import Any

from wolfxl._compat import _install_openpyxl_iter
from wolfxl.styles.cell_style import CellStyle, StyleArray
from wolfxl.styles.numbers import BUILTIN_FORMATS_MAX_SIZE, BUILTIN_FORMATS_REVERSE
from wolfxl.styles.protection import Protection
from wolfxl._styles import Alignment, Border, Color, Font, PatternFill
from wolfxl.xml.functions import Element, localname


@dataclass(init=False)
class NamedStyle:
    """Named style (CT_CellStyle §18.8.7)."""

    name: str = "Normal"
    font: Any = None
    fill: Any = None
    border: Any = None
    alignment: Any = None
    protection: Any = None
    number_format: str = "General"
    builtinId: int | None = None  # noqa: N815
    customBuiltin: bool = False  # noqa: N815
    hidden: bool = False
    xfId: int | None = None  # noqa: N815
    tagname = "cellStyle"
    namespace = None
    idx_base = 0

    def __init__(
        self,
        name: str = "Normal",
        font: Any = None,
        fill: Any = None,
        border: Any = None,
        alignment: Any = None,
        number_format: str | None = None,
        protection: Any = None,
        builtinId: int | None = None,  # noqa: N803
        hidden: bool = False,
        *,
        customBuiltin: bool = False,  # noqa: N803
        xfId: int | None = None,  # noqa: N803
    ) -> None:
        self.name = name
        self.font = _named_style_component(font or Font())
        self.fill = _named_style_component(fill or PatternFill())
        self.border = _named_style_component(border or Border())
        self.alignment = _named_style_component(alignment or Alignment())
        self.protection = _named_style_component(protection or Protection())
        self.number_format = "General" if number_format is None else number_format
        self.builtinId = builtinId
        self.customBuiltin = customBuiltin
        self.hidden = hidden
        self.xfId = xfId
        self._wb = None
        self._style = StyleArray()

    def __setattr__(self, attr: str, value: Any) -> None:
        object.__setattr__(self, attr, value)
        if getattr(self, "_wb", None) is not None and attr in {
            "font",
            "fill",
            "border",
            "alignment",
            "number_format",
            "protection",
        }:
            self._recalculate()

    @property
    def is_builtin(self) -> bool:
        return self.builtinId is not None and not self.customBuiltin

    def to_rust_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "font": _style_to_dict(self.font),
            "fill": _style_to_dict(self.fill),
            "border": _style_to_dict(self.border),
            "alignment": _style_to_dict(self.alignment),
            "protection": _style_to_dict(self.protection),
            "number_format": self.number_format,
            "builtin_id": self.builtinId,
            "custom_builtin": self.customBuiltin,
            "hidden": self.hidden,
            "xf_id": self.xfId,
        }

    def bind(self, workbook: Any | None = None, *, wb: Any | None = None) -> None:
        """Bind this named style to a workbook."""
        workbook = workbook if workbook is not None else wb
        self._wb = workbook
        self._recalculate()

    def as_name(self) -> Any:
        """Return an openpyxl-shaped named-style metadata record."""
        return _NamedCellStyle(
            name=self.name,
            xfId=self._style.xfId,
            builtinId=self.builtinId,
            hidden=self.hidden,
        )

    def as_tuple(self) -> StyleArray:
        """Return the compact style-array tuple shape used by openpyxl."""
        return self._style

    def as_xf(self) -> Any:
        """Return an openpyxl-shaped cell-style projection."""
        xf = CellStyle.from_array(self._style)
        if self.alignment != Alignment():
            xf.alignment = self.alignment
        if self.protection != Protection():
            xf.protection = self.protection
        xf.xfId = self.xfId
        xf.quotePrefix = None
        xf.pivotButton = None
        return xf

    def _recalculate(self) -> None:
        wb = self._wb
        if wb is None:
            return
        self._style.fontId = wb._fonts.add(self.font)  # noqa: SLF001
        self._style.borderId = wb._borders.add(self.border)  # noqa: SLF001
        self._style.fillId = wb._fills.add(self.fill)  # noqa: SLF001
        self._style.protectionId = wb._protections.add(self.protection)  # noqa: SLF001
        self._style.alignmentId = wb._alignments.add(self.alignment)  # noqa: SLF001
        fmt = self.number_format
        if fmt in BUILTIN_FORMATS_REVERSE:
            self._style.numFmtId = BUILTIN_FORMATS_REVERSE[fmt]
        else:
            self._style.numFmtId = wb._number_formats.add(fmt) + (  # noqa: SLF001
                BUILTIN_FORMATS_MAX_SIZE
            )

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> Any:
        node = Element(tagname or self.tagname)
        node.set("name", self.name)
        node.set("xfId", str(0 if self.xfId is None else self.xfId))
        if self.builtinId is not None:
            node.set("builtinId", str(self.builtinId))
        if self.hidden:
            node.set("hidden", "1")
        if self.customBuiltin:
            node.set("customBuiltin", "1")
        return node

    @classmethod
    def from_tree(cls, node: Any) -> NamedStyle:
        attrs = node.attrib
        return cls(
            name=attrs.get("name", "Normal"),
            builtinId=int(attrs["builtinId"]) if "builtinId" in attrs else None,
            hidden=attrs.get("hidden", "0") not in {"0", "false", "False"},
            customBuiltin=attrs.get("customBuiltin", "0") not in {"0", "false", "False"},
            xfId=int(attrs["xfId"]) if "xfId" in attrs else None,
        )

    def __iter__(self):
        yield "name", self.name
        if self.builtinId is not None:
            yield "builtinId", str(self.builtinId)
        yield "hidden", "1" if self.hidden else "0"
        if self.xfId is not None:
            yield "xfId", str(self.xfId)


def _named_style_component(value: Any) -> Any:
    """Named styles own mutable style components, unlike direct cell styles."""
    cloned = copy(value)
    if hasattr(cloned, "_frozen"):
        object.__setattr__(cloned, "_frozen", False)
    return cloned


class _NamedCellStyle:
    """Pointer-based representation of named styles in styles.xml."""

    tagname = "cellStyle"
    __attrs__ = ("name", "xfId", "builtinId", "iLevel", "hidden", "customBuiltin")
    __elements__ = ()

    def __init__(
        self,
        name: str | None = None,
        xfId: int | None = None,  # noqa: N803
        builtinId: int | None = None,  # noqa: N803
        iLevel: int | None = None,  # noqa: N803
        hidden: bool | None = None,
        customBuiltin: bool | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
    ) -> None:
        self.name = name
        self.xfId = xfId
        self.builtinId = builtinId
        self.iLevel = iLevel
        self.hidden = hidden
        self.customBuiltin = customBuiltin
        self.extLst = extLst

    def __eq__(self, other: object) -> bool:
        return (
            getattr(other, "__class__", object).__name__ == self.__class__.__name__
            and getattr(other, "name", None) == self.name
            and getattr(other, "xfId", None) == self.xfId
            and getattr(other, "builtinId", None) == self.builtinId
            and getattr(other, "iLevel", None) == self.iLevel
            and getattr(other, "hidden", None) == self.hidden
            and getattr(other, "customBuiltin", None) == self.customBuiltin
        )

    def to_tree(self) -> Any:
        node = Element(self.tagname)
        _set_attr(node, "name", self.name)
        _set_attr(node, "xfId", self.xfId)
        _set_attr(node, "builtinId", self.builtinId)
        _set_attr(node, "iLevel", self.iLevel)
        _set_attr(node, "hidden", self.hidden)
        _set_attr(node, "customBuiltin", self.customBuiltin)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "_NamedCellStyle":
        return cls(
            name=node.get("name"),
            xfId=_int_or_none(node.get("xfId")),
            builtinId=_int_or_none(node.get("builtinId")),
            iLevel=_int_or_none(node.get("iLevel")),
            hidden=_bool_or_none(node.get("hidden")),
            customBuiltin=_bool_or_none(node.get("customBuiltin")),
        )


class _NamedCellStyleList:
    """Container for named cell style XML references."""

    tagname = "cellStyles"

    def __init__(
        self,
        count: int | None = None,  # noqa: ARG002
        cellStyle: list[_NamedCellStyle] | tuple[_NamedCellStyle, ...] = (),  # noqa: N803
    ) -> None:
        self.cellStyle = list(cellStyle)

    @property
    def count(self) -> int:
        return len(self.cellStyle)

    def __eq__(self, other: object) -> bool:
        return (
            getattr(other, "__class__", object).__name__ == self.__class__.__name__
            and getattr(other, "cellStyle", None) == self.cellStyle
        )

    def to_tree(self) -> Any:
        node = Element(self.tagname)
        node.set("count", str(self.count))
        for style in self.cellStyle:
            node.append(style.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "_NamedCellStyleList":
        return cls(
            cellStyle=[
                _NamedCellStyle.from_tree(child)
                for child in list(node)
                if localname(child) == "cellStyle"
            ]
        )

    def remove_duplicates(self) -> list[_NamedCellStyle]:
        styles = []
        names = set()
        ids = set()
        for style in sorted(self.cellStyle, key=lambda value: value.xfId or 0):
            if style.xfId in ids or style.name in names:
                continue
            ids.add(style.xfId)
            names.add(style.name)
            styles.append(style)
        return styles


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true"}


def _int_or_none(value: Any) -> int | None:
    return None if value is None else int(value)


def _set_attr(node: Any, name: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        value = "1" if value else "0"
    node.set(name, str(value))


NamedStyle.bind.__signature__ = _inspect.Signature(
    [
        _inspect.Parameter("self", _inspect.Parameter.POSITIONAL_OR_KEYWORD),
        _inspect.Parameter("wb", _inspect.Parameter.POSITIONAL_OR_KEYWORD),
    ]
)


def _style_to_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "to_rust_dict"):
        return value.to_rust_dict()
    out: dict[str, Any] = {}
    for key in (
        "name",
        "size",
        "bold",
        "italic",
        "underline",
        "strike",
        "color",
        "patternType",
        "fgColor",
        "horizontal",
        "vertical",
        "wrap_text",
        "text_rotation",
        "indent",
        "locked",
        "hidden",
    ):
        attr = getattr(value, key, None)
        if attr is not None and attr is not False and attr != 0:
            out[key] = getattr(attr, "rgb", attr)
    return out or None


_BUILTIN_SEEDS: tuple[tuple[str, int], ...] = (
    ("Normal", 0),
    ("Comma", 3),
    ("Comma [0]", 6),
    ("Currency", 4),
    ("Currency [0]", 7),
    ("Percent", 5),
    ("Hyperlink", 8),
    ("Followed Hyperlink", 9),
    ("Note", 10),
    ("Warning Text", 11),
    ("Title", 15),
    ("Heading 1", 16),
    ("Heading 2", 17),
    ("Heading 3", 18),
    ("Heading 4", 19),
    ("Input", 20),
    ("Output", 21),
    ("Calculation", 22),
    ("Check Cell", 23),
    ("Linked Cell", 24),
    ("Total", 25),
    ("Good", 26),
    ("Bad", 27),
    ("Neutral", 28),
    ("Accent1", 29),
    ("20% - Accent1", 30),
    ("40% - Accent1", 31),
    ("60% - Accent1", 32),
    ("Accent2", 33),
    ("20% - Accent2", 34),
    ("40% - Accent2", 35),
    ("60% - Accent2", 36),
    ("Accent3", 37),
    ("20% - Accent3", 38),
    ("40% - Accent3", 39),
    ("60% - Accent3", 40),
    ("Accent4", 41),
    ("20% - Accent4", 42),
    ("40% - Accent4", 43),
    ("60% - Accent4", 44),
    ("Accent5", 45),
    ("20% - Accent5", 46),
    ("40% - Accent5", 47),
    ("60% - Accent5", 48),
    ("Accent6", 49),
    ("20% - Accent6", 50),
    ("40% - Accent6", 51),
    ("60% - Accent6", 52),
)


@dataclass
class _NamedStyleList:
    """Workbook-level named-style registry exposed as ``wb.named_styles``."""

    _styles: list[NamedStyle] = field(default_factory=list)
    _by_name: dict[str, NamedStyle] = field(default_factory=dict)
    _seeded: bool = False

    def _seed_builtins(self) -> None:
        if self._seeded:
            return
        self._seeded = True
        for name, builtin_id in _BUILTIN_SEEDS:
            font = Font(color=Color(theme=1)) if name == "Normal" else None
            ns = NamedStyle(name=name, builtinId=builtin_id, font=font)
            self._styles.append(ns)
            self._by_name[name] = ns

    def append(self, ns: NamedStyle) -> None:
        if not isinstance(ns, NamedStyle):
            raise TypeError(
                f"named_styles.append requires a NamedStyle, got {type(ns).__name__}"
            )
        if not ns.name:
            raise ValueError("NamedStyle.name must be a non-empty string before append")
        self._seed_builtins()
        prior = self._by_name.get(ns.name)
        if prior is not None:
            raise ValueError(f"Style {ns.name} exists already")
        else:
            self._styles.append(ns)
        self._by_name[ns.name] = ns

    def add(self, ns: NamedStyle) -> None:
        self.append(ns)

    def __getitem__(self, name: str | int) -> NamedStyle:
        self._seed_builtins()
        if isinstance(name, int):
            return self._styles[name]
        try:
            return self._by_name[name]
        except KeyError:
            raise KeyError(f"NamedStyle {name!r} is not registered on this workbook") from None

    def __contains__(self, name: object) -> bool:
        self._seed_builtins()
        return name in self._by_name

    def __iter__(self) -> Iterator[NamedStyle]:
        self._seed_builtins()
        return iter(self._styles)

    def __len__(self) -> int:
        self._seed_builtins()
        return len(self._styles)

    @property
    def names(self) -> list[str]:
        self._seed_builtins()
        return [ns.name for ns in self._styles]

    def user_styles(self) -> list[NamedStyle]:
        self._seed_builtins()
        return [ns for ns in self._styles if not ns.is_builtin]


_install_openpyxl_iter(NamedStyle, _NamedCellStyle)

__all__ = ["NamedStyle", "_NamedCellStyle", "_NamedCellStyleList", "_NamedStyleList"]
