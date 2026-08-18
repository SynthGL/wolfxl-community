"""Namespace helper shim."""

from __future__ import annotations

from typing import Any


def namespaced(obj: Any, tagname: str, namespace: str | None = None) -> str:
    namespace = getattr(obj, "namespace", None) or namespace
    if namespace is not None:
        tagname = f"{{{namespace}}}{tagname}"
    return tagname


__all__ = ["namespaced"]
