"""Number-format utilities — bug-for-bug parity with openpyxl.

Reproduces ``openpyxl.styles.numbers.is_date_format``'s known quirks:
- only the **first** sub-format (semicolon-delimited) is inspected;
- text in double-quotes is stripped;
- ``[locale]`` brackets are stripped *unless* they are timedelta brackets
  (``[h]``, ``[mm]``, ``[ss]``);
- a date-token character (``d/m/h/y/s`` case-insensitive) preceded by an
  underscore or backslash escape does NOT count as a date marker.
"""

from __future__ import annotations

import re

# Verbatim from openpyxl/styles/numbers.py — keep these patterns aligned with
# upstream openpyxl. Drift means our parity tests catch you, not your users.
_LITERAL_GROUP = r'".*?"'
_LOCALE_GROUP = r"\[(?!hh?\]|mm?\]|ss?\])[^\]]*\]"
_STRIP_RE = re.compile(f"{_LITERAL_GROUP}|{_LOCALE_GROUP}")
_DATE_TOKEN_RE = re.compile(r"(?<![_\\])[dmhysDMHYS]")


def is_date_format(fmt: str | None) -> bool:
    """Return True iff ``fmt`` contains an unescaped date/time token."""
    if fmt is None:
        return False
    fmt = fmt.split(";")[0]
    fmt = _STRIP_RE.sub("", fmt)
    return _DATE_TOKEN_RE.search(fmt) is not None
