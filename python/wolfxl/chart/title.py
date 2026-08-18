"""`<c:title>` — chart and axis titles.

Mirrors :class:`openpyxl.chart.title.Title`. The convenience descriptor
``TitleDescriptor`` accepts a string and inflates it into a
single-paragraph rich-text title (matching openpyxl's ``title_maker``).
"""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _openpyxl_name_fallback, _resolve_openpyxl_class

from .layout import Layout
from .shapes import GraphicalProperties
from .text import (
    CharacterProperties,
    Paragraph,
    ParagraphProperties,
    RegularTextRun,
    RichText,
    Text,
)


class Title:
    """A chart title. ``tx`` holds the rich body; ``layout`` positions it.

    Attributes
    ----------
    tx : :class:`Text` | None
        Rich body (or strRef-bound) text container.
    layout : :class:`Layout` | None
        Manual placement override.
    overlay : bool | None
        Whether the title overlays the plot area.
    spPr : :class:`GraphicalProperties` | None
        Shape properties for the title's container.
    txPr : :class:`RichText` | None
        Default text formatting if ``tx.rich`` is empty.
    """

    __slots__ = ("tx", "layout", "overlay", "spPr", "txPr", "extLst")

    def __init__(
        self,
        tx: Text | None = None,
        layout: Layout | None = None,
        overlay: bool | None = None,
        spPr: GraphicalProperties | None = None,
        txPr: RichText | None = None,
        extLst: Any = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.tx = tx if tx is not None else Text()
        self.layout = layout
        self.overlay = overlay
        self.spPr = spPr
        self.txPr = txPr
        self.extLst = extLst if extLst is not None else kw.get("extLst")

    # openpyxl aliases
    @property
    def text(self) -> Text | None:
        return self.tx

    @text.setter
    def text(self, value: Text | None) -> None:
        self.tx = value if value is not None else Text()

    @property
    def body(self) -> RichText | None:
        return self.txPr

    @body.setter
    def body(self, value: RichText | None) -> None:
        self.txPr = value

    @property
    def graphicalProperties(self) -> GraphicalProperties | None:
        return self.spPr

    @graphicalProperties.setter
    def graphicalProperties(self, value: GraphicalProperties | None) -> None:
        self.spPr = value

    def to_dict(self) -> dict[str, Any]:
        """Emit the §10.3 shape: ``{text, runs, overlay, layout}``.

        The rich-text body (``self.tx.rich``) is flattened into a list
        of runs ``[{text, font: {name, size, bold, italic, color}}, ...]``.
        If every run carries the same plain text and no formatting,
        ``text`` is also surfaced as a fast-path string.
        """
        runs: list[dict[str, Any]] = []
        text_parts: list[str] = []
        all_plain = True

        if self.tx is not None and self.tx.rich is not None:
            for para in self.tx.rich.p:
                for r in para.r:
                    text_parts.append(r.t or "")
                    font: dict[str, Any] = {}
                    if r.rPr is not None:
                        if r.rPr.latin is not None:
                            font["name"] = r.rPr.latin
                        if r.rPr.sz is not None:
                            # CharacterProperties stores size as 1/100 pt;
                            # surface as integer points.
                            try:
                                font["size"] = int(r.rPr.sz) // 100
                            except (TypeError, ValueError):
                                font["size"] = r.rPr.sz
                        if r.rPr.b is not None:
                            font["bold"] = r.rPr.b
                        if r.rPr.i is not None:
                            font["italic"] = r.rPr.i
                        if r.rPr.solidFill is not None:
                            # Coerce openpyxl ColorChoice
                            # (e.g. ``ColorChoice(srgbClr="FF0000")``) to
                            # the hex string the Rust emitter wants.
                            sf = r.rPr.solidFill
                            if isinstance(sf, str):
                                font["color"] = sf
                            else:
                                # Try common openpyxl shapes:
                                # ColorChoice.srgbClr → "FF0000" (string)
                                # ColorChoice.srgbClr → RGBPercent / RGBHex
                                #   (object with .val attribute)
                                rgb = getattr(sf, "srgbClr", None)
                                if rgb is None and hasattr(sf, "value"):
                                    rgb = sf.value
                                if rgb is not None and not isinstance(rgb, str):
                                    rgb = getattr(rgb, "val", None) or str(rgb)
                                font["color"] = rgb if rgb is not None else str(sf)
                        if font:
                            all_plain = False
                    runs.append({"text": r.t or "", "font": font or None})

        text_str: str | None = None
        if all_plain and text_parts:
            text_str = "\n".join(text_parts)

        d: dict[str, Any] = {
            "text": text_str,
            "runs": runs if runs else None,
            "overlay": self.overlay,
            "layout": self.layout.to_dict() if self.layout is not None else None,
        }
        # Drop wholly-empty title (no text, no runs, no overlay, no layout)
        if (
            d["text"] is None
            and d["runs"] is None
            and d["overlay"] is None
            and d["layout"] is None
        ):
            return {}
        return d


def title_maker(text: str) -> Title:
    """Inflate a bare string into a single-run rich-text :class:`Title`.

    Mirrors openpyxl's ``title_maker`` — splits on ``"\\n"`` so multi-line
    titles emit one ``<a:p>`` per line.
    """
    title = Title()
    paraprops = ParagraphProperties(defRPr=CharacterProperties())
    paras = [
        Paragraph(pPr=paraprops, r=[RegularTextRun(t=line)])
        for line in text.split("\n")
    ]
    if title.tx is None or title.tx.rich is None:
        title.tx = Text(rich=RichText())
    title.tx.rich.paragraphs = paras
    return title


class TitleDescriptor:
    """Descriptor that auto-inflates string assignments into :class:`Title`.

    ``chart.title = "Sales"`` becomes ``Title(...)`` with a single-run
    rich body — matching openpyxl's behaviour exactly.
    """

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr = "_" + name

    def __get__(self, instance: Any, owner: type | None = None) -> Title | None:
        if instance is None:
            return self  # type: ignore[return-value]
        return getattr(instance, self._attr, None)

    def __set__(self, instance: Any, value: Any) -> None:
        if value is None:
            setattr(instance, self._attr, None)
            return
        if isinstance(value, str):
            value = title_maker(value)
        elif isinstance(value, RichText):
            # wolfxl-typed RichText.
            value = Title(tx=Text(rich=value))
        elif not isinstance(value, Title) and (
            type(value).__name__ == "RichText"
            and hasattr(value, "p")
        ):
            # openpyxl-typed RichText (or any duck-typed object with a
            # ``.p`` attribute holding a paragraph list). Convert to
            # wolfxl's RichText so the downstream ``to_dict`` path picks
            # up the runs.
            value = Title(tx=Text(rich=_coerce_openpyxl_richtext(value)))
        if not isinstance(value, Title):
            raise TypeError(
                f"Title must be str, Title, or RichText, got {type(value).__name__}"
            )
        setattr(instance, self._attr, value)


def _coerce_openpyxl_richtext(value: Any) -> RichText:
    """Convert an openpyxl ``chart.text.RichText`` into wolfxl's.

    Reads ``value.bodyPr`` and ``value.p`` (a list of openpyxl
    ``Paragraph`` objects) and rebuilds a wolfxl
    :class:`RichText`. Run-level properties (``Paragraph.r[i].rPr``)
    are duck-typed; only the attributes wolfxl's ``CharacterProperties``
    understands are copied (``b``, ``i``, ``u``, ``sz``, ``solidFill``,
    ``latin``, ``baseline``, ``strike``, ``lang``).

    Falls back to a plain wrapping if ``value`` doesn't expose ``.p``.
    """
    from .text import (
        CharacterProperties,
        Paragraph as _WPara,
        ParagraphProperties as _WParaProps,
        RegularTextRun as _WRun,
        RichTextProperties as _WBodyPr,
    )

    paras_in = getattr(value, "p", None) or []
    paras_out: list[_WPara] = []
    for p in paras_in:
        runs_in = getattr(p, "r", None) or []
        runs_out: list[_WRun] = []
        for r in runs_in:
            t_val = getattr(r, "t", "") or ""
            rpr_in = getattr(r, "rPr", None)
            rpr_out: CharacterProperties | None = None
            if rpr_in is not None:
                rpr_out = CharacterProperties(
                    lang=getattr(rpr_in, "lang", None),
                    sz=getattr(rpr_in, "sz", None),
                    b=getattr(rpr_in, "b", None),
                    i=getattr(rpr_in, "i", None),
                    u=getattr(rpr_in, "u", None),
                    strike=getattr(rpr_in, "strike", None),
                    solidFill=getattr(rpr_in, "solidFill", None),
                    latin=getattr(rpr_in, "latin", None),
                    baseline=getattr(rpr_in, "baseline", None),
                )
            runs_out.append(_WRun(rPr=rpr_out, t=t_val))
        ppr_in = getattr(p, "pPr", None)
        ppr_out: _WParaProps | None = None
        if ppr_in is not None:
            ppr_out = _WParaProps(algn=getattr(ppr_in, "algn", None))
        paras_out.append(_WPara(pPr=ppr_out, r=runs_out))
    body = getattr(value, "bodyPr", None)
    body_out = _WBodyPr() if body is None else _WBodyPr(
        rot=getattr(body, "rot", None),
        anchor=getattr(body, "anchor", None),
        wrap=getattr(body, "wrap", None),
    )
    return RichText(bodyPr=body_out, p=paras_out)


_TITLE_XML_MODEL_NAMES = (
    "Title",
    "Text",
    "RichText",
    "RichTextProperties",
    "Paragraph",
    "ParagraphProperties",
    "RegularTextRun",
    "CharacterProperties",
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
            attr_value = getattr(value, name)
            if attr_value == []:
                continue
            kwargs[name] = _to_openpyxl_model(attr_value)
    return upstream_cls(**kwargs)


def _from_openpyxl_title_model(native_cls: type, value: Any) -> Any:
    names = _xml_model_names(value.__class__)
    kwargs: dict[str, Any] = {}
    for name in names:
        if hasattr(value, name):
            kwargs[name] = _to_native_title_model(getattr(value, name))
    return native_cls(**kwargs)


def _to_native_title_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_native_title_model(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_native_title_model(item) for item in value)

    native_cls = globals().get(value.__class__.__name__)
    if not isinstance(native_cls, type) or native_cls.__name__ not in _TITLE_XML_MODEL_NAMES:
        return value
    upstream_cls = _resolve_openpyxl_class(__name__, native_cls.__name__)
    if upstream_cls is None or not isinstance(value, upstream_cls):
        return value
    return _from_openpyxl_title_model(native_cls, value)


def _title_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _title_from_tree(cls: type, node: Any) -> Any:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_title_model(cls, upstream_cls.from_tree(node))


def _title_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


def _install_title_xml_methods(*classes: type) -> None:
    for cls in classes:
        if not hasattr(cls, "to_tree"):
            cls.to_tree = _title_to_tree  # type: ignore[attr-defined]
        if "from_tree" not in cls.__dict__:
            cls.from_tree = classmethod(_title_from_tree)  # type: ignore[attr-defined]
        if "__eq__" not in cls.__dict__:
            cls.__eq__ = _title_eq  # type: ignore[attr-defined]


_install_title_xml_methods(Title)


__all__ = ["Title", "TitleDescriptor", "title_maker"]

__getattr__ = _openpyxl_name_fallback(globals())
