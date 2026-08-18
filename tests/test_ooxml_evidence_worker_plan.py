from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "plan_ooxml_evidence_workers.py"
    spec = importlib.util.spec_from_file_location("plan_ooxml_evidence_workers", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


planner = _load_module()


def test_worker_plan_groups_steps_by_phase_lane_and_name_shards(tmp_path: Path) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    _write_plan(
        ready_plan,
        [
            _step("render_one", "render", True, tmp_path / "render-one.json"),
            _step("render_two", "render", True, tmp_path / "render-two.json"),
            _step("app_open_one", "app_open", True, tmp_path / "app-open-one.json"),
        ],
    )
    _write_plan(
        round_plan,
        [
            _step("coverage_one", "coverage_gate", False, tmp_path / "coverage-one.json"),
            _step("render_three", "render", True, tmp_path / "render-three.json"),
        ],
    )

    report = planner.plan_worker_batches(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        status_report_root=tmp_path / "worker-status-reports",
        chunk_size=1,
    )

    assert report["worker_shard_count"] == 5
    assert report["excel_risk_shard_count"] == 4
    assert report["headless_shard_count"] == 1
    assert report["status_report_root"].endswith("worker-status-reports")
    ready_render = report["phases"][0]["worker_groups"][1]
    assert ready_render["lane"] == "render"
    assert ready_render["shard_count"] == 2
    assert "--name render_one" in ready_render["shards"][0]["execute_command"]
    assert "--start-at" not in ready_render["shards"][0]["execute_command"]
    assert ready_render["shards"][0]["execute_command"].startswith(
        "WOLFXL_ALLOW_EXCEL_FOCUS=1 "
    )
    assert ready_render["shards"][0]["preflight_status_report"].endswith(
        "-preflight-status.json"
    )
    assert ready_render["shards"][0]["execute_status_report"].endswith(
        "-execute-status.json"
    )
    assert (
        ready_render["shards"][0]["preflight_status_report"]
        != ready_render["shards"][0]["execute_status_report"]
    )
    assert ready_render["shards"][0]["preflight_status_report"] in ready_render[
        "shards"
    ][0]["preflight_command"]
    assert ready_render["shards"][0]["execute_status_report"] in ready_render[
        "shards"
    ][0]["execute_command"]
    round_coverage = report["phases"][1]["worker_groups"][0]
    assert round_coverage["lane"] == "coverage_gate"
    assert "WOLFXL_ALLOW_EXCEL_FOCUS=1" not in round_coverage["shards"][0][
        "execute_command"
    ]
    assert "--allow-excel-focus" not in round_coverage["shards"][0]["execute_command"]


def test_worker_plan_markdown_includes_first_shard_commands(tmp_path: Path) -> None:
    ready_plan = tmp_path / "ready.json"
    round_plan = tmp_path / "round.json"
    _write_plan(
        ready_plan,
        [_step("render_one", "render", True, tmp_path / "render-one.json")],
    )
    _write_plan(round_plan, [])

    report = planner.plan_worker_batches(
        ready_plan=ready_plan,
        round_1_plan=round_plan,
        status_report_root=tmp_path / "worker-status-reports",
        chunk_size=5,
    )

    markdown = planner.format_markdown_report(report)

    assert "# OOXML Evidence Worker Plan" in markdown
    assert "| render | 1 | 1 | true |" in markdown
    assert "WOLFXL_ALLOW_EXCEL_FOCUS=1" in markdown
    assert "--name render_one" in markdown


def _write_plan(path: Path, steps: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"steps": steps}), encoding="utf-8")


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
