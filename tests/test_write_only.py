"""Focused tests for ``Workbook(write_only=True)`` streaming write mode.

Sprint 7 / G20 / RFC-073. Mirrors openpyxl's `_write_only.py` contract:

* `WriteOnlyWorksheet.append(iterable)` is the single supported write API.
* Random access (`ws["A1"]`, `ws.cell(...)`, `iter_rows`) raises
  AttributeError.
* Re-save raises WorkbookAlreadySaved.
* Post-save append raises WorkbookAlreadySaved.
* Sheet-level slots (column_dimensions, freeze_panes, print_area) must
  be set BEFORE the first append.
* Streaming output is byte-identical to eager output for the same row
  payloads.

The 12-test surface here is the user-facing acceptance gate. Cargo-side
byte-parity already runs in `crates/wolfxl-writer/tests/streaming_write.rs`.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

import wolfxl
from wolfxl._worksheet_write_only import WriteOnlyCell
from wolfxl.utils.exceptions import WorkbookAlreadySaved


# ---------------------------------------------------------------------------
# Test 1 — basic round-trip: write 100 rows, read back identical values.
# ---------------------------------------------------------------------------


def test_basic_streaming_round_trip(tmp_path: Path) -> None:
    """Append 100 rows of numbers + strings; re-read every value matches."""
    wb = wolfxl.Workbook(write_only=True)
    ws = wb.create_sheet("Data")
    for i in range(1, 101):
        ws.append([i, f"row{i}", i * 1.5])
    out = tmp_path / "basic.xlsx"
    wb.save(out)

    rb = wolfxl.load_workbook(out)
    sheet = rb["Data"]
    rows = list(sheet.iter_rows(values_only=True, max_row=100))
    assert len(rows) == 100
    assert rows[0] == (1, "row1", 1.5)
    assert rows[99] == (100, "row100", 150.0)


# ---------------------------------------------------------------------------
# Test 2 — WriteOnlyCell with styles flows through the SST + styles builder.
# ---------------------------------------------------------------------------


def test_write_only_cell_styles(tmp_path: Path) -> None:
    """Styled WriteOnlyCells survive round-trip through the streaming path."""
    from wolfxl.styles import Font

    wb = wolfxl.Workbook(write_only=True)
    ws = wb.create_sheet("Styled")
    bold = Font(bold=True)
    ws.append([WriteOnlyCell(ws, "header", font=bold)])
    ws.append([WriteOnlyCell(ws, "value", number_format="0.00")])
    out = tmp_path / "styled.xlsx"
    wb.save(out)

    rb = wolfxl.load_workbook(out)
    cell = rb["Styled"]["A1"]
    assert cell.value == "header"
    # Style slot exists (we don't assert the exact font payload here —
    # that's the styles round-trip suite's job).
    assert cell.font is not None


# ---------------------------------------------------------------------------
# Test 3 — random access methods raise AttributeError.
# ---------------------------------------------------------------------------


def test_forbidden_methods_raise() -> None:
    """`cell`, `iter_rows`, `[]` access, etc. raise AttributeError."""
    wb = wolfxl.Workbook(write_only=True)
    ws = wb.create_sheet("X")

    with pytest.raises(AttributeError):
        _ = ws["A1"]
    with pytest.raises(AttributeError):
        ws["A1"] = "x"
    with pytest.raises(AttributeError):
        ws.cell(row=1, column=1)
    with pytest.raises(AttributeError):
        list(ws.iter_rows())
    with pytest.raises(AttributeError):
        ws.merge_cells("A1:B2")


# ---------------------------------------------------------------------------
# Test 4 — second save raises WorkbookAlreadySaved.
# ---------------------------------------------------------------------------


def test_double_save_raises(tmp_path: Path) -> None:
    """Second `wb.save(...)` raises WorkbookAlreadySaved in write-only mode."""
    wb = wolfxl.Workbook(write_only=True)
    ws = wb.create_sheet("X")
    ws.append([1, 2, 3])
    out1 = tmp_path / "first.xlsx"
    out2 = tmp_path / "second.xlsx"
    wb.save(out1)
    with pytest.raises(WorkbookAlreadySaved):
        wb.save(out2)


# ---------------------------------------------------------------------------
# Test 5 — appending after save raises WorkbookAlreadySaved.
# ---------------------------------------------------------------------------


def test_append_after_save_raises(tmp_path: Path) -> None:
    """Appending to a write-only sheet after save raises WorkbookAlreadySaved."""
    wb = wolfxl.Workbook(write_only=True)
    ws = wb.create_sheet("X")
    ws.append([1])
    wb.save(tmp_path / "x.xlsx")
    with pytest.raises(WorkbookAlreadySaved):
        ws.append([2])


# ---------------------------------------------------------------------------
# Test 6 — column_dimensions and row_dimensions slots are accessible.
# ---------------------------------------------------------------------------


def test_column_and_row_dimensions_slots() -> None:
    """The dimension slots exist; setting them is allowed before append."""
    wb = wolfxl.Workbook(write_only=True)
    ws = wb.create_sheet("Dims")
    # Dimension slots exist as plain dicts on the WriteOnlyWorksheet so
    # callers can populate them; the setter discipline is "before any
    # append". The actual dim-XML emission is a v1.5 follow-up — for v1
    # we just make sure the slots accept assignments.
    ws.column_dimensions["A"] = "stub"
    ws.row_dimensions[1] = "stub"
    assert ws.column_dimensions["A"] == "stub"
    assert ws.row_dimensions[1] == "stub"


# ---------------------------------------------------------------------------
# Test 7 — freeze_panes setter accepts pre-append, raises post-append.
# ---------------------------------------------------------------------------


def test_freeze_panes_must_be_set_before_append(tmp_path: Path) -> None:
    """Setting freeze_panes after the first append raises RuntimeError."""
    wb = wolfxl.Workbook(write_only=True)
    ws = wb.create_sheet("F")
    ws.freeze_panes = "B2"  # before append → fine
    ws.append([1, 2, 3])
    with pytest.raises(RuntimeError):
        ws.freeze_panes = "C3"
    out = tmp_path / "freeze.xlsx"
    wb.save(out)
    rb = wolfxl.load_workbook(out)
    # Smoke check that the file is readable post-save.
    assert "F" in rb.sheetnames


# ---------------------------------------------------------------------------
# Test 8 — heterogeneous types in one row.
# ---------------------------------------------------------------------------


def test_mixed_value_types(tmp_path: Path) -> None:
    """A single row with int, float, str, bool, datetime, date, None survives."""
    wb = wolfxl.Workbook(write_only=True)
    ws = wb.create_sheet("Mix")
    ws.append(
        [
            1,
            2.5,
            "text",
            True,
            datetime(2026, 5, 4, 12, 0, 0),
            date(2026, 5, 4),
            None,
        ]
    )
    out = tmp_path / "mix.xlsx"
    wb.save(out)

    rb = wolfxl.load_workbook(out)
    row = next(rb["Mix"].iter_rows(values_only=True, max_row=1))
    assert row[0] == 1
    assert row[1] == 2.5
    assert row[2] == "text"
    assert row[3] is True
    # datetime / date round-trip as datetime in xlsx (no native date type).
    assert isinstance(row[4], datetime)
    assert row[4].year == 2026
    assert isinstance(row[5], (datetime, date))
    # Trailing None column is not emitted as a cell — the row tuple
    # ends at the last populated column, matching the eager path.


# ---------------------------------------------------------------------------
# Test 9 — multiple sheets stream independently.
# ---------------------------------------------------------------------------


def test_multiple_streaming_sheets(tmp_path: Path) -> None:
    """Two streaming sheets each get their own temp file and round-trip."""
    wb = wolfxl.Workbook(write_only=True)
    a = wb.create_sheet("A")
    b = wb.create_sheet("B")
    for i in range(1, 11):
        a.append([i, f"a{i}"])
        b.append([i * 10, f"b{i}"])
    out = tmp_path / "multi.xlsx"
    wb.save(out)

    rb = wolfxl.load_workbook(out)
    a_rows = list(rb["A"].iter_rows(values_only=True, max_row=10))
    b_rows = list(rb["B"].iter_rows(values_only=True, max_row=10))
    assert a_rows[0] == (1, "a1")
    assert a_rows[-1] == (10, "a10")
    assert b_rows[0] == (10, "b1")
    assert b_rows[-1] == (100, "b10")


# ---------------------------------------------------------------------------
# Test 10 — empty write-only workbook saves cleanly.
# ---------------------------------------------------------------------------


def test_empty_streaming_sheet_self_closes(tmp_path: Path) -> None:
    """A streaming sheet with zero appends emits `<sheetData/>` and reads back empty."""
    wb = wolfxl.Workbook(write_only=True)
    wb.create_sheet("Empty")
    out = tmp_path / "empty.xlsx"
    wb.save(out)

    rb = wolfxl.load_workbook(out)
    rows = list(rb["Empty"].iter_rows(values_only=True))
    assert rows == [] or all(all(c is None for c in r) for r in rows)


# ---------------------------------------------------------------------------
# Test 11 — default sheet is NOT created in write_only mode.
# ---------------------------------------------------------------------------


def test_no_default_sheet_in_write_only_mode() -> None:
    """`Workbook(write_only=True)` skips the default 'Sheet'."""
    wb = wolfxl.Workbook(write_only=True)
    assert wb.sheetnames == []
    assert wb.write_only is True


# ---------------------------------------------------------------------------
# Test 12 — byte-parity: 50 rows streamed equal 50 rows eager-written.
# ---------------------------------------------------------------------------


def test_byte_parity_with_eager_mode(tmp_path: Path) -> None:
    """Streaming output reads back identical to the same rows written eagerly.

    We don't compare bytes (eager-mode goes through write_value_grid /
    write_cell_value with slightly different style allocation order).
    Instead we compare the round-tripped values cell-by-cell — that's
    the user-facing contract.
    """
    rows = [(i, f"v{i}", i % 2 == 0) for i in range(1, 51)]

    # Eager
    wb1 = wolfxl.Workbook()
    ws1 = wb1["Sheet"]
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row, start=1):
            ws1.cell(row=r, column=c, value=val)
    eager_out = tmp_path / "eager.xlsx"
    wb1.save(eager_out)

    # Streaming
    wb2 = wolfxl.Workbook(write_only=True)
    ws2 = wb2.create_sheet("Sheet")
    for row in rows:
        ws2.append(list(row))
    stream_out = tmp_path / "stream.xlsx"
    wb2.save(stream_out)

    eager = wolfxl.load_workbook(eager_out)
    stream = wolfxl.load_workbook(stream_out)
    eager_rows = list(eager["Sheet"].iter_rows(values_only=True, max_row=50))
    stream_rows = list(stream["Sheet"].iter_rows(values_only=True, max_row=50))
    assert eager_rows == stream_rows
