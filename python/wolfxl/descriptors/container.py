"""Container helpers for openpyxl compatibility."""

from __future__ import annotations

from wolfxl.xml.functions import Element


class ElementList(list):
    @property
    def tagname(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError()

    @property
    def expected_type(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError()

    @classmethod
    def from_tree(cls, tree):  # type: ignore[no-untyped-def]
        return cls([cls.expected_type.from_tree(el) for el in tree])

    def to_tree(self):  # type: ignore[no-untyped-def]
        container = Element(self.tagname)
        for el in self:
            container.append(el.to_tree())
        return container

    def append(self, value):  # type: ignore[no-untyped-def]
        if not isinstance(value, self.expected_type):
            raise TypeError(f"Value must of type {self.expected_type} {type(value)} provided")
        super().append(value)


__all__ = ["Element", "ElementList"]
