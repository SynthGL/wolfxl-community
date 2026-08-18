"""Worksheet structural operation queueing helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from wolfxl.utils.cell import column_index_from_string, range_boundaries

if TYPE_CHECKING:
    from wolfxl._worksheet import Worksheet


def coerce_col_idx(idx: int | str, op: str) -> int:
    """Accept either a 1-based int or an Excel column letter for col ops."""
    if isinstance(idx, str):
        try:
            col_idx = column_index_from_string(idx)
        except Exception as exc:
            raise ValueError(
                f"{op}: idx {idx!r} is not a valid column letter"
            ) from exc
    elif isinstance(idx, int) and not isinstance(idx, bool):
        col_idx = idx
    else:
        raise ValueError(f"{op}: idx must be int or str, got {idx!r}")
    if col_idx < 1:
        raise ValueError(f"{op}: idx must be >= 1, got {idx!r}")
    return col_idx


def insert_rows(ws: Worksheet, idx: int, amount: int = 1) -> None:
    """Queue an insert-rows operation for modify-mode save processing."""
    if not isinstance(idx, int) or idx < 1:
        raise ValueError(
            f"insert_rows: idx must be a positive integer (>=1), got {idx!r}"
        )
    if not isinstance(amount, int) or amount < 1:
        raise ValueError(
            f"insert_rows: amount must be a positive integer (>=1), got {amount!r}"
        )
    if _is_write_mode(ws):
        _shift_in_memory_cells(ws, axis="row", idx=idx, amount=amount)
        return
    ws._workbook._pending_axis_shifts.append((ws.title, "row", idx, amount))  # noqa: SLF001


def delete_rows(ws: Worksheet, idx: int, amount: int = 1) -> None:
    """Queue a delete-rows operation for modify-mode save processing."""
    if not isinstance(idx, int) or idx < 1:
        raise ValueError(
            f"delete_rows: idx must be a positive integer (>=1), got {idx!r}"
        )
    if not isinstance(amount, int) or amount < 1:
        raise ValueError(
            f"delete_rows: amount must be a positive integer (>=1), got {amount!r}"
        )
    if _is_write_mode(ws):
        _shift_in_memory_cells(ws, axis="row", idx=idx, amount=-amount)
        return
    ws._workbook._pending_axis_shifts.append((ws.title, "row", idx, -amount))  # noqa: SLF001


def insert_cols(ws: Worksheet, idx: int | str, amount: int = 1) -> None:
    """Queue an insert-columns operation for modify-mode save processing."""
    col_idx = coerce_col_idx(idx, "insert_cols")
    if not isinstance(amount, int) or amount < 0:
        raise ValueError(
            f"insert_cols: amount must be an integer >= 0, got {amount!r}"
        )
    if amount == 0:
        return
    if _is_write_mode(ws):
        _shift_in_memory_cells(ws, axis="col", idx=col_idx, amount=amount)
        return
    ws._workbook._pending_axis_shifts.append((ws.title, "col", col_idx, amount))  # noqa: SLF001


def delete_cols(ws: Worksheet, idx: int | str, amount: int = 1) -> None:
    """Queue a delete-columns operation for modify-mode save processing."""
    col_idx = coerce_col_idx(idx, "delete_cols")
    if not isinstance(amount, int) or amount < 0:
        raise ValueError(
            f"delete_cols: amount must be an integer >= 0, got {amount!r}"
        )
    if amount == 0:
        return
    if _is_write_mode(ws):
        _shift_in_memory_cells(ws, axis="col", idx=col_idx, amount=-amount)
        return
    ws._workbook._pending_axis_shifts.append((ws.title, "col", col_idx, -amount))  # noqa: SLF001


def move_range(
    ws: Worksheet,
    cell_range: Any,
    rows: int = 0,
    cols: int = 0,
    translate: bool = False,
) -> None:
    """Queue a rectangular range move operation for modify-mode save processing."""
    if not isinstance(rows, int) or isinstance(rows, bool):
        raise TypeError(
            f"move_range: rows must be an int, got {type(rows).__name__}"
        )
    if not isinstance(cols, int) or isinstance(cols, bool):
        raise TypeError(
            f"move_range: cols must be an int, got {type(cols).__name__}"
        )
    range_obj = None if isinstance(cell_range, str) else cell_range
    if range_obj is not None:
        cell_range = str(cell_range)
    try:
        min_col, min_row, max_col, max_row = range_boundaries(cell_range)
    except Exception as exc:
        raise ValueError(
            f"move_range: cell_range must be a valid A1 range string, "
            f"got {cell_range!r}: {exc}"
        ) from exc
    if min_col is None or min_row is None or max_col is None or max_row is None:
        raise ValueError(
            f"move_range: cell_range must have all four corners "
            f"(rows + cols), got {cell_range!r}"
        )
    if rows == 0 and cols == 0:
        return

    dst_min_row = min_row + rows
    dst_max_row = max_row + rows
    dst_min_col = min_col + cols
    dst_max_col = max_col + cols
    if dst_min_row < 1 or dst_max_row > 1_048_576:
        raise ValueError(
            f"move_range: destination row range "
            f"[{dst_min_row}, {dst_max_row}] is out of bounds "
            f"(must be in [1, 1048576])"
        )
    if dst_min_col < 1 or dst_max_col > 16_384:
        raise ValueError(
            f"move_range: destination column range "
            f"[{dst_min_col}, {dst_max_col}] is out of bounds "
            f"(must be in [1, 16384])"
        )
    if _is_write_mode(ws):
        _move_in_memory_range(
            ws,
            int(min_row),
            int(min_col),
            int(max_row),
            int(max_col),
            int(rows),
            int(cols),
            bool(translate),
        )
        if range_obj is not None and hasattr(range_obj, "shift"):
            range_obj.shift(col_shift=int(cols), row_shift=int(rows))
        return
    ws._workbook._pending_range_moves.append(  # noqa: SLF001
        (
            ws.title,
            int(min_col),
            int(min_row),
            int(max_col),
            int(max_row),
            int(rows),
            int(cols),
            bool(translate),
        )
    )
    if range_obj is not None and hasattr(range_obj, "shift"):
        range_obj.shift(col_shift=int(cols), row_shift=int(rows))


def _is_write_mode(ws: Worksheet) -> bool:
    wb = ws._workbook  # noqa: SLF001
    if getattr(wb, "_rust_reader", None) is None and getattr(wb, "_rust_patcher", None) is None:
        return True
    return getattr(wb, "_rust_writer", None) is not None and getattr(wb, "_rust_patcher", None) is None


def move_cell(
    ws: Worksheet,
    row: int,
    column: int,
    row_offset: int,
    col_offset: int,
    translate: bool = False,
) -> None:
    """Move one materialized cell in memory using openpyxl's private helper shape."""
    _move_in_memory_range(
        ws,
        int(row),
        int(column),
        int(row),
        int(column),
        int(row_offset),
        int(col_offset),
        bool(translate),
    )


def gutter(idx: int, offset: int, max_val: int) -> range:
    """Return the indexes left behind by an in-memory row/column delete."""
    return range(max(max_val + 1 - offset, idx), min(idx + offset, max_val) + 1)


def _materialize_pending_write_buffers(ws: Worksheet) -> None:
    if ws._append_buffer:  # noqa: SLF001
        ws._materialize_append_buffer()  # noqa: SLF001
    if ws._bulk_writes:  # noqa: SLF001
        ws._materialize_bulk_writes()  # noqa: SLF001


def _shift_in_memory_cells(ws: Worksheet, *, axis: str, idx: int, amount: int) -> None:
    _materialize_pending_write_buffers(ws)
    if amount == 0:
        return

    new_cells: dict[tuple[int, int], Any] = {}
    deleted_start = idx
    deleted_end = idx + abs(amount) - 1
    for (row, col), cell in list(ws._cells.items()):  # noqa: SLF001
        coordinate = row if axis == "row" else col
        if amount > 0:
            if coordinate >= idx:
                row, col = _offset_coordinate(row, col, axis, amount)
        elif deleted_start <= coordinate <= deleted_end:
            continue
        elif coordinate > deleted_end:
            row, col = _offset_coordinate(row, col, axis, amount)
        cell._row = row  # noqa: SLF001
        cell._col = col  # noqa: SLF001
        cell._value_dirty = True  # noqa: SLF001
        if _cell_has_format(cell):
            cell._format_dirty = True  # noqa: SLF001
        new_cells[(row, col)] = cell
    ws._cells = new_cells  # noqa: SLF001
    _mark_all_materialized_cells_dirty(ws)
    _recompute_write_bounds(ws)


def _offset_coordinate(row: int, col: int, axis: str, amount: int) -> tuple[int, int]:
    if axis == "row":
        return row + amount, col
    return row, col + amount


def _move_in_memory_range(
    ws: Worksheet,
    min_row: int,
    min_col: int,
    max_row: int,
    max_col: int,
    rows: int,
    cols: int,
    translate: bool,
) -> None:
    _materialize_pending_write_buffers(ws)
    source: dict[tuple[int, int], Any] = {}
    for key, cell in list(ws._cells.items()):  # noqa: SLF001
        row, col = key
        if min_row <= row <= max_row and min_col <= col <= max_col:
            source[key] = cell
            del ws._cells[key]  # noqa: SLF001

    dst_min_row = min_row + rows
    dst_max_row = max_row + rows
    dst_min_col = min_col + cols
    dst_max_col = max_col + cols
    for key in list(ws._cells):  # noqa: SLF001
        row, col = key
        if dst_min_row <= row <= dst_max_row and dst_min_col <= col <= dst_max_col:
            del ws._cells[key]  # noqa: SLF001

    for (row, col), cell in source.items():
        new_row = row + rows
        new_col = col + cols
        if translate:
            _translate_cell_formula(cell, row, col, rows, cols)
        cell._row = new_row  # noqa: SLF001
        cell._col = new_col  # noqa: SLF001
        cell._value_dirty = True  # noqa: SLF001
        if _cell_has_format(cell):
            cell._format_dirty = True  # noqa: SLF001
        ws._cells[(new_row, new_col)] = cell  # noqa: SLF001

    _mark_all_materialized_cells_dirty(ws)
    _recompute_write_bounds(ws)


def _translate_cell_formula(cell: Any, row: int, col: int, rows: int, cols: int) -> None:
    value = getattr(cell, "_value", None)
    if not isinstance(value, str) or not value.startswith("="):
        return
    try:
        from openpyxl.formula.translate import Translator

        from wolfxl._utils import rowcol_to_a1

        origin = rowcol_to_a1(row, col)
        cell._value = Translator(value, origin=origin).translate_formula(  # noqa: SLF001
            row_delta=rows,
            col_delta=cols,
        )
    except Exception:
        return


def _cell_has_format(cell: Any) -> bool:
    from wolfxl._cell import _UNSET

    return any(
        getattr(cell, attr, _UNSET) is not _UNSET
        for attr in (
            "_font",
            "_fill",
            "_border",
            "_alignment",
            "_number_format",
            "_protection",
            "_named_style",
        )
    )


def _mark_all_materialized_cells_dirty(ws: Worksheet) -> None:
    ws._dirty = set(ws._cells.keys())  # noqa: SLF001
    ws._dirty_values.clear()  # noqa: SLF001
    ws._format_dirty_cells = {  # noqa: SLF001
        key
        for key, cell in ws._cells.items()  # noqa: SLF001
        if getattr(cell, "_format_dirty", False)
    }


def _recompute_write_bounds(ws: Worksheet) -> None:
    if not ws._cells:  # noqa: SLF001
        ws._max_col_idx = 0  # noqa: SLF001
        ws._next_append_row = 1  # noqa: SLF001
        ws._current_row = 0  # noqa: SLF001
        return
    ws._max_col_idx = max(col for _row, col in ws._cells)  # noqa: SLF001
    ws._current_row = max(row for row, _col in ws._cells)  # noqa: SLF001
    ws._next_append_row = ws._current_row + 1  # noqa: SLF001
