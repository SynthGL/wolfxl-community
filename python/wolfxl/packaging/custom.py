"""Custom document property containers compatible with openpyxl."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Iterator
from warnings import warn

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.xml import LXML
from wolfxl.xml.constants import CPROPS_FMTID, CUSTPROPS_NS, VTYPES_NS
from wolfxl.xml.functions import Element, SubElement, localname

CLASS_MAPPING: dict[str, type["_TypedProperty"]] = {}
XML_MAPPING: dict[str, str] = {}


@dataclass(eq=False, repr=False)
class _TypedProperty:
    """Base class for a named custom document property."""

    name: str
    value: Any

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        parent = self.__dict__.get("_parent")
        if parent is not None and name != "_parent":
            parent._mark_dirty()

    def _attach_list(self, parent: "CustomPropertyList") -> None:
        object.__setattr__(self, "_parent", parent)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}, name={self.name}, value={self.value}"

    def __eq__(self, other: object) -> bool:
        return (
            getattr(other, "__class__", object).__name__ == self.__class__.__name__
            and getattr(other, "name", None) == self.name
            and getattr(other, "value", None) == self.value
        )


@dataclass(eq=False, repr=False)
class StringProperty(_TypedProperty):
    """String custom document property."""

    value: str | None


@dataclass(eq=False, repr=False)
class IntProperty(_TypedProperty):
    """Integer custom document property."""

    value: int


@dataclass(eq=False, repr=False)
class FloatProperty(_TypedProperty):
    """Floating-point custom document property."""

    value: float


@dataclass(eq=False, repr=False)
class BoolProperty(_TypedProperty):
    """Boolean custom document property."""

    value: bool


@dataclass(eq=False, repr=False)
class DateTimeProperty(_TypedProperty):
    """Datetime custom document property."""

    value: dt.datetime


@dataclass(eq=False, repr=False)
class LinkProperty(_TypedProperty):
    """Linked custom document property."""

    value: str


CLASS_MAPPING.update(
    {
        StringProperty: "lpwstr",
        IntProperty: "i4",
        FloatProperty: "r8",
        BoolProperty: "bool",
        DateTimeProperty: "filetime",
        LinkProperty: "lpwstr",
        "str": StringProperty,
        "int": IntProperty,
        "float": FloatProperty,
        "bool": BoolProperty,
        "datetime": DateTimeProperty,
        "link": LinkProperty,
    }
)
XML_MAPPING.update(
    {
        "lpwstr": StringProperty,
        "i4": IntProperty,
        "r8": FloatProperty,
        "bool": BoolProperty,
        "filetime": DateTimeProperty,
    }
)


class _CustomDocumentProperty:
    """Low-level XML representation of one custom document property."""

    tagname = "property"
    __attrs__ = ("name", "linkTarget", "fmtid", "pid")
    __elements__ = ("bool", "filetime", "i4", "lpwstr", "r8")

    def __init__(
        self,
        name: str | None = None,
        pid: int = 0,
        fmtid: str = CPROPS_FMTID,
        linkTarget: str | None = None,  # noqa: N803 - openpyxl API
        **kw: Any,
    ) -> None:
        self.fmtid = fmtid
        self.pid = pid
        self.name = name
        self._typ: str | None = None
        self.linkTarget = linkTarget
        for element in self.__elements__:
            setattr(self, element, None)
        for key, value in kw.items():
            setattr(self, key, value)
            self._typ = key

    @property
    def type(self) -> str | None:
        if self._typ is not None:
            return self._typ
        for attr in self.__elements__:
            if getattr(self, attr) is not None:
                return attr
        if self.linkTarget is not None:
            return "linkTarget"
        return None

    def __eq__(self, other: object) -> bool:
        if getattr(other, "__class__", object).__name__ != self.__class__.__name__:
            return False
        return (
            getattr(other, "name", None) == self.name
            and getattr(other, "pid", None) == self.pid
            and getattr(other, "fmtid", None) == self.fmtid
            and getattr(other, "linkTarget", None) == self.linkTarget
            and getattr(other, "type", None) == self.type
            and getattr(other, self.type or "", None)
            == getattr(self, self.type or "", None)
        )

    def to_tree(self) -> Element:
        node = Element(self.tagname)
        _set_attr(node, "name", self.name)
        _set_attr(node, "pid", self.pid)
        _set_attr(node, "fmtid", self.fmtid)
        _set_attr(node, "linkTarget", self.linkTarget)
        typ = self._typ or self.type
        if typ == "linkTarget":
            typ = "lpwstr"
        if typ not in self.__elements__:
            return node
        child = SubElement(node, f"{{{VTYPES_NS}}}{typ}")
        text = _custom_value_to_text(typ, getattr(self, typ))
        if text != "":
            child.text = text
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "_CustomDocumentProperty":
        kwargs: dict[str, Any] = {
            "name": node.get("name"),
            "pid": _int_or_default(node.get("pid"), 0),
            "fmtid": node.get("fmtid", CPROPS_FMTID),
            "linkTarget": node.get("linkTarget"),
        }
        prop = cls(**kwargs)
        for child in list(node):
            typ = localname(child)
            if typ in cls.__elements__:
                setattr(prop, typ, _custom_text_to_value(typ, child.text))
                prop._typ = typ
                break
        return prop


class _CustomDocumentPropertyList:
    """Low-level XML representation of the custom-properties part."""

    tagname = "Properties"

    def __init__(self, property: list[_CustomDocumentProperty] | tuple[_CustomDocumentProperty, ...] = ()) -> None:
        self.property = list(property)

    @property
    def customProps(self) -> list[_CustomDocumentProperty]:  # noqa: N802 - openpyxl API
        return self.property

    def __len__(self) -> int:
        return len(self.property)

    def to_tree(self) -> Element:
        if LXML:
            root = Element(
                f"{{{CUSTPROPS_NS}}}Properties",
                nsmap={None: CUSTPROPS_NS, "vt": VTYPES_NS},
            )
        else:
            root = Element(f"{{{CUSTPROPS_NS}}}Properties")
        for pid, prop in enumerate(self.property, 2):
            prop.pid = pid
            root.append(prop.to_tree())
        return root

    @classmethod
    def from_tree(cls, node: Any) -> "_CustomDocumentPropertyList":
        props = [
            _CustomDocumentProperty.from_tree(child)
            for child in list(node)
            if localname(child) == "property"
        ]
        return cls(property=props)


class CustomPropertyList:
    """List-like container for workbook custom document properties."""

    def __init__(self) -> None:
        self.props: list[_TypedProperty] = []
        self._wb: Any = None

    @property
    def names(self) -> list[str]:
        """Return custom property names in document order."""
        return [prop.name for prop in self.props]

    def append(self, prop: _TypedProperty) -> None:
        """Append a custom property, rejecting duplicate names."""
        if prop.name in self.names:
            raise ValueError(f"Property with name {prop.name} already exists")
        prop._attach_list(self)
        self.props.append(prop)
        self._mark_dirty()

    def __len__(self) -> int:
        return len(self.props)

    def __iter__(self) -> Iterator[_TypedProperty]:
        return iter(self.props)

    def __getitem__(self, name: str) -> _TypedProperty:
        for prop in self.props:
            if prop.name == name:
                return prop
        raise KeyError(f"Property with name {name} not found")

    def __delitem__(self, name: str) -> None:
        for index, prop in enumerate(self.props):
            if prop.name == name:
                self.props.pop(index)
                self._mark_dirty()
                return
        raise KeyError(f"Property with name {name} not found")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} containing {self.props}"

    def to_tree(self) -> Element:
        """Serialize custom properties to the OOXML custom-properties part."""
        props: list[_CustomDocumentProperty] = []
        for prop in self.props:
            attr = _property_xml_attr(prop)
            if attr is None:
                raise TypeError(f"Unknown adapter for {prop}")
            if prop.__class__.__name__ == "LinkProperty":
                xml_prop = _CustomDocumentProperty(
                    name=prop.name,
                    linkTarget=prop.value,
                    lpwstr=None,
                )
            else:
                xml_prop = _CustomDocumentProperty(name=prop.name, **{attr: prop.value})
            props.append(xml_prop)
        return _CustomDocumentPropertyList(property=props).to_tree()

    @classmethod
    def from_tree(cls, tree: Any) -> "CustomPropertyList":
        """Create a typed custom-property list from an OOXML element."""
        prop_list = _CustomDocumentPropertyList.from_tree(tree)
        props: list[_TypedProperty] = []
        for prop in prop_list.property:
            attr = prop.type
            typ = XML_MAPPING.get(attr)
            if typ is None:
                warn(f"Unknown type for {prop.name}", UserWarning, stacklevel=2)
                continue
            value = getattr(prop, attr)
            if prop.linkTarget is not None:
                new_prop = LinkProperty(name=prop.name, value=prop.linkTarget)
            else:
                new_prop = typ(name=prop.name, value=value)
            props.append(new_prop)
        new_prop_list = cls()
        new_prop_list.props = props
        for prop in new_prop_list.props:
            prop._attach_list(new_prop_list)
        return new_prop_list

    def _attach_workbook(self, wb: Any) -> None:
        self._wb = wb
        for prop in self.props:
            prop._attach_list(self)

    def _mark_dirty(self) -> None:
        if self._wb is not None:
            self._wb._custom_doc_props_dirty = True  # noqa: SLF001


def _custom_text_to_value(typ: str, text: str | None) -> Any:
    if typ == "bool":
        return str(text).lower() in {"1", "true"}
    if typ == "filetime" and text:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    if typ == "i4" and text is not None:
        return int(text)
    if typ == "r8" and text is not None:
        return float(text)
    return text


def _custom_value_to_text(typ: str, value: Any) -> str:
    if value is None:
        return ""
    if typ == "bool":
        return "1" if value else "0"
    if typ == "filetime" and isinstance(value, dt.datetime):
        text = value.replace(microsecond=0).isoformat()
        if value.tzinfo is None:
            text += "Z"
        return text
    return str(value)


def _int_or_default(value: Any, default: int) -> int:
    return default if value is None else int(value)


def _property_xml_attr(prop: _TypedProperty) -> str | None:
    attr = CLASS_MAPPING.get(prop.__class__)
    if attr is not None:
        return attr
    return {
        "StringProperty": "lpwstr",
        "IntProperty": "i4",
        "FloatProperty": "r8",
        "BoolProperty": "bool",
        "DateTimeProperty": "filetime",
        "LinkProperty": "lpwstr",
    }.get(prop.__class__.__name__)


def _set_attr(node: Any, name: str, value: Any) -> None:
    if value is None:
        return
    node.set(name, str(value))


__all__ = [
    "BoolProperty",
    "CLASS_MAPPING",
    "CustomPropertyList",
    "DateTimeProperty",
    "FloatProperty",
    "IntProperty",
    "LinkProperty",
    "StringProperty",
    "XML_MAPPING",
    "_CustomDocumentProperty",
    "_CustomDocumentPropertyList",
    "_TypedProperty",
]

__getattr__ = _openpyxl_name_fallback(globals())
