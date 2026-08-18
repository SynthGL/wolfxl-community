"""``openpyxl.comments.author`` import shim."""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.xml.functions import Element, localname


class AuthorList(list[str]):
    tagname = "authors"

    def __init__(self, author=()) -> None:  # type: ignore[no-untyped-def]
        super().__init__(author or ())

    def append(self, value: str) -> None:
        raise AttributeError("'AuthorList' object has no attribute 'append'")

    @property
    def author(self) -> list[str]:
        return self

    @author.setter
    def author(self, value: list[str]) -> None:
        self[:] = list(value)

    @property
    def authors(self) -> list[str]:
        return self.author

    @authors.setter
    def authors(self, value: list[str]) -> None:
        self.author = value

    def to_tree(self):  # type: ignore[no-untyped-def]
        node = Element(self.tagname)
        for value in self:
            child = Element("author")
            child.text = value
            node.append(child)
        return node

    @classmethod
    def from_tree(cls, node):  # type: ignore[no-untyped-def]
        return cls(
            author=[
                child.text or ""
                for child in list(node)
                if localname(child) == "author"
            ]
        )


__all__ = ["AuthorList"]

__getattr__ = _openpyxl_name_fallback(globals())
