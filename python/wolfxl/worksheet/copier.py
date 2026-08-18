"""``openpyxl.worksheet.copier`` — :class:`WorksheetCopy` value type."""

from __future__ import annotations

from copy import copy
from typing import Any

from wolfxl._cell import _UNSET
from wolfxl._worksheet import Worksheet


class WorksheetCopy:
    """Copy worksheet state from an existing source sheet into a target sheet."""

    __slots__ = ("source", "target")

    def __init__(self, source: Any, target: Any) -> None:
        self.source = source
        self.target = target
        self._verify_resources()

    def _verify_resources(self) -> None:
        """Validate the source and target sheets using openpyxl's rules."""
        if not isinstance(self.source, Worksheet) or not isinstance(self.target, Worksheet):
            raise TypeError("Can only copy worksheets")
        if self.source is self.target:
            raise ValueError("Cannot copy a worksheet to itself")
        if self.source.parent != self.target.parent:
            raise ValueError("Cannot copy between worksheets from different workbooks")

    def copy_worksheet(self) -> Any:
        """Copy cells and worksheet-level metadata into the existing target."""
        self._copy_cells()
        self._copy_dimensions()
        self.target.sheet_format = copy(self.source.sheet_format)
        self.target.sheet_properties = copy(self.source.sheet_properties)
        self._copy_merged_cells()
        self.target.page_margins = copy(self.source.page_margins)
        self.target.page_setup = copy(self.source.page_setup)
        self.target._print_options = copy(self.source.print_options)  # noqa: SLF001

    def _copy_cells(self) -> None:
        """Copy materialized cell values, data types, styles, links, and comments."""
        self._materialize_source_cells()
        for (row, col), source_cell in self.source._cells.items():  # noqa: SLF001
            target_cell = self.target.cell(column=col, row=row)

            value = source_cell.value
            target_cell._value = value  # noqa: SLF001
            target_cell._value_dirty = value is not _UNSET  # noqa: SLF001
            target_cell.data_type = source_cell.data_type

            target_cell._style = copy(source_cell._style)  # noqa: SLF001

            hyperlink = source_cell.hyperlink
            if hyperlink:
                target_cell.hyperlink = copy(hyperlink)

            comment = source_cell.comment
            if comment:
                target_cell.comment = copy(comment)
        if self.target._cells:  # noqa: SLF001
            self.target._dimensions = (  # noqa: SLF001
                max(row for row, _col in self.target._cells),  # noqa: SLF001
                max(col for _row, col in self.target._cells),  # noqa: SLF001
            )

    def _copy_dimensions(self) -> None:
        """Copy row and column display metadata into the target worksheet."""
        _copy_row_dimensions(self.source, self.target)
        _copy_column_dimensions(self.source, self.target)

    def _copy_merged_cells(self) -> None:
        refs = {str(rng) for rng in self.source.merged_cells.ranges}
        self.target._merged_ranges = set(refs)  # noqa: SLF001
        self.target._collection_merged_ranges = set(refs)  # noqa: SLF001
        self.target._pending_collection_merged_ranges.update(refs)  # noqa: SLF001

    def _materialize_source_cells(self) -> None:
        if self.source._cells:  # noqa: SLF001
            return
        if getattr(self.source._workbook, "_rust_reader", None) is None:  # noqa: SLF001
            return
        for row in self.source.iter_rows():
            for cell in row:
                cell.value

    def copy_cells(self) -> Any:
        """Compatibility alias for callers using the older WolfXL helper."""
        return self.copy_worksheet()


def _copy_row_dimensions(source: Worksheet, target: Worksheet) -> None:
    for key, dimension in source.row_dimensions.items():
        height = dimension.height
        hidden = dimension.hidden
        outline_level = dimension.outlineLevel
        copied = copy(dimension)
        copied._ws = target  # noqa: SLF001
        target._row_dimensions.add(key)  # noqa: SLF001
        if height is not None:
            target._row_heights[key] = height  # noqa: SLF001
        target._row_hidden[key] = hidden  # noqa: SLF001
        target._row_outline_levels[key] = outline_level  # noqa: SLF001


def _copy_column_dimensions(source: Worksheet, target: Worksheet) -> None:
    for key, dimension in source.column_dimensions.items():
        width = dimension.width
        hidden = dimension.hidden
        outline_level = dimension.outlineLevel
        copied = copy(dimension)
        copied._ws = target  # noqa: SLF001
        target._col_dimensions.add(key)  # noqa: SLF001
        target._column_dimension_cache[key] = copied  # noqa: SLF001
        if width is not None:
            target._col_widths[key] = width  # noqa: SLF001
        target._col_hidden[key] = hidden  # noqa: SLF001
        target._col_outline_levels[key] = outline_level  # noqa: SLF001


__all__ = ["Worksheet", "WorksheetCopy", "copy"]
