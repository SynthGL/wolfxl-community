"""Oracle-based write parity.

SynthGL writes xlsx in narrow patterns (GL rows, column widths, simple
styles). These tests exercise those patterns by writing with wolfxl, then
re-opening with openpyxl as the reference oracle. If openpyxl can round-trip
the file and values match, the write path is valid.

Keep scenarios small — the goal is to cover the exact write APIs SynthGL
uses, not to re-do ExcelBench's full fidelity matrix.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

wolfxl = pytest.importorskip("wolfxl")
openpyxl = pytest.importorskip("openpyxl")


@pytest.fixture
def tmp_xlsx(tmp_path: Path) -> Path:
    return tmp_path / "wolfxl_out.xlsx"


class _ReopenedWorkbook:
    """Context manager wrapper.

    openpyxl < 3.1 doesn't implement ``__enter__`` / ``__exit__`` on Workbook,
    so we wrap manually to keep the test syntax identical regardless of which
    openpyxl version CI happens to install.
    """

    def __init__(self, path: Path) -> None:
        self._wb = openpyxl.load_workbook(path, data_only=True)

    def __enter__(self) -> Any:
        return self._wb

    def __exit__(self, *exc: object) -> None:
        self._wb.close()


def _reopen(path: Path) -> _ReopenedWorkbook:
    return _ReopenedWorkbook(path)


class TestRoundTripValues:
    """Scalar values wolfxl writes must round-trip via openpyxl."""

    def test_string_int_float(self, tmp_xlsx: Path) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws["A1"] = "hello"
        ws["B1"] = 42
        ws["C1"] = 3.14
        wb.save(tmp_xlsx)

        with _reopen(tmp_xlsx) as op:
            ws2 = op.active
            assert ws2["A1"].value == "hello"
            assert ws2["B1"].value == 42
            assert ws2["C1"].value == pytest.approx(3.14)

    def test_bool_and_none(self, tmp_xlsx: Path) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws["A1"] = True
        ws["B1"] = False
        ws["C1"] = None
        wb.save(tmp_xlsx)

        with _reopen(tmp_xlsx) as op:
            ws2 = op.active
            assert ws2["A1"].value is True
            assert ws2["B1"].value is False
            assert ws2["C1"].value is None

    def test_date_and_datetime(self, tmp_xlsx: Path) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws["A1"] = date(2026, 4, 14)
        ws["B1"] = datetime(2026, 4, 14, 10, 30, 0)
        wb.save(tmp_xlsx)

        with _reopen(tmp_xlsx) as op:
            ws2 = op.active
            # openpyxl reads dates as datetime; compare on the date component.
            a1 = ws2["A1"].value
            assert a1 is not None
            assert (a1.date() if isinstance(a1, datetime) else a1) == date(2026, 4, 14)
            assert ws2["B1"].value == datetime(2026, 4, 14, 10, 30, 0)


class TestRoundTripAppend:
    """``ws.append`` is the GL-row write primitive SynthGL uses most."""

    def test_append_rows(self, tmp_xlsx: Path) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        assert ws is not None
        rows = [
            ["date", "debit", "credit", "memo"],
            ["2026-01-01", 100.0, 0.0, "opening"],
            ["2026-01-02", 0.0, 50.0, "payment"],
        ]
        for r in rows:
            ws.append(r)
        wb.save(tmp_xlsx)

        with _reopen(tmp_xlsx) as op:
            ws2 = op.active
            observed = [
                [cell.value for cell in row]
                for row in ws2.iter_rows(min_row=1, max_row=3, max_col=4)
            ]
            # openpyxl may infer date type — coerce back to ISO string for equality.
            for row in observed:
                if isinstance(row[0], datetime):
                    row[0] = row[0].date().isoformat()
            assert observed == rows


class TestRoundTripMergeAndLayout:
    """Merged cells + column widths — the layout primitives SynthGL touches."""

    def test_merge_cells(self, tmp_xlsx: Path) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws["A1"] = "Header"
        ws.merge_cells("A1:C1")
        wb.save(tmp_xlsx)

        with _reopen(tmp_xlsx) as op:
            ws2 = op.active
            merged = {str(r) for r in ws2.merged_cells.ranges}
            assert "A1:C1" in merged

    def test_column_widths(self, tmp_xlsx: Path) -> None:
        wb = wolfxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.column_dimensions["A"].width = 20.0
        ws.column_dimensions["B"].width = 12.5
        ws["A1"] = "x"  # Force a cell so xlsx isn't empty-saved into a no-op.
        wb.save(tmp_xlsx)

        with _reopen(tmp_xlsx) as op:
            ws2 = op.active
            # rust_xlsxwriter applies an additional padding constant when
            # serializing column widths (~0.71). Until wolfxl normalizes,
            # tolerate a 1.0-unit drift. Tracked in KNOWN_GAPS.md.
            assert ws2.column_dimensions["A"].width == pytest.approx(20.0, abs=1.0)
            assert ws2.column_dimensions["B"].width == pytest.approx(12.5, abs=1.0)
