"""G14 — stopIfTrue + explicit priority + dxf integration round-trip.

Each test saves a CF rule (or several) through ``wolfxl.Workbook.save`` and
reloads via ``wolfxl.load_workbook``. The reloaded :class:`Rule` exposes the
``stopIfTrue`` flag and the explicit ``priority`` so users can author
openpyxl-style multi-rule blocks. ``fill=PatternFill(...)`` collapses into a
shared ``<dxf>`` record (deduped via ``StylesBuilder::intern_dxf``) and the
emitted ``<cfRule>`` carries a matching ``dxfId``.

The probe ``cf.stop_if_true_priority`` in the openpyxl-compat oracle backs the
``stopIfTrue`` half of this contract; the tests here cover the explicit-priority
and dxf-integration halves so a future regression on either is local.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import wolfxl
from wolfxl.formatting.rule import CellIsRule, FormulaRule
from wolfxl.styles import PatternFill


CF_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _read_sheet_xml(path: Path, sheet: str = "xl/worksheets/sheet1.xml") -> str:
    """Return the raw OOXML text of one worksheet inside an xlsx file."""
    with zipfile.ZipFile(path, "r") as zf:
        with zf.open(sheet) as fh:
            return fh.read().decode("utf-8")


def _read_styles_xml(path: Path) -> str:
    """Return ``xl/styles.xml`` text for inspecting the dxfs table."""
    with zipfile.ZipFile(path, "r") as zf:
        with zf.open("xl/styles.xml") as fh:
            return fh.read().decode("utf-8")


def _save_with_rules(tmp_path: Path, rules: list[tuple[str, object]], name: str) -> Path:
    """Save a workbook with the given (range, rule) pairs and return the path."""
    wb = wolfxl.Workbook()
    ws = wb.active
    for i in range(1, 6):
        ws.cell(row=i, column=1, value=i)
    for range_string, rule in rules:
        ws.conditional_formatting.add(range_string, rule)
    out = tmp_path / f"{name}.xlsx"
    wb.save(out)
    return out


def _reload_rules(path: Path) -> list[object]:
    """Load all CF rules back through wolfxl as a flat list."""
    wb = wolfxl.load_workbook(path)
    rules: list[object] = []
    for cf_range in wb.active.conditional_formatting:
        rules.extend(cf_range.rules if hasattr(cf_range, "rules") else [])
    return rules


# --------------------------------------------------------------------------
# stopIfTrue
# --------------------------------------------------------------------------


def test_stopiftrue_round_trip(tmp_path: Path) -> None:
    """``stopIfTrue=True`` survives wolfxl save/load."""
    rule = CellIsRule(operator="greaterThan", formula=["3"], stopIfTrue=True)
    out = _save_with_rules(tmp_path, [("A1:A5", rule)], "stop_true")

    rules = _reload_rules(out)
    assert rules, "no rules preserved"
    assert getattr(rules[0], "stopIfTrue", False) is True


def test_stopiftrue_default_absent(tmp_path: Path) -> None:
    """A rule without an explicit ``stopIfTrue`` stays absent on reload."""
    rule = CellIsRule(operator="greaterThan", formula=["3"])
    out = _save_with_rules(tmp_path, [("A1:A5", rule)], "stop_default")

    rules = _reload_rules(out)
    assert rules
    assert getattr(rules[0], "stopIfTrue", True) is None


# --------------------------------------------------------------------------
# fill= / dxfId integration
# --------------------------------------------------------------------------


def test_cellis_with_fill_dxf_round_trip(tmp_path: Path) -> None:
    """``fill=PatternFill(...)`` produces a ``<dxf>`` and a ``dxfId`` on the cfRule."""
    rule = CellIsRule(
        operator="greaterThan",
        formula=["3"],
        fill=PatternFill(fill_type="solid", fgColor="FFFF00"),
    )
    out = _save_with_rules(tmp_path, [("A1:A5", rule)], "fill_dxf")

    sheet_xml = _read_sheet_xml(out)
    styles_xml = _read_styles_xml(out)

    # Sheet's cfRule should carry a dxfId attribute.
    assert "dxfId=" in sheet_xml, sheet_xml
    # Styles should contain a dxfs table with at least one dxf carrying our fill.
    assert "<dxfs" in styles_xml
    assert "FFFF00" in styles_xml.upper(), styles_xml


def test_no_dxf_when_no_fill(tmp_path: Path) -> None:
    """A CF rule without ``fill=`` produces no ``dxfId`` on the emitted cfRule."""
    rule = CellIsRule(operator="greaterThan", formula=["3"])
    out = _save_with_rules(tmp_path, [("A1:A5", rule)], "no_fill")

    sheet_xml = _read_sheet_xml(out)
    assert "dxfId=" not in sheet_xml, sheet_xml


def test_dxf_dedup(tmp_path: Path) -> None:
    """Two rules with the same fill share one ``<dxf>`` slot in styles.xml."""
    rule_a = CellIsRule(
        operator="greaterThan",
        formula=["3"],
        fill=PatternFill(fill_type="solid", fgColor="FFFF00"),
    )
    rule_b = FormulaRule(
        formula=["A1<0"],
        fill=PatternFill(fill_type="solid", fgColor="FFFF00"),
    )
    out = _save_with_rules(
        tmp_path,
        [("A1:A5", rule_a), ("B1:B5", rule_b)],
        "dxf_dedup",
    )

    styles_xml = _read_styles_xml(out)
    # Parse the dxfs subtree and count children — should be exactly 1.
    root = ET.fromstring(styles_xml)
    dxfs = root.find(f"{CF_NS}dxfs")
    assert dxfs is not None, "no <dxfs> in styles.xml"
    assert len(list(dxfs)) == 1, f"expected 1 dxf, got {len(list(dxfs))}: {styles_xml}"


# --------------------------------------------------------------------------
# explicit priority
# --------------------------------------------------------------------------


def test_explicit_priority_round_trip(tmp_path: Path) -> None:
    """``rule.priority = 7`` survives wolfxl save/load."""
    rule = CellIsRule(operator="greaterThan", formula=["3"])
    rule.priority = 7  # type: ignore[assignment]
    out = _save_with_rules(tmp_path, [("A1:A5", rule)], "explicit_priority")

    sheet_xml = _read_sheet_xml(out)
    assert 'priority="7"' in sheet_xml, sheet_xml

    rules = _reload_rules(out)
    assert rules
    assert getattr(rules[0], "priority", None) == 7


def test_multiple_rules_priority_ordering(tmp_path: Path) -> None:
    """Three CellIsRules with priorities 3, 1, 2 round-trip with their explicit values."""
    r1 = CellIsRule(operator="greaterThan", formula=["1"])
    r1.priority = 3  # type: ignore[assignment]
    r2 = CellIsRule(operator="greaterThan", formula=["2"])
    r2.priority = 1  # type: ignore[assignment]
    r3 = CellIsRule(operator="greaterThan", formula=["3"])
    r3.priority = 2  # type: ignore[assignment]

    out = _save_with_rules(
        tmp_path,
        [("A1:A5", r1), ("A1:A5", r2), ("A1:A5", r3)],
        "multi_priority",
    )

    sheet_xml = _read_sheet_xml(out)
    # Each emitted rule should carry its authored priority.
    assert 'priority="3"' in sheet_xml, sheet_xml
    assert 'priority="1"' in sheet_xml, sheet_xml
    assert 'priority="2"' in sheet_xml, sheet_xml

    rules = _reload_rules(out)
    priorities = [getattr(r, "priority", None) for r in rules]
    # The reader iterates in document order, so we should see all three values.
    assert sorted(priorities) == [1, 2, 3], priorities


# --------------------------------------------------------------------------
# Combined: stopIfTrue + explicit priority + dxf
# --------------------------------------------------------------------------


def test_combined_stopiftrue_priority_dxf(tmp_path: Path) -> None:
    """Mirrors the openpyxl-compat oracle probe: all three knobs round-trip."""
    rule = CellIsRule(
        operator="greaterThan",
        formula=["3"],
        fill=PatternFill(fill_type="solid", fgColor="FFFF00"),
        stopIfTrue=True,
    )
    rule.priority = 1  # type: ignore[assignment]
    out = _save_with_rules(tmp_path, [("A1:A5", rule)], "combined")

    sheet_xml = _read_sheet_xml(out)
    assert "stopIfTrue=" in sheet_xml, sheet_xml
    assert 'priority="1"' in sheet_xml, sheet_xml
    assert "dxfId=" in sheet_xml, sheet_xml

    rules = _reload_rules(out)
    assert rules
    r0 = rules[0]
    assert getattr(r0, "stopIfTrue", False) is True
    assert getattr(r0, "priority", None) == 1
