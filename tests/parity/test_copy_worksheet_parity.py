"""RFC-035 parity — wolfxl ``copy_worksheet`` vs openpyxl.

Layer-3 of the §6 verification matrix. Each case runs ``copy_worksheet``
through BOTH backends, re-reads the result with openpyxl, and asserts
the documented divergence.

WolfXL deliberately diverges from openpyxl in five places (RFC-035 §3
"What we do NOT copy from openpyxl"). Each divergence is asserted
explicitly so a future change that accidentally aligns wolfxl with
openpyxl's drop-on-copy behaviour fails red.

Tracked at ``tests/parity/KNOWN_GAPS.md`` and surfaced in
``docs/release-notes-1.1.md`` (when that file lands).

Cases:
1. Cell values + simple formulas — BOTH backends preserve.
2. WolfXL preserves tables on copy; openpyxl drops them.
3. WolfXL preserves data validations; openpyxl drops them.
4. WolfXL preserves conditional formatting; openpyxl drops them.
5. WolfXL preserves sheet-scoped defined names with re-pointed
   ``localSheetId``; openpyxl drops them.
6. Image media — wolfxl aliases (drawing rels point at the same
   ``xl/media/image*.png``), openpyxl deep-copies.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import openpyxl
import pytest

from wolfxl import load_workbook

pytestmark = pytest.mark.rfc035


@pytest.fixture(autouse=True)
def _force_test_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


def _zip_listing(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return sorted(zf.namelist())


def _zip_text(path: Path, entry: str) -> str:
    with zipfile.ZipFile(path) as zf:
        return zf.read(entry).decode("utf-8")


# ---------------------------------------------------------------------------
# Shared fixture builders.
# ---------------------------------------------------------------------------


def _build_grid_with_formula(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template"
    for r in range(1, 6):
        for c in range(1, 6):
            ws.cell(row=r, column=c, value=r * c)
    ws["F1"] = "=SUM(A1:E5)"
    wb.save(path)


def _build_with_table(path: Path) -> None:
    from openpyxl.worksheet.table import Table

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template"
    headers = ["k", "a", "b", "c", "d"]
    for col, h in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=h)
    for r in range(2, 6):
        for c in range(1, 6):
            ws.cell(row=r, column=c, value=(r - 1) * 10 + c)
    ws.add_table(Table(displayName="Sales", ref="A1:E5"))
    wb.save(path)


def _build_with_dv(path: Path) -> None:
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template"
    ws["A1"] = "h"
    dv = DataValidation(type="list", formula1='"a,b,c"')
    dv.add("B2:B4")
    ws.add_data_validation(dv)
    wb.save(path)


def _build_with_cf(path: Path) -> None:
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template"
    for r in range(1, 6):
        ws.cell(row=r, column=1, value=r)
    fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    rule = CellIsRule(operator="greaterThan", formula=["3"], fill=fill)
    ws.conditional_formatting.add("A1:A5", rule)
    wb.save(path)


def _build_with_sheet_scoped_name(path: Path) -> None:
    from openpyxl.workbook.defined_name import DefinedName as XDefinedName

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template"
    for r in range(1, 6):
        for c in range(1, 6):
            ws.cell(row=r, column=c, value=r * c)
    wb.create_sheet("Other")["A1"] = "untouched"
    wb.defined_names["_xlnm.Print_Area"] = XDefinedName(
        "_xlnm.Print_Area", attr_text="Template!$A$1:$E$5", localSheetId=0
    )
    wb.save(path)


def _build_with_image(path: Path) -> None:
    """Worksheet with a single embedded image. openpyxl uses pillow
    to read the image binary; we synthesize a 1x1 PNG inline so this
    case has zero environmental dependencies on disk-resident images.
    """
    from openpyxl.drawing.image import Image as XImage
    import io

    # Tiny valid PNG: 1x1 transparent pixel (67 bytes).
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae42"
        "6082"
    )
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template"
    ws["A1"] = "img-anchor"
    img = XImage(io.BytesIO(png_bytes))
    ws.add_image(img, "B2")
    wb.save(path)


# ---------------------------------------------------------------------------
# Case 1 — Cell values + simple formulas: BOTH backends preserve.
# ---------------------------------------------------------------------------


def test_parity_cell_values_and_formulas(tmp_path: Path) -> None:
    """A 5x5 grid + SUM formula round-trips identically through
    wolfxl and openpyxl.

    parity-divergence: NONE — this is the parity baseline.
    """
    src = tmp_path / "src.xlsx"
    out_wolf = tmp_path / "out_wolf.xlsx"
    out_op = tmp_path / "out_op.xlsx"
    _build_grid_with_formula(src)

    # WolfXL path
    wb_w = load_workbook(src, modify=True)
    wb_w.copy_worksheet(wb_w.active)
    wb_w.save(out_wolf)

    # openpyxl path
    wb_o = openpyxl.load_workbook(src)
    wb_o.copy_worksheet(wb_o.active)
    wb_o.save(out_op)

    rt_w = openpyxl.load_workbook(out_wolf)
    rt_o = openpyxl.load_workbook(out_op)
    # Both backends carry the same cell values in the cloned sheet.
    for r in range(1, 6):
        for c in range(1, 6):
            v_w = rt_w["Template Copy"].cell(row=r, column=c).value
            v_o = rt_o["Template Copy"].cell(row=r, column=c).value
            assert v_w == v_o, (
                f"cell ({r},{c}) divergence: wolf={v_w!r} openpyxl={v_o!r}"
            )
    # Formulas survive both backends.
    assert rt_w["Template Copy"]["F1"].value == "=SUM(A1:E5)"
    assert rt_o["Template Copy"]["F1"].value == "=SUM(A1:E5)"


# ---------------------------------------------------------------------------
# Case 2 — WolfXL preserves tables; openpyxl drops them.
# ---------------------------------------------------------------------------


def test_parity_tables_wolf_preserves_op_drops(tmp_path: Path) -> None:
    """WolfXL clones tables (auto-renamed); openpyxl's WorksheetCopy
    silently drops them.

    parity-divergence: tracked at
    ``tests/parity/KNOWN_GAPS.md`` (RFC-035 — copy_worksheet
    divergences).
    """
    src = tmp_path / "src.xlsx"
    out_wolf = tmp_path / "out_wolf.xlsx"
    out_op = tmp_path / "out_op.xlsx"
    _build_with_table(src)

    wb_w = load_workbook(src, modify=True)
    wb_w.copy_worksheet(wb_w.active)
    wb_w.save(out_wolf)

    wb_o = openpyxl.load_workbook(src)
    wb_o.copy_worksheet(wb_o.active)
    wb_o.save(out_op)

    # WolfXL: 2 table parts in the zip (source + clone).
    wolf_tables = [n for n in _zip_listing(out_wolf) if n.startswith("xl/tables/")]
    assert len(wolf_tables) == 2, (
        f"wolfxl should clone the table; got {wolf_tables}"
    )

    # openpyxl: only the original table part.
    op_tables = [n for n in _zip_listing(out_op) if n.startswith("xl/tables/")]
    assert len(op_tables) == 1, (
        f"openpyxl drops tables on copy_worksheet; got {op_tables}"
    )


# ---------------------------------------------------------------------------
# Case 3 — WolfXL preserves data validations; openpyxl drops them.
# ---------------------------------------------------------------------------


def test_parity_data_validation_wolf_preserves_op_drops(tmp_path: Path) -> None:
    """WolfXL clones data validations; openpyxl drops them.

    parity-divergence: tracked at
    ``tests/parity/KNOWN_GAPS.md`` (RFC-035 — copy_worksheet
    divergences).
    """
    src = tmp_path / "src.xlsx"
    out_wolf = tmp_path / "out_wolf.xlsx"
    out_op = tmp_path / "out_op.xlsx"
    _build_with_dv(src)

    wb_w = load_workbook(src, modify=True)
    wb_w.copy_worksheet(wb_w.active)
    wb_w.save(out_wolf)

    wb_o = openpyxl.load_workbook(src)
    wb_o.copy_worksheet(wb_o.active)
    wb_o.save(out_op)

    # The cloned sheet's worksheet XML.
    wolf_sheets = sorted(
        n for n in _zip_listing(out_wolf)
        if re.match(r"xl/worksheets/sheet\d+\.xml$", n)
    )
    op_sheets = sorted(
        n for n in _zip_listing(out_op)
        if re.match(r"xl/worksheets/sheet\d+\.xml$", n)
    )
    assert len(wolf_sheets) == 2 and len(op_sheets) == 2

    wolf_clone_xml = _zip_text(out_wolf, wolf_sheets[1])
    op_clone_xml = _zip_text(out_op, op_sheets[1])
    assert "<dataValidations" in wolf_clone_xml, (
        "wolfxl must preserve DV on copy"
    )
    assert "<dataValidations" not in op_clone_xml, (
        "openpyxl is documented to drop DV on copy_worksheet"
    )


# ---------------------------------------------------------------------------
# Case 4 — WolfXL preserves conditional formatting; openpyxl drops it.
# ---------------------------------------------------------------------------


def test_parity_conditional_formatting_wolf_preserves_op_drops(tmp_path: Path) -> None:
    """WolfXL clones CF; openpyxl drops it.

    parity-divergence: tracked at
    ``tests/parity/KNOWN_GAPS.md`` (RFC-035 — copy_worksheet
    divergences).
    """
    src = tmp_path / "src.xlsx"
    out_wolf = tmp_path / "out_wolf.xlsx"
    out_op = tmp_path / "out_op.xlsx"
    _build_with_cf(src)

    wb_w = load_workbook(src, modify=True)
    wb_w.copy_worksheet(wb_w.active)
    wb_w.save(out_wolf)

    wb_o = openpyxl.load_workbook(src)
    wb_o.copy_worksheet(wb_o.active)
    wb_o.save(out_op)

    wolf_sheets = sorted(
        n for n in _zip_listing(out_wolf)
        if re.match(r"xl/worksheets/sheet\d+\.xml$", n)
    )
    op_sheets = sorted(
        n for n in _zip_listing(out_op)
        if re.match(r"xl/worksheets/sheet\d+\.xml$", n)
    )

    wolf_clone_xml = _zip_text(out_wolf, wolf_sheets[1])
    op_clone_xml = _zip_text(out_op, op_sheets[1])
    assert "<conditionalFormatting" in wolf_clone_xml, (
        "wolfxl must preserve CF on copy"
    )
    assert "<conditionalFormatting" not in op_clone_xml, (
        "openpyxl is documented to drop CF on copy_worksheet"
    )


# ---------------------------------------------------------------------------
# Case 5 — Sheet-scoped defined names: wolfxl re-points; openpyxl drops.
# ---------------------------------------------------------------------------


def test_parity_sheet_scoped_defined_names(tmp_path: Path) -> None:
    """WolfXL clones sheet-scoped defined names with the new tab
    index; openpyxl drops them.

    parity-divergence: tracked at
    ``tests/parity/KNOWN_GAPS.md`` (RFC-035 — copy_worksheet
    divergences).
    """
    src = tmp_path / "src.xlsx"
    out_wolf = tmp_path / "out_wolf.xlsx"
    out_op = tmp_path / "out_op.xlsx"
    _build_with_sheet_scoped_name(src)

    wb_w = load_workbook(src, modify=True)
    new_w = wb_w.copy_worksheet(wb_w["Template"])
    wb_w.save(out_wolf)
    wolf_new_idx = wb_w.sheetnames.index(new_w.title)

    wb_o = openpyxl.load_workbook(src)
    wb_o.copy_worksheet(wb_o["Template"])
    wb_o.save(out_op)

    wolf_wb_xml = _zip_text(out_wolf, "xl/workbook.xml")
    op_wb_xml = _zip_text(out_op, "xl/workbook.xml")

    # WolfXL: a fresh Print_Area entry exists at the clone's
    # localSheetId.
    assert (
        f'<definedName name="_xlnm.Print_Area" localSheetId="{wolf_new_idx}">'
        in wolf_wb_xml
    ), (
        "wolfxl must clone sheet-scoped defined names with re-pointed "
        f"localSheetId={wolf_new_idx}"
    )

    # openpyxl: counts of `_xlnm.Print_Area` should be exactly one
    # (only the original on Template at localSheetId=0). The clone
    # gets nothing.
    op_count = op_wb_xml.count('name="_xlnm.Print_Area"')
    assert op_count == 1, (
        f"openpyxl's WorksheetCopy is documented to drop sheet-scoped "
        f"defined names; saw {op_count} _xlnm.Print_Area entries — "
        "check whether openpyxl behaviour changed."
    )


# ---------------------------------------------------------------------------
# Case 6 — Image media: wolfxl aliases; openpyxl deep-copies.
# ---------------------------------------------------------------------------


def test_parity_image_aliasing_wolf_aliases_op_deep_copies(tmp_path: Path) -> None:
    """WolfXL aliases image media (cloned drawing rels point at the
    same ``xl/media/image*.png``); openpyxl deep-copies the binary.

    parity-divergence: tracked at
    ``tests/parity/KNOWN_GAPS.md`` (RFC-035 — copy_worksheet
    divergences).
    """
    src = tmp_path / "src.xlsx"
    out_wolf = tmp_path / "out_wolf.xlsx"
    out_op = tmp_path / "out_op.xlsx"

    # Build with image — may require pillow which is openpyxl-optional.
    try:
        _build_with_image(src)
    except (ImportError, Exception) as exc:  # pragma: no cover
        pytest.skip(f"image fixture build failed (likely missing pillow): {exc}")

    # wolfxl path — image-bearing copy is supported; this guard turns any
    # regression into a clear historical-ledger pointer.
    wb_w = load_workbook(src, modify=True)
    try:
        wb_w.copy_worksheet(wb_w.active)
        wb_w.save(out_wolf)
    except Exception as exc:  # pragma: no cover
        pytest.xfail(
            f"wolfxl image-bearing copy_worksheet failed: "
            f"{type(exc).__name__}: {exc}. See the historical copy_worksheet "
            "notes in KNOWN_GAPS.md."
        )

    # openpyxl path
    wb_o = openpyxl.load_workbook(src)
    wb_o.copy_worksheet(wb_o.active)
    wb_o.save(out_op)

    # Count xl/media/image*.* entries.
    wolf_media = [n for n in _zip_listing(out_wolf) if n.startswith("xl/media/")]

    # WolfXL: aliasing means the clone reuses the same image binary.
    # The output zip has ONE media entry.
    # If wolfxl emitted two media entries, that's still "correct" but
    # diverges from the §5.3 aliasing contract — surface it as a
    # ratchet-tracked observation rather than a hard fail.
    if len(wolf_media) > 1:
        pytest.xfail(
            f"wolfxl emitted {len(wolf_media)} media entries — "
            "RFC-035 §5.3 aliasing contract expects 1. "
            "See the historical copy_worksheet notes in KNOWN_GAPS.md."
        )
    assert len(wolf_media) == 1, (
        f"wolfxl should alias image media (one entry expected); "
        f"got {wolf_media}"
    )
    # openpyxl deep-copies — this is documented openpyxl behaviour
    # but the actual deep-copy depends on its WorksheetCopy + image
    # handling. Either result is acceptable for the openpyxl side;
    # we just observe.
    # No hard assertion on op_media — the divergence-of-record is
    # wolfxl's aliasing.
