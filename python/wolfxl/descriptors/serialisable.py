"""openpyxl.descriptors.serialisable compatibility."""

from __future__ import annotations

from copy import copy
from keyword import kwlist
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable
from wolfxl._compat import _make_helper
from wolfxl.descriptors.base import Alias, Descriptor as _BaseDescriptor, Typed
from wolfxl.descriptors.sequence import MultiSequencePart, NestedSequence, Sequence
from wolfxl.xml.functions import Element, localname

KEYWORDS = frozenset(kwlist)
seq_types = (list, tuple)
safe_string = _make_helper("safe_string")


def _is_sequence(desc: Any) -> bool:
    return isinstance(desc, Sequence) or type(desc).__name__ in {
        "Sequence",
        "UniqueSequence",
        "ValueSequence",
        "NestedSequence",
        "MultiSequence",
    }


def _is_nested_sequence(desc: Any) -> bool:
    return isinstance(desc, NestedSequence) or type(desc).__name__ == "NestedSequence"


def _is_multi_sequence_part(desc: Any) -> bool:
    return isinstance(desc, MultiSequencePart) or type(desc).__name__ == "MultiSequencePart"


class MetaSerialisable(type):
    """Bind descriptor names at class-creation time.

    openpyxl's descriptor protocol stores values via
    ``instance.__dict__[self.name]`` and falls back to ``__dict__`` for
    reads because the descriptors only implement ``__set__``. Without
    binding ``name`` on every Descriptor in the class body, ``__set__``
    writes to ``instance.__dict__[None]`` and reads return the descriptor
    object itself. openpyxl's own MetaSerialisable does the same walk
    (plus ``__attrs__`` / ``__elements__`` computation); wolfxl mirrors
    just the name binding so existing ``_OpenpyxlSerialisable.__init__``
    keyword wiring keeps working while corpus tests that read descriptor
    values back start passing.
    """

    def __new__(cls, clsname, bases, methods):
        attrs = []
        nested = []
        elements = []
        namespaced_attrs = []
        for k, v in methods.items():
            descriptor_like = isinstance(v, _BaseDescriptor) or (
                hasattr(v, "__set__") and (hasattr(v, "name") or hasattr(v, "store"))
            )
            if descriptor_like:
                v.name = k
                ns = getattr(v, "namespace", None)
                if ns:
                    namespaced_attrs.append((k, f"{{{ns}}}{k}"))
                kind = type(v).__name__
                is_sequence = _is_sequence(v)
                is_multi_sequence_part = _is_multi_sequence_part(v)
                is_typed = isinstance(v, Typed) or hasattr(v, "expected_type")
                is_alias = isinstance(v, Alias) or hasattr(v, "alias")
                if getattr(v, "nested", False):
                    nested.append(k)
                    elements.append(k)
                elif is_sequence:
                    elements.append(k)
                elif is_multi_sequence_part or is_alias:
                    continue
                elif is_typed:
                    expected = getattr(v, "expected_type", None)
                    if hasattr(expected, "to_tree"):
                        elements.append(k)
                    elif isinstance(expected, tuple) and any(hasattr(item, "to_tree") for item in expected):
                        continue
                    else:
                        attrs.append(k)
                else:
                    attrs.append(k)
        if methods.get("__attrs__") is None:
            methods["__attrs__"] = tuple(attrs)
        methods["__namespaced__"] = tuple(namespaced_attrs)
        if methods.get("__nested__") is None:
            methods["__nested__"] = tuple(sorted(nested))
        if methods.get("__elements__") is None:
            methods["__elements__"] = tuple(sorted(elements))
        return type.__new__(cls, clsname, bases, methods)


class Serialisable(_OpenpyxlSerialisable, metaclass=MetaSerialisable):
    def __iter__(self):
        for attr in getattr(self, "__attrs__", ()):
            value = getattr(self, attr)
            if value is None or isinstance(value, (list, tuple, dict)):
                continue
            key = attr[1:] if attr.startswith("_") else attr
            desc = getattr(self.__class__, attr, None)
            if getattr(desc, "hyphenated", False):
                key = key.replace("_", "-")
            if isinstance(value, bool):
                value = "1" if value else "0"
            yield key, safe_string(value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        fields = tuple(getattr(self, name, None) for name in getattr(self, "__attrs__", ()))
        return hash(fields)

    def __add__(self, other: object):
        if type(self) != type(other):
            raise TypeError("Cannot combine instances of different types")
        result = copy(self)
        for attr in getattr(self, "__attrs__", ()):
            value = getattr(other, attr)
            if value is not None:
                setattr(result, attr, value)
        return result

    def __copy__(self):
        attrs = {name: copy(getattr(self, name)) for name in getattr(self, "__attrs__", ())}
        for name in getattr(self, "__elements__", ()):
            attrs[name] = copy(getattr(self, name))
        return self.__class__(**attrs)

    def __str__(self) -> str:
        module = self.__class__.__module__.replace("tests.vendored_openpyxl.", "openpyxl.")
        lines = [f"<{module}.{self.__class__.__name__} object>", "Parameters:"]
        names = tuple(getattr(self, "__attrs__", ())) + tuple(getattr(self, "__elements__", ()))
        lines.extend(f"{name}={getattr(self, name, None)!r}" for name in names)
        return "\n".join(lines)

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002
        namespace: str | None = None,
        value: Any = None,  # noqa: ARG002
    ):
        if tagname is None:
            tagname = self.tagname
        if tagname is None:
            raise NotImplementedError()
        if tagname.startswith("_"):
            tagname = tagname[1:]
        tagname = namespaced(self, tagname, namespace)
        namespace = getattr(self, "namespace", namespace)

        attrs = dict(self)
        for key, ns in getattr(self, "__namespaced__", ()):
            if key in attrs:
                attrs[ns] = attrs.pop(key)

        node = Element(tagname, attrs)
        if "attr_text" in getattr(self, "__attrs__", ()):
            node.text = safe_string(getattr(self, "attr_text"))

        for child_tag in getattr(self, "__elements__", ()):
            desc = getattr(self.__class__, child_tag, None)
            obj = getattr(self, child_tag)
            if hasattr(desc, "namespace") and hasattr(obj, "namespace"):
                obj.namespace = desc.namespace

            if isinstance(obj, seq_types):
                if _is_nested_sequence(desc):
                    if not obj:
                        continue
                    nodes = [desc.to_tree(child_tag, obj, namespace)]
                elif _is_sequence(desc):
                    desc.idx_base = getattr(self, "idx_base", 0)
                    nodes = desc.to_tree(child_tag, obj, namespace)
                else:
                    nodes = (value.to_tree(child_tag, namespace) for value in obj)
                for child in nodes:
                    node.append(child)
            else:
                if child_tag in getattr(self, "__nested__", ()):
                    child = desc.to_tree(child_tag, obj, namespace)
                elif obj is None:
                    continue
                else:
                    child = obj.to_tree(child_tag)
                if child is not None:
                    node.append(child)
        return node

    @classmethod
    def from_tree(cls, node):
        attrib = dict(node.attrib)
        for key, ns in getattr(cls, "__namespaced__", ()):
            if ns in attrib:
                attrib[key] = attrib.pop(ns)

        for key in list(attrib):
            if key.startswith("{"):
                del attrib[key]
            elif key in KEYWORDS:
                attrib[f"_{key}"] = attrib.pop(key)
            elif "-" in key:
                attrib[key.replace("-", "_")] = attrib.pop(key)

        if node.text and "attr_text" in getattr(cls, "__attrs__", ()):
            attrib["attr_text"] = node.text

        for child in node:
            tag = localname(child)
            if tag in KEYWORDS:
                tag = f"_{tag}"
            desc = getattr(cls, tag, None)
            if desc is None or isinstance(desc, property):
                continue

            if hasattr(desc, "from_tree"):
                obj = desc.from_tree(child)
            elif hasattr(desc.expected_type, "from_tree"):
                obj = desc.expected_type.from_tree(child)
            else:
                obj = child.text

            if _is_nested_sequence(desc):
                attrib[tag] = obj
            elif _is_sequence(desc):
                attrib.setdefault(tag, [])
                attrib[tag].append(obj)
            elif _is_multi_sequence_part(desc):
                attrib.setdefault(desc.store, [])
                attrib[desc.store].append(obj)
            else:
                attrib[tag] = obj
        return cls(**attrib)


class Descriptor(_OpenpyxlSerialisable):
    pass


class Sequence(_OpenpyxlSerialisable):
    pass


class NestedSequence(_OpenpyxlSerialisable):
    pass


class MultiSequencePart(_OpenpyxlSerialisable):
    pass


def namespaced(obj: Any, tagname: str, namespace: str | None = None) -> str:
    namespace = getattr(obj, "namespace", None) or namespace
    if namespace is not None:
        tagname = f"{{{namespace}}}{tagname}"
    return tagname


__all__ = [
    "Descriptor",
    "Element",
    "KEYWORDS",
    "MetaSerialisable",
    "MultiSequencePart",
    "NestedSequence",
    "Sequence",
    "Serialisable",
    "copy",
    "kwlist",
    "localname",
    "namespaced",
    "safe_string",
    "seq_types",
]
