"""Extended document properties compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl import __version__
from wolfxl._compat import _OpenpyxlSerialisable, _iter_openpyxl_attrs
from wolfxl.xml.constants import XPROPS_NS
from wolfxl.xml.functions import Element, localname


class VectorLpstr(list):
    pass


class VectorVariant(list):
    pass


class DigSigBlob(_OpenpyxlSerialisable):
    pass


@dataclass(init=False)
class ExtendedProperties:
    Application: str | None = None
    AppVersion: str | None = None
    Company: str | None = None
    Manager: str | None = None
    HyperlinksChanged: bool | None = None
    SharedDoc: bool | None = None
    LinksUpToDate: bool | None = None
    ScaleCrop: bool | None = None
    HeadingPairs: Any = None
    TitlesOfParts: Any = None
    DocSecurity: int | None = None

    __elements__ = (
        "Application",
        "AppVersion",
        "DocSecurity",
        "ScaleCrop",
        "LinksUpToDate",
        "SharedDoc",
        "HyperlinksChanged",
    )

    def __init__(
        self,
        Application: str | None = None,  # noqa: N803
        AppVersion: str | None = None,  # noqa: N803
        Company: str | None = None,  # noqa: N803
        Manager: str | None = None,  # noqa: N803
        HyperlinksChanged: bool | None = None,  # noqa: N803
        SharedDoc: bool | None = None,  # noqa: N803
        LinksUpToDate: bool | None = None,  # noqa: N803
        ScaleCrop: bool | None = None,  # noqa: N803
        HeadingPairs: Any = None,  # noqa: N803
        TitlesOfParts: Any = None,  # noqa: N803
        DocSecurity: int | None = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.Application = f"Microsoft Excel Compatible / Openpyxl {__version__}"
        self.AppVersion = ".".join(__version__.split(".")[:-1])
        self.Company = Company
        self.Manager = Manager
        self.HyperlinksChanged = HyperlinksChanged
        self.SharedDoc = SharedDoc
        self.LinksUpToDate = LinksUpToDate
        self.ScaleCrop = ScaleCrop
        self.HeadingPairs = HeadingPairs
        self.TitlesOfParts = TitlesOfParts
        self.DocSecurity = DocSecurity
        if Application is not None:
            self.Application = Application
        if AppVersion is not None:
            self.AppVersion = AppVersion
        for name, value in kw.items():
            setattr(self, name, value)

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self)

    def to_tree(self) -> Any:
        root = Element("Properties", {"xmlns": XPROPS_NS})
        for name in self.__elements__:
            value = getattr(self, name, None)
            if value is None:
                continue
            child = Element(name)
            child.text = str(value)
            root.append(child)
        return root

    @classmethod
    def from_tree(cls, node: Any) -> "ExtendedProperties":
        kwargs = {}
        converters = {
            "DocSecurity": int,
            "ScaleCrop": bool,
            "LinksUpToDate": bool,
            "SharedDoc": bool,
            "HyperlinksChanged": bool,
        }
        for child in node:
            tag = localname(child)
            if tag not in cls.__elements__:
                continue
            text = child.text
            converter = converters.get(tag)
            if converter is not None:
                kwargs[tag] = converter(text)
            else:
                kwargs[tag] = text
        return cls(**kwargs)


NestedText = Serialisable = Typed = _OpenpyxlSerialisable

__all__ = [
    "DigSigBlob",
    "ExtendedProperties",
    "NestedText",
    "Serialisable",
    "Typed",
    "VectorLpstr",
    "VectorVariant",
    "XPROPS_NS",
]
