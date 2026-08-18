from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def _load_module() -> ModuleType:
    script = ROOT / "scripts" / "audit_real_world_fidelity_plan_state.py"
    spec = importlib.util.spec_from_file_location(
        "audit_real_world_fidelity_plan_state",
        script,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_real_world_fidelity_plan_current_repo_matches_current_evidence() -> None:
    report = audit.audit_plan_state()

    assert report["ready"] is True
    assert report["issue_count"] == 0
    assert report["current_evidence"]["final_blocker_ready"] is False
    assert report["current_evidence"]["supported_scope_ready"] is True
    assert report["current_evidence"]["competitor_gate_ready"] is True
    assert report["current_evidence"]["sota_claim_ready"] is False
    assert report["current_evidence"]["actionable_headless_step_count"] == 0
    assert report["current_evidence"]["actionable_excel_step_count"] == 0
    assert report["current_evidence"]["bundle_ready"] is True
    assert report["current_evidence"]["bundle_issue_count"] == 0
    assert report["issues"] == []


def test_real_world_fidelity_plan_blocks_stale_phrase_before_history(
    tmp_path: Path,
) -> None:
    plan = tmp_path / "plan.md"
    original = (ROOT / "Plans" / "real-world-excel-fidelity-gap-discovery.md").read_text(
        encoding="utf-8"
    )
    plan.write_text(
        "## Current audited state\n"
        "Current run says `current_supported_claim_ready=false`.\n\n"
        + original,
        encoding="utf-8",
    )

    report = audit.audit_plan_state(plan_path=plan)

    assert report["ready"] is False
    assert any(
        issue["kind"] == "stale_phrase_outside_historical_section"
        for issue in report["issues"]
    )


def test_real_world_fidelity_plan_blocks_missing_current_bundle_count(
    tmp_path: Path,
) -> None:
    plan = tmp_path / "plan.md"
    original = (ROOT / "Plans" / "real-world-excel-fidelity-gap-discovery.md").read_text(
        encoding="utf-8"
    )
    plan.write_text(
        original.replace("summary in the same report has 597 reports", "summary has reports"),
        encoding="utf-8",
    )

    report = audit.audit_plan_state(plan_path=plan)

    assert report["ready"] is False
    assert any(
        issue["kind"] == "missing_current_state_phrase"
        for issue in report["issues"]
    )
