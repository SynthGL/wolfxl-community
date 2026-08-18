"""``openpyxl.styles.alignment`` — re-export shim.

Wolfxl's :class:`~wolfxl._styles.Alignment` lives at
:mod:`wolfxl._styles`; this module surfaces it under the openpyxl-shaped
import path so ``from openpyxl.styles.alignment import Alignment`` swaps
to ``from wolfxl.styles.alignment import Alignment`` mechanically.

Pod 2 (RFC-060).
"""

from __future__ import annotations

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl._styles import Alignment

horizontal_alignments = (
    "general",
    "left",
    "center",
    "right",
    "fill",
    "justify",
    "centerContinuous",
    "distributed",
)
vertical_aligments = ("top", "center", "bottom", "justify", "distributed")

__all__ = ["Alignment", "horizontal_alignments", "vertical_aligments"]

__getattr__ = _openpyxl_name_fallback(globals())
