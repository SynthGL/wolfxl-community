"""openpyxl.compat.singleton compatibility."""

from __future__ import annotations

import weakref
from typing import Any


class Singleton(type):
    """Metaclass that returns one instance per class."""

    _instances: dict[type, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Cached(type):
    """Metaclass that caches instances by constructor arguments."""

    _instances: weakref.WeakValueDictionary[tuple[Any, ...], Any]

    def __init__(cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> None:
        super().__init__(name, bases, namespace)
        cls._instances = weakref.WeakValueDictionary()

    def __call__(cls, *args: Any) -> Any:
        key = args
        try:
            return cls._instances[key]
        except KeyError:
            obj = super(Cached, cls).__call__(*args)
            cls._instances[key] = obj
            return obj


__all__ = ["Cached", "Singleton", "weakref"]
