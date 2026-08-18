"""Vendored openpyxl 3.1.5 nested descriptors.

The previous wolfxl module was a pure pass-through: every Nested
subclass was an empty body inheriting from the corresponding base
descriptor. That kept ``isinstance`` checks happy but stripped the
``to_tree`` / ``from_tree`` round-trip the openpyxl corpus exercises
via ``NestedValue``, ``NestedText``, ``NestedBool``, and ``EmptyTag``.
Vendor the upstream contract verbatim so XML serialisation behavior
matches the oracle. wolfxl's existing ``__all__`` surface stays
unchanged. ``safe_string`` is re-imported from ``wolfxl.compat`` so
this module mirrors the openpyxl module path layout.
"""

from __future__ import annotations

from typing import Any

from wolfxl.compat import safe_string
from wolfxl.descriptors.base import (
    Bool,
    Convertible,
    Descriptor,
    Float,
    Integer,
    MinMax,
    NoneSet,
    Set,
    String,
    Text,
)
from wolfxl.xml.functions import Element, localname, whitespace


class Nested(Descriptor):

    nested = True
    attribute = "val"

    def __set__(self, instance: Any, value: Any) -> None:
        if hasattr(value, "tag"):
            tag = localname(value)
            if tag != self.name:
                raise ValueError("Tag does not match attribute")

            value = self.from_tree(value)
        super().__set__(instance, value)


    def from_tree(self, node: Any) -> Any:
        return node.get(self.attribute)


    def to_tree(self, tagname=None, value=None, namespace=None):  # type: ignore[no-untyped-def]
        namespace = getattr(self, "namespace", namespace)
        if value is not None:
            if namespace is not None:
                tagname = "{%s}%s" % (namespace, tagname)
            value = safe_string(value)
            return Element(tagname, {self.attribute: value})


class NestedValue(Nested, Convertible):
    """Nested tag storing the value on the 'val' attribute."""
    pass


class NestedText(NestedValue):
    """Represents any nested tag with the value as the contents of the tag."""


    def from_tree(self, node: Any) -> Any:
        return node.text


    def to_tree(self, tagname=None, value=None, namespace=None):  # type: ignore[no-untyped-def]
        namespace = getattr(self, "namespace", namespace)
        if value is not None:
            if namespace is not None:
                tagname = "{%s}%s" % (namespace, tagname)
            el = Element(tagname)
            el.text = safe_string(value)
            whitespace(el)
            return el


class NestedFloat(NestedValue, Float):

    pass


class NestedInteger(NestedValue, Integer):

    pass


class NestedString(NestedValue, String):

    pass


class NestedBool(NestedValue, Bool):


    def from_tree(self, node: Any) -> Any:
        return node.get("val", True)


class NestedNoneSet(Nested, NoneSet):

    pass


class NestedSet(Nested, Set):

    pass


class NestedMinMax(Nested, MinMax):

    pass


class EmptyTag(Nested, Bool):

    """Boolean if a tag exists or not."""

    def from_tree(self, node: Any) -> Any:
        del node
        return True


    def to_tree(self, tagname=None, value=None, namespace=None):  # type: ignore[no-untyped-def]
        if value:
            namespace = getattr(self, "namespace", namespace)
            if namespace is not None:
                tagname = "{%s}%s" % (namespace, tagname)
            return Element(tagname)


__all__ = [
    "Bool",
    "Convertible",
    "Descriptor",
    "Element",
    "EmptyTag",
    "Float",
    "Integer",
    "MinMax",
    "Nested",
    "NestedBool",
    "NestedFloat",
    "NestedInteger",
    "NestedMinMax",
    "NestedNoneSet",
    "NestedSet",
    "NestedString",
    "NestedText",
    "NestedValue",
    "NoneSet",
    "Set",
    "String",
    "Text",
    "localname",
    "safe_string",
    "whitespace",
]
