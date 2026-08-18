from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


def _load_corpus_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "audit_ooxml_corpus_buckets.py"
    )
    spec = importlib.util.spec_from_file_location("audit_ooxml_corpus_buckets", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


corpus = _load_corpus_module()


def test_corpus_bucket_audit_reports_missing_buckets(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    workbook = fixture_dir / "plain.xlsx"
    _write_plain_workbook(workbook, application="Microsoft Excel")
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": workbook.name,
                        "fixture_id": "plain",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = corpus.audit_corpus([fixture_dir])

    assert report["ready"] is False
    assert report["audit_mode"] == "full_snapshot"
    assert report["workbook_count"] == 1
    assert report["bucket_fixtures"]["excel_authored"] == [str(workbook)]
    assert "powerpivot_data_model" in report["missing_buckets"]


def test_corpus_bucket_audit_reports_unreadable_workbooks_without_crashing(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    valid_workbook = fixture_dir / "plain.xlsx"
    invalid_workbook = fixture_dir / "not-a-zip.xlsx"
    _write_plain_workbook(valid_workbook, application="Microsoft Excel")
    invalid_workbook.write_bytes(b"not a zip file")
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": valid_workbook.name,
                        "fixture_id": "plain",
                        "tool": "excel",
                    },
                    {
                        "filename": invalid_workbook.name,
                        "fixture_id": "invalid",
                        "tool": "excel",
                    },
                ]
            }
        )
    )

    report = corpus.audit_corpus([fixture_dir])

    assert report["ready"] is False
    assert report["workbook_count"] == 1
    assert report["skipped_workbook_count"] == 1
    assert report["skipped_workbooks"] == [
        {
            "path": str(invalid_workbook),
            "source_label": str(fixture_dir),
            "tool": "excel",
            "reason": "BadZipFile: File is not a zip file",
        }
    ]


def test_corpus_bucket_audit_skips_timed_out_workbook(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    workbook = fixture_dir / "slow.xlsx"
    _write_plain_workbook(workbook, application="Microsoft Excel")

    def timed_out_run(*args: object, **kwargs: object) -> object:
        raise corpus.subprocess.TimeoutExpired(cmd=["audit"], timeout=0.01)

    monkeypatch.setattr(corpus.subprocess, "run", timed_out_run)

    report = corpus.audit_corpus([fixture_dir], workbook_timeout_seconds=0.01)

    assert report["ready"] is False
    assert report["workbook_count"] == 0
    assert report["skipped_workbook_count"] == 1
    assert report["skipped_workbooks"][0]["path"] == str(workbook)
    assert report["skipped_workbooks"][0]["source_label"] == str(fixture_dir)
    assert report["skipped_workbooks"][0]["tool"] is None
    assert report["skipped_workbooks"][0]["reason"].startswith(
        "WorkbookAuditTimeoutError: timed out after 0.01s"
    )


def test_corpus_bucket_audit_package_only_mode_uses_package_features(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    workbook = fixture_dir / "package.xlsx"
    _write_feature_rich_workbook(workbook)

    report = corpus.audit_corpus([fixture_dir], package_only=True)

    assert report["audit_mode"] == "package_only"
    assert report["workbook_count"] == 1
    assert report["skipped_workbook_count"] == 0
    buckets = set(report["workbooks"][0]["buckets"])
    assert {
        "excel_authored",
        "macro_vba",
        "powerpivot_data_model",
        "slicer_or_timeline",
        "embedded_object_or_control",
        "external_link",
        "chart_or_chart_style",
        "conditional_formatting_extension",
        "table_structured_ref_or_validation",
        "drawing_comment_or_media",
        "workbook_global_state",
    }.issubset(buckets)


def test_package_only_global_parts_keep_only_global_workbook_payloads() -> None:
    parts = {
        "xl/workbook.xml",
        "xl/worksheets/sheet1.xml",
        "xl/styles.xml",
        "xl/calcChain.xml",
        "xl/vbaProject.bin",
        "customXml/item1.xml",
        "xl/printerSettings/printerSettings1.bin",
    }

    assert set(corpus._package_only_global_parts(parts)) == {
        "xl/calcChain.xml",
        "xl/vbaProject.bin",
        "customXml/item1.xml",
        "xl/printerSettings/printerSettings1.bin",
    }


def test_corpus_bucket_audit_classifies_feature_rich_manifest(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    workbook = fixture_dir / "rich.xlsm"
    _write_feature_rich_workbook(workbook)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": workbook.name,
                        "fixture_id": "rich",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = corpus.audit_corpus([fixture_dir])

    buckets = set(report["workbooks"][0]["buckets"])
    assert {
        "excel_authored",
        "macro_vba",
        "powerpivot_data_model",
        "python_in_excel",
        "sheet_metadata",
        "slicer_or_timeline",
        "embedded_object_or_control",
        "external_link",
        "chart_or_chart_style",
        "conditional_formatting_extension",
        "table_structured_ref_or_validation",
        "drawing_comment_or_media",
        "workbook_global_state",
    }.issubset(buckets)


def _write_plain_workbook(path: Path, *, application: str) -> None:
    entries = _base_entries(application=application)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_feature_rich_workbook(path: Path) -> None:
    entries = _base_entries(application="Microsoft Excel")
    entries.update(
        {
            "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <definedNames><definedName name="Data">Sheet1!$A$1:$B$2</definedName></definedNames>
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
            "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLink" Target="externalLinks/externalLink1.xml"/>
  <Relationship Id="rId4" Type="http://schemas.microsoft.com/office/2006/relationships/slicerCache" Target="slicerCaches/slicerCache1.xml"/>
  <Relationship Id="rId5" Type="http://schemas.microsoft.com/office/2011/relationships/timelineCache" Target="timelineCaches/timelineCache1.xml"/>
  <Relationship Id="rId6" Type="http://schemas.microsoft.com/office/2006/relationships/powerPivotData" Target="model/item.data"/>
</Relationships>""",
            "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
           xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">
  <sheetData><row r="1"><c r="A1"><f>SUM(Table1[Amount])</f></c></row></sheetData>
  <conditionalFormatting sqref="A1"><cfRule type="expression" priority="1"><formula>A1&gt;0</formula></cfRule></conditionalFormatting>
  <dataValidations count="1"><dataValidation type="whole" sqref="A1"><formula1>1</formula1></dataValidation></dataValidations>
  <tableParts count="1"><tablePart r:id="rId1"/></tableParts>
  <drawing r:id="rId2"/>
  <legacyDrawing r:id="rId3"/>
  <extLst><ext uri="{78C0D931-6437-407d-A8EE-F0AAD7539E65}"><x14:conditionalFormattings/></ext></extLst>
</worksheet>""",
            "xl/worksheets/_rels/sheet1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="../tables/table1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing" Target="../drawings/vmlDrawing1.vml"/>
</Relationships>""",
            "xl/tables/table1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" id="1" name="Table1" ref="A1:B2"/>""",
            "xl/drawings/drawing1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"/>""",
            "xl/drawings/vmlDrawing1.vml": "<xml><shape><ClientData><Anchor>0,0,0,0,1,0,1,0</Anchor></ClientData></shape></xml>",
            "xl/comments1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<comments xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><authors><author>A</author></authors></comments>""",
            "xl/charts/chart1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"/>""",
            "xl/charts/style1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<cs:chartStyle xmlns:cs="http://schemas.microsoft.com/office/drawing/2012/chartStyle"/>""",
            "xl/externalLinks/externalLink1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
            "xl/slicerCaches/slicerCache1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<slicerCacheDefinition xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" name="Slicer"/>""",
            "xl/timelines/timeline1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<timeline xmlns="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main" name="Timeline"/>""",
            "xl/timelineCaches/timelineCache1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<timelineCacheDefinition xmlns="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main" name="Timeline"/>""",
            "xl/ctrlProps/ctrlProp1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<formControlPr xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" objectType="List"/>""",
            "xl/model/item.data": b"model",
            "xl/python.xml": """<?xml version="1.0" encoding="UTF-8"?>
<python xmlns="http://schemas.microsoft.com/office/spreadsheetml/2023/python">
  <environmentDefinition id="{11111111-2222-3333-4444-555555555555}">
    <initialization><code>import pandas as pd</code></initialization>
  </environmentDefinition>
</python>""",
            "xl/metadata.xml": """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:xda="http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray">
  <futureMetadata name="XLDAPR" count="1">
    <bk><extLst><ext uri="{bdbb8cdc-fa1e-496e-a857-3c3f30c029c3}">
      <xda:dynamicArrayProperties fDynamic="1" fCollapsed="0"/>
    </ext></extLst></bk>
  </futureMetadata>
</metadata>""",
            "xl/vbaProject.bin": b"vba",
        }
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _base_entries(*, application: str) -> dict[str, str | bytes]:
    return {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "docProps/app.xml": f"""<?xml version="1.0" encoding="UTF-8"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>{application}</Application></Properties>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
    }
