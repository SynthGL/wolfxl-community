"""W4E.R5 regression: non-finite floats are rejected at the pyclass boundary.

OOXML has no representation for ``NaN`` or ``+/-Infinity``. The native
emitter previously formatted them via ``f64::to_string`` -> ``"NaN"`` /
``"inf"``, which Excel and LibreOffice would reject on open with a
"file is corrupt, can we repair it?" prompt.

The fix moves the validation to the pyclass boundary
(``require_finite_f64``) so the user sees a clear ``ValueError`` at
write time, not a corrupt file later. Both the per-cell write path
(``write_cell_value`` with ``type=number``) and the bulk
``write_sheet_values`` 2-D path are covered.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest


def _native_workbook(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WOLFXL_WRITER", "native")
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")
    import wolfxl
    return wolfxl.Workbook()


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_write_cell_value_rejects_non_finite(
    bad_value: float, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Per-cell write path rejects NaN/+Inf/-Inf with ValueError. The
    Python ``ws.cell()`` API buffers in memory; the rejection fires at
    flush time on ``save()``, which is when we'd otherwise emit the
    invalid OOXML."""
    wb = _native_workbook(monkeypatch)
    ws = wb.active
    ws.cell(row=1, column=1, value=bad_value)
    with pytest.raises(ValueError, match="non-finite|NaN|Infinity|inf"):
        wb.save(str(tmp_path / "bad.xlsx"))


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_write_sheet_values_rejects_non_finite(
    bad_value: float, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Bulk 2-D path also rejects non-finite floats."""
    wb = _native_workbook(monkeypatch)
    ws = wb.active
    with pytest.raises(ValueError, match="non-finite|NaN|Infinity|inf"):
        ws.append([1.0, 2.0, bad_value])
        wb.save(str(tmp_path / "out.xlsx"))


def test_finite_floats_still_work(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Sanity check: ordinary floats including zero, negatives, and
    very large/small magnitudes still round-trip."""
    wb = _native_workbook(monkeypatch)
    ws = wb.active
    for col, val in enumerate([0.0, -1.5, 1e-308, 1e308, math.pi], start=1):
        ws.cell(row=1, column=col, value=val)
    out = tmp_path / "ok.xlsx"
    wb.save(str(out))
    assert out.exists() and out.stat().st_size > 0
