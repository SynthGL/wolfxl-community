"""openpyxl.formatting.rule compatibility.

Conditional-formatting rules are real dataclasses in T1. Each specific
rule type (``CellIsRule``, ``FormulaRule``, ``ColorScaleRule``, etc.)
constructs a ``Rule`` with the correct ``type`` tag set.

Excel's rule taxonomy:

- ``cellIs`` — compares cell value to a formula (``CellIsRule``)
- ``expression`` — arbitrary boolean formula (``FormulaRule``)
- ``colorScale`` — 2/3-color gradient (``ColorScaleRule``)
- ``dataBar`` — horizontal bar (``DataBarRule``)
- ``iconSet`` — traffic-light icons (``IconSetRule``)

wolfxl stores the rule metadata; actual style (color scale stops, bar
color) is preserved on modify-mode round-trip via the Rust layer but
not fully exposed to Python construction yet. Write-mode authoring
via ``ws.conditional_formatting.add()`` lands in PR5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

from wolfxl._compat import _install_openpyxl_iter, _openpyxl_name_fallback
from wolfxl.styles import Color
from wolfxl.styles.differential import DifferentialStyle
from wolfxl.utils.cell import COORD_RE


_OPERATOR_EXPANSIONS = {
    ">": "greaterThan",
    ">=": "greaterThanOrEqual",
    "<": "lessThan",
    "<=": "lessThanOrEqual",
    "=": "equal",
    "==": "equal",
    "!=": "notEqual",
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _bool_or_none(value: Any) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value not in {"0", "false", "False"}
    return bool(value)


def _number_or_formula(value: Any) -> Any:
    if value is None or isinstance(value, (int, float)):
        return value
    raw = str(value)
    try:
        return float(raw)
    except ValueError:
        return raw


def _serialise_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _element(tagname: str) -> ET.Element:
    from wolfxl.xml.functions import Element

    return Element(tagname)


def _append_child(parent: ET.Element, child: ET.Element) -> None:
    parent.append(child)


def _color_value(value: Color | str | None) -> Color | None:
    if value is None or isinstance(value, Color):
        return value
    return Color(value)


def _color_to_tree(value: Color | str, tagname: str = "color") -> ET.Element:
    color = _color_value(value)
    node = _element(tagname)
    if color is None:
        return node
    source = color.to_tree(tagname)
    for key, attr_value in source.attrib.items():
        node.set(key, _serialise_value(attr_value))
    return node


@dataclass(init=False)
class FormatObject:
    """Openpyxl-shaped ``<cfvo>`` conditional-format value object."""

    type: str
    val: Any = None
    gte: bool | None = None
    extLst: Any = None  # noqa: N815
    tagname = "cfvo"
    __attrs__ = ("type", "val", "gte")
    __elements__: tuple[str, ...] = ()

    def __init__(
        self,
        type: str,  # noqa: A002 - openpyxl public API
        val: Any = None,
        gte: bool | None = None,
        extLst: Any = None,  # noqa: N803
    ) -> None:
        self.type = type
        self.val = _number_or_formula(val)
        self.gte = _bool_or_none(gte)
        self.extLst = extLst

    def __iter__(self):
        for name in self.__attrs__:
            value = getattr(self, name)
            if value is None:
                continue
            yield name, _serialise_value(value)

    @classmethod
    def from_tree(cls, node: ET.Element) -> "FormatObject":
        return cls(**dict(node.attrib))

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        node = _element(tagname or self.tagname)
        for key, value in self:
            node.set(key, value)
        return node


@dataclass(init=False)
class ColorScale:
    """Openpyxl-shaped ``<colorScale>`` value class."""

    cfvo: list[FormatObject]
    color: list[Color]
    tagname = "colorScale"
    __attrs__: tuple[str, ...] = ()
    __elements__ = ("cfvo", "color")

    def __init__(
        self,
        cfvo: list[FormatObject] | tuple[FormatObject, ...] | None = None,
        color: list[Color | str] | tuple[Color | str, ...] | None = None,
    ) -> None:
        self.cfvo = list(cfvo or [])
        self.color = [
            resolved
            for value in (color or [])
            if (resolved := _color_value(value)) is not None
        ]

    @classmethod
    def from_tree(cls, node: ET.Element) -> "ColorScale":
        cfvo: list[FormatObject] = []
        colors: list[Color] = []
        for child in list(node):
            name = _local_name(child.tag)
            if name == "cfvo":
                cfvo.append(FormatObject.from_tree(child))
            elif name == "color":
                colors.append(Color.from_tree(child))
        return cls(cfvo=cfvo, color=colors)

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        node = _element(tagname or self.tagname)
        for cfvo in self.cfvo:
            _append_child(node, cfvo.to_tree())
        for color in self.color:
            _append_child(node, _color_to_tree(color))
        return node


@dataclass(init=False)
class DataBar:
    """Openpyxl-shaped ``<dataBar>`` value class."""

    minLength: int | None = None  # noqa: N815
    maxLength: int | None = None  # noqa: N815
    showValue: bool | None = None  # noqa: N815
    cfvo: list[FormatObject] = field(default_factory=list)
    color: Color | None = None
    tagname = "dataBar"
    __attrs__ = ("minLength", "maxLength", "showValue")
    __elements__ = ("cfvo", "color")

    def __init__(
        self,
        minLength: int | None = None,  # noqa: N803
        maxLength: int | None = None,  # noqa: N803
        showValue: bool | None = None,  # noqa: N803
        cfvo: list[FormatObject] | tuple[FormatObject, ...] | None = None,
        color: Color | str | None = None,
    ) -> None:
        self.minLength = None if minLength is None else int(minLength)
        self.maxLength = None if maxLength is None else int(maxLength)
        self.showValue = _bool_or_none(showValue)
        self.cfvo = list(cfvo or [])
        self.color = _color_value(color)

    def __iter__(self):
        for name in self.__attrs__:
            value = getattr(self, name)
            if value is None:
                continue
            yield name, _serialise_value(value)

    @classmethod
    def from_tree(cls, node: ET.Element) -> "DataBar":
        cfvo: list[FormatObject] = []
        color: Color | None = None
        for child in list(node):
            name = _local_name(child.tag)
            if name == "cfvo":
                cfvo.append(FormatObject.from_tree(child))
            elif name == "color":
                color = Color.from_tree(child)
        return cls(cfvo=cfvo, color=color, **dict(node.attrib))

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        node = _element(tagname or self.tagname)
        for key, value in self:
            node.set(key, value)
        for cfvo in self.cfvo:
            _append_child(node, cfvo.to_tree())
        if self.color is not None:
            _append_child(node, _color_to_tree(self.color))
        return node


@dataclass(init=False)
class IconSet:
    """Openpyxl-shaped ``<iconSet>`` value class."""

    iconSet: str | None = None  # noqa: N815
    showValue: bool | None = None  # noqa: N815
    percent: bool | None = None
    reverse: bool | None = None
    cfvo: list[FormatObject] = field(default_factory=list)
    tagname = "iconSet"
    __attrs__ = ("iconSet", "showValue", "percent", "reverse")
    __elements__ = ("cfvo",)

    def __init__(
        self,
        iconSet: str | None = None,  # noqa: N803
        showValue: bool | None = None,  # noqa: N803
        percent: bool | None = None,
        reverse: bool | None = None,
        cfvo: list[FormatObject] | tuple[FormatObject, ...] | None = None,
    ) -> None:
        self.iconSet = iconSet
        self.showValue = _bool_or_none(showValue)
        self.percent = _bool_or_none(percent)
        self.reverse = _bool_or_none(reverse)
        self.cfvo = list(cfvo or [])

    def __iter__(self):
        for name in self.__attrs__:
            value = getattr(self, name)
            if value is None:
                continue
            yield name, _serialise_value(value)

    @classmethod
    def from_tree(cls, node: ET.Element) -> "IconSet":
        cfvo = [
            FormatObject.from_tree(child)
            for child in list(node)
            if _local_name(child.tag) == "cfvo"
        ]
        return cls(cfvo=cfvo, **dict(node.attrib))

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        node = _element(tagname or self.tagname)
        for key, value in self:
            node.set(key, value)
        for cfvo in self.cfvo:
            _append_child(node, cfvo.to_tree())
        return node


@dataclass(init=False)
class Rule:
    """A generic conditional-formatting rule.

    Direct construction is rare — users build via the specific
    subclasses below, which default ``type`` to the right tag. The
    generic class exists because Excel has more rule types (above/below
    average, top/bottom, duplicates, text contains, ...) than we've
    wrapped with a dedicated constructor.
    """

    type: str
    priority: int = 0
    operator: str | None = None
    formula: list[str] = field(default_factory=list)
    stopIfTrue: bool | None = None  # noqa: N815 - openpyxl public API
    dxfId: int | None = None  # noqa: N815 - openpyxl public API
    aboveAverage: bool | None = None  # noqa: N815 - openpyxl public API
    percent: bool | None = None
    bottom: bool | None = None
    text: str | None = None
    timePeriod: str | None = None  # noqa: N815 - openpyxl public API
    rank: int | None = None
    stdDev: int | None = None  # noqa: N815 - openpyxl public API
    equalAverage: bool | None = None  # noqa: N815 - openpyxl public API
    colorScale: ColorScale | None = None  # noqa: N815 - openpyxl public API
    dataBar: DataBar | None = None  # noqa: N815 - openpyxl public API
    iconSet: IconSet | None = None  # noqa: N815 - openpyxl public API
    # ``color_scale`` / ``data_bar`` / ``icon_set`` metadata blobs are
    # preserved on round-trip but not decomposed here — T2 territory.
    extra: dict[str, Any] = field(default_factory=dict)
    tagname = "cfRule"
    __attrs__ = (
        "type",
        "rank",
        "priority",
        "equalAverage",
        "operator",
        "aboveAverage",
        "dxfId",
        "stdDev",
        "stopIfTrue",
        "timePeriod",
        "text",
        "percent",
        "bottom",
    )
    __elements__ = ("colorScale", "dataBar", "iconSet", "formula")

    def __init__(
        self,
        type: str,  # noqa: A002 - openpyxl public API
        dxfId: int | None = None,  # noqa: N803
        priority: int = 0,
        stopIfTrue: bool | None = None,  # noqa: N803
        aboveAverage: bool | None = None,  # noqa: N803
        percent: bool | None = None,
        bottom: bool | None = None,
        operator: str | None = None,
        text: str | None = None,
        timePeriod: str | None = None,  # noqa: N803
        rank: int | None = None,
        stdDev: int | None = None,  # noqa: N803
        equalAverage: bool | None = None,  # noqa: N803
        formula: list[str] | tuple[str, ...] | str | None = None,
        colorScale: ColorScale | None = None,  # noqa: N803
        dataBar: DataBar | None = None,  # noqa: N803
        iconSet: IconSet | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
        dxf: Any = None,
        extra: dict[str, Any] | None = None,
        **kw: Any,
    ) -> None:
        self.type = type
        self.priority = int(priority)
        self.operator = _OPERATOR_EXPANSIONS.get(operator, operator)
        if formula is None:
            self.formula = []
        elif isinstance(formula, str):
            self.formula = [formula]
        else:
            self.formula = [str(item) for item in formula]
        self.stopIfTrue = _bool_or_none(stopIfTrue)
        self.dxfId = None if dxfId is None else int(dxfId)
        self.aboveAverage = _bool_or_none(aboveAverage)
        self.percent = _bool_or_none(percent)
        self.bottom = _bool_or_none(bottom)
        self.text = text
        self.timePeriod = timePeriod
        self.rank = None if rank is None else int(rank)
        self.stdDev = None if stdDev is None else int(stdDev)
        self.equalAverage = _bool_or_none(equalAverage)
        self.colorScale = colorScale
        self.dataBar = dataBar
        self.iconSet = iconSet
        self.extLst = extLst
        extras = dict(extra or {})
        # Preserve unrecognized keyword payloads instead of rejecting
        # openpyxl-shaped Rule construction that carries extension data.
        for key, value in kw.items():
            if key not in extras and value is not None:
                extras[key] = value
        self.extra = extras
        if dxf is not None:
            self.dxf = dxf

    @property
    def dxf(self) -> DifferentialStyle | None:
        """openpyxl-shaped ``DifferentialStyle`` view of this rule's fill /
        font / border state.

        openpyxl exposes ``rule.dxf`` as a :class:`DifferentialStyle` whose
        ``font`` / ``fill`` / ``border`` mirror the kwargs the user passed
        in. Wolfxl stashes those kwargs inside :attr:`extra`; this property
        reconstructs the shim on demand. Returns ``None`` when no styling
        was supplied so callers can branch on truthiness.
        """
        extra = self.extra or {}
        if isinstance(extra.get("dxf"), DifferentialStyle):
            return extra["dxf"]
        if not any(extra.get(k) is not None for k in ("font", "fill", "border")):
            return None
        return DifferentialStyle(
            font=extra.get("font"),
            fill=extra.get("fill"),
            border=extra.get("border"),
        )

    @dxf.setter
    def dxf(self, value: DifferentialStyle | None) -> None:
        if self.extra is None:
            self.extra = {}
        self.extra["dxf"] = value

    def __iter__(self):
        for name in self.__attrs__:
            value = getattr(self, name)
            if value is None:
                continue
            yield name, _serialise_value(value)

    @classmethod
    def from_tree(cls, node: ET.Element) -> "Rule":
        kwargs: dict[str, Any] = dict(node.attrib)
        formulas: list[str] = []
        for child in list(node):
            name = _local_name(child.tag)
            if name == "formula":
                formulas.append(child.text or "")
            elif name == "colorScale":
                kwargs["colorScale"] = ColorScale.from_tree(child)
            elif name == "dataBar":
                kwargs["dataBar"] = DataBar.from_tree(child)
            elif name == "iconSet":
                kwargs["iconSet"] = IconSet.from_tree(child)
        if formulas:
            kwargs["formula"] = formulas
        return cls(**kwargs)

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        node = _element(tagname or self.tagname)
        for key, value in self:
            node.set(key, value)
        for child_name in ("colorScale", "dataBar", "iconSet"):
            child = getattr(self, child_name)
            if child is not None:
                _append_child(node, child.to_tree())
        for formula in self.formula:
            child = _element("formula")
            child.text = formula
            _append_child(node, child)
        return node


def _absorb_dxf_kwargs(kw: dict[str, Any]) -> dict[str, Any]:
    """Pull openpyxl-shaped dxf kwargs (``fill=``, ``font=``, ``border=``, ``dxf=``)
    off ``kw`` and stash them inside ``extra`` so they survive the ``Rule``
    dataclass constructor (G14).

    openpyxl's ``CellIsRule(fill=PatternFill(...))`` collapses the kwarg into a
    ``DifferentialStyle`` and the rule grows a ``dxfId`` at write time.
    Wolfxl mirrors the surface here: the kwargs are recorded inside
    ``Rule.extra`` and the write-mode payload helper
    (``_conditional_format_payload``) translates them into the Rust-side cfg
    dict so ``dict_to_conditional_format`` can intern a ``DxfRecord`` and
    stamp the resulting ``dxfId`` on the emitted ``<cfRule>``.
    """
    if not any(k in kw for k in ("fill", "font", "border", "dxf")):
        return kw
    extra = dict(kw.pop("extra", {}) or {})
    for key in ("fill", "font", "border", "dxf"):
        if key in kw:
            extra[key] = kw.pop(key)
    kw["extra"] = extra
    return kw


class CellIsRule(Rule):
    """Conditional format triggered when a cell value matches an operator+operand.

    Example: ``CellIsRule(operator="greaterThan", formula=["50"])``.

    The openpyxl-compatible ``fill=PatternFill(...)`` / ``font=Font(...)`` /
    ``border=Border(...)`` / ``dxf=DifferentialStyle(...)`` kwargs are accepted
    and routed through ``Rule.extra`` so the writer can intern a matching
    ``<dxf>`` record and stamp its index as ``dxfId`` on the emitted
    ``<cfRule>`` (G14).
    """

    def __init__(
        self,
        operator: str | None = None,
        formula: list[str] | None = None,
        stopIfTrue: bool | None = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        kw = _absorb_dxf_kwargs(kw)
        extra = dict(kw.pop("extra", {}) or {})
        dxf = extra.pop("dxf", None)
        if dxf is None:
            dxf = DifferentialStyle(
                font=extra.pop("font", None),
                border=extra.pop("border", None),
                fill=extra.pop("fill", None),
            )
        super().__init__(
            type="cellIs",
            operator=operator,
            formula=list(formula or []),
            stopIfTrue=stopIfTrue,
            dxf=dxf,
            extra=extra,
            **kw,
        )


class FormulaRule(Rule):
    """Conditional format triggered when a boolean formula is TRUE.

    Example: ``FormulaRule(formula=["$A1>100"])``.

    Accepts the same openpyxl ``fill=`` / ``font=`` / ``border=`` / ``dxf=``
    kwargs as ``CellIsRule``; they ride on ``Rule.extra`` and feed the dxf
    intern path on save (G14).
    """

    def __init__(
        self,
        formula: list[str] | None = None,
        stopIfTrue: bool | None = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        kw = _absorb_dxf_kwargs(kw)
        extra = dict(kw.pop("extra", {}) or {})
        dxf = extra.pop("dxf", None)
        if dxf is None:
            dxf = DifferentialStyle(
                font=extra.pop("font", None),
                border=extra.pop("border", None),
                fill=extra.pop("fill", None),
            )
        super().__init__(
            type="expression",
            formula=list(formula or []),
            stopIfTrue=stopIfTrue,
            dxf=dxf,
            extra=extra,
            **kw,
        )


class ColorScaleRule(Rule):
    """2- or 3-stop color scale.

    ``start_type`` / ``mid_type`` / ``end_type`` are openpyxl's
    interpolation anchors (``"min"``, ``"max"``, ``"percentile"``,
    ``"num"``, ``"formula"``). We capture them in ``extra`` for round-
    trip; they don't feed the Rust writer yet (PR5 passes a simplified
    shape through).
    """

    def __init__(
        self,
        start_type: str | None = None,
        start_value: Any = None,
        start_color: str | None = None,
        mid_type: str | None = None,
        mid_value: Any = None,
        mid_color: str | None = None,
        end_type: str | None = None,
        end_value: Any = None,
        end_color: str | None = None,
        **kw: Any,
    ) -> None:
        formats: list[FormatObject] = []
        if start_type is not None:
            formats.append(FormatObject(type=start_type, val=start_value))
        if mid_type is not None:
            formats.append(FormatObject(type=mid_type, val=mid_value))
        if end_type is not None:
            formats.append(FormatObject(type=end_type, val=end_value))
        colors = [
            resolved
            for value in (start_color, mid_color, end_color)
            if (resolved := _color_value(value)) is not None
        ]
        color_scale = ColorScale(cfvo=formats, color=colors)
        extra = {
            "start_type": start_type,
            "start_value": start_value,
            "start_color": start_color,
            "mid_type": mid_type,
            "mid_value": mid_value,
            "mid_color": mid_color,
            "end_type": end_type,
            "end_value": end_value,
            "end_color": end_color,
        }
        super().__init__(type="colorScale", colorScale=color_scale, extra=extra, **kw)


class DataBarRule(Rule):
    """In-cell horizontal data bar."""

    def __init__(
        self,
        start_type: str | None = None,
        start_value: Any = None,
        end_type: str | None = None,
        end_value: Any = None,
        color: str | None = None,
        showValue: bool | None = None,  # noqa: N803
        minLength: int | None = None,  # noqa: N803
        maxLength: int | None = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        data_bar = DataBar(
            minLength=minLength,
            maxLength=maxLength,
            showValue=showValue,
            cfvo=[
                FormatObject(start_type, start_value),
                FormatObject(end_type, end_value),
            ],
            color=color,
        )
        extra = {
            "start_type": start_type,
            "start_value": start_value,
            "end_type": end_type,
            "end_value": end_value,
            "color": color,
            "show_value": showValue,
            "min_length": minLength,
            "max_length": maxLength,
        }
        super().__init__(type="dataBar", dataBar=data_bar, extra=extra, **kw)


class IconSetRule(Rule):
    """Icon set (3 arrows, 5 traffic lights, etc.)."""

    def __init__(
        self,
        icon_style: str | None = None,
        type: str | None = None,  # noqa: A002 - keyword openpyxl uses
        values: list[Any] | None = None,
        showValue: bool | None = None,  # noqa: N803
        percent: bool | None = None,
        reverse: bool | None = None,
        **kw: Any,
    ) -> None:
        # openpyxl's IconSetRule positional ``type`` ("percent", "percentile",
        # "num", "formula") differs from Rule.type — we stash it inside extra.
        icon_set = IconSet(
            iconSet=icon_style,
            cfvo=[FormatObject(type, value) for value in (values or [])],
            showValue=showValue,
            percent=percent,
            reverse=reverse,
        )
        extra = {
            "icon_style": icon_style,
            "value_type": type,
            "values": list(values or []),
            "show_value": showValue,
            "percent": percent,
            "reverse": reverse,
        }
        super().__init__(type="iconSet", iconSet=icon_set, extra=extra, **kw)


class RuleType:
    """Marker for parametrized CF rule kinds.

    Constants mirror openpyxl's ``RuleType`` enum so user code that
    references ``RuleType.COLOR_SCALE`` keeps working.

    Pod 2 (RFC-060 §2.4).
    """

    AVERAGE = "aboveAverage"
    COLOR_SCALE = "colorScale"
    DATA_BAR = "dataBar"
    ICON_SET = "iconSet"
    FORMULA = "expression"
    EXPRESSION = "expression"
    DUPLICATE_VALUES = "duplicateValues"
    UNIQUE_VALUES = "uniqueValues"
    CONTAINS_TEXT = "containsText"
    NOT_CONTAINS_TEXT = "notContainsText"
    BEGINS_WITH = "beginsWith"
    ENDS_WITH = "endsWith"
    CONTAINS_BLANKS = "containsBlanks"
    CONTAINS_NO_BLANKS = "notContainsBlanks"
    CONTAINS_ERRORS = "containsErrors"
    CONTAINS_NO_ERRORS = "notContainsErrors"
    TIME_PERIOD = "timePeriod"
    ABOVE_AVERAGE = "aboveAverage"
    TOP10 = "top10"
    CELL_IS = "cellIs"


_install_openpyxl_iter(DifferentialStyle, RuleType, Rule)

__all__ = [
    "CellIsRule",
    "ColorScale",
    "ColorScaleRule",
    "COORD_RE",
    "DataBar",
    "DataBarRule",
    "DifferentialStyle",
    "FormulaRule",
    "IconSet",
    "IconSetRule",
    "Rule",
    "RuleType",
]

__getattr__ = _openpyxl_name_fallback(globals())
