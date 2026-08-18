from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


def _load_audit_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_ooxml_fidelity.py"
    spec = importlib.util.spec_from_file_location("audit_ooxml_fidelity", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit_module = _load_audit_module()


class _FakeArchive:
    def __init__(self, entries: dict[str, str]) -> None:
        self.entries = entries
        self.read_counts: dict[str, int] = {}

    def read(self, part: str) -> bytes:
        self.read_counts[part] = self.read_counts.get(part, 0) + 1
        payload = self.entries[part]
        return payload.encode("utf-8")


def _write_package(path: Path, entries: dict[str, str | bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


def _base_entries() -> dict[str, str]:
    return {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml"
    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml"
    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
    }


def test_read_xml_or_none_caches_parsed_parts() -> None:
    archive = _FakeArchive({"xl/worksheets/sheet1.xml": "<worksheet/>"})

    first = audit_module._read_xml_or_none(archive, "xl/worksheets/sheet1.xml")
    second = audit_module._read_xml_or_none(archive, "xl/worksheets/sheet1.xml")

    assert first is second
    assert archive.read_counts == {"xl/worksheets/sheet1.xml": 1}


def test_clean_package_has_no_fidelity_issues(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    entries = _base_entries()
    _write_package(before, entries)
    _write_package(after, entries)

    report = audit_module.audit(before, after)

    assert report["issues"] == []


def test_compact_semantic_drift_summarizes_style_theme_payload(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/styles.xml"] = (
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<fonts count='1'><font><sz val='11'/></font></fonts>"
        "</styleSheet>"
    )
    after_entries = dict(before_entries)
    after_entries["xl/styles.xml"] = (
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<fonts count='1'><font><b/><sz val='11'/></font></fonts>"
        "</styleSheet>"
    )
    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after, compact_semantic_drift=True)

    assert report["issue_count"] == 1
    issue = report["issues"][0]
    assert issue["kind"] == "style_theme_semantic_drift"
    assert "compact summary" in issue["message"]
    assert "before_summary" in issue
    assert "before={'xl/styles.xml'" not in issue["message"]


def test_relationship_source_rejects_backslash_package_paths() -> None:
    with pytest.raises(ValueError, match="unsafe OOXML package part path"):
        audit_module._source_part_for_rels(r"xl\_rels\workbook.xml.rels")


def test_dangling_relationship_audit_treats_part_names_case_insensitively(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    entries = _base_entries()
    entries["[Content_Types].xml"] = entries["[Content_Types].xml"].replace(
        "</Types>",
        '  <Override PartName="/xl/sharedStrings.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>\n'
        "</Types>",
    )
    entries["xl/_rels/workbook.xml.rels"] = entries["xl/_rels/workbook.xml.rels"].replace(
        "</Relationships>",
        '  <Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
        'Target="sharedStrings.xml"/>\n'
        "</Relationships>",
    )
    entries["xl/SharedStrings.xml"] = (
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<si><t>Hello</t></si></sst>"
    )
    _write_package(before, entries)
    _write_package(after, entries)

    report = audit_module.audit(before, after)

    assert report["issues"] == []


def test_detects_dangling_chart_relationship_after_modify_save(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["[Content_Types].xml"] = before_entries["[Content_Types].xml"].replace(
        "</Types>",
        '  <Override PartName="/xl/charts/chart1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>\n'
        "</Types>",
    )
    before_entries["xl/worksheets/_rels/sheet1.xml.rels"] = (
        """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
    Target="../charts/chart1.xml"/>
</Relationships>"""
    )
    before_entries["xl/charts/chart1.xml"] = (
        '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"/>'
    )
    after_entries = dict(before_entries)
    del after_entries["xl/charts/chart1.xml"]

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)
    kinds = {issue["kind"] for issue in report["issues"]}

    assert "missing_part" in kinds
    assert "dangling_relationship" in kinds
    assert "feature_part_loss" in kinds


def test_internal_fragment_hyperlinks_are_not_dangling_parts(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    entries = _base_entries()
    entries["xl/drawings/_rels/drawing1.xml.rels"] = (
        """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
    Target="#'Sheet1'!A1"/>
</Relationships>"""
    )
    _write_package(before, entries)
    _write_package(after, entries)

    report = audit_module.audit(before, after)

    assert report["issues"] == []


def test_detects_malformed_xml_part_after_save(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    entries = _base_entries()
    after_entries = dict(entries)
    after_entries["xl/worksheets/sheet1.xml"] = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<hyperlinks><hyperlink ref="A1" location="Sec. 1 & 2 Notes!A1"/></hyperlinks>'
        "</worksheet>"
    )
    _write_package(before, entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "malformed_xml_part" for issue in report["issues"])


def test_ignores_preexisting_malformed_xml_part(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    entries = _base_entries()
    entries["xl/worksheets/sheet1.xml"] = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<hyperlinks><hyperlink ref="A1" location="Sec. 1 & 2 Notes!A1"/></hyperlinks>'
        "</worksheet>"
    )
    _write_package(before, entries)
    _write_package(after, entries)

    report = audit_module.audit(before, after)

    assert not any(issue["kind"] == "malformed_xml_part" for issue in report["issues"])


def test_detects_conditional_formatting_dxf_reference_out_of_range(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    entries = _base_entries()
    entries["[Content_Types].xml"] = entries["[Content_Types].xml"].replace(
        "</Types>",
        '  <Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>\n'
        "</Types>",
    )
    entries["xl/styles.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dxfs count="0"/>
</styleSheet>"""
    entries["xl/worksheets/sheet1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <conditionalFormatting sqref="A1:A5">
    <cfRule type="cellIs" dxfId="1" priority="1" operator="greaterThan">
      <formula>5</formula>
    </cfRule>
  </conditionalFormatting>
</worksheet>"""
    _write_package(before, entries)
    _write_package(after, entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "conditional_formatting_dxf_out_of_range"
        for issue in report["issues"]
    )


def test_detects_table_ref_column_count_mismatch(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/tables/table1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<x:table xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main" id="1" ref="A1:C4">
  <x:autoFilter ref="A1:C4"/>
  <x:tableColumns count="3">
    <x:tableColumn id="1" name="Region"/>
    <x:tableColumn id="2" name="Product"/>
    <x:tableColumn id="3" name="Sales"/>
  </x:tableColumns>
</x:table>"""
    after_entries = dict(before_entries)
    after_entries["xl/tables/table1.xml"] = before_entries["xl/tables/table1.xml"].replace(
        'ref="A1:C4"', 'ref="A1:B4"'
    )

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    issue = next(
        issue
        for issue in report["issues"]
        if issue["kind"] == "table_column_count_mismatch"
    )
    assert issue["part"] == "xl/tables/table1.xml"
    assert "ref width=2" in issue["message"]
    assert "tableColumn children=3" in issue["message"]


def test_detects_chart_formula_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/charts/chart1.xml"] = _chart_xml("Sheet1!$A$1:$A$5")
    after_entries = dict(before_entries)
    after_entries["xl/charts/chart1.xml"] = _chart_xml("Sheet1!$B$1:$B$5")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "charts_semantic_drift" for issue in report["issues"])


def test_detects_chart_formula_reference_to_missing_sheet(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/charts/chart1.xml"] = _chart_xml("Sheet1!$A$1:$A$5")
    after_entries = dict(before_entries)
    after_entries["xl/workbook.xml"] = after_entries["xl/workbook.xml"].replace(
        'name="Sheet1"', 'name="WolfXL Fidelity Rename"'
    )

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    issue = next(
        issue
        for issue in report["issues"]
        if issue["kind"] == "chart_formula_missing_sheet"
    )
    assert issue["part"] == "xl/charts/chart1.xml"
    assert "Sheet1" in issue["message"]


def test_chart_formula_sheet_reference_audit_accepts_quoted_and_external_refs(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "chart-formulas.xlsx"
    entries = _base_entries()
    entries["xl/workbook.xml"] = entries["xl/workbook.xml"].replace(
        'name="Sheet1"', 'name="WolfXL Fidelity Rename"'
    )
    entries["xl/charts/chart1.xml"] = _chart_xml(
        "'WolfXL Fidelity Rename'!$A$1:$A$5"
    )
    entries["xl/charts/chart2.xml"] = _chart_xml("'[Book.xlsx]Sheet1'!$A$1:$A$5")

    _write_package(workbook, entries)

    snapshot = audit_module.snapshot(workbook)

    assert snapshot.chart_sheet_ref_issues == []


def test_detects_chart_pivot_source_reference_to_missing_sheet(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/charts/chart1.xml"] = _chart_pivot_source_xml(
        "[Book.xlsx]Sheet1!PivotTable1"
    )
    after_entries = dict(before_entries)
    after_entries["xl/workbook.xml"] = after_entries["xl/workbook.xml"].replace(
        'name="Sheet1"', 'name="WolfXL Fidelity Rename"'
    )

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    issue = next(
        issue
        for issue in report["issues"]
        if issue["kind"] == "chart_pivot_source_missing_sheet"
    )
    assert issue["part"] == "xl/charts/chart1.xml"
    assert "Sheet1" in issue["message"]


def test_detects_workbook_defined_name_reference_to_missing_sheet(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/workbook.xml"] = before_entries["xl/workbook.xml"].replace(
        "<sheets>",
        '<definedNames><definedName name="ReportRange">'
        "'Sheet1'!$A$1:$D$4"
        "</definedName></definedNames><sheets>",
    )
    after_entries = dict(before_entries)
    after_entries["xl/workbook.xml"] = after_entries["xl/workbook.xml"].replace(
        'name="Sheet1"', 'name="WolfXL Fidelity Rename"'
    )

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    issue = next(
        issue
        for issue in report["issues"]
        if issue["kind"] == "workbook_defined_name_missing_sheet"
    )
    assert issue["part"] == "xl/workbook.xml"
    assert "ReportRange" in issue["message"]
    assert "Sheet1" in issue["message"]


def test_ignores_preexisting_workbook_defined_name_reference_to_missing_sheet(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    entries = _base_entries()
    entries["xl/workbook.xml"] = entries["xl/workbook.xml"].replace(
        "<sheets>",
        '<definedNames><definedName name="ReportRange">'
        "'Deleted Sheet'!$A$1:$D$4"
        "</definedName></definedNames><sheets>",
    )

    _write_package(before, entries)
    _write_package(after, entries)

    report = audit_module.audit(before, after)

    assert not any(
        issue["kind"] == "workbook_defined_name_missing_sheet"
        for issue in report["issues"]
    )


def test_workbook_defined_name_reference_audit_accepts_current_external_and_ref(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "defined-names.xlsx"
    entries = _base_entries()
    entries["xl/workbook.xml"] = entries["xl/workbook.xml"].replace(
        'name="Sheet1"',
        'name="WolfXL Fidelity Rename"',
    ).replace(
        "<sheets>",
        '<definedNames><definedName name="CurrentRange">'
        "'WolfXL Fidelity Rename'!$A$1:$D$4"
        '</definedName><definedName name="ExternalRange">'
        "'[Book.xlsx]Sheet1'!$A$1"
        '</definedName><definedName name="BrokenAllowed">'
        "#REF!"
        "</definedName></definedNames><sheets>",
    )

    _write_package(workbook, entries)

    snapshot = audit_module.snapshot(workbook)

    assert snapshot.workbook_sheet_ref_issues == []


def test_detects_worksheet_formula_references_to_missing_sheet(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/worksheets/sheet1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
  xmlns:xm="http://schemas.microsoft.com/office/excel/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1"><f>Sheet1!A1</f></c>
      <c r="B1"><f>"Sheet1!"</f></c>
    </row>
  </sheetData>
  <conditionalFormatting sqref="A1:A5">
    <cfRule type="expression" priority="1">
      <formula>Sheet1!$A$1&gt;0</formula>
    </cfRule>
  </conditionalFormatting>
  <dataValidations count="1">
    <dataValidation type="list" sqref="C1">
      <formula1>Sheet1!$A$1:$A$3</formula1>
      <formula2>"Sheet1!"</formula2>
    </dataValidation>
  </dataValidations>
  <extLst>
    <ext uri="{CCE6A557-97BC-4b89-ADB6-D9C93CAAB3DF}">
      <x14:dataValidations count="1">
        <x14:dataValidation type="list">
          <x14:formula1><xm:f>Sheet1!$A$1:$A$3</xm:f></x14:formula1>
        </x14:dataValidation>
      </x14:dataValidations>
    </ext>
  </extLst>
</worksheet>"""
    after_entries = dict(before_entries)
    after_entries["xl/workbook.xml"] = after_entries["xl/workbook.xml"].replace(
        'name="Sheet1"', 'name="WolfXL Fidelity Rename"'
    )

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    issues = [
        issue
        for issue in report["issues"]
        if issue["kind"] == "worksheet_formula_missing_sheet"
    ]
    assert len(issues) == 4
    assert {issue["part"] for issue in issues} == {"xl/worksheets/sheet1.xml"}
    assert all("Sheet1" in issue["message"] for issue in issues)
    assert all('"Sheet1!"' not in issue["message"] for issue in issues)


def test_worksheet_formula_reference_audit_accepts_current_external_and_literals(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "worksheet-formulas.xlsx"
    entries = _base_entries()
    entries["xl/workbook.xml"] = entries["xl/workbook.xml"].replace(
        'name="Sheet1"', 'name="WolfXL Fidelity Rename"'
    )
    entries["xl/worksheets/sheet1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1"><f>'WolfXL Fidelity Rename'!A1</f></c>
      <c r="B1"><f>'[Book.xlsx]Sheet1'!A1</f></c>
      <c r="C1"><f>"Sheet1!"</f></c>
    </row>
  </sheetData>
  <conditionalFormatting sqref="A1:A5">
    <cfRule type="expression" priority="1">
      <formula>'WolfXL Fidelity Rename'!$A$1&gt;0</formula>
    </cfRule>
  </conditionalFormatting>
  <dataValidations count="1">
    <dataValidation type="list" sqref="D1">
      <formula1>'WolfXL Fidelity Rename'!$A$1:$A$3</formula1>
    </dataValidation>
  </dataValidations>
</worksheet>"""

    _write_package(workbook, entries)

    snapshot = audit_module.snapshot(workbook)

    assert snapshot.worksheet_sheet_ref_issues == []


def test_detects_pivot_cache_source_reference_to_missing_sheet(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries() | _pivot_slicer_entries("A1:B4", "1")
    after_entries = dict(before_entries)
    after_entries["xl/workbook.xml"] = after_entries["xl/workbook.xml"].replace(
        'name="Sheet1"', 'name="WolfXL Fidelity Rename"'
    )
    after_entries["xl/pivotCache/pivotCacheDefinition1.xml"] = after_entries[
        "xl/pivotCache/pivotCacheDefinition1.xml"
    ].replace('sheet="Data"', 'sheet="Sheet1"')

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    issue = next(
        issue
        for issue in report["issues"]
        if issue["kind"] == "pivot_cache_source_missing_sheet"
    )
    assert issue["part"] == "xl/pivotCache/pivotCacheDefinition1.xml"
    assert "Sheet1" in issue["message"]


def test_fingerprints_structured_references_without_external_links(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "structured-ref.xlsx"
    entries = _base_entries()
    entries["xl/worksheets/sheet1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1"><f>SUM(Table1[Amount])</f></c></row>
    <row r="2"><c r="A2"><f>'[Book.xlsx]Sheet1'!A1</f></c></row>
  </sheetData>
</worksheet>"""
    _write_package(workbook, entries)

    snapshot = audit_module.snapshot(workbook)

    structured = snapshot.semantic_fingerprints["structured_references"]
    assert "xl/worksheets/sheet1.xml" in structured
    assert len(structured["xl/worksheets/sheet1.xml"]) == 1
    assert structured["xl/worksheets/sheet1.xml"][0][2] == "SUM(Table1[Amount])"


def test_fingerprints_workbook_global_state(tmp_path: Path) -> None:
    workbook = tmp_path / "workbook-globals.xlsx"
    entries = _base_entries()
    entries["xl/workbook.xml"] = entries["xl/workbook.xml"].replace(
        "<sheets>",
        '<definedNames><definedName name="ReportRange">Sheet1!$A$1</definedName></definedNames>'
        '<workbookProtection lockStructure="1"/>'
        '<calcPr calcMode="manual"/>'
        "<sheets>",
    )
    entries["xl/calcChain.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<calcChain xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>"""
    entries["xl/printerSettings/printerSettings1.bin"] = b"printer-settings"
    _write_package(workbook, entries)

    snapshot = audit_module.snapshot(workbook)

    workbook_globals = snapshot.semantic_fingerprints["workbook_globals"]
    assert "xl/workbook.xml" in workbook_globals
    assert "xl/printerSettings/printerSettings1.bin" in workbook_globals["package_parts"]
    assert "xl/printerSettings/printerSettings1.bin" in workbook_globals["package_payloads"]
    assert "calc_chain" in snapshot.feature_parts


def test_detects_workbook_global_package_payload_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsm"
    after = tmp_path / "after.xlsm"
    before_entries = _base_entries()
    before_entries.update(_workbook_global_package_entries(b"vba-a", "custom-a"))
    after_entries = _base_entries()
    after_entries.update(_workbook_global_package_entries(b"vba-b", "custom-b"))

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "workbook_globals_semantic_drift"
        for issue in report["issues"]
    )


def test_detects_python_and_sheet_metadata_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_python_metadata_entries("import pandas as pd", "1"))
    after_entries = _base_entries()
    after_entries.update(_python_metadata_entries("import polars as pl", "0"))

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)
    kinds = {issue["kind"] for issue in report["issues"]}

    assert "python_semantic_drift" in kinds
    assert "sheet_metadata_semantic_drift" in kinds


def test_detects_workbook_connection_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_connection_entries("Provider=A;Location=Sales", "Sales"))
    after_entries = _base_entries()
    after_entries.update(_connection_entries("Provider=B;Location=Sales", "Sales"))

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "connections_semantic_drift" for issue in report["issues"])


def test_detects_data_model_binary_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_data_model_entries(b"powerpivot-model-a"))
    after_entries = _base_entries()
    after_entries.update(_data_model_entries(b"powerpivot-model-b"))

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "data_model_semantic_drift" for issue in report["issues"])


def test_detects_generic_extension_payload_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/drawings/drawing1.xml"] = _drawing_extension_xml("shape-a")
    after_entries = dict(before_entries)
    after_entries["xl/drawings/drawing1.xml"] = _drawing_extension_xml("shape-b")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "extensions_semantic_drift" for issue in report["issues"])


def test_generic_extension_payload_allows_added_copied_parts(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/drawings/drawing1.xml"] = _drawing_extension_xml("shape-a")
    after_entries = dict(before_entries)
    after_entries["xl/drawings/drawing2.xml"] = _drawing_extension_xml("shape-a")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert not any(
        issue["kind"] == "extensions_semantic_drift" for issue in report["issues"]
    )


def test_detects_drawing_comment_object_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_drawing_object_entries(anchor_row="0", media=b"image-a"))
    after_entries = dict(before_entries)
    after_entries["xl/drawings/drawing1.xml"] = _drawing_anchor_xml("1")
    after_entries["xl/media/image1.png"] = b"image-b"

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "drawing_objects_semantic_drift" for issue in report["issues"])


def test_drawing_comment_object_fingerprint_allows_added_copied_parts(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_drawing_object_entries(anchor_row="0", media=b"image-a"))
    after_entries = dict(before_entries)
    after_entries["xl/drawings/drawing2.xml"] = _drawing_anchor_xml("0")
    after_entries["xl/media/image2.png"] = b"image-a"

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert not any(
        issue["kind"] == "drawing_objects_semantic_drift" for issue in report["issues"]
    )


def test_fingerprints_data_model_content_default_and_workbook_relationship(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "data-model.xlsx"
    entries = _base_entries()
    entries.update(_data_model_entries(b"powerpivot-model"))
    _write_package(workbook, entries)

    snapshot = audit_module.snapshot(workbook)

    fingerprint = snapshot.semantic_fingerprints["data_model"]
    assert "data_model" in snapshot.feature_parts
    assert fingerprint["content_defaults"] == {
        "data": "application/vnd.openxmlformats-officedocument.model+data"
    }
    assert fingerprint["xl/workbook.xml"][0][1] == [
        (
            "rId3",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/powerPivotData",
            "model/item.data",
            None,
        )
    ]


def test_detects_chart_axis_layout_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/charts/chart1.xml"] = _chart_axis_layout_xml(
        cat_axis="10", val_axis="20", layout_x="0.10"
    )
    after_entries = dict(before_entries)
    after_entries["xl/charts/chart1.xml"] = _chart_axis_layout_xml(
        cat_axis="10", val_axis="30", layout_x="0.20"
    )

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "charts_semantic_drift" for issue in report["issues"])


def test_detects_chart_sheet_relationship_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_chartsheet_entries("rId1", "../drawings/drawing1.xml"))
    after_entries = dict(before_entries)
    after_entries.update(_chartsheet_entries("rId2", "../drawings/drawing2.xml"))

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "chart_sheets_semantic_drift" for issue in report["issues"])


def test_detects_chart_style_color_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/charts/style1.xml"] = _chart_style_xml("accent1")
    before_entries["xl/charts/colors1.xml"] = _chart_colors_xml("accent1")
    after_entries = dict(before_entries)
    after_entries["xl/charts/style1.xml"] = _chart_style_xml("accent2")
    after_entries["xl/charts/colors1.xml"] = _chart_colors_xml("accent2")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "chart_styles_semantic_drift" for issue in report["issues"])


def test_detects_workbook_style_theme_color_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_style_theme_entries("4F81BD"))
    after_entries = dict(before_entries)
    after_entries["xl/theme/theme1.xml"] = _theme_xml("C0504D")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "style_theme_semantic_drift" for issue in report["issues"])


def test_detects_chart_axis_and_layout_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/charts/chart1.xml"] = _chart_axis_xml(axis_id="1")
    after_entries = dict(before_entries)
    after_entries["xl/charts/chart1.xml"] = _chart_axis_xml(axis_id="2")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "charts_semantic_drift" for issue in report["issues"])


def test_detects_chart_sheet_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/chartsheets/sheet1.xml"] = _chart_sheet_xml("rId1")
    after_entries = dict(before_entries)
    after_entries["xl/chartsheets/sheet1.xml"] = _chart_sheet_xml("rId2")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "chart_sheets_semantic_drift" for issue in report["issues"])


def test_detects_conditional_formatting_sqref_semantic_drift(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/worksheets/sheet1.xml"] = _cf_xml("A1:A5")
    after_entries = dict(before_entries)
    after_entries["xl/worksheets/sheet1.xml"] = _cf_xml("A1:A4")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "conditional_formatting_semantic_drift"
        for issue in report["issues"]
    )


def test_detects_conditional_formatting_extension_semantic_drift(
    tmp_path: Path,
) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/worksheets/sheet1.xml"] = _cf_extension_xml("A1:A5")
    after_entries = dict(before_entries)
    after_entries["xl/worksheets/sheet1.xml"] = _cf_extension_xml("A1:A4")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "conditional_formatting_semantic_drift"
        for issue in report["issues"]
    )


def test_detects_data_validation_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/worksheets/sheet1.xml"] = _data_validation_xml("A1:A5")
    after_entries = dict(before_entries)
    after_entries["xl/worksheets/sheet1.xml"] = _data_validation_xml("A1:A4")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "data_validations_semantic_drift"
        for issue in report["issues"]
    )


def test_detects_external_link_target_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_external_link_entries("../inputs/source-a.xlsx"))
    after_entries = dict(before_entries)
    after_entries.update(_external_link_entries("../inputs/source-b.xlsx"))

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "external_links_semantic_drift"
        for issue in report["issues"]
    )


def test_detects_external_link_cached_data_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_external_link_cache_entries("100"))
    after_entries = dict(before_entries)
    after_entries.update(_external_link_cache_entries("200"))

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "external_links_semantic_drift"
        for issue in report["issues"]
    )


def test_detects_external_formula_reference_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_external_link_entries("../inputs/source-a.xlsx"))
    before_entries["xl/worksheets/sheet1.xml"] = _formula_xml("'[source-a.xlsx]Data'!A1")
    after_entries = dict(before_entries)
    after_entries["xl/worksheets/sheet1.xml"] = _formula_xml("'[source-b.xlsx]Data'!A1")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "external_links_semantic_drift"
        for issue in report["issues"]
    )


def test_structured_reference_formula_is_not_external_link(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    entries = _base_entries()
    entries["xl/worksheets/sheet1.xml"] = _formula_xml(
        "SUBTOTAL(103,Table1[REGION])"
    )

    _write_package(before, entries)
    _write_package(after, entries)

    before_snapshot = audit_module.snapshot(before)

    assert before_snapshot.semantic_fingerprints["external_links"] == {}


def test_detects_internal_worksheet_formula_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/worksheets/sheet1.xml"] = _formula_xml("A1+A2", cell="C1")
    after_entries = dict(before_entries)
    after_entries["xl/worksheets/sheet1.xml"] = _formula_xml("A1+A3", cell="C1")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "worksheet_formulas_semantic_drift"
        for issue in report["issues"]
    )


def test_detects_formula_cell_coordinate_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/worksheets/sheet1.xml"] = _formula_xml("Z1", cell="AA1")
    after_entries = dict(before_entries)
    after_entries["xl/worksheets/sheet1.xml"] = _formula_xml("Z1", cell="AA2")

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(
        issue["kind"] == "worksheet_formulas_semantic_drift"
        for issue in report["issues"]
    )


def test_detects_pivot_and_slicer_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_pivot_slicer_entries(cache_ref="A1:C5", slicer_cache_id="1"))
    after_entries = dict(before_entries)
    after_entries.update(_pivot_slicer_entries(cache_ref="A1:C4", slicer_cache_id="2"))

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)
    kinds = {issue["kind"] for issue in report["issues"]}

    assert "pivots_semantic_drift" in kinds
    assert "slicers_semantic_drift" in kinds


def test_detects_pivot_calculated_field_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries.update(_pivot_calculated_entries("revenue*0.1"))
    after_entries = dict(before_entries)
    after_entries.update(_pivot_calculated_entries("revenue*0.2"))

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)

    assert any(issue["kind"] == "pivots_semantic_drift" for issue in report["issues"])


def test_detects_slicer_and_timeline_extension_semantic_drift(tmp_path: Path) -> None:
    before = tmp_path / "before.xlsx"
    after = tmp_path / "after.xlsx"
    before_entries = _base_entries()
    before_entries["xl/workbook.xml"] = _workbook_extension_xml(
        slicer_cache_id="1", timeline_cache_id="1"
    )
    after_entries = dict(before_entries)
    after_entries["xl/workbook.xml"] = _workbook_extension_xml(
        slicer_cache_id="2", timeline_cache_id="2"
    )

    _write_package(before, before_entries)
    _write_package(after, after_entries)

    report = audit_module.audit(before, after)
    kinds = {issue["kind"] for issue in report["issues"]}

    assert "slicers_semantic_drift" in kinds
    assert "timelines_semantic_drift" in kinds


def _chart_xml(formula: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart">
  <c:chart><c:plotArea><c:barChart><c:ser>
    <c:val><c:numRef><c:f>{formula}</c:f></c:numRef></c:val>
  </c:ser></c:barChart></c:plotArea></c:chart>
</c:chartSpace>"""


def _chart_pivot_source_xml(name: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart">
  <c:pivotSource><c:name>{name}</c:name><c:fmtId val="0"/></c:pivotSource>
  <c:chart><c:plotArea/></c:chart>
</c:chartSpace>"""


def _chart_axis_layout_xml(cat_axis: str, val_axis: str, layout_x: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart">
  <c:chart><c:plotArea>
    <c:layout><c:manualLayout><c:x val="{layout_x}"/></c:manualLayout></c:layout>
    <c:barChart><c:ser><c:idx val="0"/><c:order val="0"/>
      <c:val><c:numRef><c:f>Sheet1!$A$1:$A$5</c:f></c:numRef></c:val>
    </c:ser><c:axId val="{cat_axis}"/><c:axId val="{val_axis}"/></c:barChart>
    <c:catAx><c:axId val="{cat_axis}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:axPos val="b"/><c:crossAx val="{val_axis}"/></c:catAx>
    <c:valAx><c:axId val="{val_axis}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:axPos val="l"/><c:crossAx val="{cat_axis}"/></c:valAx>
  </c:plotArea></c:chart>
</c:chartSpace>"""


def _chartsheet_entries(rid: str, target: str) -> dict[str, str]:
    return {
        "xl/chartsheets/sheet1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<chartsheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetViews><sheetView workbookViewId="0" tabSelected="1"/></sheetViews>
  <drawing r:id="{rid}"/>
</chartsheet>""",
        "xl/chartsheets/_rels/sheet1.xml.rels": f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="{rid}"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
    Target="{target}"/>
</Relationships>""",
        "xl/drawings/drawing1.xml": "<wsDr/>",
        "xl/drawings/drawing2.xml": "<wsDr/>",
    }


def _chart_style_xml(color: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cs:chartStyle xmlns:cs="http://schemas.microsoft.com/office/drawing/2012/chartStyle">
  <cs:styleEntry><cs:fillRef idx="1"><cs:schemeClr val="{color}"/></cs:fillRef></cs:styleEntry>
</cs:chartStyle>"""


def _chart_colors_xml(color: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cs:colorStyle xmlns:cs="http://schemas.microsoft.com/office/drawing/2012/chartStyle">
  <cs:schemeClr val="{color}"/>
</cs:colorStyle>"""


def _style_theme_entries(accent1: str) -> dict[str, str]:
    entries = {
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><color theme="1"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="solid"><fgColor rgb="FFFF0000"/></patternFill></fill></fills>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>""",
        "xl/theme/theme1.xml": _theme_xml(accent1),
    }
    entries["[Content_Types].xml"] = _base_entries()["[Content_Types].xml"].replace(
        "</Types>",
        '  <Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>\n'
        '  <Override PartName="/xl/theme/theme1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>\n'
        "</Types>",
    )
    entries["xl/_rels/workbook.xml.rels"] = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    Target="styles.xml"/>
  <Relationship Id="rId3"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
    Target="theme/theme1.xml"/>
</Relationships>"""
    return entries


def _theme_xml(accent1: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
  <a:themeElements>
    <a:clrScheme name="Office">
      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
      <a:accent1><a:srgbClr val="{accent1}"/></a:accent1>
    </a:clrScheme>
  </a:themeElements>
</a:theme>"""


def _chart_axis_xml(axis_id: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart">
  <c:chart><c:plotArea>
    <c:barChart><c:ser><c:idx val="0"/><c:order val="0"/><c:val><c:numRef><c:f>Sheet1!$A$1:$A$5</c:f></c:numRef></c:val></c:ser><c:axId val="{axis_id}"/></c:barChart>
    <c:catAx><c:axId val="{axis_id}"/><c:axPos val="b"/><c:scaling><c:orientation val="minMax"/></c:scaling></c:catAx>
    <c:layout><c:manualLayout><c:x val="0.1"/></c:manualLayout></c:layout>
  </c:plotArea></c:chart>
</c:chartSpace>"""


def _chart_sheet_xml(drawing_rid: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<chartsheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetViews><sheetView workbookViewId="0"/></sheetViews>
  <drawing r:id="{drawing_rid}"/>
</chartsheet>"""


def _cf_xml(sqref: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <conditionalFormatting sqref="{sqref}">
    <cfRule type="expression" priority="1"><formula>A1&gt;0</formula></cfRule>
  </conditionalFormatting>
</worksheet>"""


def _cf_extension_xml(sqref: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">
  <extLst><ext uri="{{78C0D931-6437-407d-A8EE-F0AAD7539E65}}">
    <x14:conditionalFormattings>
      <x14:conditionalFormatting sqref="{sqref}">
        <x14:cfRule type="dataBar" priority="1"><x14:dataBar minLength="0" maxLength="100"/></x14:cfRule>
      </x14:conditionalFormatting>
    </x14:conditionalFormattings>
  </ext></extLst>
</worksheet>"""


def _data_validation_xml(sqref: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dataValidations count="1">
    <dataValidation type="whole" operator="between" sqref="{sqref}">
      <formula1>1</formula1><formula2>100</formula2>
    </dataValidation>
  </dataValidations>
</worksheet>"""


def _external_link_entries(target: str) -> dict[str, str]:
    return {
        "xl/externalLinks/externalLink1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <externalBook r:id="rId1"><sheetNames><sheetName val="Sheet1"/></sheetNames></externalBook>
</externalLink>""",
        "xl/externalLinks/_rels/externalLink1.xml.rels": f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath"
    Target="{target}" TargetMode="External"/>
</Relationships>""",
    }


def _external_link_cache_entries(value: str) -> dict[str, str]:
    entries = _external_link_entries("../inputs/source.xlsx")
    entries["xl/externalLinks/externalLink1.xml"] = f"""<?xml version="1.0" encoding="UTF-8"?>
<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <externalBook r:id="rId1">
    <sheetNames><sheetName val="Sheet1"/></sheetNames>
    <sheetDataSet><sheetData sheetId="0"><row r="1"><cell r="A1" t="n"><v>{value}</v></cell></row></sheetData></sheetDataSet>
  </externalBook>
</externalLink>"""
    return entries


def _connection_entries(connection: str, command: str) -> dict[str, str]:
    return {
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/connections"
    Target="connections.xml"/>
</Relationships>""",
        "xl/connections.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<connections xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1">
  <connection id="1" name="Query - Sales" type="5" refreshedVersion="7" background="1" saveData="1">
    <dbPr connection="{connection}" command="{command}" commandType="1"/>
  </connection>
</connections>""",
    }


def _drawing_extension_xml(creation_id: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
          xmlns:a16="http://schemas.microsoft.com/office/drawing/2014/main">
  <xdr:twoCellAnchor>
    <xdr:sp>
      <xdr:nvSpPr>
        <xdr:cNvPr id="2" name="Shape 1">
          <a:extLst>
            <a:ext uri="{{FF2B5EF4-FFF2-40B4-BE49-F238E27FC236}}">
              <a16:creationId id="{creation_id}"/>
            </a:ext>
          </a:extLst>
        </xdr:cNvPr>
      </xdr:nvSpPr>
    </xdr:sp>
  </xdr:twoCellAnchor>
</xdr:wsDr>"""


def _drawing_object_entries(anchor_row: str, media: bytes) -> dict[str, str | bytes]:
    entries = {
        "xl/drawings/drawing1.xml": _drawing_anchor_xml(anchor_row),
        "xl/media/image1.png": media,
        "xl/comments1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<comments xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <authors><author>WolfXL</author></authors>
  <commentList><comment ref="A1" authorId="0"><text><t>Original note</t></text></comment></commentList>
</comments>""",
        "xl/drawings/commentsDrawing1.vml": """<?xml version="1.0" encoding="UTF-8"?>
<xml xmlns:v="urn:schemas-microsoft-com:vml">
  <v:shape id="_x0000_s1025" type="#_x0000_t202"/>
</xml>""",
        "xl/embeddings/oleObject1.bin": b"ole-object",
    }
    entries["[Content_Types].xml"] = _base_entries()["[Content_Types].xml"].replace(
        "</Types>",
        '  <Default Extension="png" ContentType="image/png"/>\n'
        '  <Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>\n'
        '  <Override PartName="/xl/drawings/drawing1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>\n'
        '  <Override PartName="/xl/comments1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"/>\n'
        "</Types>",
    )
    return entries


def _drawing_anchor_xml(anchor_row: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <xdr:twoCellAnchor>
    <xdr:from><xdr:col>0</xdr:col><xdr:row>{anchor_row}</xdr:row></xdr:from>
    <xdr:to><xdr:col>2</xdr:col><xdr:row>4</xdr:row></xdr:to>
    <xdr:pic><xdr:nvPicPr><xdr:cNvPr id="2" name="Picture 1"/></xdr:nvPicPr></xdr:pic>
  </xdr:twoCellAnchor>
</xdr:wsDr>"""


def _workbook_global_package_entries(vba_payload: bytes, custom_value: str) -> dict[str, str | bytes]:
    entries = {
        "xl/vbaProject.bin": vba_payload,
        "customXml/item1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<root><value>{custom_value}</value></root>""",
        "customXml/_rels/item1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>""",
        "xl/printerSettings/printerSettings1.bin": b"printer-settings",
    }
    entries["[Content_Types].xml"] = _base_entries()["[Content_Types].xml"].replace(
        "</Types>",
        '  <Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>\n'
        '  <Override PartName="/customXml/item1.xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/xl/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/>\n'
        "</Types>",
    )
    return entries


def _python_metadata_entries(code: str, dynamic: str) -> dict[str, str]:
    entries = {
        "xl/python.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<python xmlns="http://schemas.microsoft.com/office/spreadsheetml/2023/python">
  <environmentDefinition id="{{11111111-2222-3333-4444-555555555555}}">
    <initialization><code>{code}</code></initialization>
  </environmentDefinition>
</python>""",
        "xl/metadata.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:xda="http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray">
  <futureMetadata name="XLDAPR" count="1">
    <bk><extLst><ext uri="{{bdbb8cdc-fa1e-496e-a857-3c3f30c029c3}}">
      <xda:dynamicArrayProperties fDynamic="{dynamic}" fCollapsed="0"/>
    </ext></extLst></bk>
  </futureMetadata>
</metadata>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sheetMetadata" Target="metadata.xml"/>
  <Relationship Id="rId4" Type="http://schemas.microsoft.com/office/2023/09/relationships/Python" Target="python.xml"/>
</Relationships>""",
    }
    entries["[Content_Types].xml"] = _base_entries()["[Content_Types].xml"].replace(
        "</Types>",
        '  <Override PartName="/xl/python.xml" ContentType="application/vnd.ms-excel.python+xml"/>\n'
        '  <Override PartName="/xl/metadata.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheetMetadata+xml"/>\n'
        "</Types>",
    )
    return entries


def _data_model_entries(payload: bytes) -> dict[str, str | bytes]:
    entries = _connection_entries("Provider=MSOLAP;Data Source=$Embedded$", "Model")
    entries["[Content_Types].xml"] = _base_entries()["[Content_Types].xml"].replace(
        "</Types>",
        '  <Default Extension="data" '
        'ContentType="application/vnd.openxmlformats-officedocument.model+data"/>\n'
        "</Types>",
    )
    entries["xl/_rels/workbook.xml.rels"] = entries["xl/_rels/workbook.xml.rels"].replace(
        "</Relationships>",
        '  <Relationship Id="rId3"\n'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/powerPivotData"\n'
        '    Target="model/item.data"/>\n'
        "</Relationships>",
    )
    entries["xl/model/item.data"] = payload
    return entries


def _formula_xml(formula: str, *, cell: str = "A1") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData><row r="1"><c r="{cell}"><f>{formula}</f></c></row></sheetData>
</worksheet>"""


def _pivot_slicer_entries(cache_ref: str, slicer_cache_id: str) -> dict[str, str]:
    return {
        "xl/pivotCache/pivotCacheDefinition1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  refreshOnLoad="1">
  <cacheSource type="worksheet"><worksheetSource ref="{cache_ref}" sheet="Data"/></cacheSource>
  <cacheFields count="1"><cacheField name="region"/></cacheFields>
</pivotCacheDefinition>""",
        "xl/pivotTables/pivotTable1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  name="PivotTable1" cacheId="1">
  <rowFields count="1"><field x="0"/></rowFields>
  <dataFields count="1"><dataField name="Sum of revenue" fld="0" subtotal="sum"/></dataFields>
</pivotTableDefinition>""",
        "xl/slicerCaches/slicerCache1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<slicerCacheDefinition xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
  name="Slicer_region" pivotCacheId="{slicer_cache_id}">
  <data pivotCacheId="{slicer_cache_id}"/>
</slicerCacheDefinition>""",
        "xl/slicers/slicer1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<slicerList xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">
  <slicer name="Slicer_region1" cache="Slicer_region" caption="Region"/>
</slicerList>""",
    }


def _pivot_calculated_entries(formula: str) -> dict[str, str]:
    return {
        "xl/pivotCache/pivotCacheDefinition1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <cacheFields count="2"><cacheField name="revenue"/><cacheField name="tax" formula="{formula}"/></cacheFields>
  <calculatedFields count="1"><calculatedField name="tax" formula="{formula}"/></calculatedFields>
</pivotCacheDefinition>""",
        "xl/pivotTables/pivotTable1.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  name="PivotTable1" cacheId="1">
  <calculatedItems count="1"><calculatedItem field="1" formula="{formula}"/></calculatedItems>
</pivotTableDefinition>""",
    }


def _workbook_extension_xml(slicer_cache_id: str, timeline_cache_id: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
  xmlns:x15="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
  <extLst>
    <ext uri="{{A8765BA9-456A-4DAB-B4F3-ACF838C121DE}}"><x14:slicerCaches><x14:slicerCache r:id="rId{slicer_cache_id}"/></x14:slicerCaches></ext>
    <ext uri="{{7E03D99C-DC04-49d9-9315-930204A7B6E9}}"><x15:timelineCacheRefs><x15:timelineCacheRef r:id="rId{timeline_cache_id}"/></x15:timelineCacheRefs></ext>
  </extLst>
</workbook>"""
