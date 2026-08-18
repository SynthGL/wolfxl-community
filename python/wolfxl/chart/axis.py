"""Chart axes — `<c:catAx>`, `<c:valAx>`, `<c:dateAx>`, `<c:serAx>`.

Mirrors :mod:`openpyxl.chart.axis`. Each axis subclass shares the
:class:`_BaseAxis` slot set and adds type-specific extras.

Chart-side axis IDs default to the same constants openpyxl picks
(``catAx`` 10, ``valAx`` 100, ``dateAx`` 500, ``serAx`` 1000) so the
emitted XML matches openpyxl's by default.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import (
    _install_openpyxl_iter,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)

from .data_source import NumFmt
from .layout import Layout
from .shapes import GraphicalProperties
from .text import RichText, Text
from .title import TitleDescriptor, _to_native_title_model


_VALID_AX_POS = ("b", "l", "r", "t")
_VALID_TICK_MARK = (None, "cross", "in", "out", "none")
_VALID_TICK_LBL_POS = (None, "high", "low", "nextTo", "none")
_VALID_CROSSES = (None, "autoZero", "max", "min")
_VALID_TIME_UNIT = (None, "days", "months", "years")


class ChartLines:
    """`<c:majorGridlines>` / `<c:minorGridlines>` — optional spPr-only block.

    Emits ``{graphical_properties}`` snake-case. Empty ``{}`` means
    "default gridlines"; ``None`` at the parent means "no gridlines".
    """

    __slots__ = ("spPr",)

    def __init__(self, spPr: GraphicalProperties | None = None) -> None:
        self.spPr = spPr

    @property
    def graphicalProperties(self) -> GraphicalProperties | None:
        return self.spPr

    @graphicalProperties.setter
    def graphicalProperties(self, v: GraphicalProperties | None) -> None:
        self.spPr = v

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.spPr is not None:
            d["graphical_properties"] = self.spPr.to_dict()
        return d


# Public alias used by external callers.
Gridlines = ChartLines


class Scaling:
    """`<c:scaling>` — log base, orientation, manual min/max."""

    __slots__ = ("logBase", "orientation", "max", "min", "extLst")

    def __init__(
        self,
        logBase: float | None = None,
        orientation: str = "minMax",
        max: float | None = None,
        min: float | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        if logBase is not None:
            logBase = _coerce_float(logBase)
        if max is not None:
            max = _coerce_float(max)
        if min is not None:
            min = _coerce_float(min)
        if orientation not in ("minMax", "maxMin"):
            raise ValueError(f"orientation={orientation!r} must be 'minMax' or 'maxMin'")
        self.logBase = logBase
        self.orientation = orientation
        self.max = max
        self.min = min
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"orientation": self.orientation}
        if self.logBase is not None:
            d["logBase"] = self.logBase
        if self.max is not None:
            d["max"] = self.max
        if self.min is not None:
            d["min"] = self.min
        return d


class DisplayUnitsLabel:
    """`<c:dispUnitsLbl>` — label for axis display units."""

    __slots__ = ("layout", "tx", "spPr", "txPr")

    def __init__(
        self,
        layout: Layout | None = None,
        tx: Text | None = None,
        spPr: GraphicalProperties | None = None,
        txPr: RichText | None = None,
    ) -> None:
        self.layout = layout
        self.tx = tx
        self.spPr = spPr
        self.txPr = txPr

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.layout is not None:
            d["layout"] = self.layout.to_dict()
        if self.tx is not None:
            d["tx"] = self.tx.to_dict()
        if self.spPr is not None:
            d["spPr"] = self.spPr.to_dict()
        if self.txPr is not None:
            d["txPr"] = self.txPr.to_dict()
        return d


class DisplayUnitsLabelList:
    """`<c:dispUnits>` — display unit selector + label."""

    __slots__ = ("custUnit", "builtInUnit", "dispUnitsLbl", "extLst")

    _VALID_BUILTIN = (
        None,
        "hundreds",
        "thousands",
        "tenThousands",
        "hundredThousands",
        "millions",
        "tenMillions",
        "hundredMillions",
        "billions",
        "trillions",
    )

    def __init__(
        self,
        custUnit: float | None = None,
        builtInUnit: str | None = None,
        dispUnitsLbl: DisplayUnitsLabel | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        if builtInUnit not in self._VALID_BUILTIN:
            raise ValueError(f"builtInUnit={builtInUnit!r} not in {self._VALID_BUILTIN}")
        self.custUnit = custUnit
        self.builtInUnit = builtInUnit
        self.dispUnitsLbl = dispUnitsLbl
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.custUnit is not None:
            d["custUnit"] = self.custUnit
        if self.builtInUnit is not None:
            d["builtInUnit"] = self.builtInUnit
        if self.dispUnitsLbl is not None:
            d["dispUnitsLbl"] = self.dispUnitsLbl.to_dict()
        return d


class _AxisMeta(type):
    def __instancecheck__(cls, instance: Any) -> bool:
        if type.__instancecheck__(cls, instance):
            return True
        instance_cls = getattr(instance, "__class__", None)
        return (
            getattr(cls, "__name__", None) == getattr(instance_cls, "__name__", None)
            and str(getattr(cls, "__module__", "")).endswith("chart.axis")
            and str(getattr(instance_cls, "__module__", "")).endswith("chart.axis")
        )


class _BaseAxis(metaclass=_AxisMeta):
    """Common axis state shared by every axis kind.

    Attributes mirror openpyxl's :class:`_BaseAxis` exactly. ``title``
    accepts either a string (auto-inflated via :class:`TitleDescriptor`)
    or a constructed :class:`Title`.
    """

    title = TitleDescriptor()

    # Per-instance slot list — declared via __init_subclass__ on subclasses
    # via plain attributes. We keep ``__slots__`` empty here so the
    # descriptor's ``_title`` storage on the instance works.

    def __init__(
        self,
        axId: int | None = None,
        scaling: Scaling | None = None,
        delete: bool | None = None,
        axPos: str = "l",
        majorGridlines: ChartLines | None = None,
        minorGridlines: ChartLines | None = None,
        title: Any | None = None,
        numFmt: Any | None = None,
        majorTickMark: str | None = "none",
        minorTickMark: str | None = "none",
        tickLblPos: str | None = None,
        spPr: GraphicalProperties | None = None,
        txPr: RichText | None = None,
        crossAx: int | None = None,
        crosses: str | None = None,
        crossesAt: float | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        if axPos not in _VALID_AX_POS:
            raise ValueError(f"axPos={axPos!r} not in {_VALID_AX_POS}")
        if scaling is not None and not isinstance(scaling, Scaling):
            raise TypeError(f"{type(self)}.scaling should be {Scaling} but value is {type(scaling)}")
        if majorTickMark not in _VALID_TICK_MARK:
            raise ValueError(f"majorTickMark={majorTickMark!r} not in {_VALID_TICK_MARK}")
        if minorTickMark not in _VALID_TICK_MARK:
            raise ValueError(f"minorTickMark={minorTickMark!r} not in {_VALID_TICK_MARK}")
        if tickLblPos not in _VALID_TICK_LBL_POS:
            raise ValueError(f"tickLblPos={tickLblPos!r} not in {_VALID_TICK_LBL_POS}")
        if crosses not in _VALID_CROSSES:
            raise ValueError(f"crosses={crosses!r} not in {_VALID_CROSSES}")

        self.axId = axId
        self.scaling = scaling if scaling is not None else Scaling()
        self.delete = delete
        self.axPos = axPos
        self.majorGridlines = majorGridlines
        self.minorGridlines = minorGridlines
        self.title = title  # via TitleDescriptor
        self._numFmt: Any | None = None
        self.numFmt = numFmt
        self.majorTickMark = majorTickMark
        self.minorTickMark = minorTickMark
        self.tickLblPos = tickLblPos
        self.spPr = spPr
        self.txPr = txPr
        self.crossAx = crossAx
        self.crosses = crosses
        self.crossesAt = crossesAt
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    # numFmt accepts either a NumFmt or a bare format string (openpyxl alias)
    @property
    def numFmt(self) -> NumFmt | None:
        return self._numFmt

    @numFmt.setter
    def numFmt(self, value: Any) -> None:
        if value is None:
            self._numFmt = None
        elif isinstance(value, str):
            self._numFmt = NumFmt(formatCode=value)
        else:
            self._numFmt = value

    @property
    def number_format(self) -> NumFmt | None:
        return self._numFmt

    @number_format.setter
    def number_format(self, value: Any) -> None:
        self.numFmt = value

    @property
    def graphicalProperties(self) -> GraphicalProperties | None:
        return self.spPr

    @graphicalProperties.setter
    def graphicalProperties(self, v: GraphicalProperties | None) -> None:
        self.spPr = v

    @property
    def textProperties(self) -> RichText | None:
        return self.txPr

    @textProperties.setter
    def textProperties(self, v: RichText | None) -> None:
        self.txPr = v

    def _base_to_dict(self) -> dict[str, Any]:
        """Emit the snake_case shared keys."""
        scaling_d = self.scaling.to_dict() if self.scaling is not None else None
        if scaling_d is not None:
            # Map nested keys to snake_case per §10.7
            scaling_d = {
                "min": scaling_d.get("min"),
                "max": scaling_d.get("max"),
                "orientation": scaling_d.get("orientation"),
                "log_base": scaling_d.get("logBase"),
            }
            if all(v is None for v in scaling_d.values()):
                scaling_d = None

        num_fmt_d: dict[str, Any] | None = None
        if self._numFmt is not None:
            nf = self._numFmt.to_dict()
            num_fmt_d = {
                "format_code": nf.get("formatCode"),
                "source_linked": nf.get("sourceLinked", False),
            }

        d: dict[str, Any] = {
            "ax_id": self.axId,
            "cross_ax": self.crossAx,
            "scaling": scaling_d,
            "delete": self.delete,
            "axis_position": self.axPos,
            "title": self.title.to_dict() if self.title is not None else None,
            "number_format": num_fmt_d,
            "major_tick_mark": self.majorTickMark,
            "minor_tick_mark": self.minorTickMark,
            "major_gridlines": (
                self.majorGridlines.to_dict() if self.majorGridlines is not None else None
            ),
            "minor_gridlines": (
                self.minorGridlines.to_dict() if self.minorGridlines is not None else None
            ),
            "graphical_properties": self.spPr.to_dict() if self.spPr is not None else None,
            "tick_lbl_pos": self.tickLblPos,
            "crosses": self.crosses,
            "crosses_at": self.crossesAt,
        }
        return d


class NumericAxis(_BaseAxis):
    """`<c:valAx>` — numeric (value) axis."""

    tagname = "valAx"

    def __init__(
        self,
        crossBetween: str | None = None,
        majorUnit: float | None = None,
        minorUnit: float | None = None,
        dispUnits: DisplayUnitsLabelList | None = None,
        **kw: Any,
    ) -> None:
        if crossBetween is not None and crossBetween not in ("between", "midCat"):
            raise ValueError(f"crossBetween={crossBetween!r} not in (between, midCat)")
        if dispUnits is not None and not isinstance(dispUnits, DisplayUnitsLabelList):
            raise TypeError(
                f"{type(self)}.dispUnits should be {DisplayUnitsLabelList} "
                f"but value is {type(dispUnits)}"
            )
        if majorUnit is not None:
            majorUnit = _coerce_float(majorUnit)
        if minorUnit is not None:
            minorUnit = _coerce_float(minorUnit)
        kw.setdefault("majorGridlines", ChartLines())
        kw.setdefault("axId", 100)
        kw.setdefault("crossAx", 10)
        super().__init__(**kw)
        self.crossBetween = crossBetween
        self.majorUnit = majorUnit
        self.minorUnit = minorUnit
        self.dispUnits = dispUnits

    def to_dict(self) -> dict[str, Any]:
        d = self._base_to_dict()
        d["ax_type"] = "val"
        if self.majorUnit is not None:
            d["major_unit"] = self.majorUnit
        if self.minorUnit is not None:
            d["minor_unit"] = self.minorUnit
        if self.crossBetween is not None:
            d["cross_between"] = self.crossBetween
        if self.dispUnits is not None:
            d["disp_units"] = self.dispUnits.to_dict()
        return d


# openpyxl alias
ValueAxis = NumericAxis
ValAx = NumericAxis


class TextAxis(_BaseAxis):
    """`<c:catAx>` — categorical (text) axis."""

    tagname = "catAx"

    def __init__(
        self,
        auto: bool | None = None,
        lblAlgn: str | None = None,
        lblOffset: int = 100,
        tickLblSkip: int | None = None,
        tickMarkSkip: int | None = None,
        noMultiLvlLbl: bool | None = None,
        **kw: Any,
    ) -> None:
        if lblAlgn is not None and lblAlgn not in ("ctr", "l", "r"):
            raise ValueError(f"lblAlgn={lblAlgn!r} not in (ctr, l, r)")
        if not (0 <= lblOffset <= 1000):
            raise ValueError(f"lblOffset={lblOffset} must be in [0, 1000]")
        kw.setdefault("axId", 10)
        kw.setdefault("crossAx", 100)
        super().__init__(**kw)
        self.auto = auto
        self.lblAlgn = lblAlgn
        self.lblOffset = lblOffset
        self.tickLblSkip = tickLblSkip
        self.tickMarkSkip = tickMarkSkip
        self.noMultiLvlLbl = noMultiLvlLbl

    def to_dict(self) -> dict[str, Any]:
        d = self._base_to_dict()
        d["ax_type"] = "cat"
        d["lbl_offset"] = self.lblOffset
        if self.lblAlgn is not None:
            d["lbl_align"] = self.lblAlgn
        if self.auto is not None:
            d["auto"] = self.auto
        if self.tickLblSkip is not None:
            d["tick_lbl_skip"] = self.tickLblSkip
        if self.tickMarkSkip is not None:
            d["tick_mark_skip"] = self.tickMarkSkip
        if self.noMultiLvlLbl is not None:
            d["no_multi_lvl_lbl"] = self.noMultiLvlLbl
        return d


CategoryAxis = TextAxis
CatAx = TextAxis


class DateAxis(TextAxis):
    """`<c:dateAx>` — date axis (subclass of catAx in the spec)."""

    tagname = "dateAx"

    def __init__(
        self,
        auto: bool | None = None,
        lblOffset: int | None = None,
        baseTimeUnit: str | None = None,
        majorUnit: float | None = None,
        majorTimeUnit: str | None = None,
        minorUnit: float | None = None,
        minorTimeUnit: str | None = None,
        **kw: Any,
    ) -> None:
        if baseTimeUnit not in _VALID_TIME_UNIT:
            raise ValueError(f"baseTimeUnit={baseTimeUnit!r} not in {_VALID_TIME_UNIT}")
        if majorTimeUnit not in _VALID_TIME_UNIT:
            raise ValueError(f"majorTimeUnit={majorTimeUnit!r} not in {_VALID_TIME_UNIT}")
        if minorTimeUnit not in _VALID_TIME_UNIT:
            raise ValueError(f"minorTimeUnit={minorTimeUnit!r} not in {_VALID_TIME_UNIT}")
        self._lblOffset_explicit = lblOffset is not None
        kw.setdefault("axId", 500)
        # Avoid TextAxis lblOffset bounds check by providing a default.
        if lblOffset is None:
            kw["lblOffset"] = 100
        else:
            kw["lblOffset"] = lblOffset
        super().__init__(**kw)
        # Re-assign post-init since super() set lblOffset to a possibly-default
        self.auto = auto if auto is not None else self.auto
        self.baseTimeUnit = baseTimeUnit
        self.majorUnit = majorUnit
        self.majorTimeUnit = majorTimeUnit
        self.minorUnit = minorUnit
        self.minorTimeUnit = minorTimeUnit

    def to_dict(self) -> dict[str, Any]:
        d = self._base_to_dict()
        d["ax_type"] = "date"
        if self.auto is not None:
            d["auto"] = self.auto
        if self.lblOffset is not None:
            d["lbl_offset"] = self.lblOffset
        if self.baseTimeUnit is not None:
            d["base_time_unit"] = self.baseTimeUnit
        if self.majorUnit is not None:
            d["major_unit"] = self.majorUnit
        if self.majorTimeUnit is not None:
            d["major_time_unit"] = self.majorTimeUnit
        if self.minorUnit is not None:
            d["minor_unit"] = self.minorUnit
        if self.minorTimeUnit is not None:
            d["minor_time_unit"] = self.minorTimeUnit
        return d


DateAx = DateAxis


class SeriesAxis(_BaseAxis):
    """`<c:serAx>` — series axis (only used by 3-D charts; we keep it for compat)."""

    tagname = "serAx"

    def __init__(
        self,
        tickLblSkip: int | None = None,
        tickMarkSkip: int | None = None,
        **kw: Any,
    ) -> None:
        kw.setdefault("axId", 1000)
        kw.setdefault("crossAx", 10)
        super().__init__(**kw)
        self.tickLblSkip = tickLblSkip
        self.tickMarkSkip = tickMarkSkip

    def to_dict(self) -> dict[str, Any]:
        d = self._base_to_dict()
        d["ax_type"] = "ser"
        if self.tickLblSkip is not None:
            d["tick_lbl_skip"] = self.tickLblSkip
        if self.tickMarkSkip is not None:
            d["tick_mark_skip"] = self.tickMarkSkip
        return d


SerAx = SeriesAxis


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("expected <class 'float'>") from exc


_AXIS_XML_MODEL_NAMES = (
    "ChartLines",
    "Scaling",
    "DisplayUnitsLabel",
    "DisplayUnitsLabelList",
    "_BaseAxis",
    "NumericAxis",
    "TextAxis",
    "DateAxis",
    "SeriesAxis",
)


def _xml_model_names(cls: type) -> tuple[str, ...]:
    return tuple(getattr(cls, "__attrs__", ())) + tuple(getattr(cls, "__elements__", ()))


def _to_openpyxl_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_openpyxl_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_openpyxl_model(item) for item in value)

    cls = value.__class__
    upstream_cls = _resolve_openpyxl_class(cls.__module__, cls.__name__)
    if upstream_cls is None or cls is upstream_cls:
        return value

    names = _xml_model_names(upstream_cls)
    if not names:
        return value

    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            attr = getattr(value, name)
            if (
                isinstance(value, DateAxis)
                and name == "lblOffset"
                and attr == 100
                and not getattr(value, "_lblOffset_explicit", False)
            ):
                attr = None
            kwargs[name] = _to_openpyxl_model(attr)
    return upstream_cls(**kwargs)


def _from_openpyxl_axis_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_axis_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_axis_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_axis_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_axis_model(item) for item in value)
    if value.__class__.__module__.startswith("openpyxl.chart.title"):
        return _to_native_title_model(value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _AXIS_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_axis_model(native_cls, value)


def _axis_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
    value: Any = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _axis_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_axis_model(cls, upstream_cls.from_tree(node))


def _axis_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_axis_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _axis_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_axis_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _axis_eq  # type: ignore[attr-defined]


_install_axis_xml_methods(
    ChartLines,
    Scaling,
    DisplayUnitsLabel,
    DisplayUnitsLabelList,
    _BaseAxis,
    NumericAxis,
    TextAxis,
    DateAxis,
    SeriesAxis,
)


__all__ = [
    "Axis",
    "CategoryAxis",
    "CatAx",
    "ChartLines",
    "DateAxis",
    "DateAx",
    "DisplayUnitsLabel",
    "DisplayUnitsLabelList",
    "Gridlines",
    "NumericAxis",
    "Scaling",
    "SeriesAxis",
    "SerAx",
    "TextAxis",
    "ValAx",
    "ValueAxis",
    "_BaseAxis",
]


# Public alias matching openpyxl's surface
Axis = _BaseAxis

_install_openpyxl_iter(
    ChartLines,
    Scaling,
    DisplayUnitsLabel,
    DisplayUnitsLabelList,
    _BaseAxis,
    NumericAxis,
    TextAxis,
    DateAxis,
    SeriesAxis,
)

__getattr__ = _openpyxl_name_fallback(globals())
