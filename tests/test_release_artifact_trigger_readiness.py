from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def _load_module() -> ModuleType:
    script = ROOT / "scripts" / "audit_release_artifact_trigger_readiness.py"
    spec = importlib.util.spec_from_file_location("audit_release_artifact_trigger_readiness", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_trigger_readiness_requires_push_when_workflow_missing_on_default(
    monkeypatch,
) -> None:
    monkeypatch.setattr(audit, "_run", _fake_run_missing_default_workflow)
    monkeypatch.setattr(
        audit.audit_release_artifact_proof_workflow,
        "audit_release_artifact_proof_workflow",
        lambda: {
            "ready": True,
            "branch_push_ready": True,
            "workflow_dispatch_ready": True,
            "initial_proof_branch": "codex/move-formula-shared-slicer-ui-evidence",
        },
    )

    report = audit.audit_release_artifact_trigger_readiness()

    assert report["ready"] is False
    assert report["workflow_on_default_branch"] is False
    assert report["upstream_branch"] == (
        "origin/codex/move-formula-shared-slicer-ui-evidence"
    )
    assert report["current_branch_pushed"] is False
    assert report["current_branch_has_unpushed_commits"] is True
    assert report["volatile_git_state_included"] is False
    assert "current_head_sha" not in report
    assert "local_ahead_commit_count" not in report
    assert report["branch_push_ready_now"] is False
    assert report["branch_push_requires_push"] is True
    assert report["manual_dispatch_ready_now"] is False
    assert report["trigger_mode"] == "push_required"


def test_trigger_readiness_accepts_manual_dispatch_when_workflow_exists_on_default(
    monkeypatch,
) -> None:
    monkeypatch.setattr(audit, "_run", _fake_run_default_workflow_exists)
    monkeypatch.setattr(
        audit.audit_release_artifact_proof_workflow,
        "audit_release_artifact_proof_workflow",
        lambda: {
            "ready": True,
            "branch_push_ready": False,
            "workflow_dispatch_ready": True,
            "initial_proof_branch": "codex/move-formula-shared-slicer-ui-evidence",
        },
    )

    report = audit.audit_release_artifact_trigger_readiness()

    assert report["ready"] is True
    assert report["workflow_on_default_branch"] is True
    assert report["volatile_git_state_included"] is False
    assert report["branch_push_ready_now"] is False
    assert report["branch_push_requires_push"] is False
    assert report["manual_dispatch_ready_now"] is True
    assert report["trigger_mode"] == "manual_dispatch"


def test_trigger_readiness_can_include_volatile_git_state(
    monkeypatch,
) -> None:
    monkeypatch.setattr(audit, "_run", _fake_run_missing_default_workflow)
    monkeypatch.setattr(
        audit.audit_release_artifact_proof_workflow,
        "audit_release_artifact_proof_workflow",
        lambda: {
            "ready": True,
            "branch_push_ready": True,
            "workflow_dispatch_ready": True,
            "initial_proof_branch": "codex/move-formula-shared-slicer-ui-evidence",
        },
    )

    report = audit.audit_release_artifact_trigger_readiness(
        include_volatile_git_state=True
    )

    assert report["volatile_git_state_included"] is True
    assert report["current_head_sha"] == "b" * 40
    assert report["upstream_head_sha"] == "a" * 40
    assert report["local_ahead_commit_count"] == 267
    assert report["upstream_ahead_commit_count"] == 0


def _fake_run_missing_default_workflow(
    *args: str,
) -> subprocess.CompletedProcess[str]:
    if args[:3] == ("git", "branch", "--show-current"):
        return _completed(args, stdout="codex/move-formula-shared-slicer-ui-evidence\n")
    if args[:2] == ("git", "rev-parse") and args[2:] == ("HEAD",):
        return _completed(args, stdout=("b" * 40) + "\n")
    if args[:2] == ("git", "rev-parse") and args[2:] == (
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
    ):
        return _completed(
            args,
            stdout="origin/codex/move-formula-shared-slicer-ui-evidence\n",
        )
    if args[:2] == ("git", "rev-parse") and args[2:] == ("@{u}",):
        return _completed(args, stdout=("a" * 40) + "\n")
    if args[:3] == ("git", "rev-list", "--left-right"):
        return _completed(args, stdout="0 267\n")
    if args[:4] == ("gh", "repo", "view", "--json"):
        return _completed(args, stdout=_repo_view_json())
    if args[:3] == ("gh", "api", f"repos/:owner/:repo/contents/{audit.WORKFLOW_PATH}"):
        return _completed(args, returncode=1, stderr="gh: Not Found (HTTP 404)\n")
    return _completed(args, returncode=1, stderr="unexpected command")


def _fake_run_default_workflow_exists(
    *args: str,
) -> subprocess.CompletedProcess[str]:
    if args[:3] == ("git", "branch", "--show-current"):
        return _completed(args, stdout="main\n")
    if args[:2] == ("git", "rev-parse") and args[2:] == ("HEAD",):
        return _completed(args, stdout=("c" * 40) + "\n")
    if args[:2] == ("git", "rev-parse") and args[2:] == (
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
    ):
        return _completed(args, stdout="origin/main\n")
    if args[:2] == ("git", "rev-parse") and args[2:] == ("@{u}",):
        return _completed(args, stdout=("c" * 40) + "\n")
    if args[:3] == ("git", "rev-list", "--left-right"):
        return _completed(args, stdout="0 0\n")
    if args[:4] == ("gh", "repo", "view", "--json"):
        return _completed(args, stdout=_repo_view_json())
    if args[:3] == ("gh", "api", f"repos/:owner/:repo/contents/{audit.WORKFLOW_PATH}"):
        return _completed(
            args,
            stdout=json.dumps(
                {
                    "path": audit.WORKFLOW_PATH,
                    "sha": "c" * 40,
                    "html_url": "https://github.com/SynthGL/wolfxl/blob/main/"
                    + audit.WORKFLOW_PATH,
                }
            ),
        )
    return _completed(args, returncode=1, stderr="unexpected command")


def _repo_view_json() -> str:
    return json.dumps(
        {
            "defaultBranchRef": {"name": "main"},
            "nameWithOwner": "SynthGL/wolfxl",
            "url": "https://github.com/SynthGL/wolfxl",
        }
    )


def _completed(
    args: tuple[str, ...],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)
