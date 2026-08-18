"""openpyxl.worksheet.hyperlink compatibility.

T1 makes ``Hyperlink`` a real dataclass. Reads work from any file; writes
via ``cell.hyperlink = Hyperlink(...)`` land in write mode (T1 PR4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from wolfxl._compat import _iter_openpyxl_attrs, _openpyxl_name_fallback
from wolfxl.xml.constants import REL_NS
from wolfxl.xml.functions import Element, localname


@dataclass
class Hyperlink:
    """A cell hyperlink.

    ``target`` holds an external URL (http:// / mailto: / file://).
    ``location`` holds an internal reference (``Sheet1!A1``) for intra-
    workbook links. ``display`` is the visible text that overrides the
    cell value, ``tooltip`` the screen-tip on hover. ``id`` is the rel id
    assigned by the writer — read-only from Python.
    """

    tagname: ClassVar[str] = "hyperlink"
    __attrs__: ClassVar[tuple[str, ...]] = (
        "ref",
        "location",
        "tooltip",
        "display",
        "id",
    )

    ref: str | None = None
    target: str | None = None
    location: str | None = None
    tooltip: str | None = None
    display: str | None = None
    id: str | None = None

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for name, value in self:
            if name == "id":
                node.set(f"{{{REL_NS}}}id", value)
            else:
                node.set(name, value)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "Hyperlink":
        attrs = {
            _local_name(key): value
            for key, value in node.attrib.items()
            if _local_name(key) in cls.__attrs__
        }
        return cls(**attrs)


class HyperlinkList(list):
    """``openpyxl``-shaped list container for :class:`Hyperlink` entries.

    openpyxl exposes ``HyperlinkList`` as the type backing
    ``ws.hyperlinks``.  Wolfxl tracks hyperlinks on individual cell
    proxies, so this container is used purely to satisfy
    ``isinstance(ws.hyperlinks, HyperlinkList)`` migrations — it
    behaves as a plain :class:`list` of hyperlinks.

    Pod 2 (RFC-060).
    """

    tagname = "hyperlinks"
    __attrs__ = ()
    __elements__ = ("hyperlink",)

    def __init__(self, hyperlink: list[Hyperlink] | tuple[Hyperlink, ...] | None = ()) -> None:
        super().__init__([] if hyperlink is None else hyperlink)

    @property
    def hyperlink(self) -> "HyperlinkList":
        return self

    @hyperlink.setter
    def hyperlink(self, value: list[Hyperlink]) -> None:
        self.clear()
        self.extend(value)

    def to_tree(self, tagname: str | None = None, **kw: Any) -> Any:  # noqa: ARG002
        node = Element(tagname or self.tagname)
        for link in self:
            node.append(link.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "HyperlinkList":
        links = cls()
        for child in node:
            if localname(child) == "hyperlink":
                links.append(Hyperlink.from_tree(child))
        return links


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1] if "}" in name else name


__all__ = ["Hyperlink", "HyperlinkList"]

__getattr__ = _openpyxl_name_fallback(globals())
