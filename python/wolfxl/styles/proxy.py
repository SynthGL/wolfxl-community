"""openpyxl.styles.proxy compatibility."""

from __future__ import annotations

from copy import copy
from typing import Any


def deprecated(reason: str | None = None):  # noqa: ANN001
    def decorator(func: Any) -> Any:
        return func

    return decorator


class StyleProxy:
    """Read-through proxy used by openpyxl style internals."""

    __slots__ = ("__target",)

    def __init__(self, target: Any) -> None:
        object.__setattr__(self, "_StyleProxy__target", target)

    def __repr__(self) -> str:
        return repr(self.__target)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.__target, attr)

    def __setattr__(self, attr: str, value: Any) -> None:
        if attr != "_StyleProxy__target":
            raise AttributeError(
                "Style objects are immutable and cannot be changed."
                "Reassign the style with a copy"
            )
        object.__setattr__(self, attr, value)

    def __copy__(self) -> Any:
        return copy(self.__target)

    def __add__(self, other: Any) -> Any:
        return self.__target + other

    def copy(self, **kw: Any) -> Any:
        copied = copy(self.__target)
        for key, value in kw.items():
            setattr(copied, key, value)
        return copied

    def __eq__(self, other: Any) -> bool:
        return self.__target == other

    def __ne__(self, other: Any) -> bool:
        return not self == other


__all__ = ["StyleProxy", "copy", "deprecated"]
