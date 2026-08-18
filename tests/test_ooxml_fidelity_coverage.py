from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType


def _load_coverage_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_ooxml_fidelity_coverage.py"
    spec = importlib.util.spec_from_file_location("audit_ooxml_fidelity_coverage", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


coverage_module = _load_coverage_module()


def test_coverage_audit_reports_missing_real_excel_and_structural_evidence(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "chart.xlsx"
    _write_chart_fixture(fixture)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "chart",
                        "tool": "excelize",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir)

    chart = report["surfaces"]["chart_style_color_preservation"]
    assert chart["external_tool_fixtures"] == ["chart.xlsx"]
    assert chart["missing"] == ["real_excel_fixture", "structural_mutation_pass"]
    assert report["ready"] is False
    assert report["mutation_report_count"] == 0
    assert report["render_report_count"] == 0
    assert report["app_report_count"] == 0
    assert report["render_required"] is False
    assert report["intentional_render_required"] is False
    assert report["app_required"] is False
    assert report["intentional_app_required"] is False


def test_coverage_audit_can_discover_recursive_fixture_trees(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    nested_dir = fixture_dir / "nested"
    nested_dir.mkdir(parents=True)
    fixture = nested_dir / "chart.xlsx"
    _write_chart_fixture(fixture)
    report_path = tmp_path / "mutation-report.json"
    report_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": "nested/chart.xlsx",
                        "mutation": "add_remove_chart",
                        "status": "passed",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(
        fixture_dir,
        reports=[report_path],
        recursive=True,
    )

    assert report["recursive"] is True
    assert report["fixture_count"] == 1
    chart = report["surfaces"]["chart_style_color_preservation"]
    assert chart["fixtures"] == ["nested/chart.xlsx"]
    assert chart["structural_mutation_fixtures"] == ["nested/chart.xlsx"]


def test_coverage_audit_uses_application_for_recursive_source_class(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    nested_dir = fixture_dir / "nested"
    nested_dir.mkdir(parents=True)
    fixture = nested_dir / "chart.xlsx"
    _write_chart_fixture(fixture)
    _add_application_name(fixture, "Microsoft Excel")

    report = coverage_module.audit_coverage(fixture_dir, recursive=True)

    assert report["fixtures"][0]["application"] == "Microsoft Excel"
    assert report["fixtures"][0]["source_class"] == "real_excel"
    chart = report["surfaces"]["chart_style_color_preservation"]
    assert chart["real_excel_fixtures"] == ["nested/chart.xlsx"]
    python = report["surfaces"]["python_in_excel_metadata"]
    assert python["optional"] is True
    assert python["status"] == "not_applicable"
    assert python["fixtures"] == []


def test_coverage_audit_manifest_tool_overrides_application_source_class(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "openpyxl-chart.xlsx"
    _write_chart_fixture(fixture)
    _add_application_name(fixture, "Microsoft Excel")
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": fixture.name,
                        "fixture_id": "openpyxl_chart",
                        "tool": "openpyxl",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir)

    assert report["fixtures"][0]["application"] == "Microsoft Excel"
    assert report["fixtures"][0]["source_class"] == "external_tool"
    chart = report["surfaces"]["chart_style_color_preservation"]
    assert chart["external_tool_fixtures"] == ["openpyxl-chart.xlsx"]


def test_coverage_audit_tracks_present_python_and_sheet_metadata(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture = fixture_dir / "python-metadata.xlsx"
    _write_python_metadata_fixture(fixture)
    _add_application_name(fixture, "Microsoft Excel")
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": fixture.name,
                        "mutation": "marker_cell",
                        "status": "passed",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir, reports=[mutation_report])

    python = report["surfaces"]["python_in_excel_metadata"]
    assert python["optional"] is True
    assert python["real_excel_fixtures"] == ["python-metadata.xlsx"]
    assert python["structural_mutation_fixtures"] == ["python-metadata.xlsx"]
    assert python["missing"] == []
    assert python["status"] == "clear"
    metadata = report["surfaces"]["sheet_metadata_preservation"]
    assert metadata["optional"] is True
    assert metadata["real_excel_fixtures"] == ["python-metadata.xlsx"]
    assert metadata["structural_mutation_fixtures"] == ["python-metadata.xlsx"]
    assert metadata["missing"] == []
    assert metadata["status"] == "clear"


def test_strict_cli_requires_mutation_report(tmp_path: Path, capsys) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()

    code = coverage_module.main([str(fixture_dir), "--strict"])

    captured = capsys.readouterr()
    assert code == 2
    assert "--strict requires at least one --report" in captured.err
    assert captured.out == ""


def test_require_render_cli_requires_render_report(tmp_path: Path, capsys) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()

    code = coverage_module.main([str(fixture_dir), "--require-render"])

    captured = capsys.readouterr()
    assert code == 2
    assert "--require-render requires at least one --render-report" in captured.err
    assert captured.out == ""


def test_require_intentional_render_cli_requires_render_report(tmp_path: Path, capsys) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()

    code = coverage_module.main([str(fixture_dir), "--require-intentional-render"])

    captured = capsys.readouterr()
    assert code == 2
    assert "--require-intentional-render requires at least one" in captured.err
    assert captured.out == ""


def test_require_app_cli_requires_app_report(tmp_path: Path, capsys) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()

    code = coverage_module.main([str(fixture_dir), "--require-app"])

    captured = capsys.readouterr()
    assert code == 2
    assert "--require-app requires at least one --app-report" in captured.err
    assert captured.out == ""


def test_require_intentional_app_cli_requires_app_report(tmp_path: Path, capsys) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()

    code = coverage_module.main([str(fixture_dir), "--require-intentional-app"])

    captured = capsys.readouterr()
    assert code == 2
    assert "--require-intentional-app requires at least one" in captured.err
    assert captured.out == ""


def test_coverage_audit_accepts_real_excel_and_structural_evidence(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-chart.xlsx"
    excel = fixture_dir / "excel-chart.xlsx"
    _write_chart_fixture(external)
    _write_chart_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_chart",
                        "tool": "excelize",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_chart",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "add_remove_chart",
                        "status": "passed",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir, reports=[mutation_report])

    chart = report["surfaces"]["chart_style_color_preservation"]
    assert chart["external_tool_fixtures"] == ["external-chart.xlsx"]
    assert chart["real_excel_fixtures"] == ["excel-chart.xlsx"]
    assert chart["structural_mutation_fixtures"] == ["external-chart.xlsx"]
    assert chart["missing"] == []


def test_coverage_audit_can_require_render_evidence(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-chart.xlsx"
    excel = fixture_dir / "excel-chart.xlsx"
    _write_chart_fixture(external)
    _write_chart_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_chart",
                        "tool": "excelize",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_chart",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "add_remove_chart",
                        "status": "passed",
                    }
                ]
            }
        )
    )
    render_report = tmp_path / "render-report.json"
    render_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "no_op",
                        "status": "passed",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(
        fixture_dir,
        reports=[mutation_report],
        render_reports=[render_report],
        require_render=True,
    )

    chart = report["surfaces"]["chart_style_color_preservation"]
    assert report["render_report_count"] == 1
    assert report["render_required"] is True
    assert report["render_engine_required"] is None
    assert "render_no_op_pass" in report["required_evidence"]
    assert chart["render_fixtures"] == ["external-chart.xlsx"]
    assert chart["missing"] == []


def test_coverage_audit_can_require_intentional_render_evidence(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-chart.xlsx"
    excel = fixture_dir / "excel-chart.xlsx"
    _write_chart_fixture(external)
    _write_chart_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_chart",
                        "tool": "excelize",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_chart",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "add_remove_chart",
                        "status": "passed",
                    }
                ]
            }
        )
    )
    render_report = tmp_path / "render-report.json"
    render_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "copy_first_sheet",
                        "status": "rendered",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(
        fixture_dir,
        reports=[mutation_report],
        render_reports=[render_report],
        require_intentional_render=True,
    )

    chart = report["surfaces"]["chart_style_color_preservation"]
    assert report["intentional_render_required"] is True
    assert "intentional_render_pass" in report["required_evidence"]
    assert chart["intentional_render_fixtures"] == ["external-chart.xlsx"]
    assert chart["missing"] == []


def test_coverage_audit_can_require_app_open_evidence(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-chart.xlsx"
    excel = fixture_dir / "excel-chart.xlsx"
    _write_chart_fixture(external)
    _write_chart_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_chart",
                        "tool": "excelize",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_chart",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "add_remove_chart",
                        "status": "passed",
                    }
                ]
            }
        )
    )
    app_report = tmp_path / "app-report.json"
    app_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "source",
                        "app": "excel",
                        "status": "passed",
                    },
                    {
                        "fixture": external.name,
                        "mutation": "copy_first_sheet",
                        "app": "excel",
                        "status": "passed",
                    },
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(
        fixture_dir,
        reports=[mutation_report],
        app_reports=[app_report],
        require_app=True,
        require_intentional_app=True,
    )

    chart = report["surfaces"]["chart_style_color_preservation"]
    assert report["app_report_count"] == 1
    assert report["app_required"] is True
    assert report["intentional_app_required"] is True
    assert "app_open_pass" in report["required_evidence"]
    assert "intentional_app_open_pass" in report["required_evidence"]
    assert chart["app_open_fixtures"] == ["external-chart.xlsx"]
    assert chart["intentional_app_open_fixtures"] == ["external-chart.xlsx"]
    assert chart["missing"] == []


def test_coverage_audit_reports_missing_render_when_required(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-chart.xlsx"
    excel = fixture_dir / "excel-chart.xlsx"
    _write_chart_fixture(external)
    _write_chart_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_chart",
                        "tool": "excelize",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_chart",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "add_remove_chart",
                        "status": "passed",
                    }
                ]
            }
        )
    )
    render_report = tmp_path / "render-report.json"
    render_report.write_text(
        json.dumps({"results": [{"fixture": external.name, "status": "skipped"}]})
    )

    report = coverage_module.audit_coverage(
        fixture_dir,
        reports=[mutation_report],
        render_reports=[render_report],
        require_render=True,
    )

    chart = report["surfaces"]["chart_style_color_preservation"]
    assert chart["render_fixtures"] == []
    assert "render_no_op_pass" in chart["missing"]
    assert report["ready"] is False


def test_coverage_audit_can_require_specific_render_engine(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-chart.xlsx"
    excel = fixture_dir / "excel-chart.xlsx"
    _write_chart_fixture(external)
    _write_chart_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_chart",
                        "tool": "excelize",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_chart",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "add_remove_chart",
                        "status": "passed",
                    }
                ]
            }
        )
    )
    render_report = tmp_path / "render-report.json"
    render_report.write_text(
        json.dumps(
            {
                "render_engine": "libreoffice",
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "no_op",
                        "status": "passed",
                    }
                ],
            }
        )
    )

    report = coverage_module.audit_coverage(
        fixture_dir,
        reports=[mutation_report],
        render_reports=[render_report],
        require_render=True,
        require_render_engine="excel",
    )

    chart = report["surfaces"]["chart_style_color_preservation"]
    assert report["render_engine_required"] == "excel"
    assert "render_engine:excel" in report["required_evidence"]
    assert chart["render_fixtures"] == []
    assert "render_no_op_pass:excel" in chart["missing"]
    assert report["ready"] is False


def test_coverage_audit_reports_missing_intentional_render_when_required(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-chart.xlsx"
    excel = fixture_dir / "excel-chart.xlsx"
    _write_chart_fixture(external)
    _write_chart_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_chart",
                        "tool": "excelize",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_chart",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "add_remove_chart",
                        "status": "passed",
                    }
                ]
            }
        )
    )
    render_report = tmp_path / "render-report.json"
    render_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "copy_first_sheet",
                        "status": "failed",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(
        fixture_dir,
        reports=[mutation_report],
        render_reports=[render_report],
        require_intentional_render=True,
    )

    chart = report["surfaces"]["chart_style_color_preservation"]
    assert chart["intentional_render_fixtures"] == []
    assert "intentional_render_pass" in chart["missing"]
    assert report["ready"] is False


def test_coverage_audit_does_not_count_plain_worksheet_as_cf_surface(
    tmp_path: Path,
) -> None:
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
                        "tool": "synthetic-ooxml",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir)

    assert report["fixtures"][0]["surfaces"] == ["style_theme_color_preservation"]
    assert report["surfaces"]["conditional_formatting_extension_preservation"]["fixtures"] == []


def test_coverage_audit_does_not_count_pivot_as_slicer_evidence(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-pivot.xlsx"
    excel = fixture_dir / "excel-pivot.xlsx"
    _write_pivot_fixture(external)
    _write_pivot_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_pivot",
                        "tool": "closedxml",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_pivot",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "rename_first_sheet",
                        "status": "passed",
                    },
                    {
                        "fixture": excel.name,
                        "mutation": "rename_first_sheet",
                        "status": "passed",
                    },
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir, reports=[mutation_report])

    pivot_slicer = report["surfaces"]["pivot_slicer_preservation"]
    assert pivot_slicer["feature_groups"]["pivot"]["clear"] is True
    assert pivot_slicer["feature_groups"]["slicer_or_timeline"]["clear"] is False
    assert "slicer_or_timeline_fixture" in pivot_slicer["missing"]


def test_powerpivot_data_model_surface_accepts_real_excel_source(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    excel = fixture_dir / "excel-data-model.xlsx"
    _write_data_model_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_data_model",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": excel.name,
                        "mutation": "marker_cell",
                        "status": "passed",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir, reports=[mutation_report])

    data_model = report["surfaces"]["powerpivot_data_model_preservation"]
    assert data_model["required_source_classes"] == ["real_excel"]
    assert data_model["real_excel_fixtures"] == ["excel-data-model.xlsx"]
    assert data_model["external_tool_fixtures"] == []
    assert data_model["structural_mutation_fixtures"] == ["excel-data-model.xlsx"]
    assert data_model["missing"] == []


def test_external_link_surface_accepts_retarget_mutation_evidence(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-link.xlsx"
    excel = fixture_dir / "excel-link.xlsx"
    _write_external_link_fixture(external)
    _write_external_link_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_link",
                        "tool": "synthetic-ooxml",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_link",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "retarget_external_links",
                        "status": "passed_with_expected_drift",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir, reports=[mutation_report])

    external_links = report["surfaces"]["external_link_relationship_edges"]
    assert "retarget_external_links" in external_links["accepted_structural_mutations"]
    assert external_links["external_tool_fixtures"] == ["external-link.xlsx"]
    assert external_links["real_excel_fixtures"] == ["excel-link.xlsx"]
    assert external_links["structural_mutation_fixtures"] == ["external-link.xlsx"]
    assert external_links["missing"] == []


def test_extension_payload_surface_requires_source_and_mutation_evidence(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-extension.xlsx"
    excel = fixture_dir / "excel-extension.xlsx"
    _write_extension_fixture(external)
    _write_extension_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_extension",
                        "tool": "excelize",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_extension",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "marker_cell",
                        "status": "passed",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir, reports=[mutation_report])

    extensions = report["surfaces"]["ooxml_extension_payload_preservation"]
    assert extensions["external_tool_fixtures"] == ["external-extension.xlsx"]
    assert extensions["real_excel_fixtures"] == ["excel-extension.xlsx"]
    assert extensions["structural_mutation_fixtures"] == ["external-extension.xlsx"]
    assert extensions["missing"] == []


def test_style_theme_surface_requires_source_and_mutation_evidence(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    external = fixture_dir / "external-style-theme.xlsx"
    excel = fixture_dir / "excel-style-theme.xlsx"
    _write_style_theme_fixture(external)
    _write_style_theme_fixture(excel)
    (fixture_dir / "manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": external.name,
                        "fixture_id": "external_style_theme",
                        "tool": "excelize",
                    },
                    {
                        "filename": excel.name,
                        "fixture_id": "excel_style_theme",
                        "tool": "excel",
                    },
                ]
            }
        )
    )
    mutation_report = tmp_path / "mutation-report.json"
    mutation_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": external.name,
                        "mutation": "marker_cell",
                        "status": "passed",
                    }
                ]
            }
        )
    )

    report = coverage_module.audit_coverage(fixture_dir, reports=[mutation_report])

    style_theme = report["surfaces"]["style_theme_color_preservation"]
    assert style_theme["external_tool_fixtures"] == ["external-style-theme.xlsx"]
    assert style_theme["real_excel_fixtures"] == ["excel-style-theme.xlsx"]
    assert style_theme["structural_mutation_fixtures"] == ["external-style-theme.xlsx"]
    assert style_theme["missing"] == []


def _write_chart_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/charts/chart1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>
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
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
        "xl/charts/chart1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart">
  <c:chart><c:plotArea><c:barChart/></c:plotArea></c:chart>
</c:chartSpace>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


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


def _write_pivot_fixture(path: Path) -> None:
    _write_plain_fixture(path)
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/pivotTables/pivotTable1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                      name="PivotTable1" cacheId="1" dataOnRows="0">
  <location ref="A3:B6" firstHeaderRow="1" firstDataRow="2" firstDataCol="1"/>
  <rowFields count="1"><field x="0"/></rowFields>
  <dataFields count="1"><dataField name="Sum of Amount" fld="1" subtotal="sum"/></dataFields>
</pivotTableDefinition>""",
        )
        archive.writestr(
            "xl/pivotCache/pivotCacheDefinition1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                      refreshOnLoad="1">
  <cacheSource type="worksheet"><worksheetSource ref="A1:B4" sheet="Sheet1"/></cacheSource>
  <cacheFields count="2"><cacheField name="Account"/><cacheField name="Amount"/></cacheFields>
</pivotCacheDefinition>""",
        )


def _write_python_metadata_fixture(path: Path) -> None:
    _write_plain_fixture(path)
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/python.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<python xmlns="http://schemas.microsoft.com/office/spreadsheetml/2023/python">
  <environmentDefinition id="{11111111-2222-3333-4444-555555555555}">
    <initialization><code>import pandas as pd</code></initialization>
  </environmentDefinition>
</python>""",
        )
        archive.writestr(
            "xl/metadata.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:xda="http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray">
  <futureMetadata name="XLDAPR" count="1">
    <bk><extLst><ext uri="{bdbb8cdc-fa1e-496e-a857-3c3f30c029c3}">
      <xda:dynamicArrayProperties fDynamic="1" fCollapsed="0"/>
    </ext></extLst></bk>
  </futureMetadata>
</metadata>""",
        )


def _write_data_model_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="data" ContentType="application/vnd.openxmlformats-officedocument.model+data"/>
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
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/powerPivotData" Target="model/item.data"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>""",
        "xl/model/item.data": b"powerpivot-model",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_external_link_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/externalLinks/externalLink1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.externalLink+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
  <externalReferences><externalReference r:id="rId2"/></externalReferences>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLink" Target="externalLinks/externalLink1.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData><row r="1"><c r="A1"><f>'[source.xlsx]Sheet1'!A1</f></c></row></sheetData>
</worksheet>""",
        "xl/externalLinks/externalLink1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <externalBook r:id="rId1">
    <sheetNames><sheetName val="Sheet1"/></sheetNames>
    <sheetDataSet><sheetData sheetId="0"><row r="1"><cell r="A1" t="n"><v>1</v></cell></row></sheetData></sheetDataSet>
  </externalBook>
</externalLink>""",
        "xl/externalLinks/_rels/externalLink1.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath" Target="source.xlsx" TargetMode="External"/>
</Relationships>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_extension_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
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
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
           xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">
  <sheetData/>
  <extLst>
    <ext uri="{B025F937-C7B1-47D3-B67F-A62EFF666E3E}">
      <x14:id>extension-fixture</x14:id>
    </ext>
  </extLst>
</worksheet>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_style_theme_fixture(path: Path) -> None:
    entries = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
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
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
        "xl/styles.xml": """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><color theme="1"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="solid"><fgColor rgb="FFFF0000"/></patternFill></fill></fills>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>""",
        "xl/theme/theme1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
  <a:themeElements>
    <a:clrScheme name="Office">
      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
      <a:accent1><a:srgbClr val="4F81BD"/></a:accent1>
    </a:clrScheme>
  </a:themeElements>
</a:theme>""",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _add_application_name(path: Path, application: str) -> None:
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "docProps/app.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>{application}</Application>
</Properties>""",
        )
