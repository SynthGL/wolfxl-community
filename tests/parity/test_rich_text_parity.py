"""Sprint Ι Pod-α — parity test: openpyxl ↔ wolfxl rich-text reads.

For the same fixture, ``openpyxl.load_workbook(p, rich_text=True)``
and ``wolfxl.load_workbook(p, rich_text=True)`` produce equivalent
``CellRichText`` shapes — same number of runs, same text per run,
same font booleans / size / color per styled run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl
from wolfxl.cell.rich_text import CellRichText as WolfCRT
from wolfxl.cell.rich_text import TextBlock as WolfTB

openpyxl = pytest.importorskip("openpyxl")
op_rt = pytest.importorskip("openpyxl.cell.rich_text")


def _normalize(value):
    """Reduce a ``CellRichText`` (or plain str) to a list of
    ``(text, font_signature)`` tuples for cross-library comparison.

    openpyxl coerces unset booleans to ``False`` while wolfxl keeps
    them as ``None``.  We normalize both libraries' "absent" / "False"
    booleans to ``False`` so the parity comparison only flags genuine
    divergences (a flag flipped on one side but not the other).
    """
    if isinstance(value, str):
        return [("__plain__", value, None)]
    out = []
    for run in value:
        if isinstance(run, str):
            out.append(("str", run, None))
        else:
            font = run.font
            sig = {
                "b": bool(getattr(font, "b", None) or False),
                "i": bool(getattr(font, "i", None) or False),
                "strike": bool(getattr(font, "strike", None) or False),
                "sz": float(font.sz) if getattr(font, "sz", None) is not None else None,
                "rFont": getattr(font, "rFont", None),
                # openpyxl wraps colors; wolfxl returns a hex string. Compare on hex/string.
                "color": _color_hex(getattr(font, "color", None)),
            }
            out.append(("block", run.text, sig))
    return out


def _color_hex(c):
    if c is None:
        return None
    if isinstance(c, str):
        return c
    # openpyxl Color object.
    return getattr(c, "rgb", None) or getattr(c, "value", None)


@pytest.fixture
def fixture_path(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = op_rt.CellRichText(
        [op_rt.TextBlock(op_rt.InlineFont(b=True), "Bold"), " plain"]
    )
    ws["A2"] = op_rt.CellRichText(
        [op_rt.TextBlock(op_rt.InlineFont(i=True, sz=14), "italic14")]
    )
    ws["A3"] = op_rt.CellRichText(
        [
            op_rt.TextBlock(op_rt.InlineFont(b=True, color="FF00AA00"), "green"),
            " ",
            op_rt.TextBlock(op_rt.InlineFont(rFont="Arial"), "arial"),
        ]
    )
    ws["A4"] = "plain"
    p = tmp_path / "rt_parity.xlsx"
    wb.save(p)
    return p


@pytest.mark.parametrize("a1", ["A1", "A2", "A3", "A4"])
def test_runs_match(fixture_path: Path, a1: str) -> None:
    op_wb = openpyxl.load_workbook(fixture_path, rich_text=True)
    wf_wb = wolfxl.load_workbook(str(fixture_path), rich_text=True)
    op_val = op_wb.active[a1].value
    wf_val = wf_wb.active[a1].value
    assert _normalize(op_val) == _normalize(wf_val), (
        f"rich-text divergence at {a1}: openpyxl={op_val!r} vs wolfxl={wf_val!r}"
    )


def test_wolfxl_rich_text_iterates_like_openpyxl(fixture_path: Path) -> None:
    """``CellRichText`` from wolfxl supports the same iteration protocol."""
    wf_wb = wolfxl.load_workbook(str(fixture_path), rich_text=True)
    val = wf_wb.active["A1"].value
    assert isinstance(val, WolfCRT)
    items = list(val)
    assert len(items) == 2
    assert isinstance(items[0], WolfTB)
    assert items[0].text == "Bold"
    assert items[1] == " plain"
