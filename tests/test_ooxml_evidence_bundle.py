from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType


def _load_bundle_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_ooxml_evidence_bundle.py"
    spec = importlib.util.spec_from_file_location("audit_ooxml_evidence_bundle", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bundle = _load_bundle_module()


def test_bundle_audit_accepts_expected_report_values(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(
            {
                "ready": True,
                "fixture_count": 22,
                "surfaces": {
                    "pivot_slicer_preservation": {
                        "clear": True,
                    }
                },
            }
        )
    )
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [
                            {"path": "ready", "equals": True},
                            {"path": "fixture_count", "at_least": 20},
                            {
                                "path": "surfaces.pivot_slicer_preservation.clear",
                                "equals": True,
                            },
                        ],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is True
    assert audit["issue_count"] == 0
    assert audit["producer_count"] == 1
    assert audit["reports"][0]["producer"] == "uv run --no-sync python scripts/example.py"


def test_bundle_audit_accepts_length_expectation(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"fixtures": ["a.xlsx", "b.xlsx"]}))
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [
                            {"path": "fixtures", "length_at_least": 2},
                        ],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is True
    assert audit["issue_count"] == 0


def test_bundle_audit_accepts_exact_length_expectation(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"fixtures": ["a.xlsx", "b.xlsx"]}))
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [
                            {"path": "fixtures", "length": 2},
                        ],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is True
    assert audit["issue_count"] == 0


def test_bundle_audit_accepts_contains_expectation(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(
        json.dumps(
            {
                "message": "external link target wolfxl-retargeted-external-link.xlsx",
                "fixtures": ["external-link.xlsx", "plain.xlsx"],
            }
        )
    )
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [
                            {
                                "path": "message",
                                "contains": "wolfxl-retargeted-external-link.xlsx",
                            },
                            {"path": "fixtures", "contains": "external-link.xlsx"},
                        ],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is True
    assert audit["issue_count"] == 0


def test_bundle_audit_accepts_render_compare_rendered_statuses(tmp_path: Path) -> None:
    report_path = tmp_path / "render.json"
    report_path.write_text(
        json.dumps(
            {
                "result_count": 4,
                "failure_count": 0,
                "density": 96,
                "max_normalized_rmse_threshold": 0.001,
                "results": [
                    {"fixture": "a.xlsx", "mutation": "no_op", "status": "passed"},
                    {
                        "fixture": "b.xlsx",
                        "mutation": "no_op",
                        "status": "sampled_passed",
                    },
                    {
                        "fixture": "c.xlsx",
                        "mutation": "marker_cell",
                        "status": "rendered",
                    },
                    {
                        "fixture": "d.xlsx",
                        "mutation": "marker_cell",
                        "status": "sampled_rendered",
                    },
                ],
            }
        )
    )
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "render",
                        "path": str(report_path),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures "
                            "--render-engine excel"
                        ),
                        "expect": [
                            {"path": "failure_count", "equals": 0},
                        ],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is True
    assert audit["issue_count"] == 0
    implicit_checks = [
        check for check in audit["reports"][0]["checks"] if check["path"] == "results.*.status"
    ]
    assert implicit_checks == [
        {
            "path": "results.*.status",
            "actual": ["passed", "sampled_passed", "rendered", "sampled_rendered"],
            "passed": True,
            "message": "ok",
        }
    ]


def test_bundle_audit_rejects_skipped_render_compare_results(tmp_path: Path) -> None:
    report_path = tmp_path / "render.json"
    report_path.write_text(
        json.dumps(
            {
                "result_count": 1,
                "failure_count": 0,
                "density": 96,
                "max_normalized_rmse_threshold": 0.001,
                "results": [
                    {
                        "fixture": "a.xlsx",
                        "mutation": "marker_cell",
                        "status": "skipped",
                        "message": "Microsoft Excel not found",
                    }
                ],
            }
        )
    )
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "render",
                        "path": str(report_path),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures "
                            "--render-engine excel"
                        ),
                        "expect": [
                            {"path": "failure_count", "equals": 0},
                        ],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is False
    assert audit["issue_count"] == 1
    assert audit["issues"][0]["check"] == "results.*.status"
    assert "non-rendered or skipped" in audit["issues"][0]["message"]
    assert "'status': 'skipped'" in audit["issues"][0]["message"]


def test_bundle_audit_does_not_apply_render_guard_to_derived_audits(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "render-equivalence.json"
    report_path.write_text(
        json.dumps(
            {
                "ready": True,
                "failure_count": 0,
                "results": [
                    {
                        "fixture": "a.xlsx",
                        "status": "inconclusive",
                        "message": "source first sheet is hidden",
                    }
                ],
            }
        )
    )
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "render_equivalence",
                        "path": str(report_path),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures && "
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_copy_sheet_render_equivalence.py"
                        ),
                        "expect": [
                            {"path": "failure_count", "equals": 0},
                        ],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is True
    assert audit["issue_count"] == 0
    assert all(check["path"] != "results.*.status" for check in audit["reports"][0]["checks"])


def test_bundle_audit_reports_unhashable_contains_expectation(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"fixtures": {"external-link.xlsx": {"ok": True}}}))
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [
                            {"path": "fixtures", "contains": ["external-link.xlsx"]},
                        ],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is False
    assert audit["issue_count"] == 1
    assert "to contain ['external-link.xlsx']" in audit["issues"][0]["message"]


def test_bundle_audit_reports_missing_and_stale_evidence(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"ready": False}))
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [
                            {"path": "ready", "equals": True},
                            {"path": "fixture_count", "equals": 22},
                        ],
                    },
                    {
                        "name": "missing",
                        "path": str(tmp_path / "missing.json"),
                        "producer": "uv run --no-sync python scripts/missing.py",
                        "expect": [
                            {"path": "ready", "equals": True},
                        ],
                    },
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is False
    assert audit["issue_count"] == 3
    messages = [issue["message"] for issue in audit["issues"]]
    assert "expected ready == True, got False" in messages
    assert any("missing path" in message for message in messages)
    assert "report file is missing" in messages


def test_bundle_audit_reports_missing_producer(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"ready": True}))
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "expect": [
                            {"path": "ready", "equals": True},
                        ],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is False
    assert audit["producer_count"] == 0
    assert audit["issues"] == [
        {
            "report": "coverage",
            "path": str(report_path),
            "check": "producer",
            "message": "producer command is missing",
        }
    ]


def test_bundle_audit_rejects_duplicate_report_names_and_paths(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"ready": True}))
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [{"path": "ready", "equals": True}],
                    },
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example_again.py",
                        "expect": [{"path": "ready", "equals": True}],
                    },
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is False
    duplicate_issues = [
        issue for issue in audit["issues"] if issue["check"].startswith("duplicate_")
    ]
    assert duplicate_issues == [
        {
            "report": "coverage",
            "path": str(report_path),
            "check": "duplicate_name",
            "message": f"duplicate report name also used for {report_path}",
        },
        {
            "report": "coverage",
            "path": str(report_path),
            "check": "duplicate_path",
            "message": "duplicate report path also used by coverage",
        },
    ]


def test_bundle_audit_can_require_portable_paths(tmp_path: Path) -> None:
    report_path = (
        Path(tempfile.gettempdir())
        / f"wolfxl-volatile-evidence-{tmp_path.name}.json"
    )
    report_path.write_text(json.dumps({"ready": True}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "volatile",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [{"path": "ready", "equals": True}],
                    }
                ]
            }
        )
    )

    try:
        default_audit = bundle.audit_bundle(manifest)
        portable_audit = bundle.audit_bundle(manifest, require_portable_paths=True)
    finally:
        report_path.unlink(missing_ok=True)

    assert default_audit["ready"] is True
    assert default_audit["absolute_path_count"] == 1
    assert default_audit["volatile_path_count"] == 1
    assert default_audit["portable_paths_ready"] is False
    assert portable_audit["ready"] is False
    assert portable_audit["issue_count"] == 1
    assert portable_audit["issues"][0]["check"] == "portable_path"
    assert "absolute and under volatile temporary storage" in (
        portable_audit["issues"][0]["message"]
    )


def test_bundle_audit_summarizes_missing_reports_by_producer_lane(tmp_path: Path) -> None:
    existing_report = tmp_path / "existing.json"
    existing_report.write_text(json.dumps({"ready": True}) + "\n")
    missing_headless = tmp_path / "missing-headless.json"
    missing_render = tmp_path / "missing-render.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "existing",
                        "path": str(existing_report),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_fidelity_mutations.py fixtures"
                        ),
                        "expect": [{"path": "ready", "equals": True}],
                    },
                    {
                        "name": "missing headless",
                        "path": str(missing_headless),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_gap_radar.py fixtures --json"
                        ),
                    },
                    {
                        "name": "missing render",
                        "path": str(missing_render),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures "
                            "--render-engine excel"
                        ),
                    },
                    {
                        "name": "missing manual excel",
                        "path": str(tmp_path / "missing-manual-excel.json"),
                        "producer": (
                            "Native Microsoft Excel copy baseline: open workbook, "
                            "copy a sheet, save, and inspect workbook.xml."
                        ),
                    },
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["producer_lane_counts"] == {
        "excel_gui_manual": 1,
        "headless": 2,
        "render": 1,
    }
    assert audit["missing_report_lane_counts"] == {
        "excel_gui_manual": 1,
        "headless": 1,
        "render": 1,
    }
    assert audit["missing_report_action_counts"] == {
        "defer_excel_batch": 2,
        "rerun_headless": 1,
    }


def test_bundle_cli_can_require_portable_paths(tmp_path: Path, capsys) -> None:
    report_path = (
        Path(tempfile.gettempdir())
        / f"wolfxl-volatile-evidence-cli-{tmp_path.name}.json"
    )
    report_path.write_text(json.dumps({"ready": True}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "volatile",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [{"path": "ready", "equals": True}],
                    }
                ]
            }
        )
    )

    try:
        code = bundle.main([str(manifest), "--strict", "--require-portable-paths"])
    finally:
        report_path.unlink(missing_ok=True)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 1
    assert payload["ready"] is False
    assert payload["absolute_path_count"] == 1
    assert payload["volatile_path_count"] == 1


def test_bundle_cli_can_print_summary_only(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"ready": True}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [{"path": "ready", "equals": True}],
                    }
                ]
            }
        )
    )

    code = bundle.main([str(manifest), "--summary-only"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ready"] is True
    assert payload["report_count"] == 1
    assert "reports" not in payload
    assert "issues" not in payload


def test_bundle_strict_cli_fails_for_stale_evidence(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"ready": False}))
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [
                            {"path": "ready", "equals": True},
                        ],
                    }
                ]
            }
        )
    )

    code = bundle.main([str(manifest), "--strict"])

    captured = capsys.readouterr()
    assert code == 1
    payload = json.loads(captured.out)
    assert payload["ready"] is False


def test_bundle_audit_reports_invalid_json_without_crashing(tmp_path: Path) -> None:
    report_path = tmp_path / "empty.json"
    report_path.write_text("")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "empty",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [{"path": "ready", "equals": True}],
                    }
                ]
            }
        )
    )

    audit = bundle.audit_bundle(manifest)

    assert audit["ready"] is False
    assert audit["issue_count"] == 1
    assert audit["issues"][0]["check"] == "json"
    assert "not valid JSON" in audit["issues"][0]["message"]
