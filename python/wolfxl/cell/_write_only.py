"""WriteOnlyCell — stripped-down cell for streaming construction.

openpyxl's ``Workbook(write_only=True)`` mode constructs cells
via :class:`WriteOnlyCell` and appends them row-by-row without
materializing the full sheet.  Wolfxl doesn't have a separate
write-only mode (the native writer streams internally), but the
class exists for drop-in import parity — user code that does
``WriteOnlyCell(ws, value=42, font=Font(bold=True))`` can be
migrated with a one-line import swap.

Reference: ``openpyxl.cell.cell.WriteOnlyCell`` (openpyxl 3.1.x).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from wolfxl._worksheet import Worksheet


class WriteOnlyCell:
    """Lightweight cell for construction-time use.

    Stores value + style attributes as plain instance fields.
    The native writer / append path consumes the same attribute
    names so a ``WriteOnlyCell`` can be passed directly to
    ``ws.append([...])``.
    """

    __slots__ = (
        "parent",
        "value",
        "font",
        "fill",
        "border",
        "alignment",
        "number_format",
        "protection",
        "hyperlink",
        "comment",
    )

    def __init__(
        self,
        ws: Worksheet | None = None,
        value: Any = None,
        font: Any = None,
        fill: Any = None,
        border: Any = None,
        alignment: Any = None,
        number_format: str | None = None,
        protection: Any = None,
        hyperlink: Any = None,
        comment: Any = None,
    ) -> None:
        self.parent = ws
        self.value = value
        self.font = font
        self.fill = fill
        self.border = border
        self.alignment = alignment
        self.number_format = number_format
        self.protection = protection
        self.hyperlink = hyperlink
        self.comment = comment

    def __repr__(self) -> str:
        return f"<WriteOnlyCell value={self.value!r}>"


__all__ = ["WriteOnlyCell"]
