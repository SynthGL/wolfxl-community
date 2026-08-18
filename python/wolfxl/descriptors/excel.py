"""Excel-specific descriptor and serialisable shims."""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable
from wolfxl.descriptors.base import Integer, MatchPattern, MinMax, String
from wolfxl.descriptors.nested import NestedText
from wolfxl.descriptors.sequence import Sequence
from wolfxl.descriptors.serialisable import Serialisable
from wolfxl.packaging.relationship import REL_NS, Relationship, get_dependents, get_rels_path
from wolfxl.xml.functions import Element


class Relation(String):
    namespace = REL_NS
    allow_none = True


class HexBinary(MatchPattern):
    pattern = r"[0-9a-fA-F]+$"


class Base64Binary(MatchPattern):
    pattern = r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{4})$"


class UniversalMeasure(MatchPattern):
    pattern = r"[0-9]+(\.[0-9]+)?(mm|cm|in|pt|pc|pi)"


class TextPoint(MinMax):
    expected_type = int
    min = -400000
    max = 400000


class Guid(MatchPattern):
    pattern = r"{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}"


class Percentage(MinMax):
    # Class-level defaults match openpyxl's so the zero-arg ctor
    # (which the upstream descriptor required Min/Max metadata for)
    # keeps working after wolfxl's descriptors started enforcing
    # presence of ``min``/``max``.
    pattern = r"((100)|([0-9][0-9]?))(\.[0-9][0-9]?)?%"
    min = -1000000
    max = 1000000

    def __set__(self, instance: Any, value: Any) -> None:
        if isinstance(value, str) and "%" in value:
            value = value.replace("%", "")
            value = int(float(value) * 1000)
        super().__set__(instance, value)


class Coordinate(MatchPattern):
    # Excel A1 coordinate; same pattern openpyxl ships so a zero-arg
    # ctor matches behavior after the descriptor switch to validation.
    pattern = r"^[$]?([A-Za-z]{1,3})[$]?(\d+)$"


class CellRange(MatchPattern):
    """Descriptor shim for ``openpyxl.descriptors.excel.CellRange``."""

    pattern = r"^[$]?([A-Za-z]{1,3})[$]?(\d+)(:[$]?([A-Za-z]{1,3})[$]?(\d+)?)?$|^[A-Za-z]{1,3}:[A-Za-z]{1,3}$"
    allow_none = True

    def __init__(self, name: str | None = None, **kw: Any) -> None:
        super().__init__(name=name, **kw)


class Extension(_OpenpyxlSerialisable):
    __attrs__ = ("uri",)

    def __init__(self, uri: str | None = None, **kw: Any) -> None:
        super().__init__(uri=uri, **kw)


class ExtensionList(_OpenpyxlSerialisable):
    __attrs__ = ("ext",)

    def __init__(self, ext: Any = (), **kw: Any) -> None:
        super().__init__(ext=list(ext or ()), **kw)


def safe_string(value: Any) -> str:
    return "" if value is None else str(value)


__all__ = [
    "Base64Binary",
    "CellRange",
    "Coordinate",
    "Element",
    "Extension",
    "ExtensionList",
    "Guid",
    "HexBinary",
    "Integer",
    "MatchPattern",
    "MinMax",
    "Percentage",
    "REL_NS",
    "Relation",
    "Relationship",
    "SHEET_MAIN_NS",
    "Sequence",
    "Serialisable",
    "String",
    "TextPoint",
    "UniversalMeasure",
    "NestedText",
    "get_dependents",
    "get_rels_path",
    "safe_string",
]

from wolfxl.xml.constants import SHEET_MAIN_NS  # noqa: E402
