"""openpyxl.descriptors compatibility surface."""

from __future__ import annotations

import re

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.descriptors.base import (
    ASCII,
    Alias,
    Bool,
    Convertible,
    DEBUG,
    DateTime,
    Default,
    Descriptor,
    Float,
    Integer,
    Length,
    MatchPattern,
    Max,
    Min,
    MinMax,
    NoneSet,
    Set,
    String,
    Text,
    Tuple,
    Typed,
    datetime,
    from_ISO8601,
)
from wolfxl.descriptors.sequence import Sequence
from wolfxl.descriptors.serialisable import MetaSerialisable


class MetaStrict(type):
    """Auto-name descriptors at class-creation time.

    openpyxl's descriptors store values on ``instance.__dict__[name]``
    and read them back via the dict lookup that falls through when no
    ``__get__`` is defined. That mechanism only works when the
    descriptor knows the attribute name on the owning class; openpyxl
    binds that name here rather than relying on ``__set_name__`` so
    classes written before Python 3.6 keep working. Mirror the same
    contract so ``value = Bool()`` followed by ``obj.value = 1`` lands
    in the right slot.
    """

    def __new__(cls, clsname, bases, methods):
        for k, v in methods.items():
            if isinstance(v, Descriptor):
                v.name = k
        return type.__new__(cls, clsname, bases, methods)


class Strict(metaclass=MetaStrict):
    pass


_fallback_getattr = _openpyxl_name_fallback(globals())


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    if name in {"base", "container", "excel", "namespace", "nested", "sequence", "serialisable"}:
        from importlib import import_module
        value = import_module(f"wolfxl.descriptors.{name}")
    elif name == "namespaced":
        from importlib import import_module
        value = import_module("wolfxl.descriptors.namespace")
    else:
        value = _fallback_getattr(name)
    globals()[name] = value
    return value


__all__ = [
    "ASCII",
    "Alias",
    "Bool",
    "Convertible",
    "DEBUG",
    "DateTime",
    "Default",
    "Descriptor",
    "Float",
    "Integer",
    "Length",
    "MatchPattern",
    "Max",
    "MetaSerialisable",
    "MetaStrict",
    "Min",
    "MinMax",
    "NoneSet",
    "Sequence",
    "Set",
    "Strict",
    "String",
    "Text",
    "Tuple",
    "Typed",
    "container",
    "datetime",
    "excel",
    "from_ISO8601",
    "namespace",
    "namespaced",
    "re",
]
