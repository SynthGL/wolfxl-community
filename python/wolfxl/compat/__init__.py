"""openpyxl.compat compatibility package."""

from __future__ import annotations

import inspect
import warnings
from functools import wraps
from typing import Any, Callable, TypeVar

from wolfxl.compat.numbers import NUMERIC_TYPES
from wolfxl.compat.strings import safe_string

F = TypeVar("F", bound=Callable[..., Any])
string_types = (bytes, str)
_SUBMODULES = {"abc", "numbers", "product", "singleton", "strings"}


class DummyCode:
    """Small code-object stand-in used by openpyxl's deprecated wrapper."""

    def __init__(
        self,
        filename: str | None = None,
        firstlineno: int | None = None,
    ) -> None:
        if filename is None and firstlineno is None:
            return
        self.co_filename = filename
        self.co_firstlineno = firstlineno


def deprecated(reason: str) -> Callable[[F], F]:
    """Return a decorator that emits a deprecation warning on call."""
    if not isinstance(reason, string_types):
        if inspect.isclass(reason) or inspect.isfunction(reason):
            raise TypeError("Reason for deprecation must be supplied")
        raise TypeError(repr(type(reason)))

    def decorator(func: F) -> F:
        if inspect.isclass(func):
            message = f"Call to deprecated class {func.__name__} ({reason})."
        else:
            message = f"Call to deprecated function {func.__name__} ({reason})."

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warnings.warn(
                message,
                category=DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        deprecation_note = "\n\n.. note::\n    Deprecated: " + reason
        wrapper.__doc__ = (func.__doc__ + deprecation_note) if func.__doc__ else deprecation_note
        return wrapper  # type: ignore[return-value]

    return decorator


def __getattr__(name: str) -> Any:
    if name in _SUBMODULES:
        from importlib import import_module

        value = import_module(f"wolfxl.compat.{name}")
        globals()[name] = value
        return value
    raise AttributeError(name)


__all__ = [
    "DummyCode",
    "NUMERIC_TYPES",
    "abc",
    "deprecated",
    "inspect",
    "numbers",
    "product",
    "safe_string",
    "singleton",
    "string_types",
    "strings",
    "warnings",
    "wraps",
]
