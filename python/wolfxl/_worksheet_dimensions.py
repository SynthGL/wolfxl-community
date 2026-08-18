"""Worksheet row and column dimension proxy objects."""

from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Any

from wolfxl._utils import column_index, column_letter
from wolfxl.styles.cell_style import StyleArray
from wolfxl.utils import get_column_interval
from wolfxl.xml.functions import Element

if TYPE_CHECKING:
    from wolfxl._worksheet import Worksheet


DEFAULT_COLUMN_WIDTH = 13.0


def _workbook_for(ws: Any) -> Any:
    return getattr(ws, "_workbook", getattr(ws, "parent", None))


def _worksheet_title(ws: Any) -> str:
    return getattr(ws, "_title", getattr(ws, "title", ""))


def _store(ws: Any, name: str, default: Any) -> Any:
    return getattr(ws, name, default)


def _safe_string(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _default_style_value(name: str) -> Any:
    if name == "font":
        from wolfxl import Font

        return Font()
    if name == "fill":
        from wolfxl import PatternFill

        return PatternFill()
    if name == "border":
        from wolfxl import Border

        return Border()
    if name == "alignment":
        from wolfxl import Alignment

        return Alignment()
    if name == "protection":
        from wolfxl.styles import Protection

        return Protection()
    if name == "number_format":
        return "General"
    return None


class _DimensionStyleMixin:
    @property
    def parent(self) -> Any:
        return self._ws  # type: ignore[attr-defined]

    @property
    def has_style(self) -> bool:
        return any(getattr(self, "_style", StyleArray()))

    @property
    def style_id(self) -> int:
        style = getattr(self, "_style", StyleArray())
        if not any(style):
            return 0
        workbook = _workbook_for(self.parent)
        styles = getattr(workbook, "_cell_styles", None)
        if styles is not None and hasattr(styles, "add"):
            return int(styles.add(style))
        return 1

    @property
    def style(self) -> int:
        return self.style_id

    @style.setter
    def style(self, value: Any) -> None:
        if isinstance(value, str):
            raise AttributeError("Style objects are immutable and cannot be changed."
                                 "Reassign the style with a copy")
        self._style = StyleArray(value)

    @property
    def _wb(self) -> Any:
        return _workbook_for(self.parent)

    def _collection_value(self, attr: str, style_attr: str, fallback: str) -> Any:
        collection = getattr(self._wb, attr, None)
        style = getattr(self, "_style", StyleArray())
        index = getattr(style, style_attr, 0)
        try:
            return collection[index]
        except Exception:
            return _default_style_value(fallback)

    def _set_collection_value(self, collection_name: str, style_attr: str, value: Any) -> None:
        collection = getattr(self._wb, collection_name, None)
        if collection is not None and hasattr(collection, "add"):
            index = collection.add(value)
        else:
            index = 1
        style = copy(getattr(self, "_style", StyleArray()))
        setattr(style, style_attr, index)
        self._style = style

    @property
    def number_format(self) -> str:
        return _default_style_value("number_format")

    @number_format.setter
    def number_format(self, value: str) -> None:
        style = copy(getattr(self, "_style", StyleArray()))
        style.numFmtId = 1 if value != "General" else 0
        self._style = style

    @property
    def font(self) -> Any:
        return self._collection_value("_fonts", "fontId", "font")

    @font.setter
    def font(self, value: Any) -> None:
        self._set_collection_value("_fonts", "fontId", value)

    @property
    def fill(self) -> Any:
        return self._collection_value("_fills", "fillId", "fill")

    @fill.setter
    def fill(self, value: Any) -> None:
        self._set_collection_value("_fills", "fillId", value)

    @property
    def border(self) -> Any:
        return self._collection_value("_borders", "borderId", "border")

    @border.setter
    def border(self, value: Any) -> None:
        self._set_collection_value("_borders", "borderId", value)

    @property
    def alignment(self) -> Any:
        return self._collection_value("_alignments", "alignmentId", "alignment")

    @alignment.setter
    def alignment(self, value: Any) -> None:
        self._set_collection_value("_alignments", "alignmentId", value)

    @property
    def protection(self) -> Any:
        return self._collection_value("_protections", "protectionId", "protection")

    @protection.setter
    def protection(self, value: Any) -> None:
        self._set_collection_value("_protections", "protectionId", value)

    @property
    def quotePrefix(self) -> bool:  # noqa: N802
        return False

    @property
    def pivotButton(self) -> bool:  # noqa: N802
        return False


class Dimension(_DimensionStyleMixin):
    """Information about the display properties of a row or column."""

    __slots__ = (
        "_ws",
        "index",
        "hidden",
        "_hidden",
        "outlineLevel",
        "_outlineLevel",
        "collapsed",
        "_collapsed",
        "_style",
    )
    __fields__ = ("hidden", "outlineLevel", "collapsed")

    def __init__(
        self,
        index: Any,
        hidden: bool,
        outlineLevel: int | None,
        collapsed: bool,
        worksheet: Any,
        visible: bool | None = True,
        style: Any = None,
    ) -> None:
        self._ws = worksheet
        self.index = index
        self.hidden = bool(hidden)
        self.outlineLevel = outlineLevel
        self.collapsed = collapsed
        self._style = StyleArray(style)

    @property
    def outline_level(self) -> int | None:
        return self.outlineLevel

    @outline_level.setter
    def outline_level(self, value: int | None) -> None:
        self.outlineLevel = value

    def __iter__(self):
        for key in self.__fields__:
            value = getattr(self, key, None)
            if value:
                yield key, _safe_string(value)

    def __copy__(self):
        cp = self.__class__(
            worksheet=self.parent,
            index=self.index,
            hidden=self.hidden,
            outlineLevel=self.outlineLevel,
            collapsed=self.collapsed,
            style=copy(self._style),
        )
        return cp

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} Instance, Attributes={dict(self)}>"


class RowDimensionProxy:
    """Dict-like proxy for row metadata.

    Examples:
        Set row height using the openpyxl-shaped API:

        >>> ws.row_dimensions[1].height = 30
    """

    __slots__ = ("_ws", "max_outline")

    def __init__(self, ws: Worksheet) -> None:
        self._ws = ws
        self.max_outline = None

    def __getitem__(self, row: int) -> RowDimension:
        self._ws._row_dimensions.add(row)  # noqa: SLF001
        return RowDimension(self._ws, row)

    def __setitem__(self, row: int, value: RowDimension | None) -> None:
        self._ws._row_dimensions.add(int(row))  # noqa: SLF001
        if value is None:
            return
        if not isinstance(value, RowDimension):
            raise TypeError("RowDimensionProxy values must be RowDimension or None")
        dimension = self[int(row)]
        dimension.height = value.height
        dimension.hidden = value.hidden
        dimension.outline_level = value.outline_level
        dimension.collapsed = value.collapsed
        dimension.thickBot = value.thickBot
        dimension.thickTop = value.thickTop

    def get(self, row: int, default: Any = None) -> RowDimension | Any:
        if not isinstance(row, int):
            return default
        dimension = RowDimension(self._ws, row)
        if (
            dimension.height is not None
            or dimension.hidden
            or dimension.outline_level
            or row in self._ws._row_dimensions  # noqa: SLF001
            or row in self._reader_dimensions()
        ):
            return dimension
        return default

    def __iter__(self):  # type: ignore[no-untyped-def]
        keys = (
            set(self._ws._row_heights)  # noqa: SLF001
            | set(self._ws._row_dimensions)  # noqa: SLF001
            | set(self._ws._row_hidden)  # noqa: SLF001
            | set(self._ws._row_outline_levels)  # noqa: SLF001
            | set(self._reader_dimensions())
        )
        return iter(sorted(keys))

    def __len__(self) -> int:
        return len(
            set(self._ws._row_heights)  # noqa: SLF001
            | set(self._ws._row_dimensions)  # noqa: SLF001
            | set(self._ws._row_hidden)  # noqa: SLF001
            | set(self._ws._row_outline_levels)  # noqa: SLF001
            | set(self._reader_dimensions())
        )

    def __contains__(self, row: object) -> bool:
        return isinstance(row, int) and row in (
            set(self._ws._row_heights)  # noqa: SLF001
            | set(self._ws._row_dimensions)  # noqa: SLF001
            | set(self._ws._row_hidden)  # noqa: SLF001
            | set(self._ws._row_outline_levels)  # noqa: SLF001
            | set(self._reader_dimensions())
        )

    def keys(self):  # type: ignore[no-untyped-def]
        return list(iter(self))

    def values(self):  # type: ignore[no-untyped-def]
        return [RowDimension(self._ws, key) for key in self]  # noqa: SLF001

    def items(self):  # type: ignore[no-untyped-def]
        return [(key, RowDimension(self._ws, key)) for key in self]  # noqa: SLF001

    def group(
        self,
        start: int,
        end: int | None = None,
        outline_level: int = 1,
        hidden: bool = False,
    ) -> None:
        if end is None:
            end = start
        for row in range(start, end + 1):
            dimension = self[row]
            dimension.outline_level = outline_level
            dimension.hidden = hidden

    def to_tree(self) -> Any:
        return None

    def _reader_dimensions(self) -> dict[int, Any]:
        wb = self._ws._workbook  # noqa: SLF001
        reader = getattr(wb, "_rust_reader", None)
        if reader is None or not hasattr(reader, "read_row_dimensions"):
            return {}
        try:
            payload = reader.read_row_dimensions(self._ws._title)  # noqa: SLF001
        except Exception:
            return {}
        if isinstance(payload, dict):
            return {int(key): value for key, value in payload.items()}
        return {}


class RowDimension(Dimension):
    """Single row dimension with openpyxl-shaped metadata properties."""

    __slots__ = ("_row", "_ht", "thickBot", "thickTop")
    __fields__ = Dimension.__fields__ + (
        "ht",
        "customFormat",
        "customHeight",
        "s",
        "thickBot",
        "thickTop",
    )

    def __init__(
        self,
        worksheet: Any,
        index: int = 0,
        ht: float | None = None,
        customHeight: bool | None = None,  # noqa: N803, ARG002
        s: Any = None,
        customFormat: bool | None = None,  # noqa: N803, ARG002
        hidden: bool = False,
        outlineLevel: int = 0,  # noqa: N803
        outline_level: int | None = None,
        collapsed: bool = False,
        visible: bool | None = None,
        height: float | None = None,
        r: int | None = None,
        spans: Any = None,  # noqa: ARG002
        thickBot: bool | None = None,  # noqa: N803
        thickTop: bool | None = None,  # noqa: N803
        **kw: Any,  # noqa: ARG002
    ) -> None:
        if r is not None:
            index = r
        if height is not None:
            ht = height
        if outline_level is not None:
            outlineLevel = outline_level
        self._row = int(index)
        self._ht = ht
        self.thickBot = bool(thickBot) if thickBot is not None else False
        self.thickTop = bool(thickTop) if thickTop is not None else False
        if visible is not None:
            hidden = not visible
        self._ws = worksheet
        self._hidden = bool(hidden)
        self._outlineLevel = outlineLevel
        self._collapsed = bool(collapsed)
        self._style = StyleArray(s)

    @property
    def index(self) -> int:
        return self._row

    @index.setter
    def index(self, value: int) -> None:
        self._row = int(value)

    @property
    def r(self) -> int:
        return self._row

    @property
    def height(self) -> float | None:
        row_heights = _store(self._ws, "_row_heights", {})
        if self._row in row_heights:
            return row_heights[self._row]
        if self._ht is not None:
            return self._ht
        payload = self._reader_payload()
        if payload is not None:
            height = payload.get("height")
            return float(height) if height is not None else None
        wb = _workbook_for(self._ws)
        reader = getattr(wb, "_rust_reader", None)
        if reader is not None:
            return reader.read_row_height(_worksheet_title(self._ws), self._row)
        return row_heights.get(self._row)

    def _reader_payload(self) -> dict[str, Any] | None:
        wb = _workbook_for(self._ws)
        reader = getattr(wb, "_rust_reader", None)
        if reader is None or not hasattr(reader, "read_row_dimensions"):
            return None
        try:
            payload = reader.read_row_dimensions(_worksheet_title(self._ws))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        entry = payload.get(self._row)
        return entry if isinstance(entry, dict) else None

    @height.setter
    def height(self, value: float | None) -> None:
        self._ht = value
        if hasattr(self._ws, "_row_heights"):
            self._ws._row_heights[self._row] = value  # noqa: SLF001

    @property
    def ht(self) -> float | None:
        return self.height

    @ht.setter
    def ht(self, value: float | None) -> None:
        self.height = value

    @property
    def customHeight(self) -> bool:  # noqa: N802
        return self.height is not None

    @property
    def hidden(self) -> bool:
        row_hidden = _store(self._ws, "_row_hidden", {})
        if self._row in row_hidden:
            return bool(row_hidden[self._row])
        wb = _workbook_for(self._ws)
        reader = getattr(wb, "_rust_reader", None)
        if reader is not None and hasattr(self._ws, "sheet_visibility"):
            return self._row in self._ws.sheet_visibility()["hidden_rows"]
        return bool(getattr(self, "_hidden", False))

    @hidden.setter
    def hidden(self, value: bool) -> None:
        self._hidden = bool(value)
        if hasattr(self._ws, "_row_hidden"):
            self._ws._row_hidden[self._row] = bool(value)  # noqa: SLF001

    @property
    def collapsed(self) -> bool:
        return bool(getattr(self, "_collapsed", False))

    @collapsed.setter
    def collapsed(self, value: bool) -> None:
        self._collapsed = bool(value)

    @property
    def s(self) -> int:
        return self.style_id

    @property
    def customFormat(self) -> bool:  # noqa: N802
        return self.has_style

    @property
    def outlineLevel(self) -> int:  # noqa: N802 - openpyxl public API
        return self.outline_level

    @outlineLevel.setter
    def outlineLevel(self, value: int) -> None:  # noqa: N802
        self.outline_level = value

    @property
    def outline_level(self) -> int:
        row_outline_levels = _store(self._ws, "_row_outline_levels", {})
        if self._row in row_outline_levels:
            return int(row_outline_levels[self._row])
        wb = _workbook_for(self._ws)
        reader = getattr(wb, "_rust_reader", None)
        if reader is not None and hasattr(self._ws, "sheet_visibility"):
            return int(self._ws.sheet_visibility()["row_outline_levels"].get(self._row, 0))
        return int(getattr(self, "_outlineLevel", 0) or 0)

    @outline_level.setter
    def outline_level(self, value: int) -> None:
        self._outlineLevel = int(value)
        if hasattr(self._ws, "_row_outline_levels"):
            self._ws._row_outline_levels[self._row] = int(value)  # noqa: SLF001

    def __copy__(self):
        return self.__class__(
            worksheet=self.parent,
            index=self.index,
            ht=self.ht,
            s=copy(self._style),
            hidden=self.hidden,
            outlineLevel=self.outlineLevel or 0,
            collapsed=self.collapsed,
            thickBot=self.thickBot,
            thickTop=self.thickTop,
        )


class ColumnDimensionProxy:
    """Dict-like proxy for column metadata.

    Examples:
        Set column width using the openpyxl-shaped API:

        >>> ws.column_dimensions["A"].width = 15
    """

    __slots__ = ("_ws", "max_outline")

    def __init__(self, ws: Worksheet) -> None:
        self._ws = ws
        self.max_outline = None

    def __getitem__(self, col_letter: str) -> ColumnDimension:
        key = col_letter.upper()
        self._ws._col_dimensions.add(key)  # noqa: SLF001
        cache = self._ws._column_dimension_cache  # noqa: SLF001
        if key not in cache:
            dimension = ColumnDimension(self._ws, key)
            payload = dimension._reader_payload()
            if payload is not None:
                dimension.min = payload.get("min")
                dimension.max = payload.get("max")
            cache[key] = dimension
        return cache[key]

    def get(self, col_letter: str, default: Any = None) -> ColumnDimension | Any:
        if not isinstance(col_letter, str):
            return default
        key = col_letter.upper()
        cache = self._ws._column_dimension_cache  # noqa: SLF001
        dimension = cache.get(key) or ColumnDimension(self._ws, key)
        if (
            dimension._explicit_width() is not None
            or dimension.hidden
            or dimension.outline_level
            or key in self._ws._col_dimensions  # noqa: SLF001
            or key in self._reader_dimensions()
        ):
            return dimension
        return default

    def __iter__(self):  # type: ignore[no-untyped-def]
        keys = set(self._ws._col_dimensions) | set(self._reader_dimensions())  # noqa: SLF001
        return iter(sorted(keys))

    def __len__(self) -> int:
        return len(set(self._ws._col_dimensions) | set(self._reader_dimensions()))  # noqa: SLF001

    def __contains__(self, col_letter: object) -> bool:
        return (
            isinstance(col_letter, str)
            and col_letter.upper() in set(self._ws._col_dimensions) | set(self._reader_dimensions())  # noqa: SLF001
        )

    def keys(self):  # type: ignore[no-untyped-def]
        return list(iter(self))

    def values(self):  # type: ignore[no-untyped-def]
        return [self[key] for key in self]

    def items(self):  # type: ignore[no-untyped-def]
        return [(key, self[key]) for key in self]

    def group(
        self,
        start: str,
        end: str | None = None,
        outline_level: int = 1,
        hidden: bool = False,
    ) -> None:
        if end is None:
            end = start
        start_key = start.upper()
        end_key = end.upper()
        dimension = self[start_key]
        dimension.outline_level = outline_level
        dimension.hidden = hidden
        dimension.min = column_index(start_key)
        dimension.max = column_index(end_key)
        for col_letter in get_column_interval(start_key, end_key)[1:]:
            key = col_letter.upper()
            if hasattr(self._ws, "_col_dimensions"):
                self._ws._col_dimensions.discard(key)  # noqa: SLF001
            if hasattr(self._ws, "_column_dimension_cache"):
                self._ws._column_dimension_cache.pop(key, None)  # noqa: SLF001
            if hasattr(self._ws, "_col_widths"):
                self._ws._col_widths.pop(key, None)  # noqa: SLF001
            if hasattr(self._ws, "_col_hidden"):
                self._ws._col_hidden.pop(key, None)  # noqa: SLF001
            if hasattr(self._ws, "_col_outline_levels"):
                self._ws._col_outline_levels.pop(key, None)  # noqa: SLF001

    def to_tree(self) -> Any:
        node = Element("cols")
        outlines = set()
        dimensions = list(self.values())
        for dimension in sorted(dimensions, key=lambda value: value.min or column_index(value.index)):
            dimension.reindex()
            child = dimension.to_tree()
            if child is not None:
                outlines.add(dimension.outlineLevel)
                node.append(child)
        if outlines:
            self.max_outline = max(outlines)  # type: ignore[attr-defined]
        if len(node):
            return node
        return None

    def _reader_dimensions(self) -> dict[str, Any]:
        wb = self._ws._workbook  # noqa: SLF001
        reader = getattr(wb, "_rust_reader", None)
        if reader is None or not hasattr(reader, "read_column_dimensions"):
            return {}
        try:
            payload = reader.read_column_dimensions(self._ws._title)  # noqa: SLF001
        except Exception:
            return {}
        if isinstance(payload, dict):
            return {str(key).upper(): value for key, value in payload.items()}
        return {}


class ColumnDimension(Dimension):
    """Single column dimension with openpyxl-shaped metadata properties."""

    __slots__ = ("_col_letter", "_width", "bestFit", "min", "max")
    __fields__ = Dimension.__fields__ + (
        "width",
        "bestFit",
        "customWidth",
        "style",
        "min",
        "max",
    )

    def __init__(
        self,
        worksheet: Any,
        index: str = "A",
        width: float | None = DEFAULT_COLUMN_WIDTH,
        bestFit: bool = False,  # noqa: N803
        hidden: bool = False,
        outlineLevel: int = 0,  # noqa: N803
        outline_level: int | None = None,
        collapsed: bool = False,
        style: Any = None,
        min: int | None = None,  # noqa: A002
        max: int | None = None,  # noqa: A002
        customWidth: bool = False,  # noqa: N803, ARG002
        visible: bool | None = None,
        auto_size: bool | None = None,
    ) -> None:
        if auto_size is not None:
            bestFit = auto_size
        if outline_level is not None:
            outlineLevel = outline_level
        self._col_letter = str(index).upper()
        self._width = width
        self.bestFit = bool(bestFit)
        self.min = min
        self.max = max
        if visible is not None:
            hidden = not visible
        self._ws = worksheet
        self._hidden = bool(hidden)
        self._outlineLevel = outlineLevel
        self._collapsed = bool(collapsed)
        self._style = StyleArray(style)

    @property
    def index(self) -> str:
        return self._col_letter

    @index.setter
    def index(self, value: str) -> None:
        self._col_letter = str(value).upper()

    @property
    def width(self) -> Any:
        dict_width = getattr(self, "__dict__", {}).get("width")
        if dict_width is not None:
            return dict_width
        explicit = self._explicit_width()
        if explicit is not None:
            return explicit
        if self._width is not None:
            return self._width
        if self._col_letter in _store(self._ws, "_col_dimensions", set()):
            return float(DEFAULT_COLUMN_WIDTH)
        return None

    def _explicit_width(self) -> float | None:
        payload = self._reader_payload()
        if payload is not None:
            width = payload.get("width")
            return float(width) if width is not None else None
        wb = _workbook_for(self._ws)
        reader = getattr(wb, "_rust_reader", None)
        if reader is not None:
            return reader.read_column_width(_worksheet_title(self._ws), self._col_letter)
        return _store(self._ws, "_col_widths", {}).get(self._col_letter)

    def _reader_payload(self) -> dict[str, Any] | None:
        wb = _workbook_for(self._ws)
        reader = getattr(wb, "_rust_reader", None)
        if reader is None or not hasattr(reader, "read_column_dimensions"):
            return None
        try:
            payload = reader.read_column_dimensions(_worksheet_title(self._ws))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        entry = payload.get(self._col_letter)
        return entry if isinstance(entry, dict) else None

    @width.setter
    def width(self, value: float | None) -> None:
        self._width = value
        if hasattr(self._ws, "_col_widths"):
            self._ws._col_widths[self._col_letter] = value  # noqa: SLF001
        if hasattr(self._ws, "_col_dimensions"):
            self._ws._col_dimensions.add(self._col_letter)  # noqa: SLF001

    @property
    def customWidth(self) -> bool:  # noqa: N802
        return bool(self.width)

    @property
    def auto_size(self) -> bool:
        return self.bestFit

    @auto_size.setter
    def auto_size(self, value: bool) -> None:
        self.bestFit = value

    @property
    def hidden(self) -> bool:
        col_hidden = _store(self._ws, "_col_hidden", {})
        if self._col_letter in col_hidden:
            return bool(col_hidden[self._col_letter])
        wb = _workbook_for(self._ws)
        reader = getattr(wb, "_rust_reader", None)
        if reader is not None and hasattr(self._ws, "sheet_visibility"):
            payload = self._reader_payload()
            if payload is not None and "hidden" in payload:
                return bool(payload["hidden"])
            return column_index(self._col_letter) in self._ws.sheet_visibility()["hidden_columns"]
        return bool(getattr(self, "_hidden", False))

    @hidden.setter
    def hidden(self, value: bool) -> None:
        self._hidden = bool(value)
        if hasattr(self._ws, "_col_hidden"):
            self._ws._col_hidden[self._col_letter] = bool(value)  # noqa: SLF001
        if hasattr(self._ws, "_col_dimensions"):
            self._ws._col_dimensions.add(self._col_letter)  # noqa: SLF001

    @property
    def collapsed(self) -> bool:
        return bool(getattr(self, "_collapsed", False))

    @collapsed.setter
    def collapsed(self, value: bool) -> None:
        self._collapsed = bool(value)

    @property
    def range(self) -> str:
        min_col = self.min or column_index(self._col_letter)
        max_col = self.max or column_index(self._col_letter)
        return f"{column_letter(min_col)}:{column_letter(max_col)}"

    def reindex(self) -> None:
        if not all([self.min, self.max]):
            self.min = self.max = column_index(self._col_letter)

    def to_tree(self) -> Any:
        attrs = dict(self)
        if attrs.keys() != {"min", "max"}:
            return Element("col", attrs)
        return None

    @property
    def outlineLevel(self) -> int:  # noqa: N802 - openpyxl public API
        return self.outline_level

    @outlineLevel.setter
    def outlineLevel(self, value: int) -> None:  # noqa: N802
        self.outline_level = value

    @property
    def outline_level(self) -> int:
        col_outline_levels = _store(self._ws, "_col_outline_levels", {})
        if self._col_letter in col_outline_levels:
            return int(col_outline_levels[self._col_letter])
        wb = _workbook_for(self._ws)
        reader = getattr(wb, "_rust_reader", None)
        if reader is not None and hasattr(self._ws, "sheet_visibility"):
            payload = self._reader_payload()
            if payload is not None and "outline_level" in payload:
                return int(payload["outline_level"])
            col = column_index(self._col_letter)
            return int(self._ws.sheet_visibility()["column_outline_levels"].get(col, 0))
        return int(getattr(self, "_outlineLevel", 0) or 0)

    @outline_level.setter
    def outline_level(self, value: int) -> None:
        self._outlineLevel = int(value)
        if hasattr(self._ws, "_col_outline_levels"):
            self._ws._col_outline_levels[self._col_letter] = int(value)  # noqa: SLF001
        if hasattr(self._ws, "_col_dimensions"):
            self._ws._col_dimensions.add(self._col_letter)  # noqa: SLF001

    def __copy__(self):
        return self.__class__(
            worksheet=self.parent,
            index=self.index,
            width=self._width,
            bestFit=self.bestFit,
            hidden=self.hidden,
            outlineLevel=self.outlineLevel or 0,
            collapsed=self.collapsed,
            style=copy(self._style),
            min=self.min,
            max=self.max,
        )
