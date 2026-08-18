from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "audit_ooxml_evidence_worker_status.py"
    spec = importlib.util.spec_from_file_location(
        "audit_ooxml_evidence_worker_status", script
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


auditor = _load_module()


def test_worker_status_reports_next_incomplete_shard_and_phase_gate(
    tmp_path: Path,
) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    complete_report = tmp_path / "complete.json"
    failed_report = tmp_path / "failed.json"
    complete_report.write_text("{}", encoding="utf-8")
    failed_report.write_text('{"ready": false}', encoding="utf-8")
    missing_report = tmp_path / "missing.json"
    phase_2_report = tmp_path / "phase-2.json"
    _write_plan(
        ready_plan,
        [
            _step("complete_one", "app_open", True, complete_report),
            _step("missing_one", "app_open", True, missing_report),
            _step("failed_one", "render", True, failed_report),
        ],
    )
    _write_plan(
        round_plan,
        [_step("phase_two_one", "coverage_gate", False, phase_2_report)],
    )
    worker_plan = tmp_path / "worker-shards.json"
    _write_worker_plan(
        worker_plan,
        ready_plan=ready_plan,
        round_plan=round_plan,
    )

    report = auditor.audit_worker_status(worker_plan)

    assert report["ready"] is False
    assert report["status_audit_ready"] is False
    assert report["all_shards_complete"] is False
    assert report["no_invalid_or_failed_shards"] is False
    assert report["no_rejected_or_mismatched_handoffs"] is False
    assert report["worker_shard_count"] == 4
    assert report["complete_shard_count"] == 1
    assert report["incomplete_shard_count"] == 3
    assert report["invalid_or_failed_shard_count"] == 1
    assert report["ready_for_phase_2"] is False
    assert report["ready_for_repin"] is False
    assert report["next_shard"]["phase"] == "phase_1_ready_excel_batch"
    assert report["next_shard"]["lane"] == "app_open"
    assert report["next_shard"]["first_step_name"] == "missing_one"
    assert report["excel_approval_required_for_next"] is True
    assert report["blocked_phase"]["name"] == "phase_2_after_ready_batch"
    assert report["lane_status_counts"]["app_open"] == {
        "complete": 1,
        "incomplete": 1,
    }
    assert report["handoff_status_counts"] == {
        "missing_complete_execute": 1,
        "not_ready": 2,
        "rejected_durable_report": 1,
    }
    assert report["accepted_handoff_shard_count"] == 0
    assert report["handoff_mismatch_count"] == 0
    assert report["rejected_handoff_shard_count"] == 1


def test_worker_status_markdown_includes_next_commands(tmp_path: Path) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    complete_report = tmp_path / "complete.json"
    complete_report.write_text("{}", encoding="utf-8")
    missing_report = tmp_path / "missing.json"
    _write_plan(
        ready_plan,
        [
            _step("complete_one", "app_open", True, complete_report),
            _step("missing_one", "app_open", True, missing_report),
            _step("failed_one", "render", True, tmp_path / "not-yet-run.json"),
        ],
    )
    _write_plan(
        round_plan,
        [_step("phase_two_one", "coverage_gate", False, tmp_path / "phase-2.json")],
    )
    worker_plan = tmp_path / "worker-shards.json"
    _write_worker_plan(
        worker_plan,
        ready_plan=ready_plan,
        round_plan=round_plan,
    )

    report = auditor.audit_worker_status(worker_plan)
    markdown = auditor.format_markdown_report(report)

    assert "# OOXML Evidence Worker Shard Status" in markdown
    assert "| Status audit ready | true |" in markdown
    assert "| All shards complete | false |" in markdown
    assert "| No invalid or failed shards | true |" in markdown
    assert "| Next shard needs Excel | true |" in markdown
    assert "## Next Runnable Shard" in markdown
    assert report["next_shard"]["lane"] == "render"
    assert report["next_shard"]["first_step_name"] == "failed_one"
    assert "Status report: `/tmp/failed_one-preflight.json`" in markdown
    assert "Status report: `/tmp/failed_one-execute.json`" in markdown
    assert "--name failed_one" in markdown
    assert "WOLFXL_ALLOW_EXCEL_FOCUS=1" in markdown


def test_worker_status_strict_audit_ready_allows_clean_incomplete_plan(
    tmp_path: Path,
) -> None:
    ready_plan = tmp_path / "ready.json"
    missing_report = tmp_path / "missing.json"
    _write_plan(
        ready_plan,
        [_step("missing_one", "app_open", True, missing_report)],
    )
    worker_plan = tmp_path / "worker-shards.json"
    payload = {
        "phases": [
            {
                "name": "phase_1_ready_excel_batch",
                "plan": str(ready_plan),
                "starts_after": [],
                "worker_groups": [
                    _group("app_open", True, [_shard(1, ["missing_one"], True)])
                ],
            }
        ],
    }
    worker_plan.write_text(json.dumps(payload), encoding="utf-8")

    report = auditor.audit_worker_status(worker_plan)
    code = auditor.main(
        ["--worker-plan", str(worker_plan), "--strict-audit-ready"]
    )

    assert report["status_audit_ready"] is True
    assert report["all_shards_complete"] is False
    assert code == 0


def test_worker_status_summarizes_preflight_and_execute_reports(
    tmp_path: Path,
) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    complete_report = tmp_path / "complete.json"
    complete_report.write_text("{}", encoding="utf-8")
    _write_plan(
        ready_plan,
        [_step("complete_one", "app_open", True, complete_report)],
    )
    _write_plan(round_plan, [])
    clean_preflight = tmp_path / "complete_one-preflight.json"
    complete_execute = tmp_path / "complete_one-execute.json"
    clean_preflight.write_text(
        json.dumps(
            {
                "dry_run": True,
                "execute": False,
                "selected_step_count": 1,
                "missing_command_count": 0,
                "invalid_durable_report_count": 0,
                "missing_durable_report_count": 1,
                "requires_explicit_excel_batch": True,
            }
        ),
        encoding="utf-8",
    )
    complete_execute.write_text(
        json.dumps(
            {
                "ready": True,
                "dry_run": False,
                "execute": True,
                "selected_step_count": 1,
                "missing_command_count": 0,
                "invalid_durable_report_count": 0,
                "failed_step_count": 0,
                "missing_durable_report_count": 0,
                "requires_explicit_excel_batch": True,
            }
        ),
        encoding="utf-8",
    )
    worker_plan = tmp_path / "worker-shards.json"
    payload = {
        "phases": [
            {
                "name": "phase_1_ready_excel_batch",
                "plan": str(ready_plan),
                "starts_after": [],
                "worker_groups": [
                    _group(
                        "app_open",
                        True,
                        [
                            _shard(
                                1,
                                ["complete_one"],
                                True,
                                preflight_status_report=clean_preflight,
                                execute_status_report=complete_execute,
                            )
                        ],
                    )
                ],
            }
        ],
    }
    worker_plan.write_text(json.dumps(payload), encoding="utf-8")

    report = auditor.audit_worker_status(worker_plan)
    markdown = auditor.format_markdown_report(report)

    assert report["clean_preflight_status_report_count"] == 1
    assert report["missing_preflight_status_report_count"] == 0
    assert report["complete_execute_status_report_count"] == 1
    assert report["missing_execute_status_report_count"] == 0
    assert report["accepted_handoff_shard_count"] == 1
    assert report["handoff_mismatch_count"] == 0
    assert report["handoff_status_counts"] == {"accepted": 1}
    assert report["ready"] is True
    assert report["status_audit_ready"] is True
    assert report["no_rejected_or_mismatched_handoffs"] is True
    shard = report["phases"][0]["worker_groups"][0]["shards"][0]
    assert shard["preflight_clean"] is True
    assert shard["execute_report_complete"] is True
    assert shard["handoff_status"] == "accepted"
    assert "| Clean preflight reports | 1 |" in markdown
    assert "| Execute | 1 | 0 | 0 |" in markdown
    assert "## Handoff Acceptance" in markdown
    assert "| accepted | 1 |" in markdown


def test_worker_status_flags_complete_execute_without_durable_reports(
    tmp_path: Path,
) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    missing_report = tmp_path / "missing.json"
    _write_plan(
        ready_plan,
        [_step("missing_one", "app_open", True, missing_report)],
    )
    _write_plan(round_plan, [])
    clean_preflight = tmp_path / "missing_one-preflight.json"
    complete_execute = tmp_path / "missing_one-execute.json"
    clean_preflight.write_text(
        json.dumps(
            {
                "dry_run": True,
                "execute": False,
                "selected_step_count": 1,
                "missing_command_count": 0,
                "invalid_durable_report_count": 0,
                "missing_durable_report_count": 1,
                "requires_explicit_excel_batch": True,
            }
        ),
        encoding="utf-8",
    )
    complete_execute.write_text(
        json.dumps(
            {
                "ready": True,
                "dry_run": False,
                "execute": True,
                "selected_step_count": 1,
                "missing_command_count": 0,
                "invalid_durable_report_count": 0,
                "failed_step_count": 0,
                "missing_durable_report_count": 0,
                "requires_explicit_excel_batch": True,
            }
        ),
        encoding="utf-8",
    )
    worker_plan = tmp_path / "worker-shards.json"
    payload = {
        "phases": [
            {
                "name": "phase_1_ready_excel_batch",
                "plan": str(ready_plan),
                "starts_after": [],
                "worker_groups": [
                    _group(
                        "app_open",
                        True,
                        [
                            _shard(
                                1,
                                ["missing_one"],
                                True,
                                preflight_status_report=clean_preflight,
                                execute_status_report=complete_execute,
                            )
                        ],
                    )
                ],
            }
        ],
    }
    worker_plan.write_text(json.dumps(payload), encoding="utf-8")

    report = auditor.audit_worker_status(worker_plan)
    markdown = auditor.format_markdown_report(report)

    assert report["complete_execute_status_report_count"] == 1
    assert report["complete_shard_count"] == 0
    assert report["handoff_mismatch_count"] == 1
    assert report["ready"] is False
    assert report["status_audit_ready"] is False
    assert report["no_invalid_or_failed_shards"] is True
    assert report["no_rejected_or_mismatched_handoffs"] is False
    assert report["handoff_status_counts"] == {
        "execute_complete_but_reports_incomplete": 1
    }
    shard = report["phases"][0]["worker_groups"][0]["shards"][0]
    assert shard["handoff_status"] == "execute_complete_but_reports_incomplete"
    assert "| Status audit ready | false |" in markdown
    assert "| No rejected or mismatched handoffs | false |" in markdown
    assert "| Handoff mismatches | 1 |" in markdown
    assert "| execute_complete_but_reports_incomplete | 1 |" in markdown
    assert (
        auditor.main(["--worker-plan", str(worker_plan), "--strict-audit-ready"])
        == 1
    )


def _write_plan(path: Path, steps: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"steps": steps}), encoding="utf-8")


def _write_worker_plan(
    path: Path,
    *,
    ready_plan: Path,
    round_plan: Path,
) -> None:
    payload = {
        "phases": [
            {
                "name": "phase_1_ready_excel_batch",
                "plan": str(ready_plan),
                "starts_after": [],
                "worker_groups": [
                    _group(
                        "app_open",
                        True,
                        [
                            _shard(1, ["complete_one"], True),
                            _shard(2, ["missing_one"], True),
                        ],
                    ),
                    _group("render", True, [_shard(1, ["failed_one"], True)]),
                ],
            },
            {
                "name": "phase_2_after_ready_batch",
                "plan": str(round_plan),
                "starts_after": ["phase_1_ready_excel_batch"],
                "worker_groups": [
                    _group(
                        "coverage_gate",
                        False,
                        [_shard(1, ["phase_two_one"], False)],
                    ),
                ],
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _group(
    lane: str,
    requires_excel: bool,
    shards: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "lane": lane,
        "requires_excel_focus": requires_excel,
        "shards": shards,
    }


def _shard(
    shard: int,
    step_names: list[str],
    requires_excel: bool,
    *,
    preflight_status_report: Path | str | None = None,
    execute_status_report: Path | str | None = None,
) -> dict[str, object]:
    first_step = step_names[0]
    return {
        "shard": shard,
        "step_names": step_names,
        "requires_excel_focus": requires_excel,
        "first_step_name": first_step,
        "last_step_name": step_names[-1],
        "preflight_command": f"uv run --no-sync python runner.py --name {first_step}",
        "execute_command": (
            f"WOLFXL_ALLOW_EXCEL_FOCUS=1 uv run --no-sync python runner.py "
            f"--name {first_step}"
            if requires_excel
            else f"uv run --no-sync python runner.py --name {first_step}"
        ),
        "preflight_status_report": str(
            preflight_status_report or f"/tmp/{first_step}-preflight.json"
        ),
        "execute_status_report": str(
            execute_status_report or f"/tmp/{first_step}-execute.json"
        ),
    }


def _step(
    name: str,
    lane: str,
    opens_excel: bool,
    durable_report_path: Path,
) -> dict[str, object]:
    return {
        "name": name,
        "lane": lane,
        "action": "defer_excel_batch" if opens_excel else "rerun_after_upstream_evidence",
        "opens_excel_or_render_oracle": opens_excel,
        "durable_report_path": str(durable_report_path),
        "durable_producer": "printf '{}\\n'",
    }
