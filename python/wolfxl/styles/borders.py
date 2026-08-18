"""``openpyxl.styles.borders`` — re-export shim for ``Border`` + ``Side``.

Pod 2 (RFC-060).
"""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl._styles import Border, Side

BORDER_NONE = None
BORDER_DASHDOT = "dashDot"
BORDER_DASHDOTDOT = "dashDotDot"
BORDER_DASHED = "dashed"
BORDER_DOTTED = "dotted"
BORDER_DOUBLE = "double"
BORDER_HAIR = "hair"
BORDER_MEDIUM = "medium"
BORDER_MEDIUMDASHDOT = "mediumDashDot"
BORDER_MEDIUMDASHDOTDOT = "mediumDashDotDot"
BORDER_MEDIUMDASHED = "mediumDashed"
BORDER_SLANTDASHDOT = "slantDashDot"
BORDER_THICK = "thick"
BORDER_THIN = "thin"
DEFAULT_BORDER = Border()

# openpyxl exposes a frozen tuple of valid border-style names at module
# scope; mirror it for callers that introspect against it.
BORDER_STYLES = (
    "dashDot",
    "dashDotDot",
    "dashed",
    "dotted",
    "double",
    "hair",
    "medium",
    "mediumDashDot",
    "mediumDashDotDot",
    "mediumDashed",
    "slantDashDot",
    "thick",
    "thin",
)

__all__ = [
    "BORDER_DASHDOT",
    "BORDER_DASHDOTDOT",
    "BORDER_DASHED",
    "BORDER_DOTTED",
    "BORDER_DOUBLE",
    "BORDER_HAIR",
    "BORDER_MEDIUM",
    "BORDER_MEDIUMDASHDOT",
    "BORDER_MEDIUMDASHDOTDOT",
    "BORDER_MEDIUMDASHED",
    "BORDER_NONE",
    "BORDER_SLANTDASHDOT",
    "BORDER_STYLES",
    "BORDER_THICK",
    "BORDER_THIN",
    "Border",
    "DEFAULT_BORDER",
    "Side",
]

__getattr__ = _openpyxl_name_fallback(globals())
