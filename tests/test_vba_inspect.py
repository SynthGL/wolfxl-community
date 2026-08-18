"""Read-only VBA archive inspection (G19, RFC-072).

Validates the public ``Workbook.vba_archive`` accessor:

* xlsx workbooks (no VBA part) yield ``None``.
* xlsm workbooks loaded via modify-mode surface the raw
  ``xl/vbaProject.bin`` bytes.
* The archive bytes round-trip byte-identical through a load → save →
  reload cycle (the patcher already raw-copies the part; this test
  guards the assertion that ``vba_archive`` continues to match after a
  no-op save).
* Write-mode workbooks (``wolfxl.Workbook()``) and non-modify reads
  yield ``None`` per the v1.0 contract — modify-mode is the only entry
  point that retains the bytes.

Authoring (creating, editing, replacing modules) is out of scope for
v1.0 and is tracked under G28.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import wolfxl


FIXTURE_DIR = Path(__file__).parent / "fixtures"
MACRO_FIXTURE = FIXTURE_DIR / "macro_basic.xlsm"
PLAIN_XLSX = FIXTURE_DIR / "minimal.xlsx"


def _require_macro_fixture() -> Path:
    if not MACRO_FIXTURE.exists():
        pytest.skip(f"VBA fixture missing: {MACRO_FIXTURE}")
    return MACRO_FIXTURE


def test_vba_archive_xlsx_returns_none(tmp_path: Path) -> None:
    """A plain .xlsx (no VBA) loaded via modify mode yields ``None``."""
    if not PLAIN_XLSX.exists():
        pytest.skip("minimal.xlsx fixture missing")
    wb = wolfxl.load_workbook(str(PLAIN_XLSX), modify=True)
    assert wb.vba_archive is None


def test_vba_archive_xlsm_returns_bytes(tmp_path: Path) -> None:
    """An .xlsm loaded via modify mode surfaces non-empty bytes."""
    fixture = _require_macro_fixture()
    wb = wolfxl.load_workbook(str(fixture), modify=True)
    arc = wb.vba_archive
    assert arc is not None
    assert isinstance(arc, (bytes, bytearray, memoryview))
    assert len(arc) > 0


def test_vba_archive_round_trip_preserves_bytes(tmp_path: Path) -> None:
    """Modify-load → save → reload preserves vba_archive byte-for-byte."""
    fixture = _require_macro_fixture()
    work = tmp_path / "macro_round_trip.xlsm"
    shutil.copy(fixture, work)

    wb1 = wolfxl.load_workbook(str(work), modify=True)
    arc1 = wb1.vba_archive
    assert arc1 is not None and len(arc1) > 0
    wb1.save(str(work))

    wb2 = wolfxl.load_workbook(str(work), modify=True)
    arc2 = wb2.vba_archive
    assert arc2 is not None
    assert isinstance(arc2, (bytes, bytearray, memoryview))
    assert len(arc2) > 0
    # The patcher raw-copies xl/vbaProject.bin on save; bytes must match.
    assert bytes(arc2) == bytes(arc1)


def test_vba_archive_write_mode_returns_none(tmp_path: Path) -> None:
    """Write-mode workbooks have no patcher and therefore no VBA archive."""
    wb = wolfxl.Workbook()
    assert wb.vba_archive is None


def test_vba_archive_non_modify_load_returns_none(tmp_path: Path) -> None:
    """Non-modify reads do not retain the VBA bytes in v1.0."""
    fixture = _require_macro_fixture()
    wb = wolfxl.load_workbook(str(fixture))  # no modify=True
    assert wb.vba_archive is None
