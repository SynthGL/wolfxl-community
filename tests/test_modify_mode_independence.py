"""Modify mode is independent of the write-mode backend.

After the W5 rip-out, the only write-mode backend is ``NativeWorkbook``.
The modify-mode patcher (``XlsxPatcher``) has its own ZIP-rewrite path
and shares zero code with the writer. This test pins that property: if
a future change introduces a fall-through from the patcher to the
writer, the silent coupling is caught.

One check remains after rip-out:

1. **Source-level**: ``src/wolfxl/`` contains no ``rust_xlsxwriter``
   references. The reference is gone, but a grep enforces the absence
   in case anything reintroduces it.

The T1.5 raise-consistency test was removed once Phase-3 shipped: the
last T1.5-deferred features (RFC-021 defined names, RFC-022 hyperlinks,
RFC-023 comments, RFC-024 tables, RFC-025 data validations, RFC-026
conditional formatting, RFC-020 properties) all now round-trip
cleanly. Positive coverage lives in the per-RFC modify-mode test
files (``tests/test_defined_names_modify.py`` etc.).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "tests" / "fixtures" / "minimal.xlsx"


def test_xlsxpatcher_has_no_rust_xlsxwriter_references() -> None:
    """``src/wolfxl/`` must never import or call ``rust_xlsxwriter``.

    The W5 rip-out removed the dependency entirely. If a future commit
    reintroduces a coupling here (e.g. a debug helper that imports the
    crate), this grep catches it.
    """
    target = REPO / "src" / "wolfxl"
    result = subprocess.run(
        ["grep", "-rln", "rust_xlsxwriter", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    # grep returns 1 when no matches — that's the success path.
    assert result.returncode == 1, (
        "src/wolfxl/ has rust_xlsxwriter references — Wave 5 rip-out "
        "would silently break modify mode. Files with refs:\n"
        f"{result.stdout}"
    )


def test_t15_defined_names_round_trip_in_modify_mode(tmp_path: Path) -> None:
    """RFC-021 — adding defined names to an existing file must
    round-trip cleanly in modify mode. This is the inverse of the
    historical raise-test (preserved at git history before commit
    e2a344b for the audit trail). It catches accidental regressions
    that would re-route the patcher path back through the writer.

    Positive coverage of all RFC-021 paths (add, update, preserve,
    localSheetId, builtin, no-op) lives in
    ``tests/test_defined_names_modify.py``; this test only pins the
    contract that the operation no longer raises.
    """
    if not FIXTURE.exists():
        pytest.skip("hermetic fixture missing")

    from wolfxl.workbook.defined_name import DefinedName

    import wolfxl

    out_dn = tmp_path / "dn.xlsx"
    wb = wolfxl.load_workbook(str(FIXTURE), modify=True)
    wb.defined_names["probe"] = DefinedName(name="probe", value="Sheet1!$A$1")
    wb.save(str(out_dn))  # must not raise — RFC-021 shipped.
    assert out_dn.exists()
