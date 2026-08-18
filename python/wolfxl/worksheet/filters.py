"""AutoFilter + filter-class implementations (RFC-056 Sprint Ο Pod 1B).

Replaces the Sprint Ζ stub with the full openpyxl-shaped surface. The
class names + field names match openpyxl's
``openpyxl.worksheet.filters`` so ``from openpyxl.worksheet.filters
import …`` swaps to ``from wolfxl.worksheet.filters import …``
mechanically (Pod 2 wires the re-export shim — this module is the
implementation site).

The 11 filter classes here are PyO3-free dataclasses; they marshal
into the §10 dict shape via :class:`AutoFilter.to_rust_dict` and the
Rust crate ``wolfxl-autofilter`` does both XML emit and filter
evaluation. See ``Plans/rfcs/056-autofilter-eval.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect as _inspect
import re
from typing import Any, Literal, Optional, Union
from xml.etree import ElementTree as ET

from wolfxl._compat import _openpyxl_name_fallback


class _TreeMixin:
    tagname = ""
    namespace = None
    idx_base = 0
    __attrs__: tuple[str, ...] = ()
    __elements__: tuple[str, ...] = ()

    def __iter__(self):
        for name in self.__attrs__:
            attr_name = "and_" if name == "_and" else name
            if not hasattr(self, attr_name):
                continue
            value = getattr(self, attr_name)
            if value is None or isinstance(value, (list, tuple, dict)):
                continue
            if isinstance(value, bool):
                value = "1" if value else "0"
            else:
                value = str(value)
            yield ("and" if name == "_and" else name), value

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        """Serialize this filter helper to an ElementTree node.

        Routes through ``wolfxl.xml.functions.Element`` so the produced
        node is an lxml ``_Element`` when lxml is the active backend.
        Mixing stdlib ``xml.etree`` nodes with lxml's ``tostring`` raises
        ``Type 'Element' cannot be serialized``; corpus tests import
        ``tostring`` from the openpyxl shim, which resolves to lxml.
        """
        from wolfxl.xml.functions import Element as _Element

        node = _Element(tagname or self.tagname)
        for key, value in self:
            node.set(key, value)
        for child in _iter_child_elements(self):
            node.append(child)
        return node

    @classmethod
    def from_tree(cls, node: ET.Element):  # type: ignore[no-untyped-def]
        """Build this filter helper from a compact ElementTree node."""
        kwargs: dict[str, Any] = dict(node.attrib)
        if "and" in kwargs:
            kwargs["_and"] = kwargs.pop("and")
        for child in list(node):
            name = child.tag.rsplit("}", 1)[-1]
            if cls is Filters:
                if name == "filter":
                    kwargs.setdefault("filter", []).append(child.get("val"))
                elif name == "dateGroupItem":
                    kwargs.setdefault("dateGroupItem", []).append(
                        DateGroupItem.from_tree(child)
                    )
            elif cls is CustomFilters and name == "customFilter":
                kwargs.setdefault("customFilter", []).append(
                    CustomFilter.from_tree(child)
                )
            elif cls is FilterColumn and name in _FILTER_COLUMN_CHILDREN:
                kwargs[name] = _FILTER_COLUMN_CHILDREN[name].from_tree(child)
            elif cls is SortState and name == "sortCondition":
                kwargs.setdefault("sortCondition", []).append(
                    SortCondition.from_tree(child)
                )
            elif cls is AutoFilter:
                if name == "filterColumn":
                    kwargs.setdefault("filterColumn", []).append(
                        FilterColumn.from_tree(child)
                    )
                elif name == "sortState":
                    kwargs["sortState"] = SortState.from_tree(child)
        return cls(**kwargs)


def _bool_or_none(value: Any) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value in {"1", "true", "True"}
    return bool(value)


def _int_or_none(value: Any) -> int | None:
    return None if value is None else int(value)


def _float_or_none(value: Any) -> float | None:
    return None if value is None else float(value)


def _number_or_none(value: Any) -> int | float | None:
    if value is None:
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


def _camel_to_snake(name: str) -> str:
    """Convert ``filterColumn`` -> ``filter_column`` for attribute lookup."""
    out: list[str] = []
    for ch in name:
        if ch.isupper() and out:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _resolve_child_attr(obj: Any, name: str) -> Any:
    """Find the attribute storing the child(ren) named ``name``.

    openpyxl's ``__elements__`` names directly match attribute names
    (``filterColumn`` -> ``self.filterColumn``). wolfxl collapses
    naming variants — snake_case (``self.filter_column``) and plural
    list collections (``self.filter_columns``). When none of those
    match, fall back to ``self.filter`` for FilterColumn-style
    discriminated unions where a single field carries the active
    child whose own ``tagname`` matches ``name``.
    """
    sentinel = object()
    for candidate in (name, _camel_to_snake(name), _camel_to_snake(name) + "s"):
        value = getattr(obj, candidate, sentinel)
        if value is not sentinel and value is not None:
            return value
    held = getattr(obj, "filter", None)
    if held is not None and getattr(held, "tagname", None) == name:
        return held
    return None


def _iter_child_elements(obj: Any):
    from wolfxl.xml.functions import Element as _Element

    for name in getattr(obj, "__elements__", ()):
        value = _resolve_child_attr(obj, name)
        if value is None:
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            if item is None:
                continue
            if name == "filter" and isinstance(item, (str, int, float)):
                child = _Element("filter")
                child.set("val", str(item))
            elif hasattr(item, "to_tree"):
                child = item.to_tree()
            else:
                child = _Element(name)
                child.set("val", str(item))
            node_name = child.tag.rsplit("}", 1)[-1]
            if node_name != name and name not in {
                "filterColumn",
                "sortCondition",
                "dateGroupItem",
                "customFilter",
            }:
                child.tag = name
            yield child


# ---------------------------------------------------------------------------
# Filter primitives — mirror RFC-056 §2.1 + openpyxl ``filters.py``.
# ---------------------------------------------------------------------------


@dataclass
class BlankFilter(_TreeMixin):
    """Pass iff the cell is blank.

    openpyxl emits this as ``<filters blank="1"/>``. Wolfxl emits the
    same shape (RFC-056 §3.1).
    """

    operator: str = "notEqual"
    val: str = " "
    tagname = "customFilter"
    __attrs__ = ("operator", "val")

    def __init__(self, **kw: Any) -> None:  # noqa: ARG002
        pass

    def convert(self) -> BlankFilter:
        """Openpyxl compatibility hook; blank filters keep their sentinel value."""
        return self


@dataclass
class ColorFilter(_TreeMixin):
    """Pass iff the cell's ``dxfId`` matches.

    ``cell_color = True`` (default) → match against the cell fill.
    ``cell_color = False`` → match against the font colour. Wolfxl's
    evaluator currently accepts every row for ``ColorFilter`` (defers
    to Excel on open) — KNOWN_GAPS entry. The XML round-trips
    losslessly.
    """

    dxf_id: int | None = None
    cell_color: bool | None = None
    tagname = "colorFilter"
    __attrs__ = ("dxfId", "cellColor")

    def __init__(
        self,
        dxf_id: int | None = None,
        cell_color: bool | None = None,
        **kwargs: Any,
    ) -> None:
        raw_dxf = kwargs.pop("dxfId", dxf_id)
        self.dxf_id = _int_or_none(raw_dxf)
        self.cell_color = _bool_or_none(kwargs.pop("cellColor", cell_color))

    @property
    def dxfId(self) -> int | None:  # noqa: N802
        return self.dxf_id

    @dxfId.setter
    def dxfId(self, value: int | None) -> None:  # noqa: N802
        self.dxf_id = _int_or_none(value)

    @property
    def cellColor(self) -> bool | None:  # noqa: N802
        return self.cell_color

    @cellColor.setter
    def cellColor(self, value: bool | None) -> None:  # noqa: N802
        self.cell_color = _bool_or_none(value)


@dataclass
class CustomFilter(_TreeMixin):
    """One ``<customFilter operator val>`` row.

    ``operator`` ∈ {"equal", "lessThan", "lessThanOrEqual",
    "notEqual", "greaterThanOrEqual", "greaterThan"}.
    """

    operator: Literal[
        "equal",
        "lessThan",
        "lessThanOrEqual",
        "notEqual",
        "greaterThanOrEqual",
        "greaterThan",
    ] = "equal"
    val: str = ""
    tagname = "customFilter"
    __attrs__ = ("val", "operator")

    def convert(self) -> BlankFilter | NumberFilter | StringFilter:
        """Openpyxl compatibility hook for descriptor coercion."""
        if self.val == " ":
            return BlankFilter()
        try:
            float(self.val)
        except ValueError:
            operator, term = StringFilter._guess_operator(self.val)
            flt = StringFilter(operator, term)
            if self.operator == "notEqual":
                flt.exclude = True
            return flt
        return NumberFilter(self.operator, self.val)


@dataclass
class CustomFilters(_TreeMixin):
    """Group of ``CustomFilter`` joined by AND or OR.

    ``and_ = False`` (default) → logical OR.
    ``and_ = True`` → logical AND.
    """

    customFilter: list[CustomFilter] = field(default_factory=list)  # noqa: N815 — openpyxl name
    and_: bool | None = None
    tagname = "customFilters"
    __attrs__ = ("_and",)
    __elements__ = ("customFilter",)

    def __init__(
        self,
        customFilter: list[CustomFilter] | tuple[CustomFilter, ...] | None = None,  # noqa: N803
        and_: bool | None = None,
        _and: bool | None = None,
    ) -> None:
        self.customFilter = list(customFilter or [])
        self.and_ = _bool_or_none(and_ if _and is None else _and)

    @property
    def filters(self) -> list[CustomFilter]:
        """Alias for ``customFilter`` (the snake_case is more readable)."""
        return self.customFilter

    @filters.setter
    def filters(self, value: list[CustomFilter]) -> None:
        self.customFilter = value


@dataclass
class DateGroupItem(_TreeMixin):
    """Date-component matcher inside a ``<filters>`` group.

    Components below ``date_time_grouping`` are typically ``None``.
    """

    year: int = 0
    month: Optional[int] = None
    day: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    second: Optional[int] = None
    date_time_grouping: Literal[
        "year", "month", "day", "hour", "minute", "second"
    ] = "year"
    tagname = "dateGroupItem"
    __attrs__ = (
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
        "dateTimeGrouping",
    )

    def __init__(
        self,
        year: int = 0,
        month: Optional[int] = None,
        day: Optional[int] = None,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        second: Optional[int] = None,
        date_time_grouping: Literal["year", "month", "day", "hour", "minute", "second"] = "year",
        dateTimeGrouping: Literal["year", "month", "day", "hour", "minute", "second"] | None = None,  # noqa: N803
    ) -> None:
        self.year = int(year) if year is not None else 0
        self.month = _int_or_none(month)
        self.day = _int_or_none(day)
        self.hour = _int_or_none(hour)
        self.minute = _int_or_none(minute)
        self.second = _int_or_none(second)
        self.date_time_grouping = date_time_grouping if dateTimeGrouping is None else dateTimeGrouping

    @property
    def dateTimeGrouping(self) -> str:  # noqa: N802
        return self.date_time_grouping

    @dateTimeGrouping.setter
    def dateTimeGrouping(self, value: str) -> None:  # noqa: N802
        self.date_time_grouping = value  # type: ignore[assignment]


@dataclass
class DynamicFilter(_TreeMixin):
    """Date- or aggregate-driven dynamic filter.

    Type values (subset shown) include
    ``"today"``, ``"yesterday"``, ``"thisWeek"``, ``"Q1".."Q4"``,
    ``"M1".."M12"``, ``"aboveAverage"``, ``"belowAverage"``,
    ``"yearToDate"``. Full list in RFC-056 §2.1.
    """

    type: str = "null"
    val: Optional[float] = None
    max_val: Optional[float] = None
    val_iso: Optional[str] = None
    max_val_iso: Optional[str] = None
    tagname = "dynamicFilter"
    __attrs__ = ("type", "val", "valIso", "maxVal", "maxValIso")

    def __init__(
        self,
        type: str = "null",  # noqa: A002 - openpyxl public API
        val: Optional[float] = None,
        val_iso: Optional[str] = None,
        max_val: Optional[float] = None,
        max_val_iso: Optional[str] = None,
        valIso: Optional[str] = None,  # noqa: N803
        maxVal: Optional[float] = None,  # noqa: N803
        maxValIso: Optional[str] = None,  # noqa: N803
    ) -> None:
        self.type = type
        self.val = val
        self.max_val = max_val if maxVal is None else maxVal
        self.val_iso = val_iso if valIso is None else valIso
        self.max_val_iso = max_val_iso if maxValIso is None else maxValIso

    @property
    def valIso(self) -> Optional[str]:  # noqa: N802
        return self.val_iso

    @valIso.setter
    def valIso(self, value: Optional[str]) -> None:  # noqa: N802
        self.val_iso = value

    @property
    def maxVal(self) -> Optional[float]:  # noqa: N802
        return self.max_val

    @maxVal.setter
    def maxVal(self, value: Optional[float]) -> None:  # noqa: N802
        self.max_val = value

    @property
    def maxValIso(self) -> Optional[str]:  # noqa: N802
        return self.max_val_iso

    @maxValIso.setter
    def maxValIso(self, value: Optional[str]) -> None:  # noqa: N802
        self.max_val_iso = value


@dataclass
class IconFilter(_TreeMixin):
    """Filter on conditional-format icon set + index.

    ``icon_set`` is the named CF icon set (e.g. ``"3Arrows"``,
    ``"5Quarters"``); ``icon_id`` is the 0-based index into it.
    Like ``ColorFilter``, evaluation is best-effort and defers to
    Excel.
    """

    icon_set: str = "3Arrows"
    icon_id: int | None = None
    tagname = "iconFilter"
    __attrs__ = ("iconSet", "iconId")

    def __init__(
        self,
        icon_set: str | None = None,
        icon_id: int | None = None,
        iconSet: str | None = None,  # noqa: N803
        iconId: int | None = None,  # noqa: N803
    ) -> None:
        self.icon_set = icon_set if iconSet is None else iconSet
        resolved_icon_id = icon_id if iconId is None else iconId
        self.icon_id = _int_or_none(resolved_icon_id)

    @property
    def iconSet(self) -> str:  # noqa: N802
        return self.icon_set

    @iconSet.setter
    def iconSet(self, value: str) -> None:  # noqa: N802
        self.icon_set = value

    @property
    def iconId(self) -> int | None:  # noqa: N802
        return self.icon_id

    @iconId.setter
    def iconId(self, value: int | None) -> None:  # noqa: N802
        self.icon_id = _int_or_none(value)


@dataclass
class NumberFilter(CustomFilter):
    """Numeric custom filter with openpyxl's ``<customFilter>`` XML shape."""

    operator: str = "equal"
    val: int | float | None = None
    filters: list[int | float] = field(default_factory=list)
    blank: bool = False
    tagname = "customFilter"
    __attrs__ = ("operator", "val")

    def __init__(
        self,
        operator: str = "equal",
        val: Any = None,
        *,
        filters: list[int | float] | tuple[int | float, ...] | None = None,
        blank: bool = False,
    ) -> None:
        self.operator = operator
        self.filters = [_number_or_none(value) for value in (filters or [])]
        self.blank = bool(blank)
        self.val = _number_or_none(val)
        if self.val is None and self.filters:
            self.val = self.filters[0]


_STRING_FORMAT_MAPPING = {
    "contains": "*{}*",
    "startswith": "{}*",
    "endswith": "*{}",
    "wildcard": "{}",
}


@dataclass
class StringFilter(CustomFilter):
    """String custom filter with wildcard escaping helpers."""

    operator: str = "contains"
    val: str | None = None
    values: list[str] = field(default_factory=list)
    exclude: bool = False
    tagname = "customFilter"
    __attrs__ = ("operator", "val", "exclude")

    def __init__(
        self,
        operator: str = "contains",
        val: Any = None,
        exclude: bool = False,
        *,
        values: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self.operator = operator
        self.values = [str(value) for value in (values or [])]
        self.val = None if val is None else str(val)
        if self.val is None and self.values:
            self.val = self.values[0]
        self.exclude = bool(exclude)

    def _escape(self) -> str:
        """Escape wildcards when serialising non-wildcard string filters."""
        if self.operator == "wildcard":
            return self.val or ""
        return re.sub(r"~|\*|\?", r"~\g<0>", self.val or "")

    @staticmethod
    def _unescape(value: str) -> str:
        return re.sub(r"~(?P<op>[~*?])", r"\g<op>", value)

    @staticmethod
    def _guess_operator(value: str) -> tuple[str, str]:
        value = StringFilter._unescape(value)
        patterns = [
            ("contains", r"^\*(?P<term>[^\*\?]*)\*$"),
            ("startswith", r"^(?P<term>[^\*\?]*)\*$"),
            ("endswith", r"^\*(?P<term>[^\*\?]*$)"),
        ]
        for operator, pattern in patterns:
            match = re.match(pattern, value)
            if match:
                return operator, match.group("term")
        return "wildcard", value

    def __iter__(self):
        yield "operator", self.operator
        yield "val", self.val
        yield "exclude", "1" if self.exclude else "0"

    def to_tree(
        self,
        tagname: str | None = None,  # noqa: ARG002 - openpyxl signature
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        op = "notEqual" if self.exclude else "equal"
        fmt = _STRING_FORMAT_MAPPING[self.operator]
        return CustomFilter(op, fmt.format(self._escape())).to_tree()


@dataclass
class Filters(_TreeMixin):
    """Openpyxl-shaped inner ``<filters>`` element."""

    blank: bool | None = None
    calendarType: str | None = None  # noqa: N815
    filter: list[str] = field(default_factory=list)
    dateGroupItem: list[DateGroupItem] = field(default_factory=list)  # noqa: N815
    tagname = "filters"
    __attrs__ = ("blank", "calendarType")
    __elements__ = ("filter", "dateGroupItem")

    def __init__(
        self,
        blank: bool | None = None,
        calendarType: str | None = None,  # noqa: N803
        filter: list[str] | tuple[str, ...] | None = None,  # noqa: A002
        dateGroupItem: list[DateGroupItem] | tuple[DateGroupItem, ...] | None = None,  # noqa: N803
    ) -> None:
        self.blank = _bool_or_none(blank)
        self.calendarType = calendarType
        self.filter = [str(value) for value in (filter or [])]
        self.dateGroupItem = list(dateGroupItem or [])

    @property
    def filters(self) -> list[str]:
        return self.filter

    @filters.setter
    def filters(self, value: list[str]) -> None:
        self.filter = value


@dataclass
class Top10(_TreeMixin):
    """Top-N or bottom-N filter, optionally as percent.

    ``top = True`` → top N. ``top = False`` → bottom N.
    ``percent = True`` → N is a percentage of the column.
    ``filter_val`` is set by Excel after evaluation; readers may
    inspect it but writers should leave it ``None`` (the patcher
    does not back-fill it).
    """

    top: bool | None = None
    percent: bool | None = None
    val: int | float | None = None
    filter_val: Optional[int | float] = None
    tagname = "top10"
    __attrs__ = ("top", "percent", "val", "filterVal")

    def __init__(
        self,
        top: bool | None = None,
        percent: bool | None = None,
        val: float | None = None,
        filter_val: Optional[float] = None,
        filterVal: Optional[float] = None,  # noqa: N803
    ) -> None:
        self.top = _bool_or_none(top)
        self.percent = _bool_or_none(percent)
        self.val = _number_or_none(val)
        self.filter_val = _number_or_none(filter_val if filterVal is None else filterVal)

    @property
    def filterVal(self) -> Optional[int | float]:  # noqa: N802
        return self.filter_val

    @filterVal.setter
    def filterVal(self, value: Optional[float]) -> None:  # noqa: N802
        self.filter_val = _number_or_none(value)


# ---------------------------------------------------------------------------
# FilterColumn + Sort
# ---------------------------------------------------------------------------


# Public discriminated union of every filter kind a FilterColumn carries.
FilterT = Union[
    BlankFilter,
    ColorFilter,
    CustomFilters,
    DynamicFilter,
    IconFilter,
    NumberFilter,
    StringFilter,
    Filters,
    Top10,
]

_FILTER_COLUMN_CHILDREN = {
    "filters": Filters,
    "top10": Top10,
    "customFilters": CustomFilters,
    "dynamicFilter": DynamicFilter,
    "colorFilter": ColorFilter,
    "iconFilter": IconFilter,
}


@dataclass
class FilterColumn(_TreeMixin):
    """One ``<filterColumn colId>`` entry inside ``<autoFilter>``.

    ``col_id`` is **0-based** relative to ``auto_filter.ref``'s left
    edge — Excel's convention for this attribute (every other column
    index in OOXML is 1-based).
    """

    col_id: int = 0
    hidden_button: bool = False
    show_button: bool = True
    filter: Optional[FilterT] = None
    date_group_items: list[DateGroupItem] = field(default_factory=list)
    extLst: Any = None  # noqa: N815
    tagname = "filterColumn"
    __attrs__ = ("colId", "hiddenButton", "showButton")
    __elements__ = (
        "filters",
        "top10",
        "customFilters",
        "dynamicFilter",
        "colorFilter",
        "iconFilter",
    )

    def __init__(
        self,
        col_id: int = 0,
        hidden_button: bool = False,
        show_button: bool = True,
        filter: Optional[FilterT] = None,  # noqa: A002
        date_group_items: Optional[list[DateGroupItem]] = None,
        colId: int | None = None,  # noqa: N803
        hiddenButton: bool | None = None,  # noqa: N803
        showButton: bool | None = None,  # noqa: N803
        filters: Filters | NumberFilter | StringFilter | None = None,
        top10: Top10 | None = None,
        customFilters: CustomFilters | None = None,  # noqa: N803
        dynamicFilter: DynamicFilter | None = None,  # noqa: N803
        colorFilter: ColorFilter | None = None,  # noqa: N803
        iconFilter: IconFilter | None = None,  # noqa: N803
        blank: bool | None = None,
        vals: list[str] | tuple[str, ...] | None = None,
        extLst: Any = None,  # noqa: N803
    ) -> None:
        self.col_id = int(col_id if colId is None else colId)
        self.hidden_button = _bool_or_none(
            hidden_button if hiddenButton is None else hiddenButton
        )
        self.show_button = _bool_or_none(
            show_button if showButton is None else showButton
        )
        self.date_group_items = list(date_group_items or [])
        openpyxl_filter: Optional[FilterT] = (
            filters
            or top10
            or customFilters
            or dynamicFilter
            or colorFilter
            or iconFilter
        )
        if vals is not None:
            openpyxl_filter = Filters(blank=blank, filter=list(vals))
        elif blank is not None and openpyxl_filter is None:
            openpyxl_filter = Filters(blank=blank)
        self.filter = filter if filter is not None else openpyxl_filter
        self.extLst = extLst

    @property
    def colId(self) -> int:  # noqa: N802
        return self.col_id

    @colId.setter
    def colId(self, value: int) -> None:  # noqa: N802
        self.col_id = int(value)

    @property
    def hiddenButton(self) -> bool:  # noqa: N802
        return self.hidden_button

    @hiddenButton.setter
    def hiddenButton(self, value: bool) -> None:  # noqa: N802
        self.hidden_button = _bool_or_none(value)

    @property
    def showButton(self) -> bool:  # noqa: N802
        return self.show_button

    @showButton.setter
    def showButton(self, value: bool) -> None:  # noqa: N802
        self.show_button = _bool_or_none(value)

    @property
    def filters(self) -> Optional[Filters | NumberFilter | StringFilter]:
        return self.filter if isinstance(self.filter, (Filters, NumberFilter, StringFilter)) else None

    @filters.setter
    def filters(self, value: Filters | NumberFilter | StringFilter | None) -> None:
        self.filter = value

    @property
    def vals(self) -> list[str]:
        if isinstance(self.filter, Filters):
            return self.filter.filter
        if isinstance(self.filter, StringFilter):
            return self.filter.values
        return []

    @vals.setter
    def vals(self, value: list[str]) -> None:
        self.filter = Filters(filter=value)

    @property
    def blank(self) -> bool | None:
        return self.filter.blank if isinstance(self.filter, Filters) else None

    @blank.setter
    def blank(self, value: bool | None) -> None:
        if isinstance(self.filter, Filters):
            self.filter.blank = value
        else:
            self.filter = Filters(blank=value)

    @property
    def customFilters(self) -> Optional[CustomFilters]:  # noqa: N802
        return self.filter if isinstance(self.filter, CustomFilters) else None

    @customFilters.setter
    def customFilters(self, value: CustomFilters | None) -> None:  # noqa: N802
        self.filter = value

    @property
    def dynamicFilter(self) -> Optional[DynamicFilter]:  # noqa: N802
        return self.filter if isinstance(self.filter, DynamicFilter) else None

    @dynamicFilter.setter
    def dynamicFilter(self, value: DynamicFilter | None) -> None:  # noqa: N802
        self.filter = value

    @property
    def colorFilter(self) -> Optional[ColorFilter]:  # noqa: N802
        return self.filter if isinstance(self.filter, ColorFilter) else None

    @colorFilter.setter
    def colorFilter(self, value: ColorFilter | None) -> None:  # noqa: N802
        self.filter = value

    @property
    def iconFilter(self) -> Optional[IconFilter]:  # noqa: N802
        return self.filter if isinstance(self.filter, IconFilter) else None

    @iconFilter.setter
    def iconFilter(self, value: IconFilter | None) -> None:  # noqa: N802
        self.filter = value

    @property
    def top10(self) -> Optional[Top10]:
        return self.filter if isinstance(self.filter, Top10) else None

    @top10.setter
    def top10(self, value: Top10 | None) -> None:
        self.filter = value


@dataclass
class SortCondition(_TreeMixin):
    """One ``<sortCondition>`` inside ``<sortState>``."""

    ref: str | None = None
    descending: bool | None = None
    sort_by: Literal["value", "cellColor", "fontColor", "icon"] | None = None
    custom_list: Optional[str] = None
    dxf_id: Optional[int] = None
    icon_set: Optional[str] = None
    icon_id: Optional[int] = None
    tagname = "sortCondition"
    __attrs__ = ("descending", "sortBy", "ref", "customList", "dxfId", "iconSet", "iconId")

    def __init__(
        self,
        ref: str | None = None,
        descending: bool | None = None,
        sort_by: Literal["value", "cellColor", "fontColor", "icon"] | None = None,
        custom_list: Optional[str] = None,
        dxf_id: Optional[int] = None,
        icon_set: Optional[str] = None,
        icon_id: Optional[int] = None,
        sortBy: Literal["value", "cellColor", "fontColor", "icon"] | None = None,  # noqa: N803
        customList: Optional[str] = None,  # noqa: N803
        dxfId: Optional[int] = None,  # noqa: N803
        iconSet: Optional[str] = None,  # noqa: N803
        iconId: Optional[int] = None,  # noqa: N803
    ) -> None:
        self.ref = ref
        self.descending = _bool_or_none(descending)
        self.sort_by = sort_by if sortBy is None else sortBy
        self.custom_list = custom_list if customList is None else customList
        self.dxf_id = _int_or_none(dxf_id if dxfId is None else dxfId)
        self.icon_set = icon_set if iconSet is None else iconSet
        self.icon_id = _int_or_none(icon_id if iconId is None else iconId)

    @property
    def sortBy(self) -> str | None:  # noqa: N802
        return self.sort_by

    @sortBy.setter
    def sortBy(self, value: str | None) -> None:  # noqa: N802
        self.sort_by = value  # type: ignore[assignment]

    @property
    def customList(self) -> Optional[str]:  # noqa: N802
        return self.custom_list

    @customList.setter
    def customList(self, value: Optional[str]) -> None:  # noqa: N802
        self.custom_list = value

    @property
    def dxfId(self) -> Optional[int]:  # noqa: N802
        return self.dxf_id

    @dxfId.setter
    def dxfId(self, value: Optional[int]) -> None:  # noqa: N802
        self.dxf_id = value

    @property
    def iconSet(self) -> Optional[str]:  # noqa: N802
        return self.icon_set

    @iconSet.setter
    def iconSet(self, value: Optional[str]) -> None:  # noqa: N802
        self.icon_set = value

    @property
    def iconId(self) -> Optional[int]:  # noqa: N802
        return self.icon_id

    @iconId.setter
    def iconId(self, value: Optional[int]) -> None:  # noqa: N802
        self.icon_id = value


@dataclass
class SortState(_TreeMixin):
    """``<sortState>`` block.

    .. note::

       v2.0 ships XML round-trip + ``sort_order`` permutation only.
       Physical row reordering is **deferred to v2.1** (RFC-056 §8).
    """

    sort_conditions: list[SortCondition] = field(default_factory=list)
    column_sort: bool | None = None
    case_sensitive: bool | None = None
    sort_method: str | None = None
    ref: Optional[str] = None
    extLst: Any = None  # noqa: N815
    tagname = "sortState"
    __attrs__ = ("columnSort", "caseSensitive", "sortMethod", "ref")
    __elements__ = ("sortCondition",)

    def __init__(
        self,
        sort_conditions: Optional[list[SortCondition]] = None,
        column_sort: bool | None = None,
        case_sensitive: bool | None = None,
        ref: Optional[str] = None,
        sortCondition: Optional[list[SortCondition] | tuple[SortCondition, ...]] = None,  # noqa: N803
        columnSort: bool | None = None,  # noqa: N803
        caseSensitive: bool | None = None,  # noqa: N803
        sortMethod: str | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
    ) -> None:
        conditions = sort_conditions if sortCondition is None else sortCondition
        self.sort_conditions = list(conditions or [])
        self.column_sort = _bool_or_none(column_sort if columnSort is None else columnSort)
        self.case_sensitive = _bool_or_none(case_sensitive if caseSensitive is None else caseSensitive)
        self.sort_method = sortMethod
        self.ref = ref
        self.extLst = extLst

    def __bool__(self) -> bool:
        return self.ref is not None

    @property
    def sortCondition(self) -> list[SortCondition]:  # noqa: N802
        return self.sort_conditions

    @sortCondition.setter
    def sortCondition(self, value: list[SortCondition]) -> None:  # noqa: N802
        self.sort_conditions = value

    @property
    def columnSort(self) -> bool | None:  # noqa: N802
        return self.column_sort

    @columnSort.setter
    def columnSort(self, value: bool) -> None:  # noqa: N802
        self.column_sort = bool(value)

    @property
    def caseSensitive(self) -> bool | None:  # noqa: N802
        return self.case_sensitive

    @caseSensitive.setter
    def caseSensitive(self, value: bool) -> None:  # noqa: N802
        self.case_sensitive = bool(value)

    @property
    def sortMethod(self) -> str | None:  # noqa: N802
        return self.sort_method

    @sortMethod.setter
    def sortMethod(self, value: str | None) -> None:  # noqa: N802
        self.sort_method = value


# ---------------------------------------------------------------------------
# Top-level AutoFilter — the dataclass version. The thin proxy on
# Worksheet (``ws.auto_filter``) wraps an instance of this class.
# ---------------------------------------------------------------------------


@dataclass
class AutoFilter(_TreeMixin):
    """``ws.auto_filter`` — sheet-scoped filter state.

    ``ref`` is the A1-notation range. ``filter_columns`` is the list
    of ``FilterColumn`` entries; ``sort_state`` is optional.

    See ``Worksheet.auto_filter`` for the friendlier in-place builder
    methods (``add_filter_column``, ``add_sort_condition``).
    """

    ref: Optional[str] = None
    filter_columns: list[FilterColumn] = field(default_factory=list)
    sort_state: Optional[SortState] = None
    extLst: Any = None  # noqa: N815
    tagname = "autoFilter"
    __attrs__ = ("ref",)
    __elements__ = ("filterColumn", "sortState")

    def __init__(
        self,
        ref: Optional[str] = None,
        filter_columns: Optional[list[FilterColumn]] = None,
        sort_state: Optional[SortState] = None,
        filterColumn: Optional[list[FilterColumn] | tuple[FilterColumn, ...]] = None,  # noqa: N803
        sortState: Optional[SortState] = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
    ) -> None:
        self.ref = ref
        columns = filter_columns if filterColumn is None else filterColumn
        self.filter_columns = list(columns or [])
        self.sort_state = sort_state if sortState is None else sortState
        self.extLst = extLst

    def __bool__(self) -> bool:
        return self.ref is not None

    @property
    def filterColumn(self) -> list[FilterColumn]:  # noqa: N802
        return self.filter_columns

    @filterColumn.setter
    def filterColumn(self, value: list[FilterColumn]) -> None:  # noqa: N802
        self.filter_columns = value

    @property
    def sortState(self) -> Optional[SortState]:  # noqa: N802
        return self.sort_state

    @sortState.setter
    def sortState(self, value: Optional[SortState]) -> None:  # noqa: N802
        self.sort_state = value

    # ------------------------------------------------------------------
    # Builders matching openpyxl-style fluency.
    # ------------------------------------------------------------------

    def add_filter_column(
        self,
        col_id: int,
        vals: Optional[FilterT | list[str] | tuple[str, ...]] = None,
        blank: bool = False,
        *,
        hidden_button: bool = False,
        show_button: bool = True,
        date_group_items: Optional[list[DateGroupItem]] = None,
    ) -> None:
        """Add a ``FilterColumn``."""
        filter: Optional[FilterT]
        if isinstance(vals, (list, tuple)):
            filter = Filters(blank=blank, filter=[str(value) for value in vals])
        else:
            filter = vals
        fc = FilterColumn(
            col_id=col_id,
            hidden_button=hidden_button,
            show_button=show_button,
            filter=filter,
            date_group_items=list(date_group_items) if date_group_items else [],
        )
        self.filter_columns.append(fc)
        return None

    def add_sort_condition(
        self,
        ref: str,
        descending: bool = False,
        sort_by: str | None = None,
        *,
        custom_list: Optional[str] = None,
        dxf_id: Optional[int] = None,
        icon_set: Optional[str] = None,
        icon_id: Optional[int] = None,
    ) -> None:
        """Add a ``SortCondition``. Auto-creates ``sort_state`` if absent."""
        if self.sort_state is None:
            self.sort_state = SortState(ref=self.ref)
        sc = SortCondition(
            ref=ref,
            descending=descending,
            sort_by=sort_by,
            custom_list=custom_list,
            dxf_id=dxf_id,
            icon_set=icon_set,
            icon_id=icon_id,
        )
        self.sort_state.sort_conditions.append(sc)
        return None

    # ------------------------------------------------------------------
    # §10 dict marshalling.
    # ------------------------------------------------------------------

    def to_rust_dict(self) -> dict[str, Any]:
        """Serialise to the RFC-056 §10 dict shape consumed by the Rust
        ``wolfxl-autofilter`` crate via the PyO3 boundary.
        """
        return {
            "ref": self.ref,
            "filter_columns": [_filter_column_to_dict(fc) for fc in self.filter_columns],
            "sort_state": _sort_state_to_dict(self.sort_state) if self.sort_state is not None else None,
        }


# ---------------------------------------------------------------------------
# §10 dict helpers (private).
# ---------------------------------------------------------------------------


def _filter_column_to_dict(fc: FilterColumn) -> dict[str, Any]:
    return {
        "col_id": int(fc.col_id),
        "hidden_button": bool(fc.hidden_button),
        "show_button": bool(fc.show_button),
        "filter": _filter_to_dict(fc.filter) if fc.filter is not None else None,
        "date_group_items": [_date_group_item_to_dict(d) for d in fc.date_group_items],
    }


def _filter_to_dict(f: FilterT) -> dict[str, Any]:
    if isinstance(f, BlankFilter):
        return {"kind": "blank"}
    if isinstance(f, ColorFilter):
        return {
            "kind": "color",
            "dxf_id": int(f.dxf_id or 0),
            "cell_color": bool(True if f.cell_color is None else f.cell_color),
        }
    if isinstance(f, DynamicFilter):
        return {
            "kind": "dynamic",
            "type": f.type,
            "val": f.val,
            "val_iso": f.val_iso,
            "max_val_iso": f.max_val_iso,
        }
    if isinstance(f, IconFilter):
        return {
            "kind": "icon",
            "icon_set": f.icon_set,
            "icon_id": int(f.icon_id or 0),
        }
    if isinstance(f, Filters):
        values = f.filter
        if f.dateGroupItem:
            return {
                "kind": "number",
                "filters": [],
                "blank": bool(f.blank),
                "calendar_type": f.calendarType,
                "date_group_items": [_date_group_item_to_dict(d) for d in f.dateGroupItem],
            }
        return {
            "kind": "string",
            "values": [str(v) for v in values],
            "blank": bool(f.blank),
            "calendar_type": f.calendarType,
        }
    if isinstance(f, NumberFilter):
        return {
            "kind": "number",
            "filters": [float(value) for value in f.filters]
            if f.filters
            else ([] if f.val is None else [float(f.val)]),
            "blank": bool(f.blank),
            "calendar_type": None,
        }
    if isinstance(f, StringFilter):
        return {
            "kind": "string",
            "values": f.values if f.values else ([] if f.val is None else [str(f.val)]),
        }
    if isinstance(f, CustomFilters):
        return {
            "kind": "custom",
            "and_": f.and_,
            "filters": [
                {"operator": cf.operator, "val": str(cf.val)} for cf in f.customFilter
            ],
        }
    if isinstance(f, CustomFilter):
        # Lone CustomFilter — wrap as a one-element CustomFilters to
        # keep the §10 shape uniform.
        return {
            "kind": "custom",
            "and_": False,
            "filters": [{"operator": f.operator, "val": str(f.val)}],
        }
    if isinstance(f, Top10):
        return {
            "kind": "top10",
            "top": f.top,
            "percent": f.percent,
            "val": float(f.val or 0),
            "filter_val": f.filter_val,
        }
    raise TypeError(f"unknown filter type: {type(f)!r}")


def _date_group_item_to_dict(d: DateGroupItem) -> dict[str, Any]:
    return {
        "year": int(d.year),
        "month": int(d.month) if d.month is not None else None,
        "day": int(d.day) if d.day is not None else None,
        "hour": int(d.hour) if d.hour is not None else None,
        "minute": int(d.minute) if d.minute is not None else None,
        "second": int(d.second) if d.second is not None else None,
        "date_time_grouping": d.date_time_grouping,
    }


AutoFilter.add_filter_column.__signature__ = _inspect.Signature(
    [
        _inspect.Parameter("self", _inspect.Parameter.POSITIONAL_OR_KEYWORD),
        _inspect.Parameter("col_id", _inspect.Parameter.POSITIONAL_OR_KEYWORD),
        _inspect.Parameter("vals", _inspect.Parameter.POSITIONAL_OR_KEYWORD),
        _inspect.Parameter(
            "blank",
            _inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=False,
        ),
    ]
)
AutoFilter.add_sort_condition.__signature__ = _inspect.Signature(
    [
        _inspect.Parameter("self", _inspect.Parameter.POSITIONAL_OR_KEYWORD),
        _inspect.Parameter("ref", _inspect.Parameter.POSITIONAL_OR_KEYWORD),
        _inspect.Parameter(
            "descending",
            _inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=False,
        ),
    ]
)


def _sort_state_to_dict(s: SortState) -> dict[str, Any]:
    return {
        "sort_conditions": [_sort_condition_to_dict(sc) for sc in s.sort_conditions],
        "column_sort": bool(s.column_sort),
        "case_sensitive": bool(s.case_sensitive),
        "ref": s.ref,
    }


def _sort_condition_to_dict(sc: SortCondition) -> dict[str, Any]:
    return {
        "ref": sc.ref,
        "descending": bool(sc.descending),
        "sort_by": sc.sort_by,
        "custom_list": sc.custom_list,
        "dxf_id": int(sc.dxf_id) if sc.dxf_id is not None else None,
        "icon_set": sc.icon_set,
        "icon_id": int(sc.icon_id) if sc.icon_id is not None else None,
    }


__all__ = [
    "AutoFilter",
    "BlankFilter",
    "ColorFilter",
    "CustomFilter",
    "CustomFilters",
    "DateGroupItem",
    "DynamicFilter",
    "FilterColumn",
    "Filters",
    "IconFilter",
    "NumberFilter",
    "SortCondition",
    "SortState",
    "StringFilter",
    "Top10",
]

__getattr__ = _openpyxl_name_fallback(globals())
