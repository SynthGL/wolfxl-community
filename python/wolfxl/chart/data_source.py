"""Cell-range and literal data sources for chart series.

Mirrors :mod:`openpyxl.chart.data_source`. Each class is a thin attribute
carrier with a ``to_dict()`` method matching the camelCase XML names so
the Rust emitter can serialise it.

* ``NumRef`` / ``StrRef`` — references to a cell range, with optional
  cached values (``numCache`` / ``strCache``).
* ``NumLit`` (a.k.a. ``NumData``) / ``StrLit`` (``StrData``) — embedded
  literal values, used for charts not backed by a sheet.
* ``NumDataSource`` / ``AxDataSource`` — wrappers chosen by
  ``Series.val`` / ``Series.cat`` / etc.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import (
    _install_openpyxl_iter,
    _make_serialisable,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)

from .reference import Reference


class NumFmt:
    """`<c:numFmt>` — number format with optional source-link flag."""

    __slots__ = ("formatCode", "sourceLinked")

    def __init__(self, formatCode: str | None = None, sourceLinked: bool = False) -> None:
        self.formatCode = formatCode
        self.sourceLinked = sourceLinked

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"sourceLinked": self.sourceLinked}
        if self.formatCode is not None:
            d["formatCode"] = self.formatCode
        return d


class NumVal:
    """A single numeric cache point (`<c:pt idx="..."><c:v>..</c:v></c:pt>`)."""

    __slots__ = ("idx", "formatCode", "v")

    def __init__(
        self,
        idx: int | None = None,
        formatCode: str | None = None,
        v: Any | None = None,
    ) -> None:
        self.idx = idx
        self.formatCode = formatCode
        self.v = v

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.idx is not None:
            d["idx"] = self.idx
        if self.formatCode is not None:
            d["formatCode"] = self.formatCode
        if self.v is not None:
            d["v"] = self.v
        return d


class NumData:
    """`<c:numCache>` / `<c:numLit>` — sequence of numeric points."""

    __slots__ = ("formatCode", "ptCount", "pt", "extLst")

    def __init__(
        self,
        formatCode: str | None = None,
        ptCount: int | None = None,
        pt: list[NumVal] | tuple[NumVal, ...] = (),
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.formatCode = formatCode
        self.ptCount = ptCount
        self.pt = list(pt)
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.formatCode is not None:
            d["formatCode"] = self.formatCode
        if self.ptCount is not None:
            d["ptCount"] = self.ptCount
        if self.pt:
            d["pt"] = [p.to_dict() for p in self.pt]
        return d


# alias matching the openpyxl name; same type, separate identity for callers
NumLit = NumData


class StrVal:
    """A single string cache point."""

    __slots__ = ("idx", "v")

    def __init__(self, idx: int = 0, v: str | None = None) -> None:
        self.idx = idx
        self.v = v

    def to_dict(self) -> dict[str, Any]:
        return {"idx": self.idx, "v": self.v}


class StrData:
    """`<c:strCache>` / `<c:strLit>`."""

    __slots__ = ("ptCount", "pt", "extLst")

    def __init__(
        self,
        ptCount: int | None = None,
        pt: list[StrVal] | tuple[StrVal, ...] = (),
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.ptCount = ptCount
        self.pt = list(pt)
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.ptCount is not None:
            d["ptCount"] = self.ptCount
        if self.pt:
            d["pt"] = [p.to_dict() for p in self.pt]
        return d


StrLit = StrData


def _ref_to_str(f: Any) -> str | None:
    """Coerce a :class:`Reference`, raw string, or None into a formula string."""
    if f is None:
        return None
    if isinstance(f, Reference):
        return str(f)
    return str(f)


class NumRef:
    """`<c:numRef>` — a numeric data range with optional cache."""

    __slots__ = ("f", "numCache", "extLst")

    def __init__(
        self,
        f: Any | None = None,
        numCache: NumData | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.f = _ref_to_str(f)
        self.numCache = numCache
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    @property
    def ref(self) -> str | None:
        return self.f

    @ref.setter
    def ref(self, value: Any) -> None:
        self.f = _ref_to_str(value)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"f": self.f}
        if self.numCache is not None:
            d["numCache"] = self.numCache.to_dict()
        return d


class StrRef:
    """`<c:strRef>` — a string data range with optional cache."""

    __slots__ = ("f", "strCache", "extLst")

    def __init__(
        self,
        f: Any | None = None,
        strCache: StrData | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.f = _ref_to_str(f)
        self.strCache = strCache
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"f": self.f}
        if self.strCache is not None:
            d["strCache"] = self.strCache.to_dict()
        return d


class NumDataSource:
    """`<c:val>` / `<c:bubbleSize>` / `<c:yVal>` — wraps numRef or numLit."""

    __slots__ = ("numRef", "numLit")

    def __init__(self, numRef: NumRef | None = None, numLit: NumData | None = None) -> None:
        self.numRef = numRef
        self.numLit = numLit

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.numRef is not None:
            d["numRef"] = self.numRef.to_dict()
        if self.numLit is not None:
            d["numLit"] = self.numLit.to_dict()
        return d


class AxDataSource:
    """`<c:cat>` / `<c:xVal>` — wraps any of {numRef, numLit, strRef, strLit, multiLvlStrRef}."""

    __slots__ = ("numRef", "numLit", "strRef", "strLit", "multiLvlStrRef")

    def __init__(
        self,
        numRef: NumRef | None = None,
        numLit: NumData | None = None,
        strRef: StrRef | None = None,
        strLit: StrData | None = None,
        multiLvlStrRef: Any | None = None,
    ) -> None:
        if not any([numRef, numLit, strRef, strLit, multiLvlStrRef]):
            raise TypeError("AxDataSource requires at least one source")
        self.numRef = numRef
        self.numLit = numLit
        self.strRef = strRef
        self.strLit = strLit
        self.multiLvlStrRef = multiLvlStrRef

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.numRef is not None:
            d["numRef"] = self.numRef.to_dict()
        if self.numLit is not None:
            d["numLit"] = self.numLit.to_dict()
        if self.strRef is not None:
            d["strRef"] = self.strRef.to_dict()
        if self.strLit is not None:
            d["strLit"] = self.strLit.to_dict()
        if self.multiLvlStrRef is not None:
            d["multiLvlStrRef"] = (
                self.multiLvlStrRef.to_dict()
                if hasattr(self.multiLvlStrRef, "to_dict")
                else self.multiLvlStrRef
            )
        return d


def _openpyxl_class(name: str) -> type:
    return _resolve_openpyxl_class(__name__, name) or _make_serialisable(
        name,
        module_name=__name__,
    )


Level = _openpyxl_class("Level")
MultiLevelStrData = _openpyxl_class("MultiLevelStrData")
MultiLevelStrRef = _openpyxl_class("MultiLevelStrRef")


_DATA_SOURCE_XML_MODEL_NAMES = (
    "NumFmt",
    "NumVal",
    "NumData",
    "StrVal",
    "StrData",
    "NumRef",
    "StrRef",
    "NumDataSource",
    "AxDataSource",
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
            kwargs[name] = _to_openpyxl_model(getattr(value, name))
    return upstream_cls(**kwargs)


def _from_openpyxl_data_source_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_data_source_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_data_source_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_data_source_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_data_source_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if (
        not isinstance(native_cls, type)
        or native_cls.__name__ not in _DATA_SOURCE_XML_MODEL_NAMES
    ):
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_data_source_model(native_cls, value)


def _data_source_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _data_source_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_data_source_model(cls, upstream_cls.from_tree(node))


def _data_source_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_data_source_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _data_source_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_data_source_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _data_source_eq  # type: ignore[attr-defined]


_install_data_source_xml_methods(
    NumFmt,
    NumVal,
    NumData,
    StrVal,
    StrData,
    NumRef,
    StrRef,
    NumDataSource,
    AxDataSource,
)


_install_openpyxl_iter(
    NumFmt,
    NumData,
    StrVal,
    StrData,
    NumRef,
    StrRef,
    NumDataSource,
    AxDataSource,
)

__all__ = [
    "AxDataSource",
    "NumData",
    "NumDataSource",
    "NumFmt",
    "NumLit",
    "NumRef",
    "NumVal",
    "StrData",
    "StrLit",
    "StrRef",
    "StrVal",
    "Level",
    "MultiLevelStrData",
    "MultiLevelStrRef",
]

__getattr__ = _openpyxl_name_fallback(globals())
