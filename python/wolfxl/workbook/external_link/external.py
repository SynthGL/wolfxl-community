"""openpyxl.workbook.external_link.external compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from xml.etree.ElementTree import fromstring

from wolfxl._compat import _OpenpyxlSerialisable, _install_openpyxl_iter
from wolfxl._external_links import ExternalFileLink, ExternalLink
from wolfxl.packaging.relationship import Relationship, get_dependents, get_rels_path
from wolfxl.xml.constants import SHEET_MAIN_NS


@dataclass
class ExternalCell:
    r: str | None = None
    t: str | None = None
    vm: int | None = None
    v: str | None = None


@dataclass
class ExternalRow:
    r: int | None = None
    cell: list[ExternalCell] = field(default_factory=list)


@dataclass
class ExternalSheetData:
    sheetId: int | None = None  # noqa: N815
    refreshError: bool | None = None  # noqa: N815
    row: list[ExternalRow] = field(default_factory=list)


@dataclass
class ExternalSheetDataSet:
    sheetData: list[ExternalSheetData] = field(default_factory=list)  # noqa: N815


@dataclass
class ExternalSheetNames:
    sheetName: list[str] = field(default_factory=list)  # noqa: N815


@dataclass
class ExternalDefinedName:
    name: str | None = None
    refersTo: str | None = None  # noqa: N815
    sheetId: int | None = None  # noqa: N815


@dataclass
class ExternalBook:
    sheetNames: ExternalSheetNames | None = None  # noqa: N815
    definedNames: list[ExternalDefinedName] = field(default_factory=list)  # noqa: N815
    sheetDataSet: ExternalSheetDataSet | None = None  # noqa: N815
    id: str | None = None


def read_external_link(archive: Any, book_path: str) -> ExternalLink:  # noqa: ARG001
    return ExternalLink(target=book_path)


_install_openpyxl_iter(
    ExternalCell,
    ExternalRow,
    ExternalSheetData,
    ExternalSheetDataSet,
    ExternalSheetNames,
    ExternalDefinedName,
    ExternalBook,
)

Bool = Integer = NestedSequence = NestedText = NoneSet = Relation = Sequence = Serialisable = String = Typed = ValueSequence = _OpenpyxlSerialisable

__all__ = [
    "Bool",
    "ExternalBook",
    "ExternalCell",
    "ExternalDefinedName",
    "ExternalFileLink",
    "ExternalLink",
    "ExternalRow",
    "ExternalSheetData",
    "ExternalSheetDataSet",
    "ExternalSheetNames",
    "Integer",
    "NestedSequence",
    "NestedText",
    "NoneSet",
    "Relation",
    "Relationship",
    "SHEET_MAIN_NS",
    "Sequence",
    "Serialisable",
    "String",
    "Typed",
    "ValueSequence",
    "fromstring",
    "get_dependents",
    "get_rels_path",
    "read_external_link",
]
