"""XML helper functions exposed under the openpyxl-shaped path."""

from __future__ import annotations

import re
from functools import partial
from xml.etree.ElementTree import iterparse as _stdlib_iterparse

from wolfxl.xml import DEFUSEDXML, LXML
from wolfxl.xml.constants import (
    CHART_DRAWING_NS,
    CHART_NS,
    COREPROPS_NS,
    CUSTPROPS_NS,
    DCTERMS_NS,
    DCTERMS_PREFIX,
    DRAWING_NS,
    REL_NS,
    SHEET_DRAWING_NS,
    SHEET_MAIN_NS,
    VTYPES_NS,
    XML_NS,
)

if LXML:
    from lxml.etree import (  # type: ignore[import-untyped]
        Element,
        QName,
        SubElement,
        XMLParser,
        fromstring as _fromstring,
        register_namespace,
        tostring as _tostring,
        xmlfile,
    )

    _safe_parser = XMLParser(resolve_entities=False)
    safe_parser = _safe_parser

    def fromstring(text, parser=None, **kwargs):  # type: ignore[no-untyped-def]
        _reject_unsafe_xml_input(text)
        if _is_file_like_xml_input(text):
            raise ValueError("fromstring expects XML bytes or text, not a file object")
        return _fromstring(text, parser=parser or _safe_parser, **kwargs)
else:
    from xml.etree.ElementTree import (  # type: ignore[assignment]
        Element,
        QName,
        SubElement,
        fromstring as _stdlib_fromstring,
        register_namespace,
        tostring as _tostring,
    )

    try:
        from et_xmlfile import xmlfile  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover - optional streaming writer dependency
        class xmlfile:  # type: ignore[no-redef]
            def __init__(self, *args: object, **kwargs: object) -> None:
                raise ImportError("et_xmlfile is required for xmlfile streaming")

    if DEFUSEDXML:
        from defusedxml.ElementTree import fromstring as _defused_fromstring

        _safe_fromstring = _defused_fromstring
    else:
        _safe_fromstring = _stdlib_fromstring
    safe_parser = None

    def fromstring(text, parser=None, **kwargs):  # type: ignore[no-untyped-def]
        if _is_file_like_xml_input(text):
            raise ValueError("fromstring expects XML bytes or text, not a file object")
        _reject_unsafe_xml_input(text)
        if parser is None and not kwargs:
            return _safe_fromstring(text)
        return _safe_fromstring(text, parser=parser, **kwargs)

iterparse = _stdlib_iterparse
if DEFUSEDXML:
    from defusedxml.ElementTree import iterparse  # type: ignore[assignment]

register_namespace(DCTERMS_PREFIX, DCTERMS_NS)
register_namespace("dcmitype", "http://purl.org/dc/dcmitype/")
register_namespace("cp", COREPROPS_NS)
register_namespace("c", CHART_NS)
register_namespace("a", DRAWING_NS)
register_namespace("s", SHEET_MAIN_NS)
register_namespace("r", REL_NS)
register_namespace("vt", VTYPES_NS)
register_namespace("xdr", SHEET_DRAWING_NS)
register_namespace("cdr", CHART_DRAWING_NS)
register_namespace("xml", XML_NS)
register_namespace("cust", CUSTPROPS_NS)

tostring = partial(_tostring, encoding="utf-8")

NS_REGEX = re.compile(r"({(?P<namespace>.*)})?(?P<localname>.*)")


def localname(node: object) -> str:
    tag = getattr(node, "tag")
    if callable(tag):
        return "comment"
    match = NS_REGEX.match(tag)
    if match is None:
        return tag
    return match.group("localname")


def _is_file_like_xml_input(value: object) -> bool:
    return not isinstance(value, (bytes, bytearray, str)) and hasattr(value, "read")


def _reject_unsafe_xml_input(value: object) -> None:
    if not DEFUSEDXML:
        return
    if isinstance(value, str):
        xml = value
    elif isinstance(value, (bytes, bytearray)):
        xml = bytes(value).decode("utf-8", errors="ignore")
    else:
        return
    lowered = xml.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        from defusedxml.common import DefusedXmlException

        raise DefusedXmlException("Entities and DTDs are forbidden")


def whitespace(node: object) -> None:
    text = getattr(node, "text", None)
    if text is None:
        return
    stripped = text.strip()
    if stripped and text != stripped:
        node.set(f"{{{XML_NS}}}space", "preserve")


__all__ = [
    "Element",
    "QName",
    "SubElement",
    "fromstring",
    "iterparse",
    "localname",
    "register_namespace",
    "safe_parser",
    "tostring",
    "whitespace",
    "xmlfile",
]
