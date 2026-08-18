"""Sequence descriptor shims."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from wolfxl.descriptors.base import Alias, Descriptor, _convert
from wolfxl.descriptors.namespace import namespaced
from wolfxl.xml.functions import Element, fromstring, localname


def _coerce_xml_node(node: Any) -> Any:
    try:
        node.tag
    except AttributeError:
        return node
    if node.__class__.__module__.startswith("xml.etree"):
        return fromstring(ET.tostring(node))
    return node


class Sequence(Descriptor):
    expected_type = type(None)
    seq_types = (list, tuple)
    idx_base = 0
    unique = False
    container = list

    def __init__(self, name: str | None = None, **kw: Any) -> None:
        super().__init__(name, **kw)

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        if self.name not in instance.__dict__:
            instance.__dict__[self.name] = []
        return instance.__dict__[self.name]

    def __set__(self, instance: Any, value: Any) -> None:
        if not isinstance(value, self.seq_types):
            raise TypeError("Value must be a sequence")
        values = self.container(_convert(self.expected_type, item) for item in value)
        if self.unique:
            values = IndexedList(values)
        super().__set__(instance, values)

    def to_tree(self, tagname: str, obj: Any, namespace: str | None = None):
        for idx, value in enumerate(obj, self.idx_base):
            if hasattr(value, "to_tree"):
                node = value.to_tree(tagname, idx)
            else:
                node = Element(namespaced(self, tagname, namespace))
                node.text = safe_string(value)
            yield node


class UniqueSequence(Sequence):
    unique = True


class ValueSequence(Sequence):
    attribute = "val"

    def to_tree(self, tagname: str, obj: Any, namespace: str | None = None):
        tagname = namespaced(self, tagname, namespace)
        for value in obj:
            yield Element(tagname, {self.attribute: safe_string(value)})

    def from_tree(self, node: Any) -> Any:
        if node.get(self.attribute) is not None:
            return _convert(self.expected_type, node.get(self.attribute))
        values = []
        for child in node:
            if localname(child) == self.name:
                values.append(_convert(self.expected_type, child.get(self.attribute)))
        return values


class NestedSequence(Sequence):
    count = False

    def __init__(self, name: str | None = None, **kw: Any) -> None:
        self.count = bool(kw.pop("count", False))
        super().__init__(name, **kw)

    def to_tree(self, tagname: str, obj: Any, namespace: str | None = None):
        container = Element(namespaced(self, tagname, namespace))
        if self.count:
            container.set("count", str(len(obj)))
        for value in obj:
            container.append(_coerce_xml_node(value.to_tree()))
        return container

    def from_tree(self, node: Any) -> list[Any]:
        return [self.expected_type.from_tree(child) for child in node]


class MultiSequence(Sequence):
    def __set__(self, instance: Any, value: Any) -> None:
        if not isinstance(value, (tuple, list)):
            raise ValueError("Value must be a sequence")
        Descriptor.__set__(self, instance, list(value))

    def to_tree(self, tagname: str, obj: Any, namespace: str | None = None):
        for value in obj:
            yield _coerce_xml_node(value.to_tree(namespace=namespace))


class MultiSequencePart(Alias):
    def __init__(self, expected_type: type, store: str) -> None:
        self.expected_type = expected_type
        self.store = store

    def __set__(self, instance: Any, value: Any) -> None:
        value = _convert(self.expected_type, value)
        instance.__dict__[self.store].append(value)

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        return self


class IndexedList(list):
    def __init__(self, iterable: Any = None) -> None:
        super().__init__([] if iterable is None else iterable)

    def add(self, value: Any) -> int:
        if value not in self:
            self.append(value)
        return self.index(value)


def safe_string(value: Any) -> str:
    return "" if value is None else str(value)


__all__ = [
    "Alias",
    "Descriptor",
    "Element",
    "IndexedList",
    "MultiSequence",
    "MultiSequencePart",
    "NestedSequence",
    "Sequence",
    "UniqueSequence",
    "ValueSequence",
    "namespaced",
    "safe_string",
]
