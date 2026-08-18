"""Sprint Ι Pod-δ D4 — `Workbook.defined_names["X"] = DefinedName(...)` round-trip.

Phase 1 KNOWN_GAPS row: Rust ``add_named_range`` already exists; this
exercises the Python-side proxy ``__setitem__`` that dispatches into
it (write mode), as well as input-validation rules.

Covers four scenarios:
    * New workbook-scope name → save → reload → present.
    * Overwrite an existing name → only one entry survives (last-write-wins).
    * Sheet-scope name (``localSheetId`` set) → routed to the right sheet.
    * Invalid name (empty / whitespace / leading digit / cell-ref) → ``ValueError``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wolfxl import Workbook
from wolfxl.workbook.defined_name import DefinedName


def test_setitem_new_workbook_scope_round_trip(tmp_path: Path) -> None:
    """Set a workbook-scope name → save → reload → present."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for i in range(1, 6):
        ws[f"A{i}"] = i
    wb.defined_names["TopFive"] = DefinedName(
        name="TopFive", value=f"{ws.title}!$A$1:$A$5"
    )
    out = tmp_path / "names_new.xlsx"
    wb.save(out)

    wb2 = Workbook._from_reader(str(out))
    assert "TopFive" in wb2.defined_names
    val = wb2.defined_names["TopFive"].value
    assert "$A$1" in val and "$A$5" in val


def test_setitem_overwrites_existing(tmp_path: Path) -> None:
    """Overwriting an existing key → only the last value survives."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = 1
    wb.defined_names["RegionA"] = DefinedName(
        name="RegionA", value=f"{ws.title}!$A$1:$A$1"
    )
    # Second write with the same key — last-write-wins per dict semantics.
    wb.defined_names["RegionA"] = DefinedName(
        name="RegionA", value=f"{ws.title}!$A$1:$A$10"
    )
    out = tmp_path / "names_overwrite.xlsx"
    wb.save(out)

    wb2 = Workbook._from_reader(str(out))
    # Only one DN with this name should round-trip.
    matches = [n for n in wb2.defined_names if n == "RegionA"]
    assert len(matches) == 1
    # The surviving value reflects the SECOND write (10 rows, not 1).
    val = wb2.defined_names["RegionA"].value
    assert "$A$10" in val


def test_setitem_sheet_scope_routed_correctly(tmp_path: Path) -> None:
    """A sheet-scope name (``localSheetId=0``) saves and reloads."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    wb.defined_names["LocalRange"] = DefinedName(
        name="LocalRange",
        value=f"{ws.title}!$A$1:$A$1",
        localSheetId=0,
    )
    out = tmp_path / "names_sheet_scope.xlsx"
    wb.save(out)

    # Reload and check the name is routed to the worksheet like openpyxl 3.1.
    wb2 = Workbook._from_reader(str(out))
    assert "LocalRange" not in wb2.defined_names
    assert "LocalRange" in wb2[ws.title].defined_names


@pytest.mark.parametrize(
    "bad_name",
    [
        "",          # empty string
        "1Foo",      # leading digit
        "Foo Bar",   # contains space
        "Foo\tBar",  # contains tab (whitespace)
        "A1",        # cell-ref-shaped
        "XFD1",      # cell-ref-shaped (max-col)
        "R",         # reserved R1C1 token
        "C",         # reserved R1C1 token
    ],
)
def test_setitem_rejects_invalid_name(bad_name: str) -> None:
    """Invalid Excel names raise ValueError before reaching Rust."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    with pytest.raises(ValueError):
        wb.defined_names[bad_name] = DefinedName(
            name=bad_name, value=f"{ws.title}!$A$1"
        )
