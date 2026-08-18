from __future__ import annotations

import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


def _load_gap_radar_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_ooxml_gap_radar.py"
    spec = importlib.util.spec_from_file_location("audit_ooxml_gap_radar", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gap_radar = _load_gap_radar_module()


def test_gap_radar_reports_unclassified_future_surface(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "future.xlsx"
    _write_future_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "future",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is False
    assert report["unknown_part_families"] == {
        "xl/future/future.xml": ["future.xlsx"]
    }
    assert report["unknown_relationship_types"] == {
        "futureFeature": ["future.xlsx"]
    }
    assert list(report["unknown_content_types"]) == [
        "application/vnd.example.future+xml"
    ]
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_reports_unknown_extension_uri_in_known_part(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "future-ext.xlsx"
    _write_future_extension_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "future_ext",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is False
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uris"] == {
        "{11111111-2222-3333-4444-555555555555}": ["future-ext.xlsx"]
    }


def test_gap_radar_allows_mac_excel_view_extension_uris(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "mac-view-ext.xlsx"
    _write_macos_view_extension_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "mac_view_ext",
                        "tool": "excel-mac",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["ready"] is True
    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_classifies_svg_blip_extension_uri(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "svg-blip.xlsx"
    _write_svg_blip_extension_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "svg_blip",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_is_clear_for_plain_core_workbook(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "plain.xlsx"
    _write_plain_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "plain",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_classifies_excel_trash_payloads(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "trash.xlsx"
    _write_plain_fixture(fixture)
    with zipfile.ZipFile(fixture, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[trash]/0000.dat", b"\xff\xff\xff\xff" + (b"\0" * 32))
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "trash",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_classifies_embedded_package_relationships(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "embedded-package.xlsx"
    _write_embedded_package_relationship_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "embedded_package",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0


def test_gap_radar_allows_case_variant_shared_strings_and_macos_junk(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "packaging-noise.xlsx"
    _write_packaging_noise_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "packaging_noise",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["ready"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0


def test_gap_radar_allows_known_named_sheet_view_and_chartex_surfaces(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "modern-excel.xlsx"
    _write_modern_excel_surface_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "modern_excel",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_reports_unreadable_workbooks_without_crashing(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "not-a-zip.xlsx"
    fixture.write_bytes(b"not a zip file")
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "invalid",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["ready"] is False
    assert report["fixture_count"] == 0
    assert report["skipped_fixture_count"] == 1
    assert report["skipped_fixtures"] == [
        {
            "filename": "not-a-zip.xlsx",
            "fixture_id": "invalid",
            "tool": "excel",
            "reason": "BadZipFile: File is not a zip file",
        }
    ]


def test_validate_package_part_names_rejects_backslashes() -> None:
    with pytest.raises(ValueError, match="unsafe OOXML package part path"):
        gap_radar._validate_package_part_names({r"xl\_rels\workbook.xml.rels"})


@pytest.mark.skipif(
    os.name == "nt",
    reason="zipfile normalizes member names on Windows before the gap radar sees them",
)
def test_gap_radar_reports_backslash_package_paths_as_skipped_invalid_inputs(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "backslash-path.xlsx"
    with zipfile.ZipFile(fixture, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>""",
        )
        backslash_part = zipfile.ZipInfo("placeholder")
        backslash_part.filename = r"xl\_rels\workbook.xml.rels"
        archive.writestr(
            backslash_part,
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>""",
        )
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "backslash_path",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["fixture_count"] == 0
    assert report["skipped_fixture_count"] == 1
    assert report["skipped_fixtures"][0]["reason"] == (
        r"ValueError: unsafe OOXML package part path: xl\_rels\workbook.xml.rels"
    )


def test_gap_radar_strict_cli_fails_for_unreadable_workbook(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "not-a-zip.xlsx"
    fixture.write_bytes(b"not a zip file")
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "invalid",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    assert gap_radar.main([str(fixture_dir), "--strict"]) == 1


def test_gap_radar_can_discover_nested_workbooks_without_manifest(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    nested_dir = fixture_dir / "nested"
    nested_dir.mkdir(parents=True)
    fixture = nested_dir / "plain.xlsx"
    _write_plain_fixture(fixture)

    non_recursive = gap_radar.audit_gap_radar(fixture_dir)
    recursive = gap_radar.audit_gap_radar(fixture_dir, recursive=True)

    assert non_recursive["fixture_count"] == 0
    assert recursive["fixture_count"] == 1
    assert recursive["fixtures"][0]["filename"] == "nested/plain.xlsx"
    assert recursive["clear"] is True


def test_gap_radar_classifies_python_and_sheet_metadata_surface(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "python.xlsx"
    _write_python_metadata_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "python",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_classifies_real_world_metadata_and_extension_surfaces(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "metadata.xlsx"
    _write_metadata_extension_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "metadata",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_classifies_vendored_openpyxl_package_shapes(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "vendored-openpyxl-shapes.xlsm"
    _write_vendored_openpyxl_shape_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "vendored_openpyxl_shapes",
                        "tool": "openpyxl-corpus",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_can_allow_intentionally_invalid_skipped_fixtures(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    valid = fixture_dir / "valid.xlsx"
    invalid = fixture_dir / "null_file.xlsx"
    _write_macos_view_extension_fixture(valid)
    invalid.write_bytes(b"")
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": valid.name,
                        "fixture_id": "valid",
                        "tool": "excel",
                    },
                    {
                        "filename": invalid.name,
                        "fixture_id": "intentional_null_file",
                        "tool": "openpyxl-corpus",
                    },
                ]
            }
        )
    )

    default_report = gap_radar.audit_gap_radar(fixture_dir)
    allowed_report = gap_radar.audit_gap_radar(
        fixture_dir,
        allow_skipped_fixtures=True,
    )

    assert default_report["clear"] is True
    assert default_report["ready"] is False
    assert allowed_report["clear"] is True
    assert allowed_report["allow_skipped_fixtures"] is True
    assert allowed_report["ready"] is True
    assert allowed_report["skipped_fixture_count"] == 1


def test_gap_radar_classifies_powerpivot_custom_property_surfaces(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "powerpivot.xlsx"
    _write_powerpivot_custom_property_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "powerpivot",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_classifies_pivot_cache_cached_unique_names_extension(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "pivot-cache-ext.xlsx"
    _write_pivot_cache_cached_unique_names_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "pivot_cache_ext",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_classifies_query_table_parts(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "query-table.xlsx"
    _write_query_table_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "query_table",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0


def test_gap_radar_reports_powerview_as_app_unsupported_feature(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "powerview.xlsx"
    _write_powerview_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "powerview",
                        "tool": "excel",
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is False
    assert report["unknown_part_family_count"] == 0
    assert report["unknown_relationship_type_count"] == 0
    assert report["unknown_content_type_count"] == 0
    assert report["unknown_extension_uri_count"] == 0
    assert report["app_unsupported_features"] == {"power_view": ["powerview.xlsx"]}
    assert report["app_unsupported_feature_count"] == 1
    assert report["unexpected_app_unsupported_features"] == {
        "power_view": ["powerview.xlsx"]
    }
    assert report["unexpected_app_unsupported_feature_count"] == 1


def test_gap_radar_allows_manifest_declared_powerview_feature(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "powerview.xlsx"
    _write_powerview_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "powerview",
                        "tool": "excel",
                        "app_unsupported_features": ["power_view"],
                    }
                ]
            }
        )
    )

    report = gap_radar.audit_gap_radar(fixture_dir)

    assert report["clear"] is True
    assert report["app_unsupported_features"] == {"power_view": ["powerview.xlsx"]}
    assert report["app_unsupported_feature_count"] == 1
    assert report["expected_app_unsupported_features"] == {
        "power_view": ["powerview.xlsx"]
    }
    assert report["unexpected_app_unsupported_feature_count"] == 0
    assert report["missing_expected_app_unsupported_feature_count"] == 0


def _write_plain_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
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
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_embedded_package_relationship_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="xlsx" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
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
        "xl/worksheets/_rels/sheet1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/package" Target="../embeddings/Microsoft_Excel_Worksheet1.xlsx"/>
</Relationships>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/embeddings/Microsoft_Excel_Worksheet1.xlsx": b"placeholder",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_powerview_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/sharedStrings.xml": """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>PowerView report</t></si></sst>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_packaging_noise_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/SharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="SharedStrings.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/SharedStrings.xml": """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Text</t></si></sst>""",
        "xl/.DS_Store": b"junk",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_powerpivot_custom_property_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/xl/customProperty1.bin" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.customProperty"/>
  <Override PartName="/xl/pivotTables/pivotTable1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>
  <Override PartName="/xl/pivotCache/pivotCacheDefinition1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml"/>
  <Override PartName="/xl/slicerCaches/slicerCache1.xml" ContentType="application/vnd.ms-excel.slicerCache+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
  <extLst>
    <ext uri="{841E416B-1EF1-43b6-AB56-02D37102CBD5}"><pivotCaches/></ext>
    <ext uri="{983426D0-5260-488c-9760-48F4B6AC55F4}"><pivotTableReferences/></ext>
  </extLst>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData/>
</worksheet>""",
        "xl/worksheets/_rels/sheet1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/customProperty" Target="../customProperty1.bin"/>
</Relationships>""",
        "xl/theme/theme1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office"/>""",
        "xl/theme/_rels/theme1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.jpeg"/>
</Relationships>""",
        "xl/pivotTables/pivotTable1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <extLst>
    <ext uri="{44433962-1CF7-4059-B4EE-95C3D5FFCF73}"><pivotTableData/></ext>
    <ext uri="{C510F80B-63DE-4267-81D5-13C33094786E}"><pivotTableServerFormats/></ext>
  </extLst>
</pivotTableDefinition>""",
        "xl/pivotCache/pivotCacheDefinition1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <extLst><ext uri="{ABF5C744-AB39-4b91-8756-CFA1BBC848D5}"><pivotCacheIdVersion/></ext></extLst>
</pivotCacheDefinition>""",
        "xl/slicerCaches/slicerCache1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<slicerCacheDefinition xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">
  <extLst><ext uri="{03082B11-2C62-411c-B77F-237D8FCFBE4C}"><slicerCachePivotTables/></ext></extLst>
</slicerCacheDefinition>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/customProperty1.bin": b"<Connections/>",
        "xl/media/image1.jpeg": b"jpeg",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_pivot_cache_cached_unique_names_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/pivotCache/pivotCacheDefinition1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
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
        "xl/pivotCache/pivotCacheDefinition1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <cacheFields count="1">
    <cacheField name="[Date].[MonthName].[MonthName]" caption="MonthName">
      <sharedItems count="1"><s v="Jan"/></sharedItems>
      <extLst>
        <ext uri="{4F2E5C28-24EA-4eb8-9CBF-B6C8F9C3D259}"
             xmlns:x15="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main">
          <x15:cachedUniqueNames>
            <x15:cachedUniqueName index="0" name="[Date].[MonthName].&amp;[Jan]"/>
          </x15:cachedUniqueNames>
        </ext>
      </extLst>
    </cacheField>
  </cacheFields>
</pivotCacheDefinition>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_query_table_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/connections.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.connections+xml"/>
  <Override PartName="/xl/queryTables/queryTable1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.queryTable+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/connections" Target="connections.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetData/>
  <tableParts count="1"><tablePart r:id="rId1"/></tableParts>
</worksheet>""",
        "xl/worksheets/_rels/sheet1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/queryTable" Target="../queryTables/queryTable1.xml"/>
</Relationships>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/connections.xml": """<?xml version="1.0" encoding="UTF-8"?>
<connections xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1">
  <connection id="1" name="Query - Sales"/>
</connections>""",
        "xl/queryTables/queryTable1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<queryTable xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
            name="Query - Sales" connectionId="1"/>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_metadata_extension_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="wmf" ContentType="image/x-wmf"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/theme/theme.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/docMetadata/LabelInfo.xml" ContentType="application/vnd.ms-office.classificationlabels+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2020/02/relationships/classificationlabels" Target="docMetadata/LabelInfo.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail" Target="docProps/thumbnail.wmf"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme.xml"/>
  <Relationship Id="rId4" Type="http://schemas.microsoft.com/office/2018/relationships/jsaProject" Target="jsaProject.bin"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">
  <sheetData/>
  <extLst>
    <ext uri="{CCE6A557-97BC-4b89-ADB6-D9C93CAAB3DF}"><x14:dataValidations count="0"/></ext>
  </extLst>
</worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/theme/theme.xml": """<?xml version="1.0" encoding="UTF-8"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office"/>""",
        "xl/drawings/drawing1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
          xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main">
  <xdr:extLst>
    <xdr:ext uri="{AF507438-7753-43E0-B8FC-AC1667EBCBE1}"><a14:hiddenEffects/></xdr:ext>
    <xdr:ext uri="{53640926-AAD7-44D8-BBD7-CCE9431645EC}"><a14:shadowObscured/></xdr:ext>
  </xdr:extLst>
</xdr:wsDr>""",
        "xl/charts/chart1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
              xmlns:c16="http://schemas.microsoft.com/office/drawing/2014/chart">
  <c:extLst><c:ext uri="{E28EC0CA-F0BB-4C9C-879D-F8772B89E7AC}"><c16:pivotOptions16/></c:ext></c:extLst>
</c:chartSpace>""",
        "docMetadata/LabelInfo.xml": """<?xml version="1.0" encoding="UTF-8"?><LabelInfo/>""",
        "docProps/thumbnail.wmf": b"wmf",
        "xl/jsaProject.bin": b"jsa",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("docProps/", b"")
        archive.writestr("xl/theme/", b"")
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_modern_excel_surface_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>
  <Override PartName="/xl/charts/chartEx1.xml" ContentType="application/vnd.ms-office.chartex+xml"/>
  <Override PartName="/xl/namedSheetViews/namedSheetView1.xml" ContentType="application/vnd.ms-excel.namedsheetviews+xml"/>
  <Override PartName="/xl/pivotTables/pivotTable1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
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
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
           xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
           xmlns:xlsdti="http://schemas.microsoft.com/office/spreadsheetml/2023/showDataTypeIcons">
  <sheetViews>
    <sheetView workbookViewId="0">
      <extLst>
        <ext uri="{77bfe23e-c014-4d31-8a63-9c772dbf06b6}">
          <xlsdti:showDataTypeIcons visible="0"/>
        </ext>
      </extLst>
    </sheetView>
  </sheetViews>
  <sheetData/>
  <drawing r:id="rId1"/>
  <extLst>
    <ext uri="{05C60535-1F16-4fd2-B633-F4F36F0B64E0}">
      <x14:sparklineGroups/>
    </ext>
  </extLst>
</worksheet>""",
        "xl/worksheets/_rels/sheet1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2019/04/relationships/namedSheetView" Target="../namedSheetViews/namedSheetView1.xml"/>
</Relationships>""",
        "xl/drawings/drawing1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"/>""",
        "xl/drawings/_rels/drawing1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/office/2014/relationships/chartEx" Target="../charts/chartEx1.xml"/>
</Relationships>""",
        "xl/charts/chartEx1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<cx:chartSpace xmlns:cx="http://schemas.microsoft.com/office/drawing/2014/chartex"/>""",
        "xl/namedSheetViews/namedSheetView1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<namedSheetViews xmlns="http://schemas.microsoft.com/office/spreadsheetml/2019/namedsheetviews">
  <namedSheetView name="Trademark"/>
</namedSheetViews>""",
        "xl/pivotTables/pivotTable1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                      xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">
  <pivotFields count="1">
    <pivotField>
      <extLst>
        <ext uri="{2946ED86-A175-432a-8AC1-64E0C546D7DE}">
          <x14:pivotField fillDownLabels="1"/>
        </ext>
      </extLst>
    </pivotField>
  </pivotFields>
</pivotTableDefinition>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_future_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/future/future.xml" ContentType="application/vnd.example.future+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.example.invalid/relationships/futureFeature" Target="future/future.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/future/future.xml": """<?xml version="1.0" encoding="UTF-8"?>
<future xmlns="http://schemas.example.invalid/future"/>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_future_extension_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
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
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">
  <sheetData/>
  <extLst><ext uri="{11111111-2222-3333-4444-555555555555}"><x14:futureThing/></ext></extLst>
</worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_macos_view_extension_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
          xmlns:mx="http://schemas.microsoft.com/office/mac/excel/2008/main">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
  <extLst><ext uri="{7523E5D3-25F3-A5E0-1632-64F254C22452}"><mx:ArchID Flags="2"/></ext></extLst>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:mx="http://schemas.microsoft.com/office/mac/excel/2008/main">
  <sheetData/>
  <extLst><ext uri="{64002731-A6B0-56B0-2670-7721B7C09600}"><mx:PLV Mode="0" OnePage="0" WScale="0"/></ext></extLst>
</worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_svg_blip_extension_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="svg" ContentType="image/svg+xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
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
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData/>
</worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/drawings/drawing1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
          xmlns:asvg="http://schemas.microsoft.com/office/drawing/2016/SVG/main">
  <xdr:twoCellAnchor>
    <xdr:from><xdr:col>0</xdr:col><xdr:row>0</xdr:row></xdr:from>
    <xdr:to><xdr:col>1</xdr:col><xdr:row>1</xdr:row></xdr:to>
    <xdr:pic>
      <xdr:nvPicPr><xdr:cNvPr id="1" name="Picture 1"/><xdr:cNvPicPr/></xdr:nvPicPr>
      <xdr:blipFill>
        <a:blip r:embed="rId1">
          <a:extLst>
            <a:ext uri="{96DAC541-7B7A-43D3-8B79-37D633B846F1}">
              <asvg:svgBlip r:embed="rId2"/>
            </a:ext>
          </a:extLst>
        </a:blip>
      </xdr:blipFill>
      <xdr:spPr/>
    </xdr:pic>
    <xdr:clientData/>
  </xdr:twoCellAnchor>
</xdr:wsDr>""",
        "xl/drawings/_rels/drawing1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.svg"/>
</Relationships>""",
        "xl/media/image1.png": b"png",
        "xl/media/image1.svg": b"<svg/>",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_vendored_openpyxl_shape_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Default Extension="bin" ContentType="application/vnd.ms-office.activeX"/>
  <Override PartName="/xl/workbook2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/customUI/customUI.xml" ContentType="application/xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook2.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail" Target="docProps/thumbnail.jpeg"/>
</Relationships>""",
        "xl/workbook2.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews>
    <workbookView>
      <extLst>
        <ext uri="http://schemas.microsoft.com/office/mac/excel/2008/main"/>
      </extLst>
    </workbookView>
  </bookViews>
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook2.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.microsoft.com/office/2006/relationships/activeXControlBinary" Target="activeX/activeX1.bin"/>
  <Relationship Id="rId4" Type="http://schemas.microsoft.com/office/2006/relationships/extensibility" Target="../customUI/customUI.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData/>
</worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "customUI/customUI.xml": """<?xml version="1.0" encoding="UTF-8"?>
<customUI xmlns="http://schemas.microsoft.com/office/2006/01/customui"/>""",
        "docProps/thumbnail.jpeg": b"jpeg",
        "xl/activeX/activeX1.bin": b"activex",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_python_metadata_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/python.xml" ContentType="application/vnd.ms-excel.python+xml"/>
  <Override PartName="/xl/metadata.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheetMetadata+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sheetMetadata" Target="metadata.xml"/>
  <Relationship Id="rId4" Type="http://schemas.microsoft.com/office/2023/09/relationships/Python" Target="python.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/python.xml": """<?xml version="1.0" encoding="UTF-8"?>
<python xmlns="http://schemas.microsoft.com/office/spreadsheetml/2023/python"><environmentDefinition id="{11111111-2222-3333-4444-555555555555}"/></python>""",
        "xl/metadata.xml": """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:xda="http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray">
  <futureMetadata name="XLDAPR" count="1"><bk><extLst><ext uri="{bdbb8cdc-fa1e-496e-a857-3c3f30c029c3}"><xda:dynamicArrayProperties fDynamic="1"/></ext></extLst></bk></futureMetadata>
</metadata>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
