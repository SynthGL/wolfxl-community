from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_boundary_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "summarize_ooxml_render_boundary.py"
    )
    spec = importlib.util.spec_from_file_location("summarize_ooxml_render_boundary", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


boundary = _load_boundary_module()


def test_render_boundary_summary_records_failed_fixture_once(tmp_path: Path) -> None:
    stage_report = tmp_path / "stage.json"
    render_report = tmp_path / "render.json"
    stage_report.write_text(
        json.dumps(
            {
                "ready": True,
                "seed": "seed-v1",
                "sample_size": 3,
                "selected_count": 3,
                "selected_source_count": 2,
                "selected_bucket_counts": {"excel_authored": 3},
            }
        )
    )
    render_report.write_text(
        json.dumps(
            {
                "render_engine": "excel",
                "excel_print_area": "$A$1:$K$80",
                "mutations": ["add_data_validation", "copy_remove_sheet"],
                "result_count": 6,
                "failure_count": 2,
                "results": [
                    {
                        "fixture": "a.xlsx",
                        "mutation": "add_data_validation",
                        "status": "sampled_rendered",
                    },
                    {
                        "fixture": "a.xlsx",
                        "mutation": "copy_remove_sheet",
                        "status": "sampled_rendered",
                    },
                    {
                        "fixture": "b.xlsx",
                        "mutation": "add_data_validation",
                        "status": "failed",
                        "message": "Microsoft Excel PDF export failed: parameter error -50",
                    },
                    {
                        "fixture": "b.xlsx",
                        "mutation": "copy_remove_sheet",
                        "status": "failed",
                        "message": "Microsoft Excel PDF export failed: parameter error -50",
                    },
                    {
                        "fixture": "c.xlsx",
                        "mutation": "add_data_validation",
                        "status": "sampled_rendered",
                    },
                    {
                        "fixture": "c.xlsx",
                        "mutation": "copy_remove_sheet",
                        "status": "sampled_rendered",
                    },
                ],
            }
        )
    )

    report = boundary.summarize_render_boundary(stage_report, render_report)

    assert report["ready"] is True
    assert report["selected_count"] == 3
    assert report["render_failure_count"] == 2
    assert report["renderable_subset_count"] == 2
    assert report["observed_fixture_count"] == 3
    assert report["consistency_issues"] == []
    assert report["status_counts"] == {"failed": 2, "sampled_rendered": 4}
    assert report["excluded_from_renderable_subset"] == [
        {
            "fixture": "b.xlsx",
            "mutations": ["add_data_validation", "copy_remove_sheet"],
            "failure_messages": [
                "Microsoft Excel PDF export failed: parameter error -50"
            ],
        }
    ]


def test_render_boundary_summary_flags_inconsistent_fixture_counts(
    tmp_path: Path,
) -> None:
    stage_report = tmp_path / "stage.json"
    render_report = tmp_path / "render.json"
    stage_report.write_text(
        json.dumps(
            {
                "ready": True,
                "seed": "seed-v1",
                "sample_size": 0,
                "selected_count": 0,
                "selected_source_count": 0,
                "selected_bucket_counts": {},
            }
        )
    )
    render_report.write_text(
        json.dumps(
            {
                "render_engine": "excel",
                "mutations": ["add_data_validation"],
                "result_count": 1,
                "failure_count": 1,
                "results": [
                    {
                        "fixture": "unexpected.xlsx",
                        "mutation": "add_data_validation",
                        "status": "failed",
                        "message": "ImageMagick compare failed",
                    }
                ],
            }
        )
    )

    report = boundary.summarize_render_boundary(stage_report, render_report)

    assert report["ready"] is False
    assert report["renderable_subset_count"] == 0
    assert report["observed_fixture_count"] == 1
    assert report["consistency_issues"] == [
        "selected_count is smaller than the number of unique fixtures "
        "observed in the render report",
        "selected_count is smaller than the number of unique failed fixtures",
    ]
    assert report["excluded_from_renderable_subset"] == [
        {
            "fixture": "unexpected.xlsx",
            "mutations": ["add_data_validation"],
            "failure_messages": ["ImageMagick compare failed"],
        }
    ]
