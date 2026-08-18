"""Cell-style array compatibility helpers."""

from __future__ import annotations

from array import array
from copy import copy
from xml.etree import ElementTree as ET
from typing import Any, Iterable

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.xml.functions import Element, fromstring, localname


class _ArrayDescriptor:
    def __init__(self, key: int) -> None:
        self.key = key

    def __get__(self, instance: "StyleArray", cls: type["StyleArray"]) -> int:
        return instance[self.key]

    def __set__(self, instance: "StyleArray", value: int) -> None:
        instance[self.key] = value


class StyleArray(array):
    """Compact nine-slot style-id tuple used by openpyxl-style callers."""

    __slots__ = ()
    tagname = "xf"

    fontId = _ArrayDescriptor(0)
    fillId = _ArrayDescriptor(1)
    borderId = _ArrayDescriptor(2)
    numFmtId = _ArrayDescriptor(3)
    protectionId = _ArrayDescriptor(4)
    alignmentId = _ArrayDescriptor(5)
    pivotButton = _ArrayDescriptor(6)
    quotePrefix = _ArrayDescriptor(7)
    xfId = _ArrayDescriptor(8)

    _KEY_INDEX = {
        "fontId": 0,
        "fillId": 1,
        "borderId": 2,
        "numFmtId": 3,
        "protectionId": 4,
        "alignmentId": 5,
        "pivotButton": 6,
        "quotePrefix": 7,
        "xfId": 8,
    }

    def __new__(
        cls,
        args: Iterable[int] | None = None,
        **kw: Any,
    ) -> "StyleArray":
        values = list(args) if args is not None else [0] * 9
        if len(values) < 9:
            values.extend([0] * (9 - len(values)))
        for key, index in cls._KEY_INDEX.items():
            if key in kw and kw[key] is not None:
                values[index] = int(kw[key])
        return array.__new__(cls, "i", values)

    def __hash__(self) -> int:
        return hash(tuple(self))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (array, list, tuple)):
            return tuple(self) == tuple(other)
        return array.__eq__(self, other)

    def __copy__(self) -> "StyleArray":
        return StyleArray(self)

    def __deepcopy__(self, memo: dict[int, object]) -> "StyleArray":
        return copy(self)

    @property
    def applyAlignment(self) -> None:  # noqa: N802
        return None

    @property
    def applyProtection(self) -> None:  # noqa: N802
        return None


class CellStyle:
    """OOXML ``xf`` record that converts to/from compact ``StyleArray``."""

    tagname = "xf"

    def __init__(
        self,
        numFmtId: int = 0,  # noqa: N803
        fontId: int = 0,  # noqa: N803
        fillId: int = 0,  # noqa: N803
        borderId: int = 0,  # noqa: N803
        xfId: int | None = None,  # noqa: N803
        quotePrefix: bool | int | None = None,  # noqa: N803
        pivotButton: bool | int | None = None,  # noqa: N803
        applyNumberFormat: bool | None = None,  # noqa: N803
        applyFont: bool | None = None,  # noqa: N803
        applyFill: bool | None = None,  # noqa: N803
        applyBorder: bool | None = None,  # noqa: N803
        applyAlignment: bool | None = None,  # noqa: N803, ARG002
        applyProtection: bool | None = None,  # noqa: N803, ARG002
        alignment: Any = None,
        protection: Any = None,
        extLst: Any = None,  # noqa: N803, ARG002
    ) -> None:
        self.numFmtId = int(numFmtId or 0)
        self.fontId = int(fontId or 0)
        self.fillId = int(fillId or 0)
        self.borderId = int(borderId or 0)
        self.xfId = None if xfId is None else int(xfId)
        self.quotePrefix = quotePrefix
        self.pivotButton = pivotButton
        self.applyNumberFormat = applyNumberFormat
        self.applyFont = applyFont
        self.applyFill = applyFill
        self.applyBorder = applyBorder
        self.alignment = alignment
        self.protection = protection

    def __eq__(self, other: object) -> bool:
        return (
            getattr(other, "__class__", object).__name__ == self.__class__.__name__
            and getattr(other, "numFmtId", None) == self.numFmtId
            and getattr(other, "fontId", None) == self.fontId
            and getattr(other, "fillId", None) == self.fillId
            and getattr(other, "borderId", None) == self.borderId
            and getattr(other, "xfId", None) == self.xfId
            and getattr(other, "quotePrefix", None) == self.quotePrefix
            and getattr(other, "pivotButton", None) == self.pivotButton
            and getattr(other, "applyAlignment", None) == self.applyAlignment
            and getattr(other, "applyProtection", None) == self.applyProtection
            and getattr(other, "alignment", None) == self.alignment
            and getattr(other, "protection", None) == self.protection
        )

    def __iter__(self):
        for key in ("numFmtId", "fontId", "fillId", "borderId"):
            yield key, str(getattr(self, key))
        for key in ("pivotButton", "quotePrefix", "xfId"):
            value = getattr(self, key)
            if value is not None:
                yield key, str(int(value)) if isinstance(value, bool) else str(value)

    @property
    def applyAlignment(self) -> bool | None:  # noqa: N802
        return self.alignment is not None or None

    @property
    def applyProtection(self) -> bool | None:  # noqa: N802
        return self.protection is not None or None

    def to_array(self) -> StyleArray:
        style = StyleArray()
        for key in (
            "fontId",
            "fillId",
            "borderId",
            "numFmtId",
            "pivotButton",
            "quotePrefix",
            "xfId",
        ):
            value = getattr(self, key, 0)
            if value is not None:
                setattr(style, key, int(value))
        return style

    @classmethod
    def from_array(cls, style: StyleArray) -> "CellStyle":
        return cls(
            numFmtId=style.numFmtId,
            fontId=style.fontId,
            fillId=style.fillId,
            borderId=style.borderId,
            xfId=style.xfId,
            quotePrefix=style.quotePrefix,
            pivotButton=style.pivotButton,
        )

    def to_tree(self, tagname: str | None = None, idx: int | None = None) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        attrs = {
            "numFmtId": self.numFmtId,
            "fontId": self.fontId,
            "fillId": self.fillId,
            "borderId": self.borderId,
            "applyAlignment": self.applyAlignment,
            "applyProtection": self.applyProtection,
            "pivotButton": self.pivotButton,
            "quotePrefix": self.quotePrefix,
            "xfId": self.xfId,
        }
        for key, value in attrs.items():
            if value is None:
                continue
            if isinstance(value, bool):
                value = int(value)
            node.set(key, str(value))
        if self.alignment is not None:
            _append_tree(node, self.alignment.to_tree("alignment"))
        if self.protection is not None:
            _append_tree(node, self.protection.to_tree("protection"))
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "CellStyle":
        from wolfxl._styles import Alignment
        from wolfxl.styles.protection import Protection

        kwargs: dict[str, Any] = {}
        for key in ("numFmtId", "fontId", "fillId", "borderId", "xfId"):
            if key in node.attrib:
                kwargs[key] = int(node.attrib[key])
        for key in ("quotePrefix", "pivotButton"):
            if key in node.attrib:
                kwargs[key] = node.attrib[key] not in {"0", "false", "False"}
        for child in node:
            name = localname(child)
            if name == "alignment":
                kwargs["alignment"] = Alignment.from_tree(child)
            elif name == "protection":
                kwargs["protection"] = Protection.from_tree(child)
        return cls(**kwargs)


def _append_tree(node: Any, child: Any) -> None:
    try:
        node.append(child)
    except TypeError:
        node.append(fromstring(ET.tostring(child)))


class CellStyleList:
    tagname = "cellXfs"

    def __init__(
        self,
        count: int | None = None,  # noqa: ARG002
        xf: Iterable[CellStyle] = (),
    ) -> None:
        self.xf = list(xf)

    @property
    def count(self) -> int:
        return len(self.xf)

    def __iter__(self):
        return iter(self.xf)

    def __getitem__(self, idx: int) -> CellStyle:
        return self.xf[idx]

    def __eq__(self, other: object) -> bool:
        return (
            getattr(other, "__class__", object).__name__ == self.__class__.__name__
            and getattr(other, "xf", None) == self.xf
        )

    def to_tree(self, tagname: str | None = None) -> Any:
        node = Element(tagname or self.tagname)
        node.set("count", str(self.count))
        for xf in self.xf:
            node.append(xf.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "CellStyleList":
        return cls(xf=[CellStyle.from_tree(child) for child in node if localname(child) == "xf"])

    def _to_array(self) -> list[StyleArray]:
        from wolfxl._styles import Alignment
        from wolfxl.styles.protection import Protection
        from wolfxl.styles.stylesheet import IndexedList

        self.prots = IndexedList([Protection()])
        self.alignments = IndexedList([Alignment()])
        styles = []
        for xf in self.xf:
            style = xf.to_array()
            if xf.alignment is not None:
                style.alignmentId = self.alignments.add(xf.alignment)
            if xf.protection is not None:
                style.protectionId = self.prots.add(xf.protection)
            styles.append(style)
        return styles

__all__ = ["CellStyle", "CellStyleList", "StyleArray"]

__getattr__ = _openpyxl_name_fallback(globals())
