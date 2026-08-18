from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "repin_ooxml_evidence_from_plan.py"
    )
    spec = importlib.util.spec_from_file_location("repin_ooxml_evidence_from_plan", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


repin = _load_module()


def test_repin_manifest_from_plan_updates_existing_durable_reports(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "Plans" / "bundle.json"
    manifest.parent.mkdir()
    durable_report = tmp_path / "docs" / "evidence" / "render" / "report.json"
    durable_report.parent.mkdir(parents=True)
    durable_report.write_text(json.dumps({"ready": True}) + "\n")
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "render_report",
                        "path": "/tmp/wolfxl-render.json",
                        "producer": "old command > /tmp/wolfxl-render.json",
                        "expect": [{"path": "ready", "equals": True}],
                    },
                    {
                        "name": "unselected_report",
                        "path": "../docs/evidence/existing.json",
                        "producer": "unchanged command",
                    },
                ]
            }
        )
    )
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "name": "render_report",
                        "durable_report_path": "docs/evidence/render/report.json",
                        "durable_producer": (
                            "uv run --no-sync python producer "
                            "> docs/evidence/render/report.json"
                        ),
                    }
                ]
            }
        )
    )
    output = tmp_path / "Plans" / "bundle-repinned.json"

    summary = repin.repin_manifest_from_plan(manifest, plan, output_manifest=output)
    payload = json.loads(output.read_text())

    assert summary["ready"] is True
    assert summary["repinned_report_count"] == 1
    assert summary["missing_durable_report_count"] == 0
    assert payload["reports"][0]["path"] == "../docs/evidence/render/report.json"
    assert payload["reports"][0]["producer"].startswith("uv run --no-sync python")
    assert payload["reports"][0]["expect"] == [{"path": "ready", "equals": True}]
    assert payload["reports"][1]["producer"] == "unchanged command"


def test_repin_manifest_from_plan_fails_when_selected_durable_report_is_missing(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "Plans" / "bundle.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "render_report",
                        "path": "/tmp/wolfxl-render.json",
                        "producer": "old command > /tmp/wolfxl-render.json",
                    }
                ]
            }
        )
    )
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "name": "render_report",
                        "durable_report_path": "docs/evidence/render/report.json",
                        "durable_producer": "new command",
                    }
                ]
            }
        )
    )
    output = tmp_path / "Plans" / "bundle-repinned.json"

    summary = repin.repin_manifest_from_plan(manifest, plan, output_manifest=output)

    assert summary["ready"] is False
    assert summary["repinned_report_count"] == 0
    assert summary["missing_durable_report_count"] == 1
    assert summary["missing_durable_reports"] == [
        {
            "name": "render_report",
            "durable_report_path": "docs/evidence/render/report.json",
        }
    ]
    assert not output.exists()


def test_repin_manifest_from_plan_can_partially_repin_existing_reports(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "Plans" / "bundle.json"
    manifest.parent.mkdir()
    durable_report = tmp_path / "docs" / "evidence" / "ready" / "report.json"
    durable_report.parent.mkdir(parents=True)
    durable_report.write_text(json.dumps({"ready": True}) + "\n")
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {"name": "ready_report", "path": "/tmp/ready.json"},
                    {"name": "missing_report", "path": "/tmp/missing.json"},
                ]
            }
        )
    )
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "name": "ready_report",
                        "durable_report_path": "docs/evidence/ready/report.json",
                        "durable_producer": "ready command",
                    },
                    {
                        "name": "missing_report",
                        "durable_report_path": "docs/evidence/missing/report.json",
                        "durable_producer": "missing command",
                    },
                ]
            }
        )
    )
    output = tmp_path / "Plans" / "bundle-partial.json"

    summary = repin.repin_manifest_from_plan(
        manifest,
        plan,
        output_manifest=output,
        only_existing=True,
    )
    payload = json.loads(output.read_text())

    assert summary["ready"] is False
    assert summary["repinned_report_count"] == 1
    assert summary["missing_durable_report_count"] == 1
    assert payload["reports"][0]["path"] == "../docs/evidence/ready/report.json"
    assert payload["reports"][1]["path"] == "/tmp/missing.json"


def test_repin_manifest_from_multiple_plans_updates_all_selected_reports(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "Plans" / "bundle.json"
    manifest.parent.mkdir()
    first_report = tmp_path / "docs" / "evidence" / "first" / "report.json"
    second_report = tmp_path / "docs" / "evidence" / "second" / "report.json"
    first_report.parent.mkdir(parents=True)
    second_report.parent.mkdir(parents=True)
    first_report.write_text(json.dumps({"ready": True}) + "\n")
    second_report.write_text(json.dumps({"ready": True}) + "\n")
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {"name": "first_report", "path": "/tmp/first.json"},
                    {"name": "second_report", "path": "/tmp/second.json"},
                    {"name": "unselected_report", "path": "/tmp/third.json"},
                ]
            }
        )
    )
    first_plan = tmp_path / "first-plan.json"
    second_plan = tmp_path / "second-plan.json"
    first_plan.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "name": "first_report",
                        "durable_report_path": "docs/evidence/first/report.json",
                        "durable_producer": "first command",
                    }
                ]
            }
        )
    )
    second_plan.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "name": "second_report",
                        "durable_report_path": "docs/evidence/second/report.json",
                        "durable_producer": "second command",
                    }
                ]
            }
        )
    )
    output = tmp_path / "Plans" / "bundle-repinned.json"

    summary = repin.repin_manifest_from_plan(
        manifest,
        [first_plan, second_plan],
        output_manifest=output,
    )
    payload = json.loads(output.read_text())

    assert summary["ready"] is True
    assert summary["plan"] is None
    assert summary["plans"] == [str(first_plan), str(second_plan)]
    assert summary["repinned_report_count"] == 2
    assert payload["reports"][0]["path"] == "../docs/evidence/first/report.json"
    assert payload["reports"][0]["producer"] == "first command"
    assert payload["reports"][1]["path"] == "../docs/evidence/second/report.json"
    assert payload["reports"][1]["producer"] == "second command"
    assert payload["reports"][2]["path"] == "/tmp/third.json"


def test_repin_manifest_from_multiple_plans_rejects_duplicate_step_names(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "Plans" / "bundle.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"reports": [{"name": "one", "path": "/tmp/one.json"}]}))
    first_plan = tmp_path / "first-plan.json"
    second_plan = tmp_path / "second-plan.json"
    step = {
        "steps": [
            {
                "name": "one",
                "durable_report_path": "docs/evidence/one.json",
            }
        ]
    }
    first_plan.write_text(json.dumps(step))
    second_plan.write_text(json.dumps(step))

    try:
        repin.repin_manifest_from_plan(manifest, [first_plan, second_plan])
    except ValueError as exc:
        assert str(exc) == "duplicate plan step name: one"
    else:
        raise AssertionError("expected duplicate plan step to fail")


def test_repin_manifest_cli_returns_nonzero_for_missing_durable_reports(
    tmp_path: Path,
    capsys,
) -> None:
    manifest = tmp_path / "Plans" / "bundle.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({"reports": [{"name": "one", "path": "/tmp/one.json"}]}))
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "name": "one",
                        "durable_report_path": "docs/evidence/one.json",
                    }
                ]
            }
        )
    )

    code = repin.main([str(manifest), "--plan", str(plan)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["ready"] is False
