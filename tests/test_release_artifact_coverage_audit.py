from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_release_artifact_coverage.py"
    spec = importlib.util.spec_from_file_location("audit_release_artifact_coverage", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_current_release_workflow_has_expected_lane_count() -> None:
    report = audit.audit_release_artifact_coverage()

    assert report["audit_ready"] is True
    assert report["coverage_ready"] is True
    assert report["expected_lane_count"] == 26
    assert report["proven_lane_count"] == 26
    assert report["missing_lane_count"] == 0
    assert "future workflow lanes" in report["claim_boundary"]
    assert "listed as missing" not in report["claim_boundary"]
    proven_lane_ids = {lane["id"] for lane in report["proven_lanes"]}
    assert {
        "wheel:linux:x86_64:cp39",
        "wheel:linux:x86_64:cp310",
        "wheel:linux:x86_64:cp311",
        "wheel:linux:x86_64:cp312",
        "wheel:linux:x86_64:cp313",
        "wheel:macos:x86_64:cp39",
        "wheel:macos:aarch64:cp39",
        "wheel:macos:aarch64:cp310",
        "wheel:macos:aarch64:cp311",
        "wheel:macos:aarch64:cp312",
        "wheel:macos:aarch64:cp313",
        "wheel:windows:x86_64:cp39",
        "wheel:windows:x86_64:cp310",
        "wheel:windows:x86_64:cp311",
        "wheel:windows:x86_64:cp312",
        "wheel:windows:x86_64:cp313",
        "wheel:linux:aarch64:cp39",
        "wheel:linux:aarch64:cp310",
        "wheel:linux:aarch64:cp311",
        "wheel:linux:aarch64:cp312",
        "wheel:linux:aarch64:cp313",
        "wheel:macos:x86_64:cp310",
        "wheel:macos:x86_64:cp311",
        "wheel:macos:x86_64:cp312",
        "wheel:macos:x86_64:cp313",
    }.issubset(proven_lane_ids)
    assert "sdist:source" in proven_lane_ids
    assert "sdist:source" not in {lane["id"] for lane in report["missing_lanes"]}


def test_all_expected_lanes_ready_when_proofs_cover_matrix(tmp_path: Path) -> None:
    workflow = tmp_path / "release.yml"
    workflow.write_text(_workflow_fixture(), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"wolfxl\"\nversion = \"2.0.0\"\nrequires-python = \">=3.9\"\n",
        encoding="utf-8",
    )
    reports = []
    for tag in (
        "cp39-cp39-manylinux_2_28_x86_64",
        "cp39-cp39-macosx_11_0_arm64",
        "cp39-cp39-win_amd64",
    ):
        path = tmp_path / f"{tag}.json"
        path.write_text(
            json.dumps(
                {
                    "ready": True,
                    "source_git_dirty": False,
                    "report_repo_git_dirty": False,
                    "wheel": {
                        "metadata_version": "2.0.0",
                        "wheel_tag": tag,
                    },
                }
            ),
            encoding="utf-8",
        )
        reports.append(path)

    report = audit.audit_release_artifact_coverage(
        release_workflow=workflow,
        pyproject=pyproject,
        release_artifact_reports=tuple(reports),
    )

    assert report["coverage_ready"] is False
    assert report["ready"] is False
    assert report["expected_lane_count"] == 4
    assert report["proven_lane_count"] == 3
    assert report["missing_lanes"] == [
        {
            "abi": "source",
            "arch": "source",
            "artifact_type": "sdist",
            "id": "sdist:source",
            "os": "source",
            "python": "source",
            "source": "sdist job",
        }
    ]


def test_currentness_tracks_lanes_not_proven_at_head(tmp_path: Path, monkeypatch) -> None:
    workflow = tmp_path / "release.yml"
    workflow.write_text(_workflow_fixture(), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"wolfxl\"\nversion = \"2.0.0\"\nrequires-python = \">=3.9\"\n",
        encoding="utf-8",
    )
    current_sha = "a" * 40
    old_sha = "b" * 40
    monkeypatch.setattr(audit, "_current_git_head", lambda: current_sha)
    monkeypatch.setattr(audit, "_current_release_relevant_source_sha", lambda: current_sha)
    reports = [
        _write_wheel_report(tmp_path, "linux.json", "cp39-cp39-manylinux_2_28_x86_64", current_sha),
        _write_wheel_report(tmp_path, "macos.json", "cp39-cp39-macosx_11_0_arm64", old_sha),
        _write_wheel_report(tmp_path, "windows.json", "cp39-cp39-win_amd64", current_sha),
        _write_sdist_report(tmp_path, "sdist.json", current_sha),
    ]

    report = audit.audit_release_artifact_coverage(
        release_workflow=workflow,
        pyproject=pyproject,
        release_artifact_reports=tuple(reports),
    )

    assert report["coverage_ready"] is True
    assert report["ready"] is False
    assert report["currentness_ready"] is False
    assert report["current_head_proven_lane_count"] == 3
    assert report["stale_proven_lane_count"] == 1
    assert report["stale_proven_lanes"] == [
        {
            "abi": "cp39",
            "arch": "aarch64",
            "artifact_type": "wheel",
            "id": "wheel:macos:aarch64:cp39",
            "os": "macos",
            "python": "3.9",
            "source": "macos matrix",
        }
    ]


def test_currentness_allows_report_only_commits(tmp_path: Path, monkeypatch) -> None:
    workflow = tmp_path / "release.yml"
    workflow.write_text(_workflow_fixture(), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"wolfxl\"\nversion = \"2.0.0\"\nrequires-python = \">=3.9\"\n",
        encoding="utf-8",
    )
    current_sha = "a" * 40
    report_head_sha = "c" * 40
    proof_sha = "b" * 40
    monkeypatch.setattr(audit, "_current_git_head", lambda: report_head_sha)
    monkeypatch.setattr(audit, "_current_release_relevant_source_sha", lambda: current_sha)
    monkeypatch.setattr(
        audit,
        "_release_artifact_relevant_changed_paths",
        lambda base_sha, head_sha: [],
    )
    monkeypatch.setattr(audit, "_current_release_artifact_relevant_dirty_paths", lambda: [])
    monkeypatch.setattr(audit, "_current_release_artifact_content_dirty_paths", lambda paths: [])
    reports = [
        _write_wheel_report(tmp_path, "linux.json", "cp39-cp39-manylinux_2_28_x86_64", proof_sha),
        _write_wheel_report(tmp_path, "macos.json", "cp39-cp39-macosx_11_0_arm64", proof_sha),
        _write_wheel_report(tmp_path, "windows.json", "cp39-cp39-win_amd64", proof_sha),
        _write_sdist_report(tmp_path, "sdist.json", proof_sha),
    ]

    report = audit.audit_release_artifact_coverage(
        release_workflow=workflow,
        pyproject=pyproject,
        release_artifact_reports=tuple(reports),
    )

    assert report["coverage_ready"] is True
    assert report["ready"] is True
    assert report["currentness_ready"] is True
    assert report["current_repo_head_sha"] == report_head_sha
    assert report["current_report_head_sha"] == report_head_sha
    assert report["current_release_relevant_source_sha"] == current_sha
    assert report["current_head_sha"] == current_sha
    assert report["current_head_sha_kind"] == "release_relevant_source_legacy_alias"
    assert "Legacy compatibility field" in report["current_head_sha_note"]
    assert report["current_head_proven_lane_count"] == 4
    assert report["stale_proven_lane_count"] == 0
    assert report["stale_proven_lanes"] == []
    markdown = audit.format_markdown(report)
    assert f"| Current repo HEAD SHA | `{report_head_sha}` |" in markdown
    assert f"| Current release-relevant source SHA | `{current_sha}` |" in markdown


def test_currentness_blocks_release_relevant_dirty_content(
    tmp_path: Path, monkeypatch
) -> None:
    workflow = tmp_path / "release.yml"
    workflow.write_text(_workflow_fixture(), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"wolfxl\"\nversion = \"2.0.0\"\nrequires-python = \">=3.9\"\n",
        encoding="utf-8",
    )
    current_sha = "a" * 40
    monkeypatch.setattr(audit, "_current_git_head", lambda: current_sha)
    monkeypatch.setattr(audit, "_current_release_relevant_source_sha", lambda: current_sha)
    monkeypatch.setattr(
        audit,
        "_current_release_artifact_relevant_dirty_paths",
        lambda: ["crates/wolfxl-writer/src/lib.rs"],
    )
    monkeypatch.setattr(
        audit,
        "_current_release_artifact_content_dirty_paths",
        lambda paths: list(paths),
    )
    reports = [
        _write_wheel_report(tmp_path, "linux.json", "cp39-cp39-manylinux_2_28_x86_64", current_sha),
        _write_wheel_report(tmp_path, "macos.json", "cp39-cp39-macosx_11_0_arm64", current_sha),
        _write_wheel_report(tmp_path, "windows.json", "cp39-cp39-win_amd64", current_sha),
        _write_sdist_report(tmp_path, "sdist.json", current_sha),
    ]

    report = audit.audit_release_artifact_coverage(
        release_workflow=workflow,
        pyproject=pyproject,
        release_artifact_reports=tuple(reports),
    )

    assert report["coverage_ready"] is True
    assert report["ready"] is False
    assert report["currentness_ready"] is False
    assert report["current_worktree_release_currentness_ready"] is False
    assert report["current_worktree_release_relevant_dirty_paths"] == [
        "crates/wolfxl-writer/src/lib.rs"
    ]
    assert report["current_worktree_release_relevant_content_dirty_paths"] == [
        "crates/wolfxl-writer/src/lib.rs"
    ]


def test_currentness_allows_whitespace_only_dirty_release_path(
    tmp_path: Path, monkeypatch
) -> None:
    workflow = tmp_path / "release.yml"
    workflow.write_text(_workflow_fixture(), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"wolfxl\"\nversion = \"2.0.0\"\nrequires-python = \">=3.9\"\n",
        encoding="utf-8",
    )
    current_sha = "a" * 40
    monkeypatch.setattr(audit, "_current_git_head", lambda: current_sha)
    monkeypatch.setattr(audit, "_current_release_relevant_source_sha", lambda: current_sha)
    monkeypatch.setattr(
        audit,
        "_current_release_artifact_relevant_dirty_paths",
        lambda: ["crates/wolfxl-writer/src/model/worksheet.rs"],
    )
    monkeypatch.setattr(audit, "_current_release_artifact_content_dirty_paths", lambda paths: [])
    reports = [
        _write_wheel_report(tmp_path, "linux.json", "cp39-cp39-manylinux_2_28_x86_64", current_sha),
        _write_wheel_report(tmp_path, "macos.json", "cp39-cp39-macosx_11_0_arm64", current_sha),
        _write_wheel_report(tmp_path, "windows.json", "cp39-cp39-win_amd64", current_sha),
        _write_sdist_report(tmp_path, "sdist.json", current_sha),
    ]

    report = audit.audit_release_artifact_coverage(
        release_workflow=workflow,
        pyproject=pyproject,
        release_artifact_reports=tuple(reports),
    )

    assert report["coverage_ready"] is True
    assert report["ready"] is True
    assert report["currentness_ready"] is True
    assert report["current_worktree_release_currentness_ready"] is True
    assert report["current_worktree_release_relevant_dirty_paths"] == [
        "crates/wolfxl-writer/src/model/worksheet.rs"
    ]
    assert report["current_worktree_release_relevant_content_dirty_paths"] == []


def test_pyproject_optional_dependencies_change_is_release_irrelevant(monkeypatch) -> None:
    base = (
        "[project]\n"
        'name = "wolfxl"\n'
        'version = "2.0.0"\n'
        'requires-python = ">=3.9"\n'
    )
    with_extra = base + (
        "\n[project.optional-dependencies]\n"
        'test = ["pytest>=8", "lxml>=5.0"]\n'
    )
    with_runtime_dep = (
        "[project]\n"
        'name = "wolfxl"\n'
        'version = "2.0.0"\n'
        'requires-python = ">=3.9"\n'
        'dependencies = ["lxml>=5.0"]\n'
    )

    # Adding an on-demand test extra never enters the built wheel/sdist proof.
    blobs = {("base", "pyproject.toml"): base, ("head", "pyproject.toml"): with_extra}
    monkeypatch.setattr(audit, "_git_blob_text", lambda rev, path: blobs[(rev, path)])
    assert (
        audit._release_artifact_committed_change_is_irrelevant(
            "pyproject.toml", "base", "head"
        )
        is True
    )

    # Control: adding a real runtime dependency DOES change the artifact -> relevant.
    blobs = {("base", "pyproject.toml"): base, ("head", "pyproject.toml"): with_runtime_dep}
    monkeypatch.setattr(audit, "_git_blob_text", lambda rev, path: blobs[(rev, path)])
    assert (
        audit._release_artifact_committed_change_is_irrelevant(
            "pyproject.toml", "base", "head"
        )
        is False
    )

    # Non-pyproject paths are never short-circuited by this carve-out.
    assert (
        audit._release_artifact_committed_change_is_irrelevant(
            "Cargo.lock", "base", "head"
        )
        is False
    )


def test_sdist_smoke_report_proves_source_lane(tmp_path: Path) -> None:
    workflow = tmp_path / "release.yml"
    workflow.write_text(_workflow_fixture(), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"wolfxl\"\nversion = \"2.0.0\"\nrequires-python = \">=3.9\"\n",
        encoding="utf-8",
    )
    sdist_report = tmp_path / "sdist.json"
    sdist_report.write_text(
        json.dumps(
            {
                "ready": True,
                "artifact_type": "sdist",
                "source_git_dirty": False,
                "report_repo_git_dirty": False,
                "sdist": {
                    "filename": "wolfxl-2.0.0.tar.gz",
                    "metadata_version": "2.0.0",
                },
            }
        ),
        encoding="utf-8",
    )

    report = audit.audit_release_artifact_coverage(
        release_workflow=workflow,
        pyproject=pyproject,
        release_artifact_reports=(sdist_report,),
    )

    assert report["proven_lanes"] == [
        {
            "abi": "source",
            "arch": "source",
            "artifact_type": "sdist",
            "id": "sdist:source",
            "os": "source",
            "python": "source",
            "source": "sdist job",
        }
    ]
    assert report["proven_lane_count"] == 1
    assert report["missing_lane_count"] == 3
    assert report["proof_reports"][0]["artifact_type"] == "sdist"
    assert report["proof_reports"][0]["sdist_filename"] == "wolfxl-2.0.0.tar.gz"


def test_dirty_report_repo_proof_does_not_prove_lane(tmp_path: Path) -> None:
    workflow = tmp_path / "release.yml"
    workflow.write_text(_workflow_fixture(), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = \"wolfxl\"\nversion = \"2.0.0\"\nrequires-python = \">=3.9\"\n",
        encoding="utf-8",
    )
    wheel_report = tmp_path / "wheel.json"
    wheel_report.write_text(
        json.dumps(
            {
                "ready": True,
                "source_git_dirty": False,
                "report_repo_git_dirty": True,
                "wheel": {
                    "metadata_version": "2.0.0",
                    "wheel_tag": "cp39-cp39-manylinux_2_28_x86_64",
                },
            }
        ),
        encoding="utf-8",
    )

    report = audit.audit_release_artifact_coverage(
        release_workflow=workflow,
        pyproject=pyproject,
        release_artifact_reports=(wheel_report,),
    )

    assert report["proven_lane_count"] == 0
    assert report["missing_lane_count"] == 4
    assert report["proof_reports"][0]["report_repo_git_dirty"] is True
    assert report["proof_reports"][0]["proven_lane_ids"] == []


def test_markdown_lists_counts_and_lanes(tmp_path: Path) -> None:
    workflow = tmp_path / "release.yml"
    workflow.write_text(_workflow_fixture(), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname = \"wolfxl\"\nversion = \"2.0.0\"\n", encoding="utf-8")

    report = audit.audit_release_artifact_coverage(
        release_workflow=workflow,
        pyproject=pyproject,
        release_artifact_reports=(),
    )
    markdown = audit.format_markdown(report)

    assert "| Expected lanes | 4 |" in markdown
    assert "| Missing lanes | 4 |" in markdown
    assert "## Currentness Policy" in markdown
    assert "latest committed release-relevant source SHA" in markdown
    assert "not the docs or audit commit" in markdown
    assert "## Claim Boundary" in markdown
    assert "future workflow lanes" in markdown
    assert "`wheel:linux:x86_64:cp39`" in markdown
    assert "`sdist:source`" in markdown


def _workflow_fixture() -> str:
    return """
name: Release

jobs:
  linux:
    strategy:
      matrix:
        target: [x86_64]
    steps:
      - name: Build wheels
        with:
          args: --release --out dist -i python3.9
  macos:
    strategy:
      matrix:
        include:
          - runner: macos-14
            target: aarch64
    steps:
      - name: Build wheels
        with:
          args: --release --out dist -i python3.9
  windows:
    strategy:
      matrix:
        python-version: ['3.9']
    steps:
      - name: Build wheels
  sdist:
    runs-on: ubuntu-latest
"""


def _write_wheel_report(
    tmp_path: Path,
    name: str,
    tag: str,
    source_git_sha: str,
) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "source_git_dirty": False,
                "source_git_sha": source_git_sha,
                "report_repo_git_dirty": False,
                "report_repo_git_sha": source_git_sha,
                "wheel": {
                    "metadata_version": "2.0.0",
                    "wheel_tag": tag,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_sdist_report(tmp_path: Path, name: str, source_git_sha: str) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "ready": True,
                "artifact_type": "sdist",
                "source_git_dirty": False,
                "source_git_sha": source_git_sha,
                "report_repo_git_dirty": False,
                "report_repo_git_sha": source_git_sha,
                "sdist": {
                    "filename": "wolfxl-2.0.0.tar.gz",
                    "metadata_version": "2.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


# --- Release-relevant source SHA must look past benchmark-neutral pyproject ---
# A PR merge ref folds in main, which may carry an additive
# [project.optional-dependencies] group (e.g. a test-only extras group). Opt-in
# extras are not part of the built wheel/sdist, so a commit that only adds them
# must NOT advance the "release-relevant source SHA" and stale every recorded
# lane proof. These tests pin that the walk skips such commits.

_BASE_PYPROJECT = """\
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "wolfxl"
version = "2.0.0"
requires-python = ">=3.9"
dependencies = ["typing-extensions"]
"""

_OPTIONAL_DEPS_BLOCK = """
[project.optional-dependencies]
test = ["pytest>=7.4", "Pillow>=10.0"]
"""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "tester@example.com")
    _git(repo, "config", "user.name", "Tester")
    _git(repo, "config", "commit.gpgsign", "false")


def test_release_relevant_source_sha_skips_optional_dependency_only_commits(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "crates").mkdir()
    (repo / "crates" / "lib.rs").write_text("// wheel source v1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(_BASE_PYPROJECT, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "material: wheel source")
    material_sha = _git(repo, "rev-parse", "HEAD")

    (repo / "pyproject.toml").write_text(
        _BASE_PYPROJECT + _OPTIONAL_DEPS_BLOCK, encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore(deps): add test optional-dependency group")

    monkeypatch.setattr(audit, "ROOT", repo)

    assert audit._current_release_relevant_source_sha() == material_sha


def test_release_relevant_source_sha_skips_optional_dependency_merge(
    tmp_path: Path, monkeypatch
) -> None:
    # Faithfully mirror GitHub's PR merge ref: the merge commit's FIRST parent
    # is the base branch (main, which only added optional extras) and its SECOND
    # parent is the PR branch (which carries the material wheel source main
    # lacks). A naive first-parent materiality check would wrongly flag the merge
    # as material; the fix must look at all parents and skip it.
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "pyproject.toml").write_text(_BASE_PYPROJECT, encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "branch", "-M", "main")

    # PR branch carries the material release source (a wheel crate) main lacks.
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "crates").mkdir()
    (repo / "crates" / "lib.rs").write_text("// wheel source v1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "material: wheel source")
    material_sha = _git(repo, "rev-parse", "HEAD")

    # main only adds a test-only optional-dependencies group.
    _git(repo, "checkout", "-q", "main")
    (repo / "pyproject.toml").write_text(
        _BASE_PYPROJECT + _OPTIONAL_DEPS_BLOCK, encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore(deps): add test optional-dependency group")

    # GitHub builds refs/pull/N/merge as `checkout base; merge head`, so the
    # base (main) is parent 1 and the PR head (feature) is parent 2.
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "feature")
    merge_parents = _git(repo, "rev-list", "--parents", "-n1", "HEAD").split()
    assert merge_parents[1] != material_sha, "expected base (main) as first parent"

    monkeypatch.setattr(audit, "ROOT", repo)

    assert audit._current_release_relevant_source_sha() == material_sha


def test_release_relevant_source_sha_stops_at_material_pyproject_change(
    tmp_path: Path, monkeypatch
) -> None:
    # A pyproject change that touches required [project].dependencies DOES move
    # the built artifact, so the walk must stop at it.
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "crates").mkdir()
    (repo / "crates" / "lib.rs").write_text("// wheel source v1\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(_BASE_PYPROJECT, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "material: wheel source")

    (repo / "pyproject.toml").write_text(
        _BASE_PYPROJECT.replace(
            'dependencies = ["typing-extensions"]',
            'dependencies = ["typing-extensions", "numpy"]',
        ),
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat: add required numpy runtime dependency")
    material_pyproject_sha = _git(repo, "rev-parse", "HEAD")

    monkeypatch.setattr(audit, "ROOT", repo)

    assert audit._current_release_relevant_source_sha() == material_pyproject_sha


def test_pyproject_without_optional_dependencies_drops_extras_group() -> None:
    base = audit._pyproject_without_optional_dependencies(_BASE_PYPROJECT.encode())
    with_extras = audit._pyproject_without_optional_dependencies(
        (_BASE_PYPROJECT + _OPTIONAL_DEPS_BLOCK).encode()
    )

    assert base == with_extras
    assert "optional-dependencies" not in with_extras.get("project", {})
