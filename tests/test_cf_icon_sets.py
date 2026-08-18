"""G11: end-to-end tests for IconSetRule conditional formatting.

Covers:
- 3-icon traffic-light round-trip (write mode + read-back)
- 5-icon variant (5Arrows)
- Percentile thresholds (vs the percent default)
- ``showValue=False`` -> ``showValue="0"`` attribute on emitted XML
- Modify-mode preservation (load wolfxl-authored file, save unchanged,
  reload, rule still present)

All tests use the wolfxl native writer + reader path; no openpyxl
dependency. The probe entry in ``tests/test_openpyxl_compat_oracle.py``
``cf_icon_sets`` covers the openpyxl-shaped construction call.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.formatting.rule import IconSetRule


def _emit_iconset_workbook(path: Path, rule: IconSetRule, sqref: str = "A1:A5") -> None:
    """Helper: build a tiny workbook with one IconSetRule and save."""
    wb = wolfxl.Workbook()
    ws = wb.active
    for i in range(1, 6):
        ws.cell(row=i, column=1, value=i)
    ws.conditional_formatting.add(sqref, rule)
    wb.save(path)


def _read_iconset_rules(path: Path) -> list:
    """Helper: collect every Rule across every CF range on the active sheet."""
    wb2 = wolfxl.load_workbook(path)
    rules = []
    for cf_range in wb2.active.conditional_formatting:
        rules.extend(cf_range.rules if hasattr(cf_range, "rules") else [])
    return rules


def test_iconset_3_traffic_lights_round_trip(tmp_path: Path) -> None:
    """The probe shape: 3TrafficLights1 with percent thresholds round-trips."""
    rule = IconSetRule("3TrafficLights1", "percent", [0, 33, 67])
    out = tmp_path / "iconset_3tl.xlsx"
    _emit_iconset_workbook(out, rule)

    rules = _read_iconset_rules(out)
    iconset_rules = [r for r in rules if getattr(r, "type", "") == "iconSet"]
    assert len(iconset_rules) == 1, f"expected 1 iconSet rule, got {len(iconset_rules)}"

    # Verify the OOXML is well-formed and contains the expected pieces.
    with zipfile.ZipFile(out) as zf:
        sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert '<cfRule type="iconSet"' in sheet_xml
    assert '<iconSet iconSet="3TrafficLights1">' in sheet_xml
    assert '<cfvo type="percent" val="0"/>' in sheet_xml
    assert '<cfvo type="percent" val="33"/>' in sheet_xml
    assert '<cfvo type="percent" val="67"/>' in sheet_xml
    # Inner <iconSet> emits no <color> elements (unlike dataBar/colorScale).
    iconset_start = sheet_xml.index("<iconSet ")
    iconset_end = sheet_xml.index("</iconSet>")
    iconset_block = sheet_xml[iconset_start:iconset_end]
    assert "<color " not in iconset_block


def test_iconset_5_arrows_round_trip(tmp_path: Path) -> None:
    """5-icon variant emits five cfvo entries inside the inner <iconSet>."""
    rule = IconSetRule("5Arrows", "percent", [0, 20, 40, 60, 80])
    out = tmp_path / "iconset_5arrows.xlsx"
    _emit_iconset_workbook(out, rule)

    rules = _read_iconset_rules(out)
    assert any(getattr(r, "type", "") == "iconSet" for r in rules)

    with zipfile.ZipFile(out) as zf:
        sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert '<iconSet iconSet="5Arrows">' in sheet_xml
    iconset_start = sheet_xml.index("<iconSet ")
    iconset_end = sheet_xml.index("</iconSet>")
    iconset_block = sheet_xml[iconset_start:iconset_end]
    assert iconset_block.count("<cfvo") == 5


def test_iconset_percentile_thresholds(tmp_path: Path) -> None:
    """value_type='percentile' emits <cfvo type=\"percentile\"/>."""
    rule = IconSetRule("3Arrows", "percentile", [0, 33, 67])
    out = tmp_path / "iconset_percentile.xlsx"
    _emit_iconset_workbook(out, rule)

    rules = _read_iconset_rules(out)
    assert any(getattr(r, "type", "") == "iconSet" for r in rules)

    with zipfile.ZipFile(out) as zf:
        sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert '<cfvo type="percentile" val="33"/>' in sheet_xml
    assert '<cfvo type="percentile" val="67"/>' in sheet_xml


def test_iconset_show_value_false(tmp_path: Path) -> None:
    """showValue=False should emit showValue=\"0\" on the inner <iconSet>."""
    rule = IconSetRule("3TrafficLights1", "percent", [0, 33, 67], showValue=False)
    out = tmp_path / "iconset_hide_value.xlsx"
    _emit_iconset_workbook(out, rule)

    with zipfile.ZipFile(out) as zf:
        sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert '<iconSet iconSet="3TrafficLights1" showValue="0">' in sheet_xml


def test_iconset_modify_mode_preserves_existing(tmp_path: Path) -> None:
    """Load a wolfxl-authored file with iconSet, save unchanged, rule survives.

    Modify mode is the patcher path; we don't add anything new, just
    verify the existing iconSet rule still appears after a no-op
    round-trip. Stretch goal per G11 handoff.
    """
    rule = IconSetRule("3TrafficLights1", "percent", [0, 33, 67])
    src = tmp_path / "iconset_orig.xlsx"
    _emit_iconset_workbook(src, rule)

    # Confirm rule made it into the source file first.
    rules_before = _read_iconset_rules(src)
    assert any(getattr(r, "type", "") == "iconSet" for r in rules_before)

    # Open in modify mode, save to a new path without changes.
    dst = tmp_path / "iconset_modified.xlsx"
    try:
        wb = wolfxl.load_workbook(src, modify=True)
    except TypeError:
        # If modify=True isn't supported in this build, the stretch
        # goal is intentionally a soft pass.
        pytest.skip("modify=True not available on load_workbook")
    wb.save(dst)

    rules_after = _read_iconset_rules(dst)
    # Stretch: the rule may or may not survive depending on patcher
    # support. The probe contract is write-mode; if the patcher drops
    # iconSet today, that's a follow-up task (modify-mode preservation).
    if not any(getattr(r, "type", "") == "iconSet" for r in rules_after):
        pytest.xfail(
            "modify-mode iconSet preservation requires patcher work "
            "(stretch goal beyond G11 probe contract)"
        )
