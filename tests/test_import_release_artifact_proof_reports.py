from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "import_release_artifact_proof_reports.py"
    )
    spec = importlib.util.spec_from_file_location("import_release_artifact_proof_reports", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


importer = _load_module()


MISSING_LANE_REPORTS = {
    "release-artifact-wheel-smoke-linux-aarch64-cp39": "cp39-cp39-manylinux_2_34_aarch64",
    "release-artifact-wheel-smoke-linux-aarch64-cp310": "cp310-cp310-manylinux_2_34_aarch64",
    "release-artifact-wheel-smoke-linux-aarch64-cp311": "cp311-cp311-manylinux_2_34_aarch64",
    "release-artifact-wheel-smoke-linux-aarch64-cp312": "cp312-cp312-manylinux_2_34_aarch64",
    "release-artifact-wheel-smoke-linux-aarch64-cp313": "cp313-cp313-manylinux_2_34_aarch64",
    "release-artifact-wheel-smoke-macos-x86_64-cp310": "cp310-cp310-macosx_11_0_x86_64",
    "release-artifact-wheel-smoke-macos-x86_64-cp311": "cp311-cp311-macosx_11_0_x86_64",
    "release-artifact-wheel-smoke-macos-x86_64-cp312": "cp312-cp312-macosx_11_0_x86_64",
    "release-artifact-wheel-smoke-macos-x86_64-cp313": "cp313-cp313-macosx_11_0_x86_64",
    "release-artifact-wheel-smoke-windows-x86_64-cp39": "cp39-cp39-win_amd64",
    "release-artifact-wheel-smoke-windows-x86_64-cp310": "cp310-cp310-win_amd64",
    "release-artifact-wheel-smoke-windows-x86_64-cp311": "cp311-cp311-win_amd64",
    "release-artifact-wheel-smoke-windows-x86_64-cp312": "cp312-cp312-win_amd64",
    "release-artifact-wheel-smoke-windows-x86_64-cp313": "cp313-cp313-win_amd64",
}


def test_importer_accepts_clean_missing_lane_report(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(source, "release-artifact-wheel-smoke-linux-aarch64-cp39")
    output_dir = tmp_path / "trust"
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: {"wheel:linux:aarch64:cp39"})

    report = importer.import_reports((source,), output_dir=output_dir)

    assert report["ready"] is True
    assert report["accepted_count"] == 1
    assert report["rejected_count"] == 0
    assert (output_dir / "release-artifact-wheel-smoke-linux-aarch64-cp39.json").exists()
    assert (output_dir / "release-artifact-wheel-smoke-linux-aarch64-cp39.md").exists()


def test_importer_accepts_clean_sdist_report(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_sdist_report(source)
    output_dir = tmp_path / "trust"
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: {"sdist:source"})

    report = importer.import_reports((source,), output_dir=output_dir)

    assert report["ready"] is True
    assert report["accepted_count"] == 1
    assert report["rejected_count"] == 0
    assert report["imported_reports"][0]["lane_id"] == "sdist:source"
    assert report["imported_reports"][0]["artifact_type"] == "sdist"
    assert report["imported_reports"][0]["wheel_tag"] is None
    assert report["imported_reports"][0]["sdist_filename"] == "wolfxl-2.0.0.tar.gz"
    assert (output_dir / "release-artifact-sdist-smoke.json").exists()
    assert (output_dir / "release-artifact-sdist-smoke.md").exists()


def test_importer_rejects_existing_lane_without_refresh_flag(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(source, "release-artifact-wheel-smoke-linux-aarch64-cp39")
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: set())

    report = importer.import_reports((source,), output_dir=tmp_path / "trust")

    assert report["ready"] is False
    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 1
    assert "lane wheel:linux:aarch64:cp39 is not currently missing" in report[
        "rejected_reports"
    ][0]["issues"]


def test_importer_refreshes_existing_lane_with_refresh_flag(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(source, "release-artifact-wheel-smoke-linux-aarch64-cp39")
    output_dir = tmp_path / "trust"
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: set())

    report = importer.import_reports(
        (source,),
        output_dir=output_dir,
        allow_refresh_existing=True,
    )

    assert report["ready"] is True
    assert report["allow_refresh_existing"] is True
    assert report["accepted_count"] == 1
    assert report["rejected_count"] == 0
    assert (output_dir / "release-artifact-wheel-smoke-linux-aarch64-cp39.json").exists()
    assert (output_dir / "release-artifact-wheel-smoke-linux-aarch64-cp39.md").exists()


def test_importer_normalizes_imported_reports_to_lf(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(
        source,
        "release-artifact-wheel-smoke-windows-x86_64-cp39",
        wheel_tag="cp39-cp39-win_amd64",
    )
    json_path = source / "release-artifact-wheel-smoke-windows-x86_64-cp39.json"
    markdown_path = source / "release-artifact-wheel-smoke-windows-x86_64-cp39.md"
    json_path.write_bytes(json_path.read_bytes().replace(b"\n", b"\r\n"))
    markdown_path.write_bytes(markdown_path.read_bytes().replace(b"\n", b"\r\n"))
    output_dir = tmp_path / "trust"
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: set())

    report = importer.import_reports(
        (source,),
        output_dir=output_dir,
        allow_refresh_existing=True,
    )

    assert report["ready"] is True
    assert b"\r" not in (
        output_dir / "release-artifact-wheel-smoke-windows-x86_64-cp39.json"
    ).read_bytes()
    assert b"\r" not in (
        output_dir / "release-artifact-wheel-smoke-windows-x86_64-cp39.md"
    ).read_bytes()


def test_importing_all_current_missing_reports_completes_release_coverage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    for stem, wheel_tag in MISSING_LANE_REPORTS.items():
        _write_report(source, stem, wheel_tag=wheel_tag)
    current_missing = {
        importer._lane_id_from_report_stem(stem) for stem in MISSING_LANE_REPORTS
    }
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: current_missing)
    assert current_missing == {
        importer._lane_id_from_report_stem(stem) for stem in MISSING_LANE_REPORTS
    }

    dry_run = importer.import_reports(
        (source,),
        output_dir=tmp_path / "dry-run-trust",
        dry_run=True,
        require_all_current_missing=True,
    )

    assert dry_run["ready"] is True
    assert dry_run["accepted_count"] == 14
    assert dry_run["rejected_count"] == 0
    assert dry_run["missing_after_import"] == []

    output_dir = tmp_path / "trust"
    imported = importer.import_reports(
        (source,),
        output_dir=output_dir,
        require_all_current_missing=True,
    )

    assert imported["ready"] is True
    assert imported["accepted_count"] == 14
    imported_reports = tuple(output_dir.glob("release-artifact-wheel-smoke-*.json"))
    coverage = importer.audit_release_artifact_coverage.audit_release_artifact_coverage(
        release_artifact_reports=(
            *importer.audit_release_artifact_coverage._default_release_artifact_reports(),
            *imported_reports,
        )
    )
    assert coverage["coverage_ready"] is True
    assert coverage["expected_lane_count"] == 26
    assert coverage["proven_lane_count"] == 26
    assert coverage["missing_lane_count"] == 0
    assert coverage["extra_proven_lane_count"] == 0


def test_importer_rejects_dirty_report_repo(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(
        source,
        "release-artifact-wheel-smoke-linux-aarch64-cp39",
        report_repo_git_dirty=True,
    )
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: {"wheel:linux:aarch64:cp39"})

    report = importer.import_reports((source,), output_dir=tmp_path / "trust")

    assert report["ready"] is False
    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 1
    assert "report_repo_git_dirty is not false" in report["rejected_reports"][0]["issues"]


def test_importer_rejects_unexpected_commit_sha(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(source, "release-artifact-wheel-smoke-linux-aarch64-cp39")
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: {"wheel:linux:aarch64:cp39"})

    report = importer.import_reports(
        (source,),
        output_dir=tmp_path / "trust",
        expected_git_sha="c" * 40,
    )

    assert report["ready"] is False
    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 1
    assert "source_git_sha does not match expected_git_sha" in report["rejected_reports"][0][
        "issues"
    ]
    assert "report_repo_git_sha does not match expected_git_sha" in report["rejected_reports"][0][
        "issues"
    ]


def test_importer_rejects_source_and_report_repo_sha_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(
        source,
        "release-artifact-wheel-smoke-linux-aarch64-cp39",
        report_repo_git_sha="c" * 40,
    )
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: {"wheel:linux:aarch64:cp39"})

    report = importer.import_reports((source,), output_dir=tmp_path / "trust")

    assert report["ready"] is False
    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 1
    assert "source_git_sha and report_repo_git_sha do not match" in report["rejected_reports"][0][
        "issues"
    ]


def test_importer_rejects_malformed_commit_sha(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(
        source,
        "release-artifact-wheel-smoke-linux-aarch64-cp39",
        source_git_sha="not-a-sha",
        report_repo_git_sha="not-a-sha",
    )
    monkeypatch.setattr(importer, "_current_missing_lane_ids", lambda: {"wheel:linux:aarch64:cp39"})

    report = importer.import_reports((source,), output_dir=tmp_path / "trust")

    assert report["ready"] is False
    assert report["accepted_count"] == 0
    assert report["rejected_count"] == 1
    assert "source_git_sha is not a 40-character hex commit" in report["rejected_reports"][0][
        "issues"
    ]
    assert "report_repo_git_sha is not a 40-character hex commit" in report[
        "rejected_reports"
    ][0]["issues"]


def test_importer_rejects_filename_and_wheel_tag_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(
        source,
        "release-artifact-wheel-smoke-windows-x86_64-cp39",
        wheel_tag="cp39-cp39-manylinux_2_34_aarch64",
    )
    monkeypatch.setattr(
        importer,
        "_current_missing_lane_ids",
        lambda: {"wheel:windows:x86_64:cp39", "wheel:linux:aarch64:cp39"},
    )

    report = importer.import_reports((source,), output_dir=tmp_path / "trust")

    assert report["ready"] is False
    assert report["accepted_count"] == 0
    assert any(
        "does not match filename lane" in issue
        for issue in report["rejected_reports"][0]["issues"]
    )


def test_importer_strict_all_missing_reports_remaining_lanes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    _write_report(source, "release-artifact-wheel-smoke-linux-aarch64-cp39")
    monkeypatch.setattr(
        importer,
        "_current_missing_lane_ids",
        lambda: {"wheel:linux:aarch64:cp39", "wheel:linux:aarch64:cp310"},
    )

    report = importer.import_reports(
        (source,),
        output_dir=tmp_path / "trust",
        require_all_current_missing=True,
    )

    assert report["ready"] is False
    assert report["accepted_count"] == 1
    assert report["missing_after_import"] == ["wheel:linux:aarch64:cp310"]


def test_importer_rejects_unsafe_zip_member(tmp_path: Path) -> None:
    archive = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../release-artifact-wheel-smoke-linux-aarch64-cp39.json", "{}")

    try:
        importer.import_reports((archive,), output_dir=tmp_path / "trust")
    except ValueError as exc:
        assert "unsafe zip member path" in str(exc)
    else:
        raise AssertionError("unsafe zip member should fail")


def _write_report(
    directory: Path,
    stem: str,
    *,
    wheel_tag: str = "cp39-cp39-manylinux_2_34_aarch64",
    source_git_sha: str = "a" * 40,
    report_repo_git_sha: str = "a" * 40,
    report_repo_git_dirty: bool = False,
) -> None:
    (directory / f"{stem}.md").write_text("# Release Artifact Smoke\n", encoding="utf-8")
    (directory / f"{stem}.json").write_text(
        json.dumps(
            {
                "ready": True,
                "artifact_type": "wheel",
                "source_git_sha": source_git_sha,
                "source_git_dirty": False,
                "report_repo_git_sha": report_repo_git_sha,
                "report_repo_git_dirty": report_repo_git_dirty,
                "wheel": {
                    "filename": "wolfxl-2.0.0-cp39-cp39-manylinux_2_34_aarch64.whl",
                    "metadata_version": "2.0.0",
                    "sha256": "b" * 64,
                    "size_bytes": 1234,
                    "wheel_tag": wheel_tag,
                },
                "venv_smoke": {
                    "write_workbook_exists": True,
                    "modified_workbook_exists": True,
                    "openpyxl_read_modified_a2": "modified",
                    "required_zip_parts_present": True,
                },
            }
        ),
        encoding="utf-8",
    )


def _write_sdist_report(
    directory: Path,
    *,
    source_git_sha: str = "a" * 40,
    report_repo_git_sha: str = "a" * 40,
    report_repo_git_dirty: bool = False,
) -> None:
    stem = "release-artifact-sdist-smoke"
    (directory / f"{stem}.md").write_text("# Release Artifact Smoke\n", encoding="utf-8")
    (directory / f"{stem}.json").write_text(
        json.dumps(
            {
                "ready": True,
                "artifact_type": "sdist",
                "source_git_sha": source_git_sha,
                "source_git_dirty": False,
                "report_repo_git_sha": report_repo_git_sha,
                "report_repo_git_dirty": report_repo_git_dirty,
                "sdist": {
                    "filename": "wolfxl-2.0.0.tar.gz",
                    "metadata_version": "2.0.0",
                    "sha256": "b" * 64,
                    "size_bytes": 1234,
                },
                "venv_smoke": {
                    "write_workbook_exists": True,
                    "modified_workbook_exists": True,
                    "openpyxl_read_modified_a2": "modified",
                    "required_zip_parts_present": True,
                },
            }
        ),
        encoding="utf-8",
    )
