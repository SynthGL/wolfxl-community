"""Rich-text primitives for chart titles, data labels, and axis labels.

A trimmed mirror of :mod:`openpyxl.chart.text` — we keep the public API
surface (``RichText``, ``Text``, ``Paragraph``, ``RegularTextRun``,
``CharacterProperties``, ``ParagraphProperties``) but implement them as
plain attribute carriers so the Rust emitter can serialise them with
minimal Python side-validation.
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import (
    _install_openpyxl_iter,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)
from wolfxl.chart.data_source import _to_native_data_source_model


class CharacterProperties:
    """`<a:rPr>` — run-level rich-text properties.

    ``lang`` (e.g. ``"en-US"``), ``sz`` (font size in 1/100 pt — 1100=11pt),
    ``b`` (bold), ``i`` (italic), ``u`` (underline style), ``strike``,
    ``solidFill`` (hex colour, e.g. ``"FF0000"``), ``latin`` (font face),
    ``baseline`` (super/subscript offset).
    """

    __slots__ = (
        "lang",
        "sz",
        "b",
        "i",
        "u",
        "strike",
        "solidFill",
        "latin",
        "baseline",
        "_extra",
    )

    def __init__(
        self,
        lang: str | None = None,
        sz: int | None = None,
        b: bool | None = None,
        i: bool | None = None,
        u: str | None = None,
        strike: str | None = None,
        solidFill: str | None = None,
        latin: str | None = None,
        baseline: int | None = None,
        **kw: Any,
    ) -> None:
        self.lang = lang
        self.sz = sz
        self.b = b
        self.i = i
        self.u = u
        self.strike = strike
        self.solidFill = solidFill
        self.latin = latin
        self.baseline = baseline
        self._extra = dict(kw)

    def __getattr__(self, name: str) -> Any:
        try:
            extra = object.__getattribute__(self, "_extra")
        except AttributeError as exc:
            raise AttributeError(name) from exc
        if name in extra:
            return extra[name]
        raise AttributeError(name)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for slot in self.__slots__:
            if slot == "_extra":
                continue
            v = getattr(self, slot)
            if v is not None:
                d[slot] = v
        return d


class ParagraphProperties:
    """`<a:pPr>` — paragraph-level properties (alignment, default run props)."""

    __slots__ = ("algn", "defRPr", "_extra")

    def __init__(
        self,
        algn: str | None = None,
        defRPr: CharacterProperties | None = None,
        **kw: Any,
    ) -> None:
        self.algn = algn
        self.defRPr = defRPr
        self._extra = dict(kw)

    def __getattr__(self, name: str) -> Any:
        try:
            extra = object.__getattribute__(self, "_extra")
        except AttributeError as exc:
            raise AttributeError(name) from exc
        if name in extra:
            return extra[name]
        raise AttributeError(name)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.algn is not None:
            d["algn"] = self.algn
        if self.defRPr is not None:
            d["defRPr"] = self.defRPr.to_dict()
        return d


class RegularTextRun:
    """`<a:r>` — a single text run with optional formatting."""

    __slots__ = ("rPr", "t")

    def __init__(
        self,
        rPr: CharacterProperties | None = None,
        t: str = "",
    ) -> None:
        self.rPr = rPr
        self.t = t

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"t": self.t}
        if self.rPr is not None:
            d["rPr"] = self.rPr.to_dict()
        return d


class LineBreak:
    """`<a:br>` — explicit line break inside a paragraph."""

    __slots__ = ("rPr",)

    def __init__(self, rPr: CharacterProperties | None = None) -> None:
        self.rPr = rPr

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"_kind": "br"}
        if self.rPr is not None:
            d["rPr"] = self.rPr.to_dict()
        return d


class Paragraph:
    """`<a:p>` — a paragraph with optional ``pPr`` and a sequence of runs."""

    __slots__ = ("pPr", "r", "_extra")

    def __init__(
        self,
        pPr: ParagraphProperties | None = None,
        r: list[RegularTextRun] | None = None,
        **kw: Any,
    ) -> None:
        self.pPr = pPr
        self.r = list(r) if r is not None else [RegularTextRun()]
        self._extra = dict(kw)

    def __getattr__(self, name: str) -> Any:
        try:
            extra = object.__getattribute__(self, "_extra")
        except AttributeError as exc:
            raise AttributeError(name) from exc
        if name in extra:
            return extra[name]
        raise AttributeError(name)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.pPr is not None:
            d["pPr"] = self.pPr.to_dict()
        if self.r:
            d["r"] = [r.to_dict() for r in self.r]
        return d


class RichTextProperties:
    """`<a:bodyPr>` — chart-text body properties.

    Optional attributes the chart spec ships:
    ``rot``, ``spcFirstLastPara``, ``vertOverflow``, ``vert``, ``wrap``,
    ``anchor``, ``anchorCtr``. We carry them as plain attributes.
    """

    __slots__ = ("rot", "spcFirstLastPara", "vertOverflow", "vert", "wrap", "anchor", "anchorCtr")

    def __init__(self, **kwargs: Any) -> None:
        for slot in self.__slots__:
            setattr(self, slot, kwargs.get(slot))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for slot in self.__slots__:
            v = getattr(self, slot)
            if v is not None:
                d[slot] = v
        return d


class RichText:
    """`<c:rich>` — the rich-text body of a title or label."""

    __slots__ = ("bodyPr", "lstStyle", "p")

    def __init__(
        self,
        bodyPr: RichTextProperties | None = None,
        lstStyle: Any | None = None,
        p: list[Paragraph] | None = None,
    ) -> None:
        self.bodyPr = bodyPr if bodyPr is not None else RichTextProperties()
        self.lstStyle = lstStyle
        self.p = list(p) if p else [Paragraph()]

    # openpyxl alias
    @property
    def paragraphs(self) -> list[Paragraph]:
        return self.p

    @paragraphs.setter
    def paragraphs(self, value: list[Paragraph]) -> None:
        self.p = list(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bodyPr": self.bodyPr.to_dict() if self.bodyPr else {},
            "p": [para.to_dict() for para in self.p],
        }


class Text:
    """`<c:tx>` — title-text container; either a strRef or a rich body."""

    __slots__ = ("strRef", "rich")

    def __init__(self, strRef: Any | None = None, rich: RichText | None = None) -> None:
        self.strRef = strRef
        self.rich = rich if rich is not None else RichText()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.strRef is not None:
            from .data_source import StrRef  # local to avoid cycle
            if isinstance(self.strRef, StrRef):
                d["strRef"] = self.strRef.to_dict()
            else:
                d["strRef"] = self.strRef
        else:
            d["rich"] = self.rich.to_dict()
        return d


_install_openpyxl_iter(
    CharacterProperties,
    ParagraphProperties,
    RegularTextRun,
    RichTextProperties,
    RichText,
    Text,
)

_TEXT_XML_MODEL_NAMES = (
    "CharacterProperties",
    "ParagraphProperties",
    "RegularTextRun",
    "LineBreak",
    "Paragraph",
    "RichTextProperties",
    "RichText",
    "Text",
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


def _from_openpyxl_text_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_text_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_text_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_text_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_text_model(item) for item in value)
    if value.__class__.__module__.startswith("openpyxl.chart.data_source"):
        return _to_native_data_source_model(value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _TEXT_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_text_model(native_cls, value)


def _text_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _text_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_text_model(cls, upstream_cls.from_tree(node))


def _text_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_text_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _text_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_text_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _text_eq  # type: ignore[attr-defined]


_install_text_xml_methods(
    CharacterProperties,
    ParagraphProperties,
    RegularTextRun,
    LineBreak,
    Paragraph,
    RichTextProperties,
    RichText,
    Text,
)

__all__ = [
    "CharacterProperties",
    "LineBreak",
    "Paragraph",
    "ParagraphProperties",
    "RegularTextRun",
    "RichText",
    "RichTextProperties",
    "Text",
]

__getattr__ = _openpyxl_name_fallback(globals())
