"""Worksheet scenario compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable
from wolfxl.worksheet.cell_range import MultiCellRange
from wolfxl.xml.functions import Element, localname


@dataclass
class InputCells:
    r: str | None = None
    deleted: bool | None = False
    undone: bool | None = False
    val: Any = None
    numFmtId: int | None = None  # noqa: N815

    def to_tree(self) -> Any:
        node = Element("inputCells")
        _set_attr(node, "r", self.r)
        _set_attr(node, "val", self.val)
        _set_attr(node, "deleted", self.deleted)
        _set_attr(node, "undone", self.undone)
        _set_attr(node, "numFmtId", self.numFmtId)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "InputCells":
        return cls(
            r=node.get("r"),
            deleted=_bool_attr(node.get("deleted"), False),
            undone=_bool_attr(node.get("undone"), False),
            val=node.get("val"),
            numFmtId=_int_attr(node.get("numFmtId")),
        )


@dataclass
class Scenario:
    name: str | None = None
    locked: bool | None = False
    hidden: bool | None = False
    count: int | None = field(default=None, compare=False)
    user: str | None = None
    comment: str | None = None
    inputCells: list[InputCells] = field(default_factory=list)  # noqa: N815

    def to_tree(self) -> Any:
        node = Element("scenario")
        _set_attr(node, "name", self.name)
        _set_attr(node, "locked", self.locked)
        _set_attr(node, "count", len(self.inputCells))
        _set_attr(node, "hidden", self.hidden)
        _set_attr(node, "user", self.user)
        _set_attr(node, "comment", self.comment)
        for cell in self.inputCells:
            node.append(cell.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "Scenario":
        cells = [
            InputCells.from_tree(child)
            for child in list(node)
            if localname(child) == "inputCells"
        ]
        return cls(
            name=node.get("name"),
            locked=_bool_attr(node.get("locked"), False),
            hidden=_bool_attr(node.get("hidden"), False),
            user=node.get("user"),
            comment=node.get("comment"),
            inputCells=cells,
        )


@dataclass
class ScenarioList:
    scenario: list[Scenario] = field(default_factory=list)
    current: int | None = None
    show: int | None = None
    sqref: MultiCellRange | None = None

    def __iter__(self):
        return iter(())

    def to_tree(self) -> Any:
        node = Element("scenarios")
        _set_attr(node, "current", self.current)
        _set_attr(node, "show", self.show)
        _set_attr(node, "sqref", self.sqref)
        for scenario in self.scenario:
            node.append(scenario.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "ScenarioList":
        scenarios = [
            Scenario.from_tree(child)
            for child in list(node)
            if localname(child) == "scenario"
        ]
        return cls(
            scenario=scenarios,
            current=_int_attr(node.get("current")),
            show=_int_attr(node.get("show")),
            sqref=node.get("sqref"),
        )


def _bool_attr(value: Any, default: bool | None = None) -> bool | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true"}


def _int_attr(value: Any) -> int | None:
    return None if value is None else int(value)


def _set_attr(node: Any, name: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        value = "1" if value else "0"
    node.set(name, str(value))


Bool = Convertible = Integer = Sequence = Serialisable = String = _OpenpyxlSerialisable

__all__ = [
    "Bool",
    "Convertible",
    "InputCells",
    "Integer",
    "MultiCellRange",
    "Scenario",
    "ScenarioList",
    "Sequence",
    "Serialisable",
    "String",
]
