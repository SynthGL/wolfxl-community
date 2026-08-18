from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "plan_ooxml_evidence_batch.py"
    spec = importlib.util.spec_from_file_location("plan_ooxml_evidence_batch", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


planner = _load_module()
RECOVERY_PLAN_DIR = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "fidelity"
    / "evidence"
    / "2026-05-31-current-evidence-recovery-plan"
)


def _read_recovery_plan(name: str) -> dict:
    return json.loads((RECOVERY_PLAN_DIR / name).read_text(encoding="utf-8"))


def test_batch_plan_groups_missing_reports_by_safe_next_action(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"ready": True}) + "\n")
    manifest = _write_manifest(tmp_path, existing)

    plan = planner.plan_batch(manifest)

    assert plan["plan_only"] is True
    assert plan["safe_to_execute_automatically"] is False
    assert plan["bundle_ready"] is False
    assert plan["total_missing_report_count"] == 3
    assert plan["selected_action_counts"] == {
        "defer_excel_batch": 1,
        "rerun_after_upstream_evidence": 1,
        "rerun_headless": 1,
    }
    assert plan["selected_upstream_ready_step_count"] == 2
    assert plan["selected_waiting_on_upstream_step_count"] == 1
    assert plan["selected_lane_counts"] == {
        "coverage_gate": 1,
        "headless": 1,
        "render": 1,
    }
    assert [step["name"] for step in plan["steps"]] == [
        "missing_headless",
        "missing_render",
        "missing_coverage",
    ]
    assert [step["opens_excel_or_render_oracle"] for step in plan["steps"]] == [
        False,
        True,
        False,
    ]
    assert [step["depends_on_oracle_evidence"] for step in plan["steps"]] == [
        False,
        False,
        True,
    ]
    coverage_step = plan["steps"][2]
    assert coverage_step["upstream_report_count"] == 1
    assert coverage_step["known_upstream_report_count"] == 1
    assert coverage_step["missing_upstream_report_count"] == 1
    assert coverage_step["missing_known_upstream_report_count"] == 1
    assert coverage_step["unknown_upstream_report_count"] == 0
    assert coverage_step["upstream_report_names"] == ["missing_render"]
    assert coverage_step["upstream_reports_ready"] is False
    assert coverage_step["missing_upstream_reports"] == [
        str(tmp_path / "missing-render.json")
    ]
    assert coverage_step["missing_upstream_report_names"] == ["missing_render"]
    assert coverage_step["unknown_upstream_reports"] == []
    assert plan["selected_missing_known_upstream_report_count"] == 1
    assert plan["selected_unknown_upstream_report_count"] == 0
    assert plan["selected_unknown_upstream_unique_count"] == 0
    assert plan["selected_unknown_upstream_reports"] == []
    assert plan["selected_dependency_round_counts"] == {"0": 2, "1": 1}
    assert plan["selected_unresolved_dependency_step_count"] == 0
    assert plan["selected_unresolved_dependency_reason_counts"] == {}
    assert [step["dependency_round"] for step in plan["steps"]] == [0, 0, 1]


def test_batch_plan_can_select_excel_batch_steps_only(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"ready": True}) + "\n")
    manifest = _write_manifest(tmp_path, existing)

    plan = planner.plan_batch(manifest, actions={"defer_excel_batch"})

    assert plan["selected_step_count"] == 1
    assert plan["skipped_by_filter_count"] == 2
    assert plan["selected_action_counts"] == {"defer_excel_batch": 1}
    assert plan["steps"][0]["name"] == "missing_render"


def test_batch_plan_can_select_upstream_ready_steps_only(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"ready": True}) + "\n")
    manifest = _write_manifest(tmp_path, existing)

    plan = planner.plan_batch(manifest, upstream_ready=True)

    assert plan["upstream_filter"] == "ready"
    assert plan["selected_step_count"] == 2
    assert plan["selected_waiting_on_upstream_step_count"] == 0
    assert [step["name"] for step in plan["steps"]] == [
        "missing_headless",
        "missing_render",
    ]


def test_batch_plan_can_select_waiting_steps_only(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"ready": True}) + "\n")
    manifest = _write_manifest(tmp_path, existing)

    plan = planner.plan_batch(manifest, upstream_ready=False)

    assert plan["upstream_filter"] == "waiting"
    assert plan["selected_step_count"] == 1
    assert plan["selected_upstream_ready_step_count"] == 0
    assert plan["steps"][0]["name"] == "missing_coverage"
    assert plan["steps"][0]["dependency_round"] is None
    assert plan["steps"][0]["dependency_unresolved_reasons"] == [
        "unselected_missing_upstream"
    ]
    assert plan["selected_unresolved_dependency_reason_counts"] == {
        "unselected_missing_upstream": 1
    }


def test_batch_plan_can_filter_by_computed_dependency_round(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"ready": True}) + "\n")
    manifest = _write_manifest(tmp_path, existing)

    plan = planner.plan_batch(manifest, dependency_round=1)

    assert plan["dependency_round_filter"] == 1
    assert plan["selected_step_count"] == 1
    assert plan["steps"][0]["name"] == "missing_coverage"
    assert plan["steps"][0]["dependency_round"] == 1
    assert plan["selected_dependency_round_counts"] == {"1": 1}
    assert plan["selected_unresolved_dependency_step_count"] == 0


def test_batch_plan_cli_summary_omits_steps(tmp_path: Path, capsys) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"ready": True}) + "\n")
    manifest = _write_manifest(tmp_path, existing)

    code = planner.main(
        [str(manifest), "--summary-only", "--lane", "headless", "--upstream-ready"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["selected_step_count"] == 1
    assert payload["selected_lane_counts"] == {"headless": 1}
    assert payload["upstream_filter"] == "ready"
    assert "steps" not in payload


def test_batch_plan_cli_can_write_json_and_markdown_outputs(
    tmp_path: Path,
    capsys,
) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"ready": True}) + "\n")
    manifest = _write_manifest(tmp_path, existing)
    output = tmp_path / "plan.json"
    markdown = tmp_path / "plan.md"

    code = planner.main(
        [
            str(manifest),
            "--lane",
            "render",
            "--output",
            str(output),
            "--markdown-output",
            str(markdown),
            "--markdown-title",
            "Render Evidence Batch",
        ]
    )
    printed = json.loads(capsys.readouterr().out)
    payload = json.loads(output.read_text())
    markdown_text = markdown.read_text()

    assert code == 0
    assert printed["selected_step_count"] == 1
    assert payload["steps"][0]["name"] == "missing_render"
    assert markdown_text.startswith("# Render Evidence Batch\n")
    assert "| `selected_step_count` | `1` |" in markdown_text
    assert "| `selected_dependency_round_counts` | `{\"0\": 1}` |" in markdown_text
    assert "uv run --no-sync python scripts/run_ooxml_render_compare.py" in markdown_text


def test_checked_in_recovery_plan_keeps_split_steps_unique_and_complete() -> None:
    all_missing = _read_recovery_plan("all-missing-summary.json")
    selected_plans = [
        _read_recovery_plan("ready-excel-batch.json"),
        _read_recovery_plan("waiting-excel-batch.json"),
        _read_recovery_plan("coverage-gates-after-excel.json"),
    ]
    step_names = [
        step["name"]
        for plan in selected_plans
        for step in plan.get("steps") or []
    ]

    assert len(step_names) == all_missing["selected_step_count"]
    assert len(step_names) == len(set(step_names))
    assert sum(plan["selected_step_count"] for plan in selected_plans) == all_missing[
        "selected_step_count"
    ]
    assert sum(
        plan["selected_unknown_upstream_report_count"] for plan in selected_plans
    ) == 0


def test_checked_in_round_one_recovery_plan_has_resolved_dependencies() -> None:
    round_one = _read_recovery_plan("round-1-after-ready.json")

    assert round_one["dependency_round_filter"] == 1
    assert round_one["selected_step_count"] == 67
    assert round_one["selected_dependency_round_counts"] == {"1": 67}
    assert round_one["selected_unresolved_dependency_step_count"] == 0
    assert round_one["selected_action_counts"] == {
        "defer_excel_batch": 59,
        "rerun_after_upstream_evidence": 8,
    }
    assert round_one["selected_execution_mode_counts"] == {
        "headless_after_excel_evidence": 59,
        "headless_after_upstream_evidence": 8,
    }
    assert round_one["selected_excel_focus_step_count"] == 0
    assert round_one["selected_headless_after_upstream_step_count"] == 8


def test_command_safety_distinguishes_excel_renders_from_json_audits() -> None:
    excel_render = (
        "uv run --no-sync python scripts/run_ooxml_render_compare.py fixtures "
        "--render-engine excel > /tmp/report.json"
    )
    json_audit = (
        "osascript -e 'tell application \"Microsoft Excel\" to quit' "
        ">/dev/null 2>&1 || true; "
        "uv run --no-sync python scripts/audit_ooxml_intentional_render_delta.py "
        "docs/fidelity/render.json --strict > docs/fidelity/delta.json"
    )
    nested_excel_render = (
        "sh -c 'uv run --no-sync python scripts/run_ooxml_render_compare.py "
        "fixtures --render-engine excel > /tmp/report.json'"
    )
    manual_excel = "Native Microsoft Excel copy baseline: open a workbook and save it."

    assert planner._command_opens_excel_or_render_oracle(excel_render) is True
    assert planner._command_opens_excel_or_render_oracle(nested_excel_render) is True
    assert planner._command_opens_excel_or_render_oracle(manual_excel) is True
    assert planner._command_opens_excel_or_render_oracle(json_audit) is True
    stripped = planner._strip_excel_quit_prefix_if_headless(json_audit)
    assert "osascript" not in stripped
    assert planner._command_opens_excel_or_render_oracle(stripped) is False


def test_checked_in_recovery_plan_uses_durable_inputs_after_first_batch() -> None:
    plan_names = [
        "waiting-excel-batch.json",
        "coverage-gates-after-excel.json",
        "round-1-after-ready.json",
    ]
    bad_inputs = []

    for plan_name in plan_names:
        plan = _read_recovery_plan(plan_name)
        for step in plan.get("steps") or []:
            for flag, path in planner._producer_report_args(
                step.get("durable_producer")
            ):
                if path.startswith("/tmp"):
                    bad_inputs.append(
                        {
                            "plan": plan_name,
                            "step": step["name"],
                            "flag": flag,
                            "path": path,
                        }
                    )

    assert bad_inputs == []


def test_checked_in_round_one_headless_audits_do_not_quit_excel() -> None:
    round_one = _read_recovery_plan("round-1-after-ready.json")
    audit_only_steps = [
        step
        for step in round_one.get("steps") or []
        if step.get("execution_mode") in {
            "headless_after_excel_evidence",
            "headless_after_upstream_evidence",
        }
    ]

    assert audit_only_steps
    assert [
        step["name"]
        for step in audit_only_steps
        if "osascript" in str(step.get("durable_producer") or "")
    ] == []


def test_batch_plan_marks_coverage_gate_ready_when_inputs_exist(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"ready": True}) + "\n")
    render_report = tmp_path / "render.json"
    render_report.write_text(json.dumps({"ready": True}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(tmp_path / "coverage.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_fidelity_coverage.py fixtures "
                            f"--render-report {render_report}"
                        ),
                    }
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)

    assert plan["selected_upstream_ready_step_count"] == 1
    assert plan["selected_waiting_on_upstream_step_count"] == 0
    assert plan["steps"][0]["upstream_reports_ready"] is True
    assert plan["steps"][0]["missing_upstream_reports"] == []


def test_batch_plan_treats_positional_json_reports_as_upstream_inputs(
    tmp_path: Path,
) -> None:
    render_report = tmp_path / "render.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "delta",
                        "path": str(tmp_path / "delta.json"),
                        "producer": (
                            "uv run --no-sync python "
                            f"scripts/audit_ooxml_intentional_render_delta.py {render_report} "
                            "--mutation marker_cell --strict "
                            f"> {tmp_path / 'delta.json'}"
                        ),
                    }
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)

    assert plan["selected_upstream_ready_step_count"] == 0
    assert plan["selected_waiting_on_upstream_step_count"] == 1
    step = plan["steps"][0]
    assert step["upstream_report_count"] == 1
    assert step["missing_upstream_reports"] == [str(render_report)]
    assert step["unknown_upstream_reports"] == [str(render_report)]
    assert step["dependency_round"] is None
    assert step["dependency_unresolved_reasons"] == ["unknown_upstream"]


def test_batch_plan_positional_render_inputs_use_render_candidates(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "timeline_copy_remove_app_open",
                        "path": str(tmp_path / "timeline-copy-remove-app.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_app_smoke.py fixtures --app excel"
                        ),
                    },
                    {
                        "name": "timeline_copy_remove_render",
                        "path": str(tmp_path / "timeline-copy-remove-render.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures --render-engine excel"
                        ),
                    },
                    {
                        "name": "timeline_copy_remove_equivalence",
                        "path": str(tmp_path / "equivalence.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_no_visual_change_render_equivalence.py "
                            "/tmp/wolfxl-render-excel-timeline-copy-remove/render-compare-report.json "
                            "--mutation copy_remove_sheet --strict"
                        ),
                    },
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)

    scratch_path = (
        "/tmp/wolfxl-render-excel-timeline-copy-remove/render-compare-report.json"
    )
    step = next(
        step
        for step in plan["steps"]
        if step["name"] == "timeline_copy_remove_equivalence"
    )
    candidates = step["unknown_upstream_report_candidates"][scratch_path]
    assert [candidate["name"] for candidate in candidates] == [
        "timeline_copy_remove_render"
    ]
    assert candidates[0]["lane"] == "render"


def test_batch_plan_maps_output_dir_artifacts_to_named_reports(
    tmp_path: Path,
) -> None:
    render_dir = tmp_path / "render-output"
    scratch_report = render_dir / "render-compare-report.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "render",
                        "path": str(tmp_path / "render.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures "
                            f"--output-dir {render_dir} --render-engine excel"
                        ),
                    },
                    {
                        "name": "equivalence",
                        "path": str(tmp_path / "equivalence.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_no_visual_change_render_equivalence.py "
                            f"{scratch_report} --mutation add_data_validation --strict"
                        ),
                    },
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)
    equivalence = next(step for step in plan["steps"] if step["name"] == "equivalence")

    assert equivalence["missing_upstream_report_names"] == ["render"]
    assert equivalence["unknown_upstream_reports"] == []
    assert equivalence["dependency_round"] == 1
    assert plan["selected_dependency_round_counts"] == {"0": 1, "1": 1}


def test_batch_plan_treats_same_producer_output_dir_artifact_as_internal(
    tmp_path: Path,
) -> None:
    render_dir = tmp_path / "render-output"
    render_report = render_dir / "render-compare-report.json"
    output_report = tmp_path / "equivalence.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "copy_sheet_equivalence",
                        "path": str(output_report),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures "
                            f"--output-dir {render_dir} --render-engine excel && "
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_copy_sheet_render_equivalence.py "
                            f"{render_report} --strict > {output_report}"
                        ),
                    }
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)
    step = plan["steps"][0]

    assert step["missing_upstream_reports"] == []
    assert step["missing_upstream_report_names"] == []
    assert step["unknown_upstream_reports"] == []
    assert step["dependency_round"] == 0
    assert step["dependency_unresolved_reasons"] == []


def test_batch_plan_maps_app_smoke_output_dir_artifacts_to_named_reports(
    tmp_path: Path,
) -> None:
    app_dir = tmp_path / "app-output"
    app_report = app_dir / "app-smoke-report.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "app_open",
                        "path": str(tmp_path / "app.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_app_smoke.py fixtures "
                            f"--output-dir {app_dir} --app excel"
                        ),
                    },
                    {
                        "name": "coverage",
                        "path": str(tmp_path / "coverage.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_fidelity_coverage.py fixtures "
                            f"--app-report {app_report}"
                        ),
                    },
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)
    coverage = next(step for step in plan["steps"] if step["name"] == "coverage")

    assert coverage["missing_upstream_report_names"] == ["app_open"]
    assert coverage["unknown_upstream_reports"] == []
    assert coverage["dependency_round"] == 1


def test_batch_plan_can_rewrite_missing_steps_to_durable_targets(
    tmp_path: Path,
) -> None:
    render_dir = Path("/tmp/wolfxl-render")
    render_report = Path("/tmp/wolfxl-render.json")
    equivalence_report = Path("/tmp/wolfxl-equivalence.json")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "render",
                        "path": str(render_report),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures "
                            f"--output-dir {render_dir} --render-engine excel "
                            f"> {render_report}"
                        ),
                    },
                    {
                        "name": "equivalence",
                        "path": str(equivalence_report),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_no_visual_change_render_equivalence.py "
                            f"{render_dir / 'render-compare-report.json'} "
                            f"--mutation add_data_validation --strict > {equivalence_report}"
                        ),
                    },
                ]
            }
        )
    )

    durable_root = tmp_path / "durable-batch"
    plan = planner.plan_batch(manifest, durable_output_root=durable_root)
    render = next(step for step in plan["steps"] if step["name"] == "render")
    equivalence = next(step for step in plan["steps"] if step["name"] == "equivalence")

    assert plan["durable_output_root"] == str(durable_root)
    assert render["durable_report_path"].endswith(
        "0001-render/wolfxl-render.json"
    )
    assert "mkdir -p" in render["durable_producer"]
    assert durable_root.relative_to(tmp_path.parent).as_posix() in render[
        "durable_producer"
    ]
    assert str(render_dir) not in render["durable_producer"]
    assert str(render_report) not in render["durable_producer"]
    assert "0001-render/artifacts/render-compare-report.json" in equivalence[
        "durable_producer"
    ]
    assert str(equivalence_report) not in equivalence["durable_producer"]


def test_batch_plan_copies_output_dir_artifact_to_durable_report(
    tmp_path: Path,
) -> None:
    output_dir = Path("/tmp/wolfxl-interactive")
    report_path = output_dir / "interactive-probe-report.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "interactive_probe",
                        "path": str(report_path),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_interactive_probe.py fixtures "
                            f"--output-dir {output_dir} "
                            "--probe-kind excel_ui_interaction"
                        ),
                    }
                ]
            }
        )
    )

    durable_root = tmp_path / "durable-batch"
    plan = planner.plan_batch(manifest, durable_output_root=durable_root)
    step = plan["steps"][0]

    assert step["durable_report_path"].endswith(
        "0001-interactive-probe/interactive-probe-report.json"
    )
    assert (
        "cp "
        in step["durable_producer"]
    )
    assert (
        "0001-interactive-probe/artifacts/interactive-probe-report.json"
        in step["durable_producer"]
    )


def test_batch_plan_rewrites_unselected_upstream_inputs_to_durable_targets(
    tmp_path: Path,
) -> None:
    missing_render = tmp_path / "missing-render.json"
    missing_coverage = tmp_path / "missing-coverage.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "missing_render",
                        "path": str(missing_render),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures "
                            "--render-engine excel "
                            f"> {missing_render}"
                        ),
                    },
                    {
                        "name": "missing_coverage",
                        "path": str(missing_coverage),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_fidelity_coverage.py fixtures "
                            f"--render-report {missing_render} > {missing_coverage}"
                        ),
                    },
                ]
            }
        )
    )

    durable_root = tmp_path / "durable-batch"
    plan = planner.plan_batch(
        manifest,
        actions={"rerun_after_upstream_evidence"},
        durable_output_root=durable_root,
    )

    assert plan["selected_step_count"] == 1
    coverage = plan["steps"][0]
    assert coverage["name"] == "missing_coverage"
    assert "0001-missing-render/missing-render.json" in coverage["durable_producer"]
    assert "0002-missing-coverage/missing-coverage.json" in coverage[
        "durable_producer"
    ]
    assert str(missing_render) not in coverage["durable_producer"]
    assert str(missing_coverage) not in coverage["durable_producer"]


def test_batch_plan_carries_manifest_expectations_into_steps(
    tmp_path: Path,
) -> None:
    missing_report = tmp_path / "missing.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "expected_failure_triage",
                        "path": str(missing_report),
                        "producer": f"printf '{{}}\\n' > {missing_report}",
                        "expect": [{"path": "failure_count", "equals": 1}],
                    },
                ],
            }
        )
    )

    plan = planner.plan_batch(manifest, durable_output_root=tmp_path / "durable")

    assert plan["steps"][0]["expect"] == [{"path": "failure_count", "equals": 1}]


def test_batch_plan_markdown_includes_durable_commands_when_requested(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps({"ready": True}) + "\n")
    manifest = _write_manifest(tmp_path, existing)
    output = tmp_path / "plan.json"
    markdown = tmp_path / "plan.md"

    code = planner.main(
        [
            str(manifest),
            "--lane",
            "render",
            "--durable-output-root",
            str(tmp_path / "durable"),
            "--output",
            str(output),
            "--markdown-output",
            str(markdown),
        ]
    )
    payload = json.loads(output.read_text())
    markdown_text = markdown.read_text()

    assert code == 0
    assert payload["durable_output_root"] == str(tmp_path / "durable")
    assert "Durable report target:" in markdown_text
    assert "Durable command:" in markdown_text


def test_batch_plan_does_not_treat_same_producer_redirect_as_upstream(
    tmp_path: Path,
) -> None:
    staged = tmp_path / "staged.json"
    output = tmp_path / "summary.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "boundary",
                        "path": str(output),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_random_corpus_holdout.py fixtures "
                            f"> {staged} && "
                            "uv run --no-sync python "
                            f"scripts/summarize_ooxml_render_boundary.py {staged} "
                            "/tmp/render/render-compare-report.json --strict "
                            f"> {output}"
                        ),
                    }
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)

    step = plan["steps"][0]
    assert str(staged) not in step["missing_upstream_reports"]
    assert str(staged) not in step["unknown_upstream_reports"]
    assert step["unknown_upstream_reports"] == [
        "/tmp/render/render-compare-report.json"
    ]


def test_batch_plan_candidate_hints_reject_numeric_shape_mismatches(
    tmp_path: Path,
) -> None:
    holdout_50 = tmp_path / "holdout-50.json"
    holdout_50.parent.mkdir(exist_ok=True)
    holdout_50.write_text(json.dumps({"ready": True}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "random_corpus_holdout_50",
                        "path": str(holdout_50),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_random_corpus_holdout.py fixtures "
                            "--sample-size 50"
                        ),
                    },
                    {
                        "name": "random_corpus_holdout_20_render_boundary",
                        "path": str(tmp_path / "boundary.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/summarize_ooxml_render_boundary.py "
                            "/tmp/wolfxl-random-corpus-holdout-20-staged-render.json "
                            "/tmp/wolfxl-render-excel-random-holdout-20/render-compare-report.json "
                            "--strict"
                        ),
                    },
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)
    step = next(
        step
        for step in plan["steps"]
        if step["name"] == "random_corpus_holdout_20_render_boundary"
    )

    assert (
        step["unknown_upstream_report_candidates"][
            "/tmp/wolfxl-random-corpus-holdout-20-staged-render.json"
        ]
        == []
    )
    assert step["unambiguous_ready_upstream_replacements"] == {}


def test_batch_plan_ready_replacements_require_ready_report(
    tmp_path: Path,
) -> None:
    durable_report = tmp_path / "durable" / "report.json"
    durable_report.parent.mkdir()
    durable_report.write_text(json.dumps({"ready": False}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "fed_aea_papers_corpus_buckets",
                        "path": str(durable_report),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_corpus_buckets.py fixtures"
                        ),
                    },
                    {
                        "name": "random_corpus_holdout_10_render_smoke",
                        "path": str(tmp_path / "render.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_random_corpus_holdout.py "
                            "/tmp/wolfxl-corpus-portfolio-buckets-with-fed-aea.json "
                            "--sample-size 10"
                        ),
                    },
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)
    step = next(
        step
        for step in plan["steps"]
        if step["name"] == "random_corpus_holdout_10_render_smoke"
    )
    scratch_path = "/tmp/wolfxl-corpus-portfolio-buckets-with-fed-aea.json"
    candidates = step["unknown_upstream_report_candidates"][scratch_path]

    assert candidates[0]["name"] == "fed_aea_papers_corpus_buckets"
    assert candidates[0]["exists"] is True
    assert candidates[0]["ready"] is False
    assert step["unknown_upstream_reports_with_ready_candidates"] == {}
    assert step["unambiguous_ready_upstream_replacements"] == {}


def test_batch_plan_does_not_treat_redirect_json_as_upstream_input(
    tmp_path: Path,
) -> None:
    output_report = tmp_path / "render.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "render",
                        "path": str(output_report),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures "
                            "--render-engine excel "
                            f"> {output_report}"
                        ),
                    }
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)

    assert plan["selected_upstream_ready_step_count"] == 1
    assert plan["selected_waiting_on_upstream_step_count"] == 0
    assert plan["steps"][0]["upstream_report_count"] == 0


def test_batch_plan_separates_external_scratch_inputs_from_manifest_reports(
    tmp_path: Path,
) -> None:
    external_render_report = tmp_path / "scratch" / "render.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(tmp_path / "coverage.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_fidelity_coverage.py fixtures "
                            f"--render-report {external_render_report}"
                        ),
                    }
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest)

    assert plan["selected_step_count"] == 1
    assert plan["selected_waiting_on_upstream_step_count"] == 1
    assert plan["selected_missing_known_upstream_report_count"] == 0
    assert plan["selected_unknown_upstream_report_count"] == 1
    assert plan["selected_unknown_upstream_unique_count"] == 1
    step = plan["steps"][0]
    assert step["upstream_report_count"] == 1
    assert step["known_upstream_report_count"] == 0
    assert step["missing_upstream_report_count"] == 1
    assert step["missing_known_upstream_report_count"] == 0
    assert step["unknown_upstream_report_count"] == 1
    assert step["upstream_report_names"] == []
    assert step["missing_upstream_report_names"] == []
    assert step["unknown_upstream_reports"] == [str(external_render_report)]
    assert step["unknown_upstream_report_candidates"] == {
        str(external_render_report): []
    }
    assert plan["selected_unknown_upstream_reports"] == [
        {
            "path": str(external_render_report),
            "dependent_step_count": 1,
            "dependent_steps": ["coverage"],
        }
    ]


def test_batch_plan_suggests_manifest_candidates_for_old_scratch_names(
    tmp_path: Path,
) -> None:
    durable_report = tmp_path / "durable" / "report.json"
    durable_report.parent.mkdir()
    durable_report.write_text(json.dumps({"ready": True}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "excel_app_open_marker_full_pack_verified_report",
                        "path": str(durable_report),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_app_smoke.py fixtures --app excel"
                        ),
                    },
                    {
                        "name": "excel_app_open_marker_full_pack_missing_report",
                        "path": str(tmp_path / "missing-app-report.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_app_smoke.py fixtures --app excel"
                        ),
                    },
                    {
                        "name": "coverage",
                        "path": str(tmp_path / "coverage.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_fidelity_coverage.py fixtures "
                            "--app-report "
                            "/tmp/wolfxl-app-smoke-excel-marker-full-pack-verified.json"
                        ),
                    },
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest, actions={"rerun_after_upstream_evidence"})

    assert plan["selected_step_count"] == 1
    assert plan["selected_unknown_upstream_report_count"] == 1
    assert plan["selected_unknown_upstream_report_candidate_count"] == 1
    assert plan["selected_unknown_upstream_report_ready_candidate_count"] == 1
    assert plan["selected_unambiguous_ready_replacement_count"] == 1
    step = plan["steps"][0]
    scratch_path = "/tmp/wolfxl-app-smoke-excel-marker-full-pack-verified.json"
    candidates = step["unknown_upstream_report_candidates"][scratch_path]
    assert candidates[0]["name"] == "excel_app_open_marker_full_pack_verified_report"
    assert candidates[0]["path"] == str(durable_report)
    assert candidates[0]["producer_path"] == durable_report.relative_to(
        tmp_path.parent
    ).as_posix()
    assert candidates[0]["exists"] is True
    assert candidates[0]["lane"] == "app_open"
    assert any(candidate["exists"] is False for candidate in candidates)
    assert step["unknown_upstream_reports_with_ready_candidates"] == {
        scratch_path: [candidate for candidate in candidates if candidate["exists"]]
    }
    assert step["unambiguous_ready_upstream_replacements"] == {
        scratch_path: candidates[0]
    }
    assert set(candidates[0]["matched_tokens"]) >= {
        "excel",
        "marker",
        "full",
        "pack",
        "verified",
    }


def test_batch_plan_candidate_hints_respect_report_argument_kind(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "external_link_retarget_excel_app_open",
                        "path": str(tmp_path / "app.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_app_smoke.py fixtures --app excel"
                        ),
                    },
                    {
                        "name": "external_link_retarget_mutation",
                        "path": str(tmp_path / "mutation.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_fidelity_mutations.py fixtures"
                        ),
                    },
                    {
                        "name": "coverage",
                        "path": str(tmp_path / "coverage.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_fidelity_coverage.py fixtures "
                            "--report "
                            "/tmp/wolfxl-ooxml-fidelity-mutations-external-link-retarget.json"
                        ),
                    },
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest, actions={"rerun_after_upstream_evidence"})

    scratch_path = "/tmp/wolfxl-ooxml-fidelity-mutations-external-link-retarget.json"
    candidates = plan["steps"][0]["unknown_upstream_report_candidates"][scratch_path]
    assert [candidate["name"] for candidate in candidates] == [
        "external_link_retarget_mutation"
    ]
    assert candidates[0]["exists"] is False
    assert candidates[0]["lane"] == "headless"
    assert (
        plan["steps"][0]["unknown_upstream_reports_with_ready_candidates"] == {}
    )
    assert plan["steps"][0]["unambiguous_ready_upstream_replacements"] == {}


def test_batch_plan_candidate_hints_prefer_less_noisy_name_ties(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "slicer_shared_two_pivots_sidecar_destructive_mutation_report",
                        "path": str(tmp_path / "destructive" / "report.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_fidelity_mutations.py fixtures"
                        ),
                    },
                    {
                        "name": "slicer_shared_two_pivots_sidecar_mutation_report",
                        "path": str(tmp_path / "neutral" / "report.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_fidelity_mutations.py fixtures"
                        ),
                    },
                    {
                        "name": "coverage",
                        "path": str(tmp_path / "coverage.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_fidelity_coverage.py fixtures "
                            "--report "
                            "/tmp/wolfxl-ooxml-fidelity-mutations-slicer-shared-two-pivots.json"
                        ),
                    },
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest, actions={"rerun_after_upstream_evidence"})

    scratch_path = "/tmp/wolfxl-ooxml-fidelity-mutations-slicer-shared-two-pivots.json"
    candidates = plan["steps"][0]["unknown_upstream_report_candidates"][scratch_path]
    assert candidates[0]["name"] == "slicer_shared_two_pivots_sidecar_mutation_report"
    assert plan["steps"][0]["unambiguous_ready_upstream_replacements"] == {}


def test_batch_plan_marks_specific_ready_candidate_as_unambiguous(
    tmp_path: Path,
) -> None:
    neutral_report = tmp_path / "neutral" / "report.json"
    destructive_report = tmp_path / "destructive" / "report.json"
    neutral_report.parent.mkdir()
    destructive_report.parent.mkdir()
    neutral_report.write_text(json.dumps({"ready": True}) + "\n")
    destructive_report.write_text(json.dumps({"ready": True}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "slicer_shared_two_pivots_sidecar_destructive_mutation_report",
                        "path": str(destructive_report),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_fidelity_mutations.py fixtures"
                        ),
                    },
                    {
                        "name": "slicer_shared_two_pivots_sidecar_mutation_report",
                        "path": str(neutral_report),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_fidelity_mutations.py fixtures"
                        ),
                    },
                    {
                        "name": "coverage",
                        "path": str(tmp_path / "coverage.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_fidelity_coverage.py fixtures "
                            "--report "
                            "/tmp/wolfxl-ooxml-fidelity-mutations-slicer-shared-two-pivots.json"
                        ),
                    },
                ]
            }
        )
    )

    plan = planner.plan_batch(manifest, actions={"rerun_after_upstream_evidence"})

    scratch_path = "/tmp/wolfxl-ooxml-fidelity-mutations-slicer-shared-two-pivots.json"
    replacement = plan["steps"][0]["unambiguous_ready_upstream_replacements"][
        scratch_path
    ]
    assert replacement["name"] == "slicer_shared_two_pivots_sidecar_mutation_report"
    assert replacement["path"] == str(neutral_report)
    assert replacement["producer_path"] == neutral_report.relative_to(
        tmp_path.parent
    ).as_posix()


def _write_manifest(tmp_path: Path, existing: Path) -> Path:
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "existing",
                        "path": str(existing),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_fidelity_mutations.py fixtures"
                        ),
                        "expect": [{"path": "ready", "equals": True}],
                    },
                    {
                        "name": "missing_headless",
                        "path": str(tmp_path / "missing-headless.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_gap_radar.py fixtures --json"
                        ),
                    },
                    {
                        "name": "missing_render",
                        "path": str(tmp_path / "missing-render.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/run_ooxml_render_compare.py fixtures "
                            "--render-engine excel"
                        ),
                    },
                    {
                        "name": "missing_coverage",
                        "path": str(tmp_path / "missing-coverage.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_fidelity_coverage.py fixtures "
                            f"--render-report {tmp_path / 'missing-render.json'}"
                        ),
                    },
                ]
            }
        )
    )
    return manifest
