"""BoundDictionary compatibility."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class BoundDictionary(defaultdict):
    def __init__(self, reference: str | None = None, *args: Any, **kwargs: Any) -> None:
        self.reference = reference
        super().__init__(*args, **kwargs)

    def __getitem__(self, key: Any) -> Any:
        value = super().__getitem__(key)
        if self.reference and hasattr(value, self.reference):
            setattr(value, self.reference, key)
        return value


__all__ = ["BoundDictionary", "defaultdict"]
