"""Helpers for worksheet pending-write overlays and bounds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from wolfxl._worksheet import Worksheet


def collect_pending_overlay(ws: Worksheet) -> dict[tuple[int, int], Any]:
    """Return ``{(row, col): value}`` for unsaved worksheet edits."""
    overlay: dict[tuple[int, int], Any] = dict(ws._dirty_values)  # noqa: SLF001
    if ws._dirty:  # noqa: SLF001
        for key in ws._dirty:  # noqa: SLF001
            cell = ws._cells.get(key)  # noqa: SLF001
            if cell is not None:
                overlay[key] = cell.value
    if ws._append_buffer:  # noqa: SLF001
        start = ws._append_buffer_start  # noqa: SLF001
        for row_offset, row_values in enumerate(ws._append_buffer):  # noqa: SLF001
            for col_offset, value in enumerate(row_values):
                overlay[(start + row_offset, col_offset + 1)] = value
    for grid, start_row, start_col, _plain_values_only, _style_grid in ws._bulk_writes:  # noqa: SLF001
        for row_offset, row_values in enumerate(grid):
            for col_offset, value in enumerate(row_values):
                overlay[(start_row + row_offset, start_col + col_offset)] = value
    return overlay


def pending_writes_bounds(ws: Worksheet) -> tuple[int, int, int, int] | None:
    """Return bounds of unsaved writes as ``(min_row, min_col, max_row, max_col)``."""
    dirty = ws._dirty  # noqa: SLF001
    dirty_values = ws._dirty_values  # noqa: SLF001
    buf = ws._append_buffer  # noqa: SLF001
    bulk = ws._bulk_writes  # noqa: SLF001
    if not dirty and not dirty_values and not buf and not bulk:
        return None

    min_r = min_c = None
    max_r = max_c = 0
    for row, col in dirty_values:
        if min_r is None or row < min_r:
            min_r = row
        if min_c is None or col < min_c:
            min_c = col
        if row > max_r:
            max_r = row
        if col > max_c:
            max_c = col

    for row, col in dirty:
        if min_r is None or row < min_r:
            min_r = row
        if min_c is None or col < min_c:
            min_c = col
        if row > max_r:
            max_r = row
        if col > max_c:
            max_c = col

    if buf:
        start = ws._append_buffer_start  # noqa: SLF001
        buf_max_r = start + len(buf) - 1
        buf_max_c = max((len(row) for row in buf), default=0)
        if min_r is None or start < min_r:
            min_r = start
        if buf_max_r > max_r:
            max_r = buf_max_r
        if buf_max_c > 0:
            if min_c is None or 1 < min_c:
                min_c = 1
            if buf_max_c > max_c:
                max_c = buf_max_c

    for grid, start_row, start_col, _plain_values_only, _style_grid in bulk:
        if not grid:
            continue
        grid_max_r = start_row + len(grid) - 1
        grid_width = max((len(row) for row in grid), default=0)
        if grid_width == 0:
            if min_r is None or start_row < min_r:
                min_r = start_row
            if grid_max_r > max_r:
                max_r = grid_max_r
            continue
        grid_max_c = start_col + grid_width - 1
        if min_r is None or start_row < min_r:
            min_r = start_row
        if min_c is None or start_col < min_c:
            min_c = start_col
        if grid_max_r > max_r:
            max_r = grid_max_r
        if grid_max_c > max_c:
            max_c = grid_max_c

    if min_r is None or min_c is None:
        return None
    return min_r, min_c, max_r, max_c
