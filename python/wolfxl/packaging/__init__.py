"""openpyxl.packaging compatibility.

Re-exports :class:`DocumentProperties` from ``core`` so users can write
``from wolfxl.packaging.core import DocumentProperties`` or the shorter
``from wolfxl.packaging import DocumentProperties``.
"""

from __future__ import annotations

from wolfxl.packaging.core import DocumentProperties
from wolfxl.packaging.custom import (
    BoolProperty,
    CustomPropertyList,
    DateTimeProperty,
    FloatProperty,
    IntProperty,
    LinkProperty,
    StringProperty,
)

_SUBMODULES = {
    "core",
    "custom",
    "extended",
    "interface",
    "manifest",
    "relationship",
    "workbook",
}


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    if name in _SUBMODULES:
        from importlib import import_module

        value = import_module(f"wolfxl.packaging.{name}")
        globals()[name] = value
        return value
    raise AttributeError(name)

__all__ = [
    "BoolProperty",
    "CustomPropertyList",
    "DateTimeProperty",
    "DocumentProperties",
    "FloatProperty",
    "IntProperty",
    "LinkProperty",
    "StringProperty",
    "core",
    "custom",
    "extended",
    "interface",
    "manifest",
    "relationship",
    "workbook",
]
