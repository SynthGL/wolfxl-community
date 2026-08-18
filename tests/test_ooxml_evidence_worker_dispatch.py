from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "plan_ooxml_evidence_worker_dispatch.py"
    spec = importlib.util.spec_from_file_location(
        "plan_ooxml_evidence_worker_dispatch", script
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dispatcher = _load_module()


def test_dispatch_board_prioritizes_runnable_excel_shards(tmp_path: Path) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    _write_plan(
        ready_plan,
        [
            _step("render_one", "render", True, tmp_path / "render-one.json"),
            _step("app_one", "app_open", True, tmp_path / "app-one.json"),
            _step("manual_one", "excel_gui_manual", True, tmp_path / "manual-one.json"),
        ],
    )
    _write_plan(
        round_plan,
        [_step("coverage_one", "coverage_gate", False, tmp_path / "coverage-one.json")],
    )
    worker_plan = tmp_path / "worker-shards.json"
    _write_worker_plan(worker_plan, ready_plan=ready_plan, round_plan=round_plan)

    report = dispatcher.build_dispatch_board(worker_plan, max_first_wave=2)

    assert report["status_audit_ready"] is True
    assert report["all_shards_complete"] is False
    assert report["no_invalid_or_failed_shards"] is True
    assert report["runnable_shard_count"] == 2
    assert report["waiting_shard_count"] == 1
    assert report["supervised_shard_count"] == 1
    assert report["clean_preflight_status_report_count"] == 0
    assert report["missing_preflight_status_report_count"] == 4
    assert report["complete_execute_status_report_count"] == 0
    assert report["missing_execute_status_report_count"] == 4
    assert report["first_wave_packet_count"] == 2
    assert report["first_wave_packets"][0]["filename"].endswith(
        "phase-1-ready-excel-batch-render-shard-001.md"
    )
    assert report["first_wave_requires_excel_approval"] is True
    assert report["local_desktop_safe_to_execute_first_wave"] is False
    unattended = report["execution_groups"]["unattended_off_desktop_excel"]
    assert unattended["can_run_now"] is True
    assert unattended["worker_kind"] == "Off-desktop Excel worker or VM"
    assert unattended["where_to_run"] == "approved off-desktop Excel machine only"
    assert unattended["shard_count"] == 2
    assert unattended["expected_report_count"] == 2
    assert unattended["requires_excel_approval"] is True
    assert unattended["local_desktop_safe"] is False
    assert unattended["clean_preflight_count"] == 0
    assert unattended["missing_execute_count"] == 2
    assert unattended["suggested_wave_count"] == 1
    assert len(unattended["first_shards"]) == 2
    watched = report["execution_groups"]["watched_off_desktop_excel"]
    assert watched["shard_count"] == 0
    assert report["execution_groups"]["supervised_excel"]["shard_count"] == 1
    future_headless = report["execution_groups"]["future_headless_after_phase_1"]
    assert future_headless["local_desktop_safe"] is True
    assert future_headless["can_run_now"] is False
    assert (
        future_headless["where_to_run"]
        == "headless worker after dependencies are complete"
    )
    checklist = report["assignment_checklist"]
    assert len(checklist) == 3
    assert checklist[0] == {
        "claim_status": "unassigned",
        "assigned_to": "",
        "result": "",
        "group": "unattended_off_desktop_excel",
        "phase": "phase_1_ready_excel_batch",
        "lane": "render",
        "shard": 1,
        "step_count": 1,
        "where_to_run": "approved off-desktop Excel machine only",
        "packet_set": "phase_1_excel_batch_parallel",
        "packet_path": (
            "worker-packets/phase-1-excel-batch-parallel/"
            "phase-1-ready-excel-batch-render-shard-001.md"
        ),
        "preflight_status": "missing",
        "execute_status": "missing",
        "handoff_status": "not_ready",
        "preflight_status_report": "/tmp/render_one-preflight.json",
        "execute_status_report": "/tmp/render_one-execute.json",
        "first_step_name": "render_one",
    }
    assert report["packet_sets"]["first_wave"]["shard_count"] == 2
    assert report["packet_sets"]["first_wave"]["requires_excel_approval"] is True
    assert report["packet_sets"]["phase_1_excel_batch_parallel"]["shard_count"] == 2
    assert (
        report["packet_sets"]["phase_1_excel_batch_parallel"][
            "requires_excel_approval"
        ]
        is True
    )
    assert report["packet_sets"]["phase_1_excel_batch_supervised"]["shard_count"] == 1
    assert (
        report["packet_sets"]["phase_1_excel_batch_supervised"][
            "requires_excel_approval"
        ]
        is True
    )
    assert (
        report["packet_sets"]["phase_2_after_ready_headless"]["shard_count"]
        == 1
    )
    assert (
        report["packet_sets"]["phase_2_after_ready_headless"][
            "requires_excel_approval"
        ]
        is False
    )
    phase_2_packet = report["packet_sets"]["phase_2_after_ready_headless"]["packets"][0]
    assert phase_2_packet["assignment_mode"] == "headless_after_dependencies"
    assert [shard["lane"] for shard in report["first_wave"]] == [
        "render",
        "app_open",
    ]
    assert report["blocked_phase"]["name"] == "phase_2_after_ready_batch"


def test_dispatch_markdown_includes_commands_and_handoff(tmp_path: Path) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    _write_plan(
        ready_plan,
        [
            _step("render_one", "render", True, tmp_path / "render-one.json"),
            _step("app_one", "app_open", True, tmp_path / "app-one.json"),
            _step("manual_one", "excel_gui_manual", True, tmp_path / "manual-one.json"),
        ],
    )
    _write_plan(
        round_plan,
        [_step("coverage_one", "coverage_gate", False, tmp_path / "coverage-one.json")],
    )
    worker_plan = tmp_path / "worker-shards.json"
    _write_worker_plan(worker_plan, ready_plan=ready_plan, round_plan=round_plan)

    report = dispatcher.build_dispatch_board(worker_plan, max_first_wave=1)
    markdown = dispatcher.format_markdown_report(report)

    assert "# OOXML Evidence Worker Dispatch Board" in markdown
    assert "| Status audit ready | true |" in markdown
    assert "| All shards complete | false |" in markdown
    assert "| No invalid or failed shards | true |" in markdown
    assert "| First wave needs Excel approval | true |" in markdown
    assert "| Missing preflight reports | 4 |" in markdown
    assert "| Missing execute reports | 4 |" in markdown
    assert "## Packet Sets" in markdown
    assert "## Parallel Execution Plan" in markdown
    assert (
        "| unattended_off_desktop_excel | Off-desktop Excel worker or VM | "
        "approved off-desktop Excel machine only | true | 2 | 2 | 2 | true | false |"
    ) in markdown
    assert (
        "| supervised_excel | Manual or closely supervised Excel worker | "
        "approved off-desktop Excel machine only | true | 1 | 1 | 1 | true | false |"
    ) in markdown
    assert (
        "| future_headless_after_phase_1 | Headless/package-level worker after "
        "phase 1 durable reports exist | headless worker after dependencies are "
        "complete | false | 1 | 1 | 1 | false | true |"
    ) in markdown
    assert "## Worker Assignment Checklist" in markdown
    assert (
        "| unassigned | unattended_off_desktop_excel | "
        "phase_1_ready_excel_batch / render / 1 | 1 | "
        "approved off-desktop Excel machine only | "
        "worker-packets/phase-1-excel-batch-parallel/"
        "phase-1-ready-excel-batch-render-shard-001.md | missing | missing | "
        "not_ready |"
    ) in markdown
    assert "| phase_1_excel_batch_parallel | All runnable phase 1" in markdown
    assert "| phase_1_excel_batch_supervised | Phase 1 Excel shards" in markdown
    assert "| phase_2_after_ready_headless | Future headless fan-out" in markdown
    assert "### phase_1_ready_excel_batch / render / shard 1" in markdown
    assert "Status report: `/tmp/render_one-preflight.json`" in markdown
    assert "Status: `missing`" in markdown
    assert "Status report: `/tmp/render_one-execute.json`" in markdown
    assert "--name render_one" in markdown
    assert "## Handoff Template" in markdown


def test_dispatch_writes_first_wave_worker_packets(tmp_path: Path) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    _write_plan(
        ready_plan,
        [
            _step("render_one", "render", True, tmp_path / "render-one.json"),
            _step("app_one", "app_open", True, tmp_path / "app-one.json"),
        ],
    )
    _write_plan(
        round_plan,
        [_step("coverage_one", "coverage_gate", False, tmp_path / "coverage-one.json")],
    )
    worker_plan = tmp_path / "worker-shards.json"
    _write_worker_plan(worker_plan, ready_plan=ready_plan, round_plan=round_plan)

    report = dispatcher.build_dispatch_board(worker_plan, max_first_wave=1)
    paths = dispatcher.write_worker_packets(report, tmp_path / "packets")

    assert [path.name for path in paths] == [
        "phase-1-ready-excel-batch-render-shard-001.md"
    ]
    packet = paths[0].read_text(encoding="utf-8")
    assert "# OOXML Evidence Worker Packet:" in packet
    assert "Run the preflight command first" in packet
    assert "Supervision note: safe for unattended off-desktop Excel workers" in packet
    assert "| Preflight status | missing |" in packet
    assert "| Execute status | missing |" in packet
    assert "## Expected Durable Reports" in packet
    assert "| render_one | missing |" in packet
    assert "Status report: `/tmp/render_one-preflight.json`" in packet
    assert "Current status: `missing`" in packet
    assert "Status report: `/tmp/render_one-execute.json`" in packet
    assert "Result: complete | failed | partial" in packet
    assert "## Coordinator Acceptance Check" in packet
    assert (
        "scripts/audit_ooxml_evidence_worker_status.py --strict-audit-ready"
        in packet
    )


def test_dispatch_writes_named_worker_packet_sets(tmp_path: Path) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    _write_plan(
        ready_plan,
        [_step("render_one", "render", True, tmp_path / "render-one.json")],
    )
    _write_plan(
        round_plan,
        [_step("coverage_one", "coverage_gate", False, tmp_path / "coverage-one.json")],
    )
    worker_plan = tmp_path / "worker-shards.json"
    _write_worker_plan(worker_plan, ready_plan=ready_plan, round_plan=round_plan)

    report = dispatcher.build_dispatch_board(worker_plan, max_first_wave=1)
    paths = dispatcher.write_worker_packet_sets(report, tmp_path / "packet-root")

    relative_paths = sorted(path.relative_to(tmp_path / "packet-root") for path in paths)
    assert relative_paths == [
        Path("first-wave/phase-1-ready-excel-batch-render-shard-001.md"),
        Path(
            "phase-1-excel-batch-parallel/"
            "phase-1-ready-excel-batch-app-open-shard-001.md"
        ),
        Path(
            "phase-1-excel-batch-parallel/"
            "phase-1-ready-excel-batch-render-shard-001.md"
        ),
        Path(
            "phase-1-excel-batch-supervised/"
            "phase-1-ready-excel-batch-excel-gui-manual-shard-001.md"
        ),
        Path(
            "phase-2-after-ready-headless/"
            "phase-2-after-ready-batch-coverage-gate-shard-001.md"
        ),
    ]
    headless_packet = (
        tmp_path
        / "packet-root"
        / "phase-2-after-ready-headless"
        / "phase-2-after-ready-batch-coverage-gate-shard-001.md"
    ).read_text(encoding="utf-8")
    assert "this shard should not open Excel" in headless_packet
    assert "Supervision note: headless once phase dependencies are complete" in headless_packet
    assert "WOLFXL_ALLOW_EXCEL_FOCUS=1" not in headless_packet
    supervised_packet = (
        tmp_path
        / "packet-root"
        / "phase-1-excel-batch-supervised"
        / "phase-1-ready-excel-batch-excel-gui-manual-shard-001.md"
    ).read_text(encoding="utf-8")
    assert "Supervision note: do not assign to unattended workers" in supervised_packet


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
                    _group("app_open", True, [_shard(1, ["app_one"], True)]),
                    _group("render", True, [_shard(1, ["render_one"], True)]),
                    _group(
                        "excel_gui_manual",
                        True,
                        [_shard(1, ["manual_one"], True)],
                    ),
                ],
            },
            {
                "name": "phase_2_after_ready_batch",
                "plan": str(round_plan),
                "starts_after": ["phase_1_ready_excel_batch"],
                "worker_groups": [
                    _group("coverage_gate", False, [_shard(1, ["coverage_one"], False)]),
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
) -> dict[str, object]:
    first_step = step_names[0]
    execute_command = f"uv run --no-sync python runner.py --name {first_step}"
    if requires_excel:
        execute_command = f"WOLFXL_ALLOW_EXCEL_FOCUS=1 {execute_command}"
    return {
        "shard": shard,
        "step_names": step_names,
        "requires_excel_focus": requires_excel,
        "first_step_name": first_step,
        "last_step_name": step_names[-1],
        "preflight_command": f"uv run --no-sync python runner.py --name {first_step}",
        "execute_command": execute_command,
        "preflight_status_report": f"/tmp/{first_step}-preflight.json",
        "execute_status_report": f"/tmp/{first_step}-execute.json",
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
