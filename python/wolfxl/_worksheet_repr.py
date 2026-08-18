"""Debug representation helpers for worksheet proxies."""

from __future__ import annotations


def worksheet_repr(title: str) -> str:
    """Return the compact debug representation for a worksheet title."""
    return f"<Worksheet [{title}]>"
