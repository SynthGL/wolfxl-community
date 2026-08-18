"""``openpyxl.packaging.relationship`` compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
import posixpath
from typing import Any
from warnings import warn

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.compat.strings import safe_string
from wolfxl.xml.constants import PKG_REL_NS, REL_NS
from wolfxl.xml.functions import Element, fromstring, localname


@dataclass(init=False)
class Relationship:
    type: str | None = None
    Target: str | None = None  # noqa: N815
    TargetMode: str | None = None  # noqa: N815
    Id: str | None = None  # noqa: N815

    def __init__(
        self,
        Id: str | None = None,  # noqa: N803
        Type: str | None = None,  # noqa: N803
        type: str | None = None,  # noqa: A002
        Target: str | None = None,  # noqa: N803
        TargetMode: str | None = None,  # noqa: N803
    ) -> None:
        self.Id = _optional_str("Id", Id)
        if Type is not None:
            self.type = _optional_str("Type", Type)
        elif type is not None:
            self.type = _normalize_rel_type(_optional_str("Type", type))
        else:
            self.type = None
        self.Target = _optional_str("Target", Target)
        self.TargetMode = _optional_str("TargetMode", TargetMode)

    @property
    def Type(self) -> str | None:  # noqa: N802
        return self.type

    @Type.setter
    def Type(self, value: str | None) -> None:  # noqa: N802
        self.type = _optional_str("Type", value)

    @property
    def id(self) -> str | None:
        return self.Id

    @id.setter
    def id(self, value: str | None) -> None:
        self.Id = _optional_str("Id", value)

    @property
    def target(self) -> str | None:
        return self.Target

    @target.setter
    def target(self, value: str | None) -> None:
        self.Target = _optional_str("Target", value)

    def __iter__(self):
        for attr in ("Type", "Target", "TargetMode", "Id"):
            value = getattr(self, attr)
            if value is not None:
                yield attr, safe_string(value)

    def to_tree(self) -> Any:
        node = Element("Relationship", dict(self))
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "Relationship":
        return cls(
            Id=node.get("Id"),
            Type=node.get("Type"),
            Target=node.get("Target"),
            TargetMode=node.get("TargetMode"),
        )


@dataclass
class RelationshipList:
    Relationship: list[Relationship] = field(default_factory=list)  # noqa: N815

    def append(self, value: Relationship) -> None:
        if not isinstance(value, Relationship):
            raise TypeError(f"Value must of type {Relationship} {type(value)} provided")
        self.Relationship.append(value)
        if not value.Id:
            value.Id = f"rId{len(self)}"

    def extend(self, values: list[Relationship] | tuple[Relationship, ...]) -> None:
        for value in values:
            self.append(value)

    def __iter__(self):
        return iter(self.Relationship)

    def __len__(self) -> int:
        return len(self.Relationship)

    def __getitem__(self, key: int | str) -> Relationship:
        if isinstance(key, int):
            return self.Relationship[key]
        for rel in self.Relationship:
            if rel.Id == key:
                return rel
        raise KeyError(key)

    def get(self, key: str) -> Relationship:
        try:
            return self[key]
        except KeyError as exc:
            raise KeyError(f"Unknown relationship: {key}") from exc

    def find(self, rel_type: str):
        for rel in self.Relationship:
            if rel.Type == rel_type:
                yield rel

    def to_dict(self) -> dict[str | None, Relationship]:
        return {rel.id: rel for rel in self}

    def to_tree(self) -> Any:
        root = Element("Relationships", {"xmlns": PKG_REL_NS})
        for rel in self.Relationship:
            root.append(rel.to_tree())
        return root

    @classmethod
    def from_tree(cls, node: Any) -> "RelationshipList":
        relationships = [
            Relationship.from_tree(child)
            for child in node
            if localname(child) == "Relationship"
        ]
        return cls(relationships)


def get_rels_path(path: str) -> str:
    part = PurePosixPath(path)
    return str(part.parent / "_rels" / f"{part.name}.rels")


def get_dependents(archive: Any, filename: str) -> RelationshipList:
    src = archive.read(filename)
    node = fromstring(src)
    try:
        rels = RelationshipList.from_tree(node)
    except TypeError:
        warn(f"{filename} contains invalid dependency definitions")
        rels = RelationshipList()
    folder = posixpath.dirname(filename)
    parent = posixpath.split(folder)[0]
    for rel in rels:
        if rel.TargetMode == "External":
            continue
        if rel.target is None:
            continue
        if rel.target.startswith("/"):
            rel.target = rel.target[1:]
        else:
            path = posixpath.join(parent, rel.target)
            rel.target = posixpath.normpath(path)
    return rels


def get_rel(archive: Any, deps: RelationshipList, id: str) -> Relationship:  # noqa: A002, ARG001
    return deps[id]


def _optional_str(name: str, value: str | None) -> str | None:
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{Relationship}.{name} should be {str} but value is {type(value)}")
    return value


def _normalize_rel_type(value: str | None) -> str | None:
    if value is None:
        return value
    return f"{REL_NS}/{value}"


__all__ = [
    "Element",
    "ElementList",
    "PKG_REL_NS",
    "REL_NS",
    "Relationship",
    "RelationshipList",
    "fromstring",
    "get_dependents",
    "get_rel",
    "get_rels_path",
    "posixpath",
    "warn",
]

ElementList = list

__getattr__ = _openpyxl_name_fallback(globals())
