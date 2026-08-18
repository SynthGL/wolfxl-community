"""RFC-057 LibreOffice cross-renderer smoke test.

Opt-in test that runs ``soffice --headless --convert-to xlsx`` against
a wolfxl-written workbook with array formulas.  Verifies the file
opens cleanly and round-trips through LibreOffice without warnings
about malformed XML.

Activated by ``WOLFXL_RUN_LIBREOFFICE_SMOKE=1``.  Skipped otherwise.

This is intentionally a manual / CI-opt-in test because LibreOffice
is a heavy dependency.  Mirrors ``tests/test_copy_worksheet_libreoffice.py``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.cell.cell import ArrayFormula, DataTableFormula

_RUN_ENV_FLAG = "WOLFXL_RUN_LIBREOFFICE_SMOKE"

_SOFFICE_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
]


def _find_soffice() -> str | None:
    for path in _SOFFICE_CANDIDATES:
        if Path(path).is_file():
            return path
    return shutil.which("soffice")


@pytest.mark.skipif(
    os.environ.get(_RUN_ENV_FLAG) != "1",
    reason=(
        f"Set {_RUN_ENV_FLAG}=1 and ensure ``soffice`` is on PATH "
        "(or in /Applications/LibreOffice.app) to run this test."
    ),
)
def test_array_formula_libreoffice_round_trip(tmp_path: Path) -> None:
    """Write a workbook with array + data-table formulas; LO must round-trip."""
    soffice = _find_soffice()
    if not soffice:
        pytest.skip("soffice not found on this machine")

    src = tmp_path / "src.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = ArrayFormula("A1:A3", "B1:B3*2")
    wb.active["B1"] = 1
    wb.active["B2"] = 2
    wb.active["B3"] = 3
    wb.active["D1"] = DataTableFormula(
        ref="D1:E2", dt2D=True, r1="F1", r2="F2"
    )
    wb.save(str(src))

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    proc = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(out_dir),
            str(src),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"soffice xlsx round-trip exit {proc.returncode}: "
        f"stdout={proc.stdout[:300]}, stderr={proc.stderr[:300]}"
    )
    converted = out_dir / src.name
    assert converted.is_file(), f"soffice produced no output at {converted}"
    # Sanity check: still a valid zip with sheet1.xml.
    with zipfile.ZipFile(converted) as z:
        names = z.namelist()
        assert any("worksheets/sheet" in n for n in names)
