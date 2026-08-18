"""`<c:ser>` — chart data series + the SeriesFactory helper.

Mirrors :mod:`openpyxl.chart.series` and :mod:`openpyxl.chart.series_factory`.
``XYSeries`` is identical to ``Series`` for our purposes (xVal/yVal/bubbleSize
are already on the parent class); we keep it as a separate name purely so
``isinstance(...)`` checks in client code continue to work.

The ``attribute_mapping`` dict mirrors openpyxl's: it tells each chart type
which slot subset of ``Series`` actually round-trips for its kind.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import (
    _install_openpyxl_iter,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)

from .data_source import (
    AxDataSource,
    NumDataSource,
    NumRef,
    StrRef,
    _to_native_data_source_model,
    _to_openpyxl_model as _data_source_to_openpyxl_model,
)
from .error_bar import ErrorBars
from .label import DataLabelList
from .marker import DataPoint, Marker
from .reference import Reference
from .shapes import GraphicalProperties, LineProperties
from .trendline import Trendline


# Per-chart-type filter for ``Series.__elements__`` — drives the order in
# which the Rust emitter writes child elements for that chart's series.
attribute_mapping = {
    "area": ("idx", "order", "tx", "spPr", "pictureOptions", "dPt", "dLbls",
             "errBars", "trendline", "cat", "val"),
    "bar": ("idx", "order", "tx", "spPr", "invertIfNegative", "pictureOptions",
            "dPt", "dLbls", "trendline", "errBars", "cat", "val", "shape"),
    "bubble": ("idx", "order", "tx", "spPr", "invertIfNegative", "dPt", "dLbls",
               "trendline", "errBars", "xVal", "yVal", "bubbleSize", "bubble3D"),
    "line": ("idx", "order", "tx", "spPr", "marker", "dPt", "dLbls",
             "trendline", "errBars", "cat", "val", "smooth"),
    "pie": ("idx", "order", "tx", "spPr", "explosion", "dPt", "dLbls", "cat", "val"),
    "radar": ("idx", "order", "tx", "spPr", "marker", "dPt", "dLbls", "cat", "val"),
    "scatter": ("idx", "order", "tx", "spPr", "marker", "dPt", "dLbls",
                "trendline", "errBars", "xVal", "yVal", "smooth"),
    "surface": ("idx", "order", "tx", "spPr", "cat", "val"),
}


class _SeriesMeta(type):
    def __instancecheck__(cls, instance: Any) -> bool:
        if type.__instancecheck__(cls, instance):
            return True
        instance_cls = getattr(instance, "__class__", None)
        return (
            getattr(cls, "__name__", None) == getattr(instance_cls, "__name__", None)
            and str(getattr(cls, "__module__", "")).endswith("chart.series")
            and str(getattr(instance_cls, "__module__", "")).endswith("chart.series")
        )


def _all_series_elements() -> tuple[str, ...]:
    names: list[str] = []
    for mapping in attribute_mapping.values():
        names.extend(mapping)
    return tuple(dict.fromkeys(names))


class SeriesLabel:
    """`<c:tx>` for a series — either a strRef or a literal value."""

    __slots__ = ("strRef", "v", "__dict__")

    def __init__(self, strRef: StrRef | None = None, v: str | None = None) -> None:
        self.strRef = strRef
        self.v = v

    @property
    def value(self) -> str | None:
        return self.v

    @value.setter
    def value(self, val: str | None) -> None:
        self.v = val

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.strRef is not None:
            d["strRef"] = self.strRef.to_dict()
        if self.v is not None:
            d["v"] = self.v
        return d


class Series(metaclass=_SeriesMeta):
    """A chart data series.

    Carries every slot any chart type might need — :func:`series_factory`
    populates the relevant subset based on whether xvalues / zvalues
    (bubble sizes) are provided. The Rust emitter consults
    :data:`attribute_mapping` to pick which slots become XML.
    """

    __slots__ = (
        "__dict__",
        "idx",
        "order",
        "tx",
        "spPr",
        "pictureOptions",
        "dPt",
        "dLbls",
        "trendline",
        "errBars",
        "cat",
        "val",
        "invertIfNegative",
        "shape",
        "xVal",
        "yVal",
        "bubbleSize",
        "bubble3D",
        "marker",
        "smooth",
        "explosion",
        "extLst",
    )

    def __init__(
        self,
        idx: int = 0,
        order: int = 0,
        tx: SeriesLabel | None = None,
        spPr: GraphicalProperties | None = None,
        pictureOptions: Any | None = None,
        dPt: list[DataPoint] | tuple[DataPoint, ...] = (),
        dLbls: DataLabelList | None = None,
        trendline: Trendline | None = None,
        errBars: ErrorBars | None = None,
        cat: AxDataSource | None = None,
        val: NumDataSource | None = None,
        invertIfNegative: bool | None = None,
        shape: str | None = None,
        xVal: AxDataSource | None = None,
        yVal: NumDataSource | None = None,
        bubbleSize: NumDataSource | None = None,
        bubble3D: bool | None = None,
        marker: Marker | None = None,
        smooth: bool | None = None,
        explosion: int | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        values = kw.pop("values", None)
        xvalues = kw.pop("xvalues", None)
        zvalues = kw.pop("zvalues", None)
        if values is not None and val is None:
            if not isinstance(values, Reference):
                values = Reference(range_string=values)
            val = NumDataSource(numRef=NumRef(f=values))
        if xvalues is not None and xVal is None:
            if not isinstance(xvalues, Reference):
                xvalues = Reference(range_string=xvalues)
            xVal = AxDataSource(numRef=NumRef(f=xvalues))
        if zvalues is not None and bubbleSize is None:
            if not isinstance(zvalues, Reference):
                zvalues = Reference(range_string=zvalues)
            bubbleSize = NumDataSource(
                numRef=NumRef(f=zvalues)
            )
        self.idx = idx
        self.order = order
        self.tx = tx
        self.spPr = (
            spPr
            if spPr is not None
            else GraphicalProperties(ln=LineProperties(prstDash="solid"))
        )
        self.pictureOptions = pictureOptions
        self.dPt = list(dPt)
        self.dLbls = dLbls
        self.trendline = trendline
        self.errBars = errBars
        self.cat = cat
        self.val = val
        self.invertIfNegative = invertIfNegative
        self.shape = shape
        self.xVal = xVal
        self.yVal = yVal
        self.bubbleSize = bubbleSize
        self.bubble3D = bubble3D
        self.marker = marker if marker is not None else Marker()
        self.smooth = smooth
        self.explosion = explosion
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    # openpyxl aliases
    @property
    def title(self) -> SeriesLabel | None:
        return self.tx

    @title.setter
    def title(self, value: SeriesLabel | None) -> None:
        self.tx = value

    @property
    def graphicalProperties(self) -> GraphicalProperties | None:
        return self.spPr

    @graphicalProperties.setter
    def graphicalProperties(self, value: GraphicalProperties | None) -> None:
        self.spPr = value

    @property
    def data_points(self) -> list[DataPoint]:
        return self.dPt

    @data_points.setter
    def data_points(self, value: list[DataPoint]) -> None:
        self.dPt = list(value)

    @property
    def labels(self) -> DataLabelList | None:
        return self.dLbls

    @labels.setter
    def labels(self, value: DataLabelList | None) -> None:
        self.dLbls = value

    @property
    def identifiers(self) -> AxDataSource | None:
        return self.cat

    @identifiers.setter
    def identifiers(self, value: AxDataSource | None) -> None:
        self.cat = value

    @property
    def zVal(self) -> NumDataSource | None:
        return self.bubbleSize

    @zVal.setter
    def zVal(self, value: NumDataSource | None) -> None:
        self.bubbleSize = value

    def to_rust_dict(self, series_type: str = "bar") -> dict[str, Any]:
        """Serialise this series for a chart of the given ``series_type``.

        Emits a flat snake_case dict for the Rust emitter:
        ``{idx, order, title_ref|title_text, values_ref, categories_ref,
        x_values_ref, y_values_ref, bubble_size_ref, graphical_properties,
        marker, smooth, invert_if_negative, data_labels, err_bars,
        trendlines}``.

        References that are :class:`Reference` / ``NumRef`` / ``StrRef``
        instances surface as A1-formula strings (``"Sheet1!$A$1:$A$10"``).
        """
        d: dict[str, Any] = {
            "idx": self.idx,
            "order": self.order,
        }

        # Title — strRef → title_ref; literal value → title_text
        if self.tx is not None:
            if self.tx.strRef is not None and self.tx.strRef.f is not None:
                d["title_ref"] = self.tx.strRef.f
            elif self.tx.v is not None:
                d["title_text"] = str(self.tx.v)

        # Data references — surface as A1 strings
        values_ref = _ref_string(self.val)
        x_values_ref = _ref_string(self.xVal)
        if series_type in ("scatter", "bubble") and x_values_ref is None:
            values_ref = None
        d["values_ref"] = values_ref
        d["categories_ref"] = _ref_string(self.cat)
        d["x_values_ref"] = x_values_ref
        d["y_values_ref"] = _ref_string(self.yVal)
        d["bubble_size_ref"] = _ref_string(self.bubbleSize)

        # spPr — graphical_properties (snake_case)
        if self.spPr is not None:
            gp_dict = self.spPr.to_dict()
            if gp_dict:
                d["graphical_properties"] = _gp_to_snake(gp_dict)

        # Marker — openpyxl emits default "none" markers for line/radar
        # series, even when the public object carries no explicit fields.
        if self.marker is not None and series_type in ("line", "radar", "scatter"):
            md = self.marker.to_dict()
            if not md:
                md = {
                    "symbol": "none",
                    "spPr": {
                        "ln": {
                            "prstDash": "solid",
                        },
                    },
                }
            if md:
                d["marker"] = _marker_to_snake(md)

        if self.dPt:
            d["data_points"] = [_data_point_to_snake(dp.to_dict()) for dp in self.dPt]

        if self.smooth is not None:
            d["smooth"] = self.smooth

        if self.invertIfNegative is not None:
            d["invert_if_negative"] = self.invertIfNegative

        # Data labels per §10.6.2
        if self.dLbls is not None:
            d["data_labels"] = _dlbls_to_snake(self.dLbls.to_dict())

        # Error bars per §10.6.3
        if self.errBars is not None:
            d["err_bars"] = _errbars_to_snake(self.errBars.to_dict())

        # Trendlines per §10.6.4 (list — Series carries 0 or 1 in our model,
        # surface as singleton list when present so consumers always iterate)
        if self.trendline is not None:
            d["trendlines"] = [_trendline_to_snake(self.trendline.to_dict())]

        # Bubble3D flag pass-through (per-series, separate from chart-level)
        if self.bubble3D is not None:
            d["bubble_3d"] = self.bubble3D

        if self.explosion is not None:
            d["explosion"] = self.explosion

        # Shape (bar variant box style)
        if self.shape is not None:
            d["shape"] = self.shape

        # Drop None-valued ref keys to keep the dict tight
        for k in (
            "values_ref",
            "categories_ref",
            "x_values_ref",
            "y_values_ref",
            "bubble_size_ref",
        ):
            if d.get(k) is None:
                d.pop(k, None)

        return d


def _ref_string(src: Any) -> str | None:
    """Pull an A1 formula string out of a NumDataSource/AxDataSource."""
    if src is None:
        return None
    # NumDataSource carries numRef, AxDataSource carries numRef|strRef
    inner = (
        getattr(src, "numRef", None)
        or getattr(src, "strRef", None)
        or None
    )
    if inner is not None and getattr(inner, "f", None) is not None:
        return inner.f
    return None


def _gp_to_snake(gp: dict[str, Any]) -> dict[str, Any]:
    """Translate :class:`GraphicalProperties.to_dict` camelCase → §10.9 snake_case."""
    out: dict[str, Any] = {}
    if "noFill" in gp:
        out["no_fill"] = gp["noFill"]
    if "solidFill" in gp:
        out["solid_fill"] = gp["solidFill"]
    if "ln" in gp:
        ln = dict(gp["ln"])
        ln_out: dict[str, Any] = {}
        if "w" in ln:
            ln_out["w_emu"] = ln["w"]
        if "cap" in ln:
            ln_out["cap"] = ln["cap"]
        if "cmpd" in ln:
            ln_out["cmpd"] = ln["cmpd"]
        if "solidFill" in ln:
            ln_out["solid_fill"] = ln["solidFill"]
        if "prstDash" in ln:
            ln_out["prst_dash"] = ln["prstDash"]
        if "noFill" in ln:
            ln_out["no_fill"] = ln["noFill"]
        out["ln"] = ln_out
    return out


def _marker_to_snake(md: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "symbol" in md:
        out["symbol"] = md["symbol"]
    if "size" in md:
        out["size"] = md["size"]
    if "spPr" in md:
        out["graphical_properties"] = _gp_to_snake(md["spPr"])
    return out


def _data_point_to_snake(dp: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "idx" in dp:
        out["idx"] = dp["idx"]
    if "invertIfNegative" in dp:
        out["invert_if_negative"] = dp["invertIfNegative"]
    if "marker" in dp:
        out["marker"] = _marker_to_snake(dp["marker"])
    if "bubble3D" in dp:
        out["bubble_3d"] = dp["bubble3D"]
    if "explosion" in dp:
        out["explosion"] = dp["explosion"]
    if "spPr" in dp:
        out["graphical_properties"] = _gp_to_snake(dp["spPr"])
    return out


def _dlbls_to_snake(dl: dict[str, Any]) -> dict[str, Any]:
    """Translate :class:`DataLabelList.to_dict` camelCase → §10.6.2 snake_case."""
    out: dict[str, Any] = {}
    mapping = {
        "showVal": "show_val",
        "showCatName": "show_cat_name",
        "showSerName": "show_ser_name",
        "showLegendKey": "show_legend_key",
        "showPercent": "show_percent",
        "showBubbleSize": "show_bubble_size",
        "dLblPos": "position",
        "numFmt": "number_format",
        "separator": "separator",
    }
    for ck, sk in mapping.items():
        if ck in dl and dl[ck] is not None:
            out[sk] = dl[ck]
    txpr = dl.get("txPr")
    if isinstance(txpr, dict):
        runs = _flatten_rich_runs(txpr)
        if runs:
            out["tx_pr_runs"] = runs
    return out


def _flatten_rich_runs(rich: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a :class:`RichText.to_dict()` payload into ``[{text, font}]``.

    Mirrors :meth:`Title.to_dict`'s flattening: each ``<a:r>`` becomes a
    ``{"text": str, "font": {name, size, bold, italic, color, underline}}``
    dict that the Rust emitter consumes via the ``TitleRun`` shape.
    """
    out: list[dict[str, Any]] = []
    paragraphs = rich.get("p") or []
    for para in paragraphs:
        for r in para.get("r", []) or []:
            text = r.get("t", "") or ""
            font: dict[str, Any] = {}
            rpr = r.get("rPr")
            if isinstance(rpr, dict):
                if rpr.get("latin") is not None:
                    font["name"] = rpr["latin"]
                sz = rpr.get("sz")
                if sz is not None:
                    try:
                        font["size"] = int(sz) // 100
                    except (TypeError, ValueError):
                        font["size"] = sz
                if rpr.get("b") is not None:
                    font["bold"] = rpr["b"]
                if rpr.get("i") is not None:
                    font["italic"] = rpr["i"]
                if rpr.get("u") is not None:
                    font["underline"] = rpr["u"] not in (None, "none")
                sf = rpr.get("solidFill")
                if sf is not None:
                    if isinstance(sf, str):
                        font["color"] = sf
                    else:
                        rgb = (
                            getattr(sf, "srgbClr", None)
                            or getattr(sf, "value", None)
                            or getattr(sf, "rgb", None)
                        )
                        if rgb is not None and not isinstance(rgb, str):
                            rgb = getattr(rgb, "val", None) or str(rgb)
                        if rgb is not None:
                            font["color"] = rgb
            out.append({"text": text, "font": font or None})
    return out


def _errbars_to_snake(eb: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "errDir" in eb:
        out["direction"] = eb["errDir"]
    if "errBarType" in eb:
        out["err_bar_type"] = eb["errBarType"]
    if "errValType" in eb:
        out["err_val_type"] = eb["errValType"]
    if "noEndCap" in eb:
        out["no_end_cap"] = eb["noEndCap"]
    if "val" in eb:
        out["val"] = eb["val"]
    plus = eb.get("plus")
    if plus is not None:
        # plus may be a NumDataSource-shaped dict {numRef:{f, ...}} or a string
        if isinstance(plus, dict):
            inner = plus.get("numRef") or plus.get("strRef")
            if isinstance(inner, dict) and inner.get("f"):
                out["plus_ref"] = inner["f"]
        elif isinstance(plus, str):
            out["plus_ref"] = plus
    minus = eb.get("minus")
    if minus is not None:
        if isinstance(minus, dict):
            inner = minus.get("numRef") or minus.get("strRef")
            if isinstance(inner, dict) and inner.get("f"):
                out["minus_ref"] = inner["f"]
        elif isinstance(minus, str):
            out["minus_ref"] = minus
    return out


def _trendline_to_snake(t: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "trendlineType" in t:
        out["trendline_type"] = t["trendlineType"]
    if "name" in t:
        out["name"] = t["name"]
    if "order" in t:
        out["order"] = t["order"]
    if "period" in t:
        out["period"] = t["period"]
    if "forward" in t:
        out["forward"] = t["forward"]
    if "backward" in t:
        out["backward"] = t["backward"]
    if "intercept" in t:
        out["intercept"] = t["intercept"]
    if "dispEq" in t:
        out["disp_eq"] = t["dispEq"]
    if "dispRSqr" in t:
        out["disp_r_sqr"] = t["dispRSqr"]
    if "spPr" in t:
        out["graphical_properties"] = _gp_to_snake(t["spPr"])
    return out


class XYSeries(Series):
    """Series for chart types with explicit X/Y (Scatter, Bubble).

    Identical storage to :class:`Series`; the dedicated subclass exists so
    callers can ``isinstance(s, XYSeries)`` to gate xVal/yVal-only logic.
    """


_SERIES_XML_MODEL_NAMES = ("SeriesLabel", "Series", "XYSeries")


def _xml_model_names(cls: type) -> tuple[str, ...]:
    return tuple(getattr(cls, "__attrs__", ())) + tuple(getattr(cls, "__elements__", ()))


def _to_openpyxl_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_openpyxl_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_openpyxl_model(item) for item in value)

    data_source_value = _data_source_to_openpyxl_model(value)
    if data_source_value is not value:
        return data_source_value

    cls = value.__class__
    upstream_cls = _resolve_openpyxl_class(cls.__module__, cls.__name__)
    if upstream_cls is None or cls is upstream_cls:
        return value

    instance_elements = tuple(getattr(value, "__elements__", ()))
    names = instance_elements or _xml_model_names(upstream_cls)
    if cls.__name__ == "Series":
        names = instance_elements or _all_series_elements()
    if not names:
        return value

    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_openpyxl_model(getattr(value, name))
    model = upstream_cls(**kwargs)
    if hasattr(value, "__elements__"):
        model.__elements__ = tuple(getattr(value, "__elements__"))
    return model


def _from_openpyxl_series_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__) or _all_series_elements()
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_series_model(getattr(value, name))
    native = native_cls(**kwargs)
    native.__elements__ = tuple(getattr(value, "__elements__", ()))
    return native


def _to_native_series_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_series_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_series_model(item) for item in value)

    native_data_source = _to_native_data_source_model(value)
    if native_data_source is not value:
        return native_data_source

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _SERIES_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_series_model(native_cls, value)


def _series_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    elements = tuple(getattr(self, "__elements__", ()))
    if not elements:
        return upstream.to_tree(tagname=tagname, idx=idx)
    upstream_cls = upstream.__class__
    original_elements = getattr(upstream_cls, "__elements__", ())
    upstream_cls.__elements__ = elements
    try:
        return upstream.to_tree(tagname=tagname, idx=idx)
    finally:
        upstream_cls.__elements__ = original_elements


def _series_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_series_model(cls, upstream_cls.from_tree(node))


def _series_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_series_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _series_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_series_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _series_eq  # type: ignore[attr-defined]


def series_factory(
    values: Any,
    xvalues: Any | None = None,
    zvalues: Any | None = None,
    title: str | SeriesLabel | None = None,
    title_from_data: bool = False,
) -> Series:
    """Factory that wraps cell ranges into a :class:`Series` of the right shape.

    Mirrors :func:`openpyxl.chart.series_factory.SeriesFactory`. The
    ``title_from_data`` flag pops the first cell of ``values`` and uses
    its sheet-qualified address as a strRef title (so a column header
    becomes the legend label).
    """
    if not isinstance(values, Reference):
        values = Reference(range_string=values)

    series_title: SeriesLabel | None = None
    if title_from_data:
        cell = values.pop()
        title_str = f"{values.sheetname}!{cell}"
        series_title = SeriesLabel(strRef=StrRef(title_str))
    elif title is not None:
        if isinstance(title, SeriesLabel):
            series_title = title
        else:
            series_title = SeriesLabel(v=str(title))

    val = NumDataSource(numRef=NumRef(f=values))

    if xvalues is not None:
        if not isinstance(xvalues, Reference):
            xvalues = Reference(range_string=xvalues)
        series: Series = XYSeries()
        series.yVal = val
        series.xVal = AxDataSource(numRef=NumRef(f=xvalues))
        if zvalues is not None:
            if not isinstance(zvalues, Reference):
                zvalues = Reference(range_string=zvalues)
            series.bubbleSize = NumDataSource(numRef=NumRef(f=zvalues))
    else:
        series = Series()
        series.val = val

    if series_title is not None:
        series.tx = series_title

    return series


# openpyxl-style camelCase alias
SeriesFactory = series_factory

_install_series_xml_methods(SeriesLabel, Series, XYSeries)

_install_openpyxl_iter(SeriesLabel, Series, XYSeries)


__all__ = [
    "Series",
    "SeriesFactory",
    "SeriesLabel",
    "XYSeries",
    "attribute_mapping",
    "series_factory",
]

__getattr__ = _openpyxl_name_fallback(globals())
