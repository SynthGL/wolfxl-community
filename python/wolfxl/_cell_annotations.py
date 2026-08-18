"""Cell-level hyperlink and comment helpers."""

from __future__ import annotations

from copy import copy
from typing import Any


def get_hyperlink(cell: Any, unset: Any) -> Any:
    """Return the cell hyperlink, including pending unsaved edits."""
    ws = cell._ws
    coord = cell.coordinate
    pending = ws._pending_hyperlinks.get(coord, unset)
    if pending is None:
        return None
    if pending is not unset:
        return pending
    return ws._get_hyperlinks_map().get(coord)


def set_hyperlink(cell: Any, value: Any) -> None:
    """Set or clear the cell hyperlink."""
    from wolfxl.worksheet.hyperlink import Hyperlink

    ws = cell._ws
    wb = ws._workbook
    if wb._rust_writer is None and wb._rust_patcher is None:
        raise RuntimeError("cell.hyperlink requires write or modify mode")

    coord = cell.coordinate
    if value is None:
        ws._pending_hyperlinks[coord] = None
        return

    if isinstance(value, str):
        value = Hyperlink(target=value)
    if not isinstance(value, Hyperlink):
        raise TypeError(
            f"hyperlink must be a Hyperlink or str, got {type(value).__name__}"
        )

    value.ref = coord
    ws._pending_hyperlinks[coord] = value
    if cell.value is None:
        display_value = value.target or value.location or value.display
        if display_value is not None:
            cell.value = display_value


def get_comment(cell: Any, unset: Any) -> Any:
    """Return the cell comment, including pending unsaved edits."""
    ws = cell._ws
    coord = cell.coordinate
    pending = ws._pending_comments.get(coord, unset)
    if pending is None:
        return None
    if pending is not unset:
        return pending
    return ws._get_comments_map().get(coord)


def set_comment(cell: Any, value: Any) -> None:
    """Set or clear the cell comment."""
    from wolfxl.comments import Comment

    ws = cell._ws
    wb = ws._workbook
    if wb._rust_writer is None and wb._rust_patcher is None:
        raise RuntimeError("cell.comment requires write or modify mode")

    coord = cell.coordinate
    if value is None:
        current = get_comment(cell, object())
        if current is not None and getattr(current, "parent", None) is cell:
            current.unbind()
        ws._pending_comments[coord] = None
        cell._comment = None
        return

    if not isinstance(value, Comment):
        raise TypeError(f"comment must be a Comment, got {type(value).__name__}")
    parent = getattr(value, "parent", None)
    if parent is not None and parent is not cell:
        value = copy(value)
    value.bind(cell)
    ws._pending_comments[coord] = value
    cell._comment = value
