from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "run_ooxml_evidence_plan.py"
    spec = importlib.util.spec_from_file_location("run_ooxml_evidence_plan", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_module()


def test_plan_runner_dry_run_reports_excel_guard(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path)

    summary = runner.summarize_plan_run(plan)

    assert summary["dry_run"] is True
    assert summary["execute"] is False
    assert summary["candidate_step_count"] == 2
    assert summary["existing_durable_report_count"] == 0
    assert summary["invalid_durable_report_count"] == 0
    assert summary["invalid_durable_reports"] == []
    assert summary["missing_durable_report_count"] == 2
    assert summary["skipped_existing_step_count"] == 0
    assert summary["next_missing_step"] == {
        "index": 1,
        "name": "safe_headless",
        "lane": "headless",
        "action": "rerun_headless",
        "durable_report_path": str(tmp_path / "safe.json"),
        "durable_report_status": {
            "status": "missing",
            "path": str(tmp_path / "safe.json"),
        },
        "requires_excel_batch": False,
    }
    assert summary["selected_step_count"] == 2
    assert summary["requires_explicit_excel_batch"] is True
    assert summary["missing_command_count"] == 0
    assert summary["selected_action_counts"] == {
        "defer_excel_batch": 1,
        "rerun_headless": 1,
    }
    assert summary["selected_lane_counts"] == {"headless": 1, "render": 1}
    assert [step["name"] for step in summary["selected_steps"]] == [
        "safe_headless",
        "excel_render",
    ]


def test_plan_runner_trusts_explicit_headless_deferred_steps(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "name": "json_delta_after_excel",
                        "lane": "render",
                        "action": "defer_excel_batch",
                        "durable_producer": "printf '{\"ok\": true}\\n' > delta.json",
                        "durable_report_path": str(tmp_path / "delta.json"),
                        "opens_excel_or_render_oracle": False,
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = runner.summarize_plan_run(plan)

    assert summary["requires_explicit_excel_batch"] is False
    assert summary["selected_steps"][0]["requires_excel_batch"] is False


def test_plan_runner_reports_existing_outputs_and_skips_them(
    tmp_path: Path,
) -> None:
    plan = _write_plan(tmp_path)
    (tmp_path / "safe.json").write_text('{"ok": true}\n')

    summary = runner.summarize_plan_run(plan, skip_existing=True)

    assert summary["candidate_step_count"] == 2
    assert summary["existing_durable_report_count"] == 1
    assert summary["invalid_durable_report_count"] == 0
    assert summary["missing_durable_report_count"] == 1
    assert summary["skipped_existing_step_count"] == 1
    assert summary["selected_step_count"] == 1
    assert summary["next_missing_step"]["name"] == "excel_render"
    assert summary["selected_steps"][0]["index"] == 2
    assert summary["selected_steps"][0]["name"] == "excel_render"


def test_plan_runner_does_not_skip_invalid_json_outputs(
    tmp_path: Path,
) -> None:
    plan = _write_plan(tmp_path)
    (tmp_path / "safe.json").write_text("{not json\n")

    summary = runner.summarize_plan_run(plan, skip_existing=True)

    assert summary["existing_durable_report_count"] == 0
    assert summary["invalid_durable_report_count"] == 1
    assert summary["invalid_durable_reports"][0]["name"] == "safe_headless"
    assert summary["missing_durable_report_count"] == 2
    assert summary["skipped_existing_step_count"] == 0
    assert [step["name"] for step in summary["selected_steps"]] == [
        "safe_headless",
        "excel_render",
    ]


def test_plan_runner_does_not_skip_failed_json_outputs(
    tmp_path: Path,
) -> None:
    plan = _write_plan(tmp_path)
    (tmp_path / "safe.json").write_text(
        json.dumps({"ready": False, "failure_count": 1}) + "\n"
    )

    summary = runner.summarize_plan_run(plan, skip_existing=True)

    assert summary["existing_durable_report_count"] == 0
    assert summary["invalid_durable_report_count"] == 1
    assert summary["invalid_durable_reports"][0]["name"] == "safe_headless"
    assert summary["invalid_durable_reports"][0]["durable_report_status"] == {
        "status": "failed_report",
        "path": str(tmp_path / "safe.json"),
        "failure_reasons": ["ready_false", "failure_count_positive"],
    }
    assert summary["missing_durable_report_count"] == 2
    assert summary["skipped_existing_step_count"] == 0
    assert [step["name"] for step in summary["selected_steps"]] == [
        "safe_headless",
        "excel_render",
    ]


def test_plan_runner_skips_expected_positive_failure_counts(
    tmp_path: Path,
) -> None:
    plan = _write_plan(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["steps"][0]["expect"] = [{"path": "failure_count", "equals": 1}]
    plan.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    (tmp_path / "safe.json").write_text(
        json.dumps({"failure_count": 1, "result_count": 63}) + "\n"
    )

    summary = runner.summarize_plan_run(plan, skip_existing=True)

    assert summary["existing_durable_report_count"] == 0
    assert summary["expected_failed_durable_report_count"] == 1
    assert summary["expected_failed_durable_reports"][0]["name"] == "safe_headless"
    assert summary["expected_failed_durable_reports"][0]["durable_report_status"] == {
        "status": "expected_failed_report",
        "path": str(tmp_path / "safe.json"),
        "expected_failure_reasons": ["failure_count_positive"],
    }
    assert summary["invalid_durable_report_count"] == 0
    assert summary["missing_durable_report_count"] == 1
    assert summary["skipped_existing_step_count"] == 1
    assert [step["name"] for step in summary["selected_steps"]] == ["excel_render"]


def test_plan_runner_cli_strict_existing_fails_on_invalid_json(
    tmp_path: Path,
    capsys,
) -> None:
    plan = _write_plan(tmp_path)
    (tmp_path / "safe.json").write_text("{not json\n")

    code = runner.main([str(plan), "--skip-existing", "--strict-existing"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["invalid_durable_report_count"] == 1
    assert payload["selected_steps"][0]["name"] == "safe_headless"


def test_plan_runner_cli_summary_only_omits_commands(
    tmp_path: Path,
    capsys,
) -> None:
    plan = _write_plan(tmp_path)

    code = runner.main([str(plan), "--summary-only"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["candidate_step_count"] == 2
    assert payload["selected_step_count"] == 2
    assert payload["selected_step_preview_count"] == 2
    assert payload["next_missing_step"]["name"] == "safe_headless"
    assert "selected_steps" not in payload
    assert "shell_script_outputs" not in payload


def test_plan_runner_cli_strict_commands_fails_on_missing_command(
    tmp_path: Path,
    capsys,
) -> None:
    plan = _write_plan(tmp_path)

    code = runner.main(
        [
            str(plan),
            "--command-field",
            "missing_command_field",
            "--strict-commands",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["missing_command_count"] == 2
    assert payload["missing_command_step_names"] == ["safe_headless", "excel_render"]


def test_plan_runner_refuses_excel_steps_without_explicit_flag(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path)

    summary = runner.run_plan(plan, cwd=tmp_path)

    assert summary["ready"] is False
    assert "allow-excel-focus" in summary["error"]
    assert not (tmp_path / "safe.json").exists()


def test_plan_runner_refuses_excel_steps_without_env_opt_in(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path)

    summary = runner.run_plan(plan, allow_excel_focus=True, cwd=tmp_path)

    assert summary["ready"] is False
    assert "WOLFXL_ALLOW_EXCEL_FOCUS=1" in summary["error"]
    assert not (tmp_path / "safe.json").exists()


def test_plan_runner_cli_refuses_excel_steps_without_env_opt_in(
    tmp_path: Path,
    capsys,
) -> None:
    plan = _write_plan(tmp_path)

    code = runner.main(
        [
            str(plan),
            "--execute",
            "--allow-excel-focus",
            "--lane",
            "render",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["ready"] is False
    assert "WOLFXL_ALLOW_EXCEL_FOCUS=1" in payload["error"]
    assert not (tmp_path / "excel.json").exists()


def test_plan_runner_executes_filtered_safe_step(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path)
    status_report = tmp_path / "status.json"

    summary = runner.run_plan(
        plan,
        lanes={"headless"},
        cwd=tmp_path,
        status_report=status_report,
    )

    assert summary["ready"] is True
    assert summary["failed_step_count"] == 0
    assert (tmp_path / "safe.json").read_text() == '{"ok": true}\n'
    status = json.loads(status_report.read_text())
    assert status["results"] == [
        {
            "name": "safe_headless",
            "returncode": 0,
            "command": "printf '{\"ok\": true}\\n' > safe.json",
        }
    ]


def test_plan_runner_executes_excel_steps_with_flag_and_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan = _write_plan(tmp_path)
    monkeypatch.setenv("WOLFXL_ALLOW_EXCEL_FOCUS", "1")

    summary = runner.run_plan(
        plan,
        lanes={"render"},
        allow_excel_focus=True,
        cwd=tmp_path,
    )

    assert summary["ready"] is True
    assert (tmp_path / "excel.json").read_text() == '{"excel": true}\n'


def test_plan_runner_cli_dry_run_is_safe_for_excel_steps(
    tmp_path: Path,
    capsys,
) -> None:
    plan = _write_plan(tmp_path)

    code = runner.main([str(plan), "--lane", "render", "--limit", "1"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["dry_run"] is True
    assert payload["requires_explicit_excel_batch"] is True
    assert payload["selected_steps"][0]["name"] == "excel_render"


def test_plan_runner_cli_can_write_shell_script_runbook(
    tmp_path: Path,
    capsys,
) -> None:
    plan = _write_plan(tmp_path)
    runbook = tmp_path / "run-selected.sh"

    code = runner.main(
        [
            str(plan),
            "--lane",
            "render",
            "--limit",
            "1",
            "--shell-script-output",
            str(runbook),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    text = runbook.read_text()

    assert code == 0
    assert payload["selected_step_count"] == 1
    if os.name != "nt":
        assert runbook.stat().st_mode & 0o111
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "# Step 2: excel_render\n" in text
    assert "# Requires explicit Excel batch: True\n" in text
    assert 'WOLFXL_ALLOW_EXCEL_FOCUS=1' in text
    assert "printf '{\"excel\": true}\\n' > excel.json\n" in text


def test_plan_runner_cli_can_write_chunked_shell_runbooks(
    tmp_path: Path,
    capsys,
) -> None:
    plan = _write_plan(tmp_path)
    output_dir = tmp_path / "chunks"
    manifest_path = tmp_path / "chunk-manifest.json"

    code = runner.main(
        [
            str(plan),
            "--chunk-size",
            "1",
            "--shell-script-dir",
            str(output_dir),
            "--chunk-manifest-output",
            str(manifest_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    chunk_paths = [Path(path) for path in payload["shell_script_outputs"]]
    manifest = json.loads(manifest_path.read_text())

    assert code == 0
    assert [path.name for path in chunk_paths] == [
        "chunk-001-steps-0001-0001.sh",
        "chunk-002-steps-0002-0002.sh",
    ]
    safe_chunk = chunk_paths[0].read_text()
    excel_chunk = chunk_paths[1].read_text()
    assert "# Step 1: safe_headless\n" in safe_chunk
    assert "# Requires explicit Excel batch: False\n" in safe_chunk
    assert "WOLFXL_ALLOW_EXCEL_FOCUS" not in safe_chunk
    assert "# Step 2: excel_render\n" in excel_chunk
    assert "# Requires explicit Excel batch: True\n" in excel_chunk
    assert 'WOLFXL_ALLOW_EXCEL_FOCUS=1' in excel_chunk
    assert payload["chunk_manifest"] == manifest
    assert manifest == [
        {
            "action_counts": {"rerun_headless": 1},
            "chunk": 1,
            "first_step_index": 1,
            "first_step_name": "safe_headless",
            "lane_counts": {"headless": 1},
            "last_step_index": 1,
            "last_step_name": "safe_headless",
            "requires_explicit_excel_batch": False,
            "shell_script": str(chunk_paths[0]),
            "step_count": 1,
        },
        {
            "action_counts": {"defer_excel_batch": 1},
            "chunk": 2,
            "first_step_index": 2,
            "first_step_name": "excel_render",
            "lane_counts": {"render": 1},
            "last_step_index": 2,
            "last_step_name": "excel_render",
            "requires_explicit_excel_batch": True,
            "shell_script": str(chunk_paths[1]),
            "step_count": 1,
        },
    ]


def test_plan_runner_summary_only_reports_chunk_manifest_count(
    tmp_path: Path,
    capsys,
) -> None:
    plan = _write_plan(tmp_path)

    code = runner.main(
        [
            str(plan),
            "--chunk-size",
            "1",
            "--summary-only",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["chunk_manifest_count"] == 2
    assert "chunk_manifest" not in payload


def _write_plan(tmp_path: Path) -> Path:
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "steps": [
                    {
                        "name": "safe_headless",
                        "lane": "headless",
                        "action": "rerun_headless",
                        "durable_producer": "printf '{\"ok\": true}\\n' > safe.json",
                        "durable_report_path": str(tmp_path / "safe.json"),
                        "opens_excel_or_render_oracle": False,
                    },
                    {
                        "name": "excel_render",
                        "lane": "render",
                        "action": "defer_excel_batch",
                        "durable_producer": "printf '{\"excel\": true}\\n' > excel.json",
                        "durable_report_path": str(tmp_path / "excel.json"),
                        "opens_excel_or_render_oracle": True,
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return plan
