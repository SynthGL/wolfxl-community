from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def _load_module() -> ModuleType:
    script = ROOT / "scripts" / "audit_release_artifact_proof_workflow.py"
    spec = importlib.util.spec_from_file_location("audit_release_artifact_proof_workflow", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_manual_release_artifact_proof_workflow_targets_current_missing_lanes() -> None:
    report = audit.audit_release_artifact_proof_workflow()

    assert report["ready"] is True
    assert report["current_missing_lane_count"] == 0
    assert report["expected_lane_count"] == 26
    assert report["planned_lane_count"] == report["expected_lane_count"]
    assert report["current_actionable_lane_count"] == (
        report["current_missing_lane_count"] + report["current_stale_lane_count"]
    )
    assert report["current_actionable_lane_count"] <= report["expected_lane_count"]
    assert report["missing_not_planned"] == []
    assert report["planned_not_missing"] == []
    assert report["actionable_not_planned"] == []
    assert len(report["planned_not_actionable"]) == (
        report["expected_lane_count"] - report["current_actionable_lane_count"]
    )
    assert report["duplicate_lane_ids"] == []
    assert report["workflow_dispatch_ready"] is True
    assert report["branch_push_ready"] is True
    assert report["initial_proof_branch"] == "codex/move-formula-shared-slicer-ui-evidence"
    assert report["artifact_paths_ready"] is True
    assert report["runner_ready"] is True
    assert report["build_action_ready"] is True
    assert report["upload_artifact_ready"] is True
    assert report["job_mechanics_ready"] is True
    assert report["jobs_missing_build_action"] == []
    assert report["jobs_missing_smoke_step"] == []
    assert report["jobs_missing_wheel_glob"] == []
    assert report["jobs_missing_artifact_upload"] == []
    assert report["jobs_missing_artifact_paths"] == []
    assert report["jobs_missing_windows_longpaths"] == []
    assert report["jobs_missing_linux_manylinux_interpreter"] == []
    assert report["unsupported_runner_labels"] == []
    assert report["lane_runner_mismatches"] == []
    assert all(report["required_arg_presence"].values())
    if report["current_actionable_lane_count"]:
        assert "currently missing or stale release lanes" in report["claim_boundary"]
    else:
        assert "no currently missing registered release lanes" in report["claim_boundary"]
    assert {
        lane["runner"] for lane in report["planned_lanes"]
    } == {
        "ubuntu-latest",
        "ubuntu-24.04-arm",
        "macos-14",
        "macos-15-intel",
        "windows-2025",
    }


def test_workflow_audit_flags_missing_lane(tmp_path: Path, monkeypatch) -> None:
    workflow = tmp_path / "release-artifact-proof.yml"
    workflow.write_text(
        _workflow_text(
            (
                "release-artifact-wheel-smoke-linux-aarch64-cp39",
                "release-artifact-wheel-smoke-linux-aarch64-cp310",
            )
        ),
        encoding="utf-8",
    )

    def fake_coverage() -> dict[str, object]:
        return {
            "expected_lanes": [
                {"id": f"wheel:linux:aarch64:{abi}"}
                for abi in ("cp39", "cp310", "cp311")
            ],
            "missing_lanes": [
                {"id": f"wheel:linux:aarch64:{abi}"}
                for abi in ("cp39", "cp310", "cp311")
            ],
            "stale_proven_lanes": [],
        }

    monkeypatch.setattr(
        audit.audit_release_artifact_coverage,
        "audit_release_artifact_coverage",
        fake_coverage,
    )
    report = audit.audit_release_artifact_proof_workflow(proof_workflow=workflow)

    assert report["ready"] is False
    assert "wheel:linux:aarch64:cp311" in report["missing_not_planned"]


def test_workflow_audit_flags_missing_clean_report_metadata(tmp_path: Path) -> None:
    workflow = tmp_path / "release-artifact-proof.yml"
    workflow.write_text(
        _workflow_text(
            ("release-artifact-wheel-smoke-linux-aarch64-cp39",),
            include_report_repo_dirty=False,
        ),
        encoding="utf-8",
    )

    report = audit.audit_release_artifact_proof_workflow(proof_workflow=workflow)

    assert report["ready"] is False
    assert report["required_arg_presence"]["--report-repo-git-dirty false"] is False


def test_workflow_audit_flags_wrong_runner_for_lane(tmp_path: Path) -> None:
    workflow = tmp_path / "release-artifact-proof.yml"
    workflow.write_text(
        _workflow_text(("release-artifact-wheel-smoke-windows-x86_64-cp39",)),
        encoding="utf-8",
    )

    report = audit.audit_release_artifact_proof_workflow(proof_workflow=workflow)

    assert report["ready"] is False
    assert report["lane_runner_mismatches"] == [
        {
            "lane_id": "wheel:windows:x86_64:cp39",
            "runner": "ubuntu-24.04-arm",
            "expected_runner": "windows-2025",
            "report_stem": "release-artifact-wheel-smoke-windows-x86_64-cp39",
        }
    ]


def test_workflow_audit_flags_missing_wheel_glob(tmp_path: Path) -> None:
    workflow = tmp_path / "release-artifact-proof.yml"
    workflow.write_text(
        _workflow_text(
            ("release-artifact-wheel-smoke-linux-aarch64-cp39",),
            include_wheel_glob=False,
        ),
        encoding="utf-8",
    )

    report = audit.audit_release_artifact_proof_workflow(proof_workflow=workflow)

    assert report["ready"] is False
    assert report["required_arg_presence"]["--wheel-glob 'dist/wolfxl-*.whl'"] is False


def test_workflow_audit_flags_job_missing_upload_even_when_other_job_uploads(
    tmp_path: Path,
) -> None:
    workflow = tmp_path / "release-artifact-proof.yml"
    workflow.write_text(
        _workflow_text(("release-artifact-wheel-smoke-linux-aarch64-cp39",))
        + _workflow_text(
            ("release-artifact-wheel-smoke-macos-x86_64-cp310",),
            job="macos-x86-64",
            runner="macos-15-intel",
            include_upload=False,
            include_header=False,
        ),
        encoding="utf-8",
    )

    report = audit.audit_release_artifact_proof_workflow(proof_workflow=workflow)

    assert report["ready"] is False
    assert report["upload_artifact_ready"] is True
    assert report["jobs_missing_artifact_upload"] == ["macos-x86-64"]


def test_workflow_audit_flags_missing_windows_longpaths(tmp_path: Path) -> None:
    workflow = tmp_path / "release-artifact-proof.yml"
    workflow.write_text(
        _workflow_text(
            ("release-artifact-wheel-smoke-windows-x86_64-cp39",),
            job="windows-x86-64",
            runner="windows-2025",
            include_windows_longpaths=False,
        ),
        encoding="utf-8",
    )

    report = audit.audit_release_artifact_proof_workflow(proof_workflow=workflow)

    assert report["ready"] is False
    assert report["jobs_missing_windows_longpaths"] == ["windows-x86-64"]


def test_workflow_audit_flags_linux_manylinux_python_interpreter(
    tmp_path: Path,
) -> None:
    workflow = tmp_path / "release-artifact-proof.yml"
    workflow.write_text(
        _workflow_text(
            ("release-artifact-wheel-smoke-linux-aarch64-cp39",),
            include_linux_manylinux_interpreter=False,
        ),
        encoding="utf-8",
    )

    report = audit.audit_release_artifact_proof_workflow(proof_workflow=workflow)

    assert report["ready"] is False
    assert report["jobs_missing_linux_manylinux_interpreter"] == ["linux-aarch64"]


def _workflow_text(
    stems: tuple[str, ...],
    *,
    job: str = "linux-aarch64",
    runner: str = "ubuntu-24.04-arm",
    include_header: bool = True,
    include_branch_push: bool = True,
    include_report_repo_dirty: bool = True,
    include_wheel_glob: bool = True,
    include_upload: bool = True,
    include_windows_longpaths: bool = True,
    include_linux_manylinux_interpreter: bool = True,
) -> str:
    matrix_entries = "\n".join(
        f"""          - python-version: "3.9"
            abi: cp39
            report-stem: {stem}"""
        for stem in stems
    )
    report_repo_dirty_arg = (
        '            --report-repo-git-dirty false\n' if include_report_repo_dirty else ""
    )
    wheel_glob_arg = (
        "            --wheel-glob 'dist/wolfxl-*.whl' \\\n" if include_wheel_glob else ""
    )
    branch_push_trigger = (
        "  push:\n"
        "    branches:\n"
        "      - codex/move-formula-shared-slicer-ui-evidence\n"
        if include_branch_push
        else ""
    )
    header = (
        f"""
name: Release Artifact Proof

on:
  workflow_dispatch:
{branch_push_trigger}

jobs:
"""
        if include_header
        else ""
    )
    upload_step = "      - uses: actions/upload-artifact@v4\n" if include_upload else ""
    windows_longpaths_step = (
        "      - name: Enable long paths for checkout\n"
        "        run: git config --global core.longpaths true\n"
        if job.startswith("windows") and include_windows_longpaths
        else ""
    )
    linux_manylinux_options = (
        """        with:
          target: aarch64
          args: --release --out dist -i python${{ matrix.python-version }}
          manylinux: auto
"""
        if job == "linux-aarch64" and include_linux_manylinux_interpreter
        else ""
    )
    return f"""{header}  {job}:
    runs-on: {runner}
    strategy:
      matrix:
        include:
{matrix_entries}
    steps:
{windows_longpaths_step}\
      - uses: actions/checkout@v4
      - name: Build wheel
        uses: PyO3/maturin-action@v1
{linux_manylinux_options}\
{upload_step}\
      - name: Smoke installed wheel
        run: |
          python scripts/smoke_release_wheel_artifact.py \\
{wheel_glob_arg}\
            --output docs/trust/${{{{ matrix.report-stem }}}}.json \\
            --markdown-output docs/trust/${{{{ matrix.report-stem }}}}.md \\
            --source-git-sha "$GITHUB_SHA" \\
            --source-git-dirty false \\
            --report-repo-git-sha "$GITHUB_SHA" \\
{report_repo_dirty_arg}"""
