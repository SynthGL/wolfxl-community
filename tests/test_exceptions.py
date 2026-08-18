"""RFC-059 (Sprint Ο Pod-1E): public exception type contracts.

These tests pin the typed-exception surface against
``wolfxl.utils.exceptions`` so user code that catches
:class:`IllegalCharacterError` / :class:`CellCoordinatesException`
/ :class:`InvalidFileException` works as a drop-in swap from
openpyxl.

The two ``ValueError`` subclasses (`IllegalCharacterError`,
`CellCoordinatesException`) are also covered for backward-compat
with existing ``except ValueError`` callsites.
"""

from __future__ import annotations

import pytest

import wolfxl
from wolfxl import Workbook
from wolfxl.utils.cell import (
    column_index_from_string,
    coordinate_to_tuple,
    range_boundaries,
)
from wolfxl.utils.exceptions import (
    CellCoordinatesException,
    IllegalCharacterError,
    InvalidFileException,
    ReadOnlyWorkbookException,
    WorkbookAlreadySaved,
)


# ---------------------------------------------------------------------------
# IllegalCharacterError — cell value setter
# ---------------------------------------------------------------------------


def test_cell_value_rejects_null_byte() -> None:
    wb = Workbook()
    ws = wb.active
    with pytest.raises(IllegalCharacterError):
        ws["A1"].value = "bad\x00byte"


def test_cell_value_rejects_control_char_x01() -> None:
    wb = Workbook()
    ws = wb.active
    with pytest.raises(IllegalCharacterError):
        ws["A1"].value = "\x01"


def test_cell_value_rejects_del_x7f() -> None:
    wb = Workbook()
    ws = wb.active
    with pytest.raises(IllegalCharacterError):
        ws["A1"].value = "before\x7fafter"


def test_cell_value_allows_tab_newline_cr() -> None:
    """Tab / LF / CR are allowed per OOXML spec — must not raise."""
    wb = Workbook()
    ws = wb.active
    ws["A1"].value = "tab\there\nnewline\rcr"
    assert ws["A1"].value == "tab\there\nnewline\rcr"


def test_illegal_character_error_subclasses_value_error() -> None:
    """Backward-compat: existing ``except ValueError`` still catches."""
    wb = Workbook()
    ws = wb.active
    with pytest.raises(ValueError):
        ws["A1"].value = "\x05"


def test_illegal_character_error_message_is_descriptive() -> None:
    wb = Workbook()
    ws = wb.active
    with pytest.raises(IllegalCharacterError, match="OOXML"):
        ws["A1"].value = "\x02"


def test_cell_value_truncates_before_illegal_character_check() -> None:
    wb = Workbook()
    ws = wb.active
    ws["A1"].value = ("x" * 32767) + "\x01"
    assert ws["A1"].value == "x" * 32767


def test_cell_factory_value_truncates_before_illegal_character_check() -> None:
    wb = Workbook()
    ws = wb.active
    cell = ws.cell(row=1, column=1, value=("x" * 32767) + "\x01")
    assert cell.value == "x" * 32767


def test_illegal_character_error_message_is_short_for_long_values() -> None:
    wb = Workbook()
    ws = wb.active
    with pytest.raises(IllegalCharacterError) as exc_info:
        ws["A1"].value = ("x" * 100) + "\x01"

    message = str(exc_info.value)
    assert "0x01" in message
    assert "length=101" in message
    assert len(message) < 260


# ---------------------------------------------------------------------------
# CellCoordinatesException — coordinate parsers
# ---------------------------------------------------------------------------


def test_coordinate_to_tuple_invalid_raises_cell_coordinates_exception() -> None:
    with pytest.raises(CellCoordinatesException):
        coordinate_to_tuple("not-a-coord")


def test_range_boundaries_invalid_raises_cell_coordinates_exception() -> None:
    with pytest.raises(CellCoordinatesException):
        range_boundaries(":::")


def test_column_index_from_string_too_long_raises() -> None:
    with pytest.raises(CellCoordinatesException, match="not a valid column name"):
        column_index_from_string("AAAA")


def test_cell_coordinates_exception_subclasses_value_error() -> None:
    """Backward-compat: existing ``except ValueError`` still catches."""
    with pytest.raises(ValueError):
        coordinate_to_tuple("???")


# ---------------------------------------------------------------------------
# InvalidFileException — load_workbook
# ---------------------------------------------------------------------------


def test_load_workbook_unknown_bytes_raises_invalid_file_exception() -> None:
    with pytest.raises(InvalidFileException, match="determine file format"):
        wolfxl.load_workbook(b"this is definitely not a spreadsheet payload")


def test_invalid_file_exception_is_plain_exception() -> None:
    """Per openpyxl contract, ``InvalidFileException`` does NOT
    subclass ``ValueError``.  Verifies isinstance vs Exception."""
    exc = InvalidFileException("test")
    assert isinstance(exc, Exception)
    assert not isinstance(exc, ValueError)


# ---------------------------------------------------------------------------
# Stub types — read-only / write-only construction
# ---------------------------------------------------------------------------


def test_read_only_workbook_exception_is_constructible() -> None:
    exc = ReadOnlyWorkbookException("workbook is read-only")
    assert isinstance(exc, Exception)
    assert str(exc) == "workbook is read-only"


def test_workbook_already_saved_is_constructible() -> None:
    exc = WorkbookAlreadySaved("already saved")
    assert isinstance(exc, Exception)
    assert str(exc) == "already saved"
