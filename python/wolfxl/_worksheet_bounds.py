"""Worksheet used-range and dimension helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wolfxl._utils import rowcol_to_a1
from wolfxl._worksheet_pending import pending_writes_bounds

if TYPE_CHECKING:
    from wolfxl._worksheet import Worksheet


def calculate_dimension(ws: Worksheet) -> str:
    """Return the used worksheet range in openpyxl's A1 range form."""
    bounds = read_dimension_bounds(ws)
    if bounds is None:
        return "A1:A1"
    min_row, min_col, max_row, max_col = bounds
    return f"{rowcol_to_a1(min_row, min_col)}:{rowcol_to_a1(max_row, max_col)}"


def read_dimension_bounds(ws: Worksheet) -> tuple[int, int, int, int] | None:
    """Return 1-based ``(min_row, min_col, max_row, max_col)`` bounds."""
    workbook = ws._workbook  # noqa: SLF001
    rust_bounds: tuple[int, int, int, int] | None = None
    if getattr(workbook, "_rust_reader", None) is not None:
        raw = workbook._rust_reader.read_sheet_bounds(ws._title)  # noqa: SLF001
        if isinstance(raw, tuple) and len(raw) == 4:
            rust_bounds = tuple(int(value) for value in raw)  # type: ignore[assignment]

    pending = pending_writes_bounds(ws)
    if rust_bounds is None and pending is None:
        return None
    if pending is None:
        return rust_bounds
    if rust_bounds is None:
        return pending
    return (
        min(rust_bounds[0], pending[0]),
        min(rust_bounds[1], pending[1]),
        max(rust_bounds[2], pending[2]),
        max(rust_bounds[3], pending[3]),
    )


def read_dimensions(ws: Worksheet) -> tuple[int, int]:
    """Discover sheet dimensions from the Rust backend in read mode."""
    if ws._dimensions is not None:  # noqa: SLF001
        return ws._dimensions  # noqa: SLF001
    workbook = ws._workbook  # noqa: SLF001
    if getattr(workbook, "_rust_reader", None) is None:
        ws._dimensions = (1, 1)  # noqa: SLF001
        return ws._dimensions  # noqa: SLF001
    xml_dims = workbook._rust_reader.read_sheet_dimensions(ws._title)  # noqa: SLF001
    if isinstance(xml_dims, tuple) and len(xml_dims) == 2:
        ws._dimensions = (int(xml_dims[0]), int(xml_dims[1]))  # noqa: SLF001
        return ws._dimensions  # noqa: SLF001
    rows = workbook._rust_reader.read_sheet_values(ws._title, None, False)  # noqa: SLF001
    if not rows or not isinstance(rows, list):
        ws._dimensions = (1, 1)  # noqa: SLF001
        return ws._dimensions  # noqa: SLF001
    max_row = len(rows)
    max_col = max((len(row) for row in rows), default=1)
    ws._dimensions = (max_row, max_col)  # noqa: SLF001
    return ws._dimensions  # noqa: SLF001


def max_row(ws: Worksheet) -> int:
    """Return the largest row index visible to openpyxl-style callers."""
    if getattr(ws._workbook, "_rust_reader", None) is not None:
        disk_max_row = read_dimensions(ws)[0]
    else:
        disk_max_row = max((key[0] for key in ws._cells), default=0)  # noqa: SLF001
    pending = pending_writes_bounds(ws)
    if pending is None:
        return disk_max_row if disk_max_row else 1
    return max(disk_max_row, pending[2])


def max_col(ws: Worksheet) -> int:
    """Return the largest column index visible to openpyxl-style callers."""
    if getattr(ws._workbook, "_rust_reader", None) is not None:
        disk_max_col = read_dimensions(ws)[1]
    else:
        disk_max_col = max((key[1] for key in ws._cells), default=0)  # noqa: SLF001
    pending = pending_writes_bounds(ws)
    if pending is None:
        return disk_max_col if disk_max_col else 1
    return max(disk_max_col, pending[3])
