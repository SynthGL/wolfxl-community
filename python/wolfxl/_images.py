"""Internal helpers for image flush — Sprint Λ Pod-β (RFC-045).

Lives at module scope so both the write-mode flush
(``Worksheet._flush_compat_properties``) and the modify-mode flush
(``Workbook._flush_pending_images_to_patcher``) share one shape.

The Rust-side ``NativeWorkbook.add_image`` and
``XlsxPatcher.queue_image_add`` consume the flat dict shape this module
produces.
"""

from __future__ import annotations

from typing import Any

from wolfxl._utils import a1_to_rowcol


def _resolve_anchor_dict(anchor: Any, img_width: int, img_height: int) -> dict[str, Any]:
    """Convert a Python anchor (str A1 / TwoCellAnchor / AbsoluteAnchor /
    OneCellAnchor / None) into the Rust writer's flat-dict shape.

    The writer expects:

    - ``one_cell``: ``{from_col, from_row, from_col_off, from_row_off}``
      (0-based + EMU offsets)
    - ``two_cell``: above + ``{to_col, to_row, to_col_off, to_row_off,
      edit_as}``
    - ``absolute``: ``{x_emu, y_emu, cx_emu, cy_emu}``
    """
    from wolfxl.drawing.spreadsheet_drawing import (
        AbsoluteAnchor,
        OneCellAnchor,
        TwoCellAnchor,
    )

    if anchor is None:
        anchor = "A1"

    if isinstance(anchor, str):
        # A1 cell reference — convert to 0-based (col, row).
        row, col = a1_to_rowcol(anchor)
        return {
            "type": "one_cell",
            "from_col": col - 1,
            "from_row": row - 1,
            "from_col_off": 0,
            "from_row_off": 0,
        }

    if isinstance(anchor, OneCellAnchor):
        m = anchor._from
        return {
            "type": "one_cell",
            "from_col": int(m.col),
            "from_row": int(m.row),
            "from_col_off": int(m.colOff),
            "from_row_off": int(m.rowOff),
        }

    if isinstance(anchor, TwoCellAnchor):
        m = anchor._from
        t = anchor.to
        return {
            "type": "two_cell",
            "from_col": int(m.col),
            "from_row": int(m.row),
            "from_col_off": int(m.colOff),
            "from_row_off": int(m.rowOff),
            "to_col": int(t.col),
            "to_row": int(t.row),
            "to_col_off": int(t.colOff),
            "to_row_off": int(t.rowOff),
            "edit_as": str(getattr(anchor, "editAs", None) or "oneCell"),
        }

    if isinstance(anchor, AbsoluteAnchor):
        return {
            "type": "absolute",
            "x_emu": int(anchor.pos.x),
            "y_emu": int(anchor.pos.y),
            "cx_emu": int(anchor.ext.cx),
            "cy_emu": int(anchor.ext.cy),
        }

    raise TypeError(
        f"add_image: unsupported anchor type {type(anchor).__name__!r}; "
        "expected str (A1), OneCellAnchor, TwoCellAnchor, or AbsoluteAnchor"
    )


def image_to_writer_payload(img: Any) -> dict[str, Any]:
    """Build the flat-dict payload consumed by NativeWorkbook.add_image
    and XlsxPatcher.queue_image_add.
    """
    return {
        "data": img._data,
        "ext": img.format.lower(),
        "width": int(img.width),
        "height": int(img.height),
        "anchor": _resolve_anchor_dict(img.anchor, img.width, img.height),
    }


__all__ = ["image_to_writer_payload"]
