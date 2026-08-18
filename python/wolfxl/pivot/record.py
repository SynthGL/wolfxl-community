"""Passive openpyxl.pivot.record compatibility models."""

from __future__ import annotations

from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _resolve_openpyxl_class
from wolfxl.descriptors.base import Integer, Typed
from wolfxl.descriptors.excel import ExtensionList
from wolfxl.descriptors.nested import NestedBool, NestedInteger
from wolfxl.descriptors.sequence import MultiSequence, MultiSequencePart, Sequence
from wolfxl.descriptors.serialisable import Serialisable
from wolfxl.xml.constants import SHEET_MAIN_NS
from wolfxl.xml.functions import tostring


class _RecordValue(_OpenpyxlSerialisable):
    __attrs__ = ("v",)


class Missing(_RecordValue):
    tagname = "m"


class Number(_RecordValue):
    tagname = "n"


class Boolean(_RecordValue):
    tagname = "b"

    def __init__(self, v: Any = False, **kwargs: Any) -> None:
        super().__init__(v=v, **kwargs)


class Error(_RecordValue):
    tagname = "e"


class Text(_RecordValue):  # type: ignore[no-redef]
    tagname = "s"


class DateTimeField(_RecordValue):
    tagname = "d"


class Index(_RecordValue):
    tagname = "x"

    def __init__(self, v: Any = 0, **kwargs: Any) -> None:
        super().__init__(v=v, **kwargs)


class TupleList(_OpenpyxlSerialisable):
    tagname = "tpls"
    __attrs__ = ("tpl",)

    def __init__(self, tpl: Any = None, **kwargs: Any) -> None:
        super().__init__(tpl=tpl or [], **kwargs)


class Record(Serialisable):
    tagname = "r"

    def __init__(
        self,
        _fields: Any = None,
        m: Any = None,
        n: Any = None,
        b: Any = None,
        e: Any = None,
        s: Any = None,
        d: Any = None,
        x: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        fields = list(_fields or [])
        for value in (m, n, b, e, s, d, x):
            if value is not None:
                fields.append(value)
        self._fields = fields


class RecordList(Serialisable):
    tagname = "pivotCacheRecords"
    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheRecords+xml"
    rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheRecords"

    def __init__(self, r: Any = None, extLst: Any = None, count: int | None = None) -> None:
        self.r = list(r or [])
        self.extLst = extLst
        if count is not None:
            self.count = count

    @property
    def path(self) -> str:
        return "/xl/pivotCache/pivotCacheRecords1.xml"

    def _write(self, archive: Any, manifest: Any) -> None:
        archive.writestr(self.path[1:], tostring(self.to_tree()))
        if hasattr(manifest, "append"):
            manifest.append(self)

    def _write_rels(self, archive: Any, manifest: Any) -> None:  # noqa: ARG002
        return None


for _name in (
    "Missing",
    "Number",
    "Boolean",
    "Error",
    "Text",
    "DateTimeField",
    "Index",
    "TupleList",
    "Record",
    "RecordList",
):
    _upstream = _resolve_openpyxl_class(__name__, _name)
    if _upstream is not None:
        globals()[_name] = _upstream


__all__ = [
    "Boolean",
    "DateTimeField",
    "Error",
    "ExtensionList",
    "Index",
    "Integer",
    "Missing",
    "MultiSequence",
    "MultiSequencePart",
    "NestedBool",
    "NestedInteger",
    "Number",
    "Record",
    "RecordList",
    "SHEET_MAIN_NS",
    "Sequence",
    "Serialisable",
    "Text",
    "TupleList",
    "Typed",
    "tostring",
]
