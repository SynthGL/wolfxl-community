"""G13 — color scales honour user-supplied cfvo + colors.

Each test saves a ``ColorScaleRule`` through ``wolfxl.Workbook.save`` and
reloads via ``wolfxl.load_workbook``. The reloaded :class:`Rule` exposes an
openpyxl-shaped ``colorScale`` shim with ``.cfvo`` and ``.color`` lists so
callers can inspect the persisted gradient anchors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl
from wolfxl.formatting.rule import ColorScaleRule


def _save_and_reload(tmp_path: Path, rule: ColorScaleRule, name: str) -> object:
    """Save ``rule`` on a single sheet at ``A1:A5`` and reload through wolfxl.

    Returns the first ``colorScale`` rule from the reloaded workbook.
    """
    wb = wolfxl.Workbook()
    ws = wb.active
    for i in range(1, 6):
        ws.cell(row=i, column=1, value=i)
    ws.conditional_formatting.add("A1:A5", rule)
    out = tmp_path / f"{name}.xlsx"
    wb.save(out)

    wb2 = wolfxl.load_workbook(out)
    rules: list = []
    for cf_range in wb2.active.conditional_formatting:
        rules.extend(cf_range.rules if hasattr(cf_range, "rules") else [])
    color_scales = [r for r in rules if getattr(r, "type", "") == "colorScale"]
    assert color_scales, f"no colorScale rule preserved for {name}"
    return color_scales[0]


def test_colorscale_2_stop_min_max(tmp_path: Path) -> None:
    """A 2-stop min/max scale round-trips with two cfvo entries."""
    rule = ColorScaleRule(
        start_type="min",
        start_color="FF0000",
        end_type="max",
        end_color="00FF00",
    )
    cs = _save_and_reload(tmp_path, rule, "two_stop")
    assert hasattr(cs, "colorScale")
    cfvo = cs.colorScale.cfvo
    assert len(cfvo) == 2, f"expected 2 cfvo entries, got {len(cfvo)}"
    assert cfvo[0].type == "min"
    assert cfvo[1].type == "max"
    assert cs.colorScale.color[0].endswith("FF0000")
    assert cs.colorScale.color[1].endswith("00FF00")


def test_colorscale_3_stop_with_percentile_mid(tmp_path: Path) -> None:
    """A 3-stop scale with percentile mid preserves all three cfvo types."""
    rule = ColorScaleRule(
        start_type="min",
        start_color="FF0000",
        mid_type="percentile",
        mid_value=50,
        mid_color="FFFF00",
        end_type="max",
        end_color="00FF00",
    )
    cs = _save_and_reload(tmp_path, rule, "three_stop_pct")
    cfvo = cs.colorScale.cfvo
    assert len(cfvo) == 3
    assert [c.type for c in cfvo] == ["min", "percentile", "max"]
    # The percentile cfvo carries val=50; the reader hands it back as a
    # string so callers can parse it however they like.
    assert str(cfvo[1].val) == "50"
    assert cs.colorScale.color[0].endswith("FF0000")
    assert cs.colorScale.color[1].endswith("FFFF00")
    assert cs.colorScale.color[2].endswith("00FF00")


def test_colorscale_with_num_thresholds(tmp_path: Path) -> None:
    """``num`` cfvo type round-trips with a literal threshold value."""
    rule = ColorScaleRule(
        start_type="num",
        start_value=10,
        start_color="FF0000",
        mid_type="num",
        mid_value=50,
        mid_color="FFFF00",
        end_type="num",
        end_value=100,
        end_color="00FF00",
    )
    cs = _save_and_reload(tmp_path, rule, "num_thresholds")
    cfvo = cs.colorScale.cfvo
    assert len(cfvo) == 3
    assert all(c.type == "num" for c in cfvo)
    assert [str(c.val) for c in cfvo] == ["10", "50", "100"]


def test_colorscale_with_formula_threshold(tmp_path: Path) -> None:
    """``formula`` cfvo with a string val round-trips."""
    rule = ColorScaleRule(
        start_type="min",
        start_color="FF0000",
        mid_type="formula",
        mid_value="$A$1",
        mid_color="FFFF00",
        end_type="max",
        end_color="00FF00",
    )
    cs = _save_and_reload(tmp_path, rule, "formula_threshold")
    cfvo = cs.colorScale.cfvo
    assert len(cfvo) == 3
    assert cfvo[1].type == "formula"
    assert cfvo[1].val == "$A$1"


@pytest.mark.parametrize(
    ("color_input", "expected_suffix"),
    [
        ("FF0000", "FF0000"),  # 6-hex normalises to FFFF0000.
        ("FFFF0000", "FFFF0000"),  # 8-hex passes through.
    ],
)
def test_colorscale_color_format_6hex_and_8hex(
    tmp_path: Path, color_input: str, expected_suffix: str
) -> None:
    """6-hex inputs are normalised to 8-hex ARGB; 8-hex passes through."""
    rule = ColorScaleRule(
        start_type="min",
        start_color=color_input,
        end_type="max",
        end_color=color_input,
    )
    cs = _save_and_reload(tmp_path, rule, f"hex_{color_input}")
    color = cs.colorScale.color[0]
    assert color.endswith(expected_suffix)
    # 8-hex ARGB strings are 8 chars long.
    assert len(color) == 8


def test_colorscale_default_3_stop_when_extra_blank(tmp_path: Path) -> None:
    """Bare ``ColorScaleRule()`` still produces a sensible 3-stop default.

    Regression: callers building a no-kwargs ``ColorScaleRule()`` should
    keep landing on the Excel "Red - Yellow - Green" preset, matching the
    pre-G13 hardcoded fallback.
    """
    rule = ColorScaleRule()
    cs = _save_and_reload(tmp_path, rule, "default")
    cfvo = cs.colorScale.cfvo
    assert len(cfvo) == 3, f"default should be 3-stop, got {len(cfvo)}"
    assert cfvo[0].type == "min"
    assert cfvo[1].type == "percentile"
    assert cfvo[2].type == "max"
    # Three colors, all 8-hex ARGB.
    assert len(cs.colorScale.color) == 3
    for color in cs.colorScale.color:
        assert len(color) == 8
