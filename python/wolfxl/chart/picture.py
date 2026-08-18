"""Chart picture options compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl._compat import (
    _OpenpyxlSerialisable,
    _install_openpyxl_iter,
    _resolve_openpyxl_class,
)


@dataclass
class PictureOptions:
    applyToFront: bool | None = None  # noqa: N815
    applyToSides: bool | None = None  # noqa: N815
    applyToEnd: bool | None = None  # noqa: N815
    pictureFormat: str | None = None  # noqa: N815
    pictureStackUnit: float | None = None  # noqa: N815


def _xml_model_names(cls: type) -> tuple[str, ...]:
    return tuple(getattr(cls, "__attrs__", ())) + tuple(getattr(cls, "__elements__", ()))


def _to_openpyxl_model(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    cls = value.__class__
    upstream_cls = _resolve_openpyxl_class(cls.__module__, cls.__name__)
    if upstream_cls is None or cls is upstream_cls:
        return value

    kwargs: dict[str, Any] = {}
    for name in _xml_model_names(upstream_cls):
        if hasattr(value, name):
            kwargs[name] = getattr(value, name)
    return upstream_cls(**kwargs)


def _from_openpyxl_picture_model(value: Any) -> PictureOptions:
    kwargs: dict[str, Any] = {}
    for name in _xml_model_names(value.__class__):
        if hasattr(value, name):
            kwargs[name] = getattr(value, name)
    return PictureOptions(**kwargs)


def _picture_to_tree(
    self: Any,
    tagname: str | None = None,
    idx: int | None = None,
    namespace: str | None = None,
):
    upstream = _to_openpyxl_model(self)
    return upstream.to_tree(tagname=tagname, idx=idx, namespace=namespace)


def _picture_from_tree(cls: type, node: Any) -> PictureOptions:
    upstream_cls = _resolve_openpyxl_class(__name__, cls.__name__)
    if upstream_cls is None:
        raise AttributeError("from_tree")
    return _from_openpyxl_picture_model(upstream_cls.from_tree(node))


def _picture_eq(self: Any, other: Any) -> bool:
    if type(self) is not type(other):
        return False
    return _to_openpyxl_model(self) == _to_openpyxl_model(other)


PictureOptions.to_tree = _picture_to_tree  # type: ignore[attr-defined]
PictureOptions.from_tree = classmethod(_picture_from_tree)  # type: ignore[attr-defined]
PictureOptions.__eq__ = _picture_eq  # type: ignore[method-assign]

_install_openpyxl_iter(PictureOptions)

NestedBool = NestedFloat = NestedMinMax = NestedNoneSet = Serialisable = (
    _OpenpyxlSerialisable
)

__all__ = [
    "NestedBool",
    "NestedFloat",
    "NestedMinMax",
    "NestedNoneSet",
    "PictureOptions",
    "Serialisable",
]
