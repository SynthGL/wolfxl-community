"""Stylesheet compatibility shims."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from warnings import warn
from xml.etree import ElementTree as ET

from wolfxl._compat import _OpenpyxlSerialisable, _install_openpyxl_iter
from wolfxl._styles import COLOR_INDEX, Alignment, Border, Color, Font, PatternFill
from wolfxl.styles.cell_style import CellStyle, StyleArray
from wolfxl.styles.differential import DifferentialStyle, DifferentialStyleList
from wolfxl.styles.fills import DEFAULT_EMPTY_FILL, DEFAULT_GRAY_FILL, Fill
from wolfxl.styles.numbers import (
    BUILTIN_FORMATS,
    BUILTIN_FORMATS_MAX_SIZE,
    BUILTIN_FORMATS_REVERSE,
    NumberFormat,
    is_date_format,
)
from wolfxl.styles.protection import Protection
from wolfxl.styles.table import TableStyle, TableStyleElement, TableStyleList
from wolfxl.styles._named_style import NamedStyle, _BUILTIN_SEEDS, _NamedCellStyleList
from wolfxl.xml.constants import ARC_STYLE, SHEET_MAIN_NS
from wolfxl.xml.functions import Element, SubElement, fromstring, localname

BUILTIN_FORMATS_MAX_SIZE = max(BUILTIN_FORMATS_MAX_SIZE, max(BUILTIN_FORMATS) + 1)
BUILTIN_FORMATS_REVERSE = {value: key for key, value in BUILTIN_FORMATS.items()}


def builtin_format_code(index: int) -> str | None:
    return BUILTIN_FORMATS.get(index)


def is_timedelta_format(fmt: str | None) -> bool:
    if fmt is None:
        return False
    return "[" in fmt and "]" in fmt and any(token in fmt.lower() for token in ("h", "m", "s"))


class IndexedList(list):
    def __init__(self, iterable: Any = None) -> None:
        super().__init__([] if iterable is None else iterable)

    def add(self, value: Any) -> int:
        if value not in self:
            self.append(value)
        return self.index(value)


@dataclass
class NumberFormatList:
    numFmt: list[NumberFormat] = field(default_factory=list)  # noqa: N815
    count: int | None = None

    def __post_init__(self) -> None:
        self.numFmt = list(self.numFmt)

    @property
    def count(self) -> int:  # type: ignore[override]
        return len(self.numFmt)

    @count.setter
    def count(self, value: int | None) -> None:  # noqa: ARG002
        return

    def __getitem__(self, idx: int) -> NumberFormat:
        return self.numFmt[idx]

    def to_tree(self) -> Any:
        node = Element("numFmts")
        node.set("count", str(self.count))
        for fmt in self.numFmt:
            child = SubElement(node, "numFmt")
            child.set("numFmtId", str(fmt.numFmtId))
            child.set("formatCode", "" if fmt.formatCode is None else str(fmt.formatCode))
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "NumberFormatList":
        return cls(
            numFmt=[
                NumberFormat(int(child.get("numFmtId")), child.get("formatCode"))
                for child in node
                if localname(child) == "numFmt"
            ]
        )


@dataclass
class ColorList:
    indexedColors: list[Any] = field(default_factory=list)  # noqa: N815
    mruColors: list[Any] = field(default_factory=list)  # noqa: N815

    def __post_init__(self) -> None:
        self.indexedColors = [self._normalise_rgb(value) for value in self.indexedColors]

    @property
    def index(self) -> list[Any]:
        return self.indexedColors

    @staticmethod
    def _normalise_rgb(value: Any) -> str:
        raw = getattr(value, "rgb", value)
        raw = str(raw)
        if len(raw) == 6:
            return f"00{raw}"
        return raw

    def __bool__(self) -> bool:
        return bool(self.indexedColors) or bool(self.mruColors)

    def to_tree(self, tagname: str | None = None, idx: int | None = None) -> Any:  # noqa: ARG002
        node = Element(tagname or "colors")
        if self.indexedColors:
            indexed = SubElement(node, "indexedColors")
            for rgb in self.indexedColors:
                child = SubElement(indexed, "rgbColor")
                child.set("rgb", rgb)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "ColorList":
        indexed_colors: list[str] = []
        for child in node:
            if localname(child) != "indexedColors":
                continue
            for rgb_color in child:
                if localname(rgb_color) == "rgbColor" and "rgb" in rgb_color.attrib:
                    indexed_colors.append(rgb_color.attrib["rgb"])
        return cls(indexedColors=indexed_colors)


class CellStyleList:
    tagname = "cellXfs"

    def __init__(
        self,
        count: int | None = None,  # noqa: ARG002
        xf: list[CellStyle] | tuple[CellStyle, ...] = (),
    ) -> None:
        self.xf = list(xf)

    @property
    def count(self) -> int:
        return len(self.xf)

    def __iter__(self):
        return iter(self.xf)

    def __getitem__(self, idx: int) -> CellStyle:
        return self.xf[idx]

    def to_tree(self, tagname: str | None = None) -> Any:
        node = Element(tagname or self.tagname)
        node.set("count", str(self.count))
        for xf in self.xf:
            node.append(xf.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "CellStyleList":
        return cls(xf=[CellStyle.from_tree(child) for child in node if localname(child) == "xf"])

    def _to_array(self) -> IndexedList:
        self.prots = IndexedList([Protection()])
        self.alignments = IndexedList([Alignment()])
        styles = []
        for xf in self.xf:
            style = xf.to_array()
            if xf.alignment is not None:
                style.alignmentId = self.alignments.add(xf.alignment)
            if xf.protection is not None:
                style.protectionId = self.prots.add(xf.protection)
            styles.append(style)
        return IndexedList(styles)


class NamedStyleList(list):
    def __init__(self, iterable=()):
        super().__init__()
        for style in iterable:
            self.append(style)

    def append(self, value: Any) -> None:
        if not isinstance(value, NamedStyle):
            raise TypeError("Only NamedStyle instances can be added")
        if value.name in self.names:
            raise ValueError(f"Style {value.name} exists already")
        value._style.xfId = len(self)  # noqa: SLF001
        super().append(value)

    @property
    def names(self) -> list[str]:
        return [style.name for style in self if getattr(style, "name", None)]

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return super().__getitem__(key)
        for style in self:
            if getattr(style, "name", None) == key:
                return style
        raise KeyError(f"No named style with the name{key} exists")


class Stylesheet(_OpenpyxlSerialisable):
    tagname = "styleSheet"

    def __init__(
        self,
        numFmts: NumberFormatList | None = None,  # noqa: N803
        fonts: list[Any] | tuple[Any, ...] = (),
        fills: list[Any] | tuple[Any, ...] = (),
        borders: list[Any] | tuple[Any, ...] = (),
        cellStyleXfs: CellStyleList | None = None,  # noqa: N803
        cellXfs: CellStyleList | None = None,  # noqa: N803
        cellStyles: _NamedCellStyleList | None = None,  # noqa: N803
        dxfs: list[Any] | tuple[Any, ...] = (),
        tableStyles: TableStyleList | None = None,  # noqa: N803
        colors: ColorList | None = None,
        extLst: Any = None,  # noqa: N803, ARG002
        **kw: Any,  # noqa: ARG002
    ) -> None:
        self.numFmts = numFmts if numFmts is not None else NumberFormatList()
        self.number_formats = IndexedList()
        self.fonts = IndexedList(fonts)
        self.fills = IndexedList(fills)
        self.borders = IndexedList(borders)
        self.cellStyleXfs = cellStyleXfs if cellStyleXfs is not None else CellStyleList()
        self.cellXfs = cellXfs if cellXfs is not None else CellStyleList()
        self.cellStyles = (
            cellStyles if cellStyles is not None else _NamedCellStyleList()
        )
        self.dxfs = list(dxfs)
        self.tableStyles = tableStyles
        self.colors = colors
        self.cell_styles = self.cellXfs._to_array()
        self.alignments = self.cellXfs.alignments
        self.protections = self.cellXfs.prots
        self._normalise_numbers()
        self.named_styles = self._merge_named_styles()

    @classmethod
    def from_tree(cls, node: Any) -> "Stylesheet":
        attrs: dict[str, Any] = {}
        for child in node:
            name = localname(child)
            if name == "numFmts":
                attrs["numFmts"] = NumberFormatList.from_tree(child)
            elif name == "fonts":
                attrs["fonts"] = [
                    Font.from_tree(grandchild)
                    for grandchild in child
                    if localname(grandchild) == "font"
                ]
            elif name == "fills":
                attrs["fills"] = [
                    Fill.from_tree(grandchild)
                    for grandchild in child
                    if localname(grandchild) == "fill"
                ]
            elif name == "borders":
                attrs["borders"] = [
                    Border.from_tree(grandchild)
                    for grandchild in child
                    if localname(grandchild) == "border"
                ]
            elif name == "cellStyleXfs":
                attrs["cellStyleXfs"] = CellStyleList.from_tree(child)
            elif name == "cellXfs":
                attrs["cellXfs"] = CellStyleList.from_tree(child)
            elif name == "cellStyles":
                attrs["cellStyles"] = _NamedCellStyleList.from_tree(child)
            elif name == "dxfs":
                attrs["dxfs"] = []
            elif name == "tableStyles":
                attrs["tableStyles"] = _table_style_list_from_tree(child)
            elif name == "colors":
                attrs["colors"] = ColorList.from_tree(child)
        return cls(**attrs)

    def _merge_named_styles(self) -> NamedStyleList:
        style_refs = self.cellStyles.remove_duplicates()
        return NamedStyleList([self._expand_named_style(style_ref) for style_ref in style_refs])

    def _expand_named_style(self, style_ref: Any) -> NamedStyle:
        xf = self.cellStyleXfs[style_ref.xfId]
        named_style = NamedStyle(
            name=style_ref.name,
            hidden=bool(style_ref.hidden),
            builtinId=style_ref.builtinId,
        )
        named_style.font = _indexed_or_default(self.fonts, xf.fontId, Font())
        named_style.fill = _indexed_or_default(self.fills, xf.fillId, DEFAULT_EMPTY_FILL)
        named_style.border = _indexed_or_default(self.borders, xf.borderId, Border())
        if xf.numFmtId < BUILTIN_FORMATS_MAX_SIZE:
            formats = BUILTIN_FORMATS
        else:
            formats = self.custom_formats
        if xf.numFmtId in formats:
            named_style.number_format = formats[xf.numFmtId]
        if xf.alignment is not None:
            named_style.alignment = xf.alignment
        if xf.protection is not None:
            named_style.protection = xf.protection
        named_style._style = xf.to_array()  # noqa: SLF001
        return named_style

    def _split_named_styles(self, wb: Any) -> None:
        registry = wb._named_styles  # noqa: SLF001
        workbook_seed_names = {name for name, _ in _BUILTIN_SEEDS}
        style_iterable = list(registry)
        if hasattr(registry, "_seeded"):
            style_iterable = [
                style
                for style in style_iterable
                if style.name == "Normal" or style.name not in workbook_seed_names
            ]
        for style in style_iterable:
            style._style.xfId = len(self.cellStyleXfs.xf)  # noqa: SLF001
            self.cellStyles.cellStyle.append(style.as_name())
            self.cellStyleXfs.xf.append(style.as_xf())

    @property
    def custom_formats(self) -> dict[int, str]:
        return {
            fmt.numFmtId: fmt.formatCode
            for fmt in self.numFmts.numFmt
            if fmt.numFmtId is not None and fmt.formatCode is not None
        }

    def _normalise_numbers(self) -> None:
        date_formats = set()
        timedelta_formats = set()
        custom = self.custom_formats
        formats = self.number_formats
        for idx, style in enumerate(self.cell_styles):
            fmt = None
            if style.numFmtId in custom:
                fmt = custom[style.numFmtId]
                if fmt in BUILTIN_FORMATS_REVERSE:
                    style.numFmtId = BUILTIN_FORMATS_REVERSE[fmt]
                else:
                    style.numFmtId = formats.add(fmt) + BUILTIN_FORMATS_MAX_SIZE
            else:
                fmt = builtin_format_code(style.numFmtId)
            if is_date_format(fmt):
                date_formats.add(idx)
            if is_timedelta_format(fmt):
                timedelta_formats.add(idx)
        self.date_formats = date_formats
        self.timedelta_formats = timedelta_formats

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002
        namespace: str | None = None,  # noqa: ARG002
    ) -> Any:
        node = Element(f"{{{SHEET_MAIN_NS}}}{tagname or self.tagname}")
        for child in (
            self.numFmts.to_tree(),
            _sequence_tree("fonts", self.fonts),
            _sequence_tree("fills", self.fills),
            _sequence_tree("borders", self.borders),
            self.cellStyleXfs.to_tree("cellStyleXfs"),
            self.cellXfs.to_tree("cellXfs"),
            self.cellStyles.to_tree(),
            _dxfs_tree(self.dxfs),
            _table_style_list_to_tree(self.tableStyles),
            self.colors.to_tree() if self.colors is not None else None,
        ):
            if child is not None:
                node.append(child)
        _qualify_tree(node)
        return node


def _indexed_or_default(values: list[Any], idx: int, default: Any) -> Any:
    try:
        return values[idx]
    except IndexError:
        return default


def _sequence_tree(tagname: str, values: list[Any]) -> Any | None:
    if not values:
        return None
    node = Element(tagname)
    node.set("count", str(len(values)))
    for value in values:
        if value is not None and hasattr(value, "to_tree"):
            child = _stylesheet_border_tree(value) if tagname == "borders" else value.to_tree()
            try:
                node.append(child)
            except TypeError:
                node.append(fromstring(ET.tostring(child)))
    return node


def _stylesheet_border_tree(border: Any) -> Any:
    node = border.to_tree()
    existing = {localname(child) for child in node}
    for name in ("left", "right", "top", "bottom", "diagonal"):
        if name not in existing:
            node.append(Element(name))
    return node


def _dxfs_tree(values: list[Any]) -> Any | None:
    if not values:
        return None
    node = Element("dxfs")
    node.set("count", str(len(values)))
    return node


def _table_style_list_to_tree(styles_list: TableStyleList | None) -> Any | None:
    if styles_list is None:
        return None
    node = Element("tableStyles")
    node.set("count", str(len(styles_list.tableStyle)))
    if styles_list.defaultTableStyle is not None:
        node.set("defaultTableStyle", styles_list.defaultTableStyle)
    if styles_list.defaultPivotStyle is not None:
        node.set("defaultPivotStyle", styles_list.defaultPivotStyle)
    return node


def _table_style_list_from_tree(node: Any) -> TableStyleList:
    styles_list = TableStyleList(
        defaultTableStyle=node.get("defaultTableStyle"),
        defaultPivotStyle=node.get("defaultPivotStyle"),
    )
    for child in node:
        if localname(child) != "tableStyle":
            continue
        table_style = TableStyle(
            name=child.get("name"),
            pivot=_bool_or_none(child.get("pivot")),
            table=_bool_or_none(child.get("table")),
        )
        for element in child:
            if localname(element) == "tableStyleElement":
                table_style.tableStyleElement.append(
                    TableStyleElement(
                        type=element.get("type"),
                        size=_int_or_none(element.get("size")),
                        dxfId=_int_or_none(element.get("dxfId")),
                    )
                )
        styles_list.append(table_style)
    return styles_list


def _bool_or_none(value: str | None) -> bool | None:
    if value is None:
        return None
    return value not in {"0", "false", "False"}


def _int_or_none(value: str | None) -> int | None:
    return None if value is None else int(value)


def _qualify_tree(node: Any) -> None:
    if not str(node.tag).startswith("{"):
        node.tag = f"{{{SHEET_MAIN_NS}}}{node.tag}"
    for child in node:
        _qualify_tree(child)


def apply_stylesheet(archive: Any, wb: Any) -> Any:
    try:
        src = archive.read(ARC_STYLE)
    except KeyError:
        return wb

    node = fromstring(src)
    stylesheet = Stylesheet.from_tree(node)

    if stylesheet.cell_styles:
        wb._borders = IndexedList(stylesheet.borders)  # noqa: SLF001
        wb._fonts = IndexedList(stylesheet.fonts)  # noqa: SLF001
        wb._fills = IndexedList(stylesheet.fills)  # noqa: SLF001
        if hasattr(wb._differential_styles, "styles"):  # noqa: SLF001
            try:
                wb._differential_styles.styles = stylesheet.dxfs  # noqa: SLF001
            except AttributeError:
                wb._differential_styles = DifferentialStyleList(stylesheet.dxfs)  # noqa: SLF001
        wb._number_formats = stylesheet.number_formats  # noqa: SLF001
        wb._protections = stylesheet.protections  # noqa: SLF001
        wb._alignments = stylesheet.alignments  # noqa: SLF001
        wb._table_styles = stylesheet.tableStyles  # noqa: SLF001
        wb._cell_styles = stylesheet.cell_styles  # noqa: SLF001
        wb._named_styles = stylesheet.named_styles  # noqa: SLF001
        wb._date_formats = stylesheet.date_formats  # noqa: SLF001
        wb._timedelta_formats = stylesheet.timedelta_formats  # noqa: SLF001
        for ns in wb._named_styles:  # noqa: SLF001
            ns.bind(wb)
    else:
        warn("Workbook contains no stylesheet, using openpyxl's defaults", UserWarning)

    if not wb._named_styles:  # noqa: SLF001
        normal = styles["Normal"]
        wb.add_named_style(normal)
        warn("Workbook contains no default style, apply openpyxl's default", UserWarning)

    if stylesheet.colors is not None:
        wb._colors = stylesheet.colors.index  # noqa: SLF001
    return wb


def write_stylesheet(wb: Any) -> Any:
    stylesheet = Stylesheet()
    stylesheet.fonts = getattr(wb, "_fonts", IndexedList())
    stylesheet.fills = getattr(wb, "_fills", IndexedList())
    stylesheet.borders = getattr(wb, "_borders", IndexedList())
    stylesheet.dxfs = getattr(getattr(wb, "_differential_styles", None), "styles", [])
    stylesheet.colors = ColorList(indexedColors=getattr(wb, "_colors", COLOR_INDEX[:64]))

    fmts = []
    for idx, code in enumerate(getattr(wb, "_number_formats", []), BUILTIN_FORMATS_MAX_SIZE):
        fmts.append(NumberFormat(idx, code))
    stylesheet.numFmts.numFmt = fmts

    xfs = []
    for style in getattr(wb, "_cell_styles", IndexedList([StyleArray()])):
        xf = CellStyle.from_array(style)
        if style.alignmentId:
            xf.alignment = wb._alignments[style.alignmentId]  # noqa: SLF001
        if style.protectionId:
            xf.protection = wb._protections[style.protectionId]  # noqa: SLF001
        xfs.append(xf)
    stylesheet.cellXfs = CellStyleList(xf=xfs)
    stylesheet.cellStyleXfs = CellStyleList()
    stylesheet.cellStyles = _NamedCellStyleList()
    stylesheet._split_named_styles(wb)
    stylesheet.tableStyles = getattr(wb, "_table_styles", TableStyleList())
    return stylesheet.to_tree()


ExtensionList = NestedSequence = Serialisable = Typed = _OpenpyxlSerialisable
styles: dict[str, NamedStyle] = {
    "Normal": NamedStyle(
        name="Normal",
        builtinId=0,
        font=Font(name="Calibri", size=11, family=2, color=Color(theme=1), scheme="minor"),
    )
}

_install_openpyxl_iter(NumberFormatList, ColorList, Stylesheet)

__all__ = [
    "ARC_STYLE",
    "BUILTIN_FORMATS",
    "BUILTIN_FORMATS_MAX_SIZE",
    "BUILTIN_FORMATS_REVERSE",
    "Border",
    "CellStyle",
    "CellStyleList",
    "ColorList",
    "DifferentialStyle",
    "DifferentialStyleList",
    "ExtensionList",
    "Fill",
    "Font",
    "IndexedList",
    "NamedStyle",
    "NamedStyleList",
    "NestedSequence",
    "NumberFormatList",
    "SHEET_MAIN_NS",
    "Serialisable",
    "StyleArray",
    "Stylesheet",
    "TableStyleList",
    "Typed",
    "apply_stylesheet",
    "builtin_format_code",
    "fromstring",
    "is_date_format",
    "is_timedelta_format",
    "styles",
    "warn",
    "write_stylesheet",
]
