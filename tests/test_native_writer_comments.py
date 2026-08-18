"""Sprint Ι Pod-δ D3 — native-writer VML margin honors per-column widths.

Before this fix, ``crates/wolfxl-writer/src/emit/drawings_vml.rs::compute_margin``
hard-coded ``COL_WIDTH_PT = 48.0`` regardless of the sheet's ``<cols>``
overrides. A comment anchored to e.g. column B on a sheet whose column
A was set to width=4 would render with ``margin-left:107.25pt``
(matching the OOXML default), even though the actual column boundary
sat much further left. Excel still drew the marker triangle on the
right cell, but the popup body floated over the wrong area.

The new ``compute_margin_with_widths`` walks per-column widths and
sums them in points, mirroring the modify-mode patcher's
``compute_margin_with_widths`` in ``src/wolfxl/comments.rs``. This
test asserts the writer-side fix lands the comment on the correct
cell boundary.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from wolfxl import Workbook
from wolfxl.comments import Comment


def _read_vml(path: Path) -> str:
    """Return the body of ``xl/drawings/vmlDrawing1.vml`` as text."""
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith("vmlDrawing1.vml") or name == "xl/drawings/vmlDrawing1.vml":
                return zf.read(name).decode("utf-8")
    raise AssertionError(f"vmlDrawing1.vml not found in {path}; entries: {zf.namelist()}")


def _col_units_to_pt(units: float) -> float:
    """Mirror of Rust's ``col_units_to_pt`` — only used by the test for
    hand-computed expected margins."""
    px = int(((units * 7.0 + 5.0) / 7.0 * 7.0 + 5.0))
    return px * 72.0 / 96.0


# OOXML constants (mirror drawings_vml.rs).
ORIGIN_LEFT_PT = 59.25
COL_WIDTH_PT = 48.0


def test_vml_margin_honors_first_column_width_4(tmp_path: Path) -> None:
    """Column A at width=4 → comment on B1 must use the per-column math.

    Without the fix, margin-left = 1 * 48 + 59.25 = 107.25pt.
    With the fix, margin-left = 59.25 + col_units_to_pt(4) ≈ 91.25pt.
    """
    path = tmp_path / "vml_margin_w4.xlsx"
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.column_dimensions["A"].width = 4
    ws["B1"] = "x"
    ws["B1"].comment = Comment(text="hi", author="A")
    wb.save(str(path))

    vml = _read_vml(path)
    expected = ORIGIN_LEFT_PT + _col_units_to_pt(4.0)
    expected_str = f"margin-left:{expected}pt"
    assert expected_str in vml, (
        f"expected margin-left fragment {expected_str!r} not in VML; "
        f"first 400 chars:\n{vml[:400]}"
    )

    # Sanity: the legacy OOXML-default fragment must NOT be present —
    # otherwise the fix wouldn't have flipped behavior.
    legacy = "margin-left:107.25pt"
    assert legacy not in vml, (
        f"legacy default margin {legacy!r} still present after width override:\n"
        f"{vml[:400]}"
    )


def test_vml_margin_unchanged_when_no_col_overrides(tmp_path: Path) -> None:
    """Default-width sheet keeps the legacy ``col0 * 48 + 59.25`` math.

    This guards against silent breakage of every existing comment
    fixture in the writer suite — if `compute_margin_with_widths`
    ever stops short-circuiting on the empty-cols path, this test
    flips red.
    """
    path = tmp_path / "vml_margin_default.xlsx"
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws["B1"] = "x"
    ws["B1"].comment = Comment(text="hi", author="A")
    wb.save(str(path))

    vml = _read_vml(path)
    legacy = f"margin-left:{1 * COL_WIDTH_PT + ORIGIN_LEFT_PT}pt"  # 107.25pt
    assert legacy in vml, f"legacy default fragment missing: {vml[:400]}"
