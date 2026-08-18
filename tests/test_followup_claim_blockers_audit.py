from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_followup_claim_blockers.py"
    spec = importlib.util.spec_from_file_location("audit_followup_claim_blockers", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_followup_claim_blockers_current_repo_is_ready() -> None:
    report = audit.audit_followup_claim_blockers()

    assert report["ready"] is True
    assert report["open_claim_blocker_count"] == 0


def test_followup_claim_blockers_flags_open_claim_blocker(tmp_path: Path) -> None:
    followups = tmp_path / "followups"
    followups.mkdir()
    report_path = tmp_path / "docs" / "trust" / "report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps({"ready": True, "failure_count": 0}) + "\n",
        encoding="utf-8",
    )
    (followups / "open.md").write_text(
        "## Status\n\n"
        "Open. This blocks a clean render-equivalence claim.\n\n"
        f"- Evidence: `{report_path}`\n",
        encoding="utf-8",
    )

    result = audit.audit_followup_claim_blockers(followups)

    assert result["ready"] is False
    assert result["open_claim_blocker_count"] == 1
    assert result["issues"][0]["reason"] == (
        "follow-up note still appears open and claim-blocking"
    )


def test_followup_claim_blockers_allows_closed_history(tmp_path: Path) -> None:
    followups = tmp_path / "followups"
    followups.mkdir()
    (followups / "closed.md").write_text(
        "## Status\n\n"
        "Closed 2026-06-02. This previously blocked a clean render-equivalence claim.\n",
        encoding="utf-8",
    )

    result = audit.audit_followup_claim_blockers(followups)
    markdown = audit.format_markdown(result)

    assert result["ready"] is True
    assert result["followup_count"] == 1
    assert "| Open claim blocker notes | 0 |" in markdown
