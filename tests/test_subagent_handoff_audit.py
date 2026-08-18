from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_subagent_handoffs.py"
    spec = importlib.util.spec_from_file_location("audit_subagent_handoffs", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_subagent_handoff_audit_accepts_complete_durable_reports(tmp_path: Path) -> None:
    json_report, md_report = _write_complete_handoff(tmp_path)
    report = audit.audit_handoffs(
        [
            audit.HandoffSpec(
                "worker_ok",
                "accepted",
                json_report,
                md_report,
            )
        ]
    )

    assert report["ready"] is True
    assert report["accepted_count"] == 1
    assert report["rejected_count"] == 0
    assert report["handoffs"][0]["accepted"] is True
    assert report["handoffs"][0]["issues"] == []


def test_subagent_handoff_audit_rejects_missing_durable_reports(tmp_path: Path) -> None:
    report = audit.audit_handoffs(
        [
            audit.HandoffSpec(
                "worker_missing",
                "accepted",
                tmp_path / "missing.json",
                tmp_path / "missing.md",
            )
        ]
    )

    assert report["ready"] is False
    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 1
    assert report["unexpected_rejection"] == ["worker_missing"]
    assert report["handoffs"][0]["issues"] == [
        "missing JSON status report",
        "missing Markdown status report",
    ]


def test_subagent_handoff_audit_rejects_unresolved_failures(tmp_path: Path) -> None:
    json_report, md_report = _write_complete_handoff(
        tmp_path,
        failures=[{"command": "example", "summary": "failed without retry"}],
    )
    report = audit.audit_handoffs(
        [audit.HandoffSpec("worker_failed", "accepted", json_report, md_report)]
    )

    assert report["ready"] is False
    assert report["accepted_count"] == 0
    assert report["unexpected_rejection"] == ["worker_failed"]
    assert "failure 1 is not marked non-blocking or resolved" in report["handoffs"][0]["issues"]


def test_subagent_handoff_audit_accepts_completed_with_findings_and_resolution(
    tmp_path: Path,
) -> None:
    json_report, md_report = _write_complete_handoff(
        tmp_path,
        failures=[
            {
                "command": "curl https://example.invalid",
                "reason": "initial request failed",
                "resolution": "retried with a different endpoint and succeeded",
            }
        ],
        status="completed_with_findings",
    )
    report = audit.audit_handoffs(
        [audit.HandoffSpec("worker_findings", "accepted", json_report, md_report)]
    )

    assert report["ready"] is True
    assert report["handoffs"][0]["accepted"] is True
    assert report["handoffs"][0]["issues"] == []


def test_subagent_handoff_audit_can_expect_rejected_missing_reports(tmp_path: Path) -> None:
    report = audit.audit_handoffs(
        [
            audit.HandoffSpec(
                "worker_missing",
                "rejected",
                tmp_path / "missing.json",
                tmp_path / "missing.md",
            )
        ]
    )

    assert report["ready"] is True
    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 1
    assert report["unexpected_rejection"] == []


def test_subagent_handoff_audit_markdown_summary(tmp_path: Path) -> None:
    json_report, md_report = _write_complete_handoff(tmp_path)
    report = audit.audit_handoffs(
        [audit.HandoffSpec("worker_ok", "accepted", json_report, md_report)]
    )

    markdown = audit.format_markdown(report)

    assert "# Subagent Handoff Audit" in markdown
    assert "| Ready | true |" in markdown
    assert "| worker_ok | accepted | true |" in markdown


def _write_complete_handoff(
    tmp_path: Path,
    *,
    failures: list[dict[str, str]] | None = None,
    status: str = "complete",
) -> tuple[Path, Path]:
    json_report = tmp_path / "worker.json"
    md_report = tmp_path / "worker.md"
    md_report.write_text("# Worker\n", encoding="utf-8")
    json_report.write_text(
        json.dumps(
            {
                "assigned_shard": "example shard",
                "machine": "example.local",
                "git_sha": "abc123",
                "status": status,
                "status_report_paths": [
                    str(json_report),
                    str(md_report),
                ],
                "commands_run": [{"command": "hostname", "result": "success"}],
                "durable_reports_created": [
                    str(json_report),
                    str(md_report),
                ],
                "failures": failures or [],
                "findings": [],
                "notes": ["example completed handoff"],
            }
        ),
        encoding="utf-8",
    )
    return json_report, md_report
