"""Packaging interface shim."""

from __future__ import annotations

from abc import ABC, abstractproperty


class ISerialisableFile(ABC):
    @abstractproperty
    def path(self) -> str:
        raise NotImplementedError


__all__ = ["ABC", "ISerialisableFile", "abstractproperty"]
