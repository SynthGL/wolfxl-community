"""``openpyxl.utils.escape`` — OOXML control-character escape helpers.

Mirrors openpyxl's ``openpyxl/utils/escape.py``. OOXML stores ASCII
control characters as ``_xHHHH_`` tokens; these helpers convert between
the Python string and OOXML token forms.

Pod 2 (RFC-060).
"""

from __future__ import annotations

import re


_CONTROL_RE = re.compile(r"[\001-\031]")
_ESCAPE_RE = re.compile(r"_x([0-9A-Fa-f]{4})_")


def escape(value: str) -> str:
    """Convert ASCII control characters to OOXML ``_xHHHH_`` tokens."""

    def _replace(match: re.Match[str]) -> str:
        return f"_x{ord(match.group(0)):0>4x}_"

    return _CONTROL_RE.sub(_replace, value)


def unescape(value: str) -> str:
    """Resolve OOXML ``_xHHHH_`` control-character tokens."""

    def _replace(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 16))

    if "_x" not in value:
        return value
    return _ESCAPE_RE.sub(_replace, value)


__all__ = ["escape", "unescape"]
