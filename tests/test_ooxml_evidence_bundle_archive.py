from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module(script_name: str) -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.removesuffix(".py"), script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


archive = _load_module("archive_ooxml_evidence_bundle.py")
bundle = _load_module("audit_ooxml_evidence_bundle.py")


def test_archive_bundle_copies_reports_to_relative_paths(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"ready": True, "fixture_count": 22}) + "\n")
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage gate",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [
                            {"path": "ready", "equals": True},
                            {"path": "fixture_count", "equals": 22},
                        ],
                    }
                ]
            }
        )
    )
    output_dir = tmp_path / "archive"

    summary = archive.archive_bundle(manifest, output_dir)

    assert summary["ready"] is True
    assert summary["copied_report_count"] == 1
    archived_manifest = output_dir / "bundle.json"
    archived_payload = json.loads(archived_manifest.read_text())
    archived_report = archived_payload["reports"][0]
    assert archived_report["path"] == "reports/0001-coverage-gate.json"
    assert archived_report["archive_status"] == "copied"
    assert len(archived_report["sha256"]) == 64
    assert (output_dir / archived_report["path"]).read_text() == report_path.read_text()

    audit = bundle.audit_bundle(archived_manifest, require_portable_paths=True)

    assert audit["ready"] is True
    assert audit["issue_count"] == 0
    assert audit["absolute_path_count"] == 0
    assert audit["volatile_path_count"] == 0
    assert audit["portable_paths_ready"] is True


def test_archive_bundle_fails_loudly_when_report_is_missing(tmp_path: Path) -> None:
    manifest = tmp_path / "bundle.json"
    missing_report = tmp_path / "missing.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "missing report",
                        "path": str(missing_report),
                        "producer": "uv run --no-sync python scripts/missing.py",
                        "expect": [{"path": "ready", "equals": True}],
                    }
                ]
            }
        )
    )
    output_dir = tmp_path / "archive"

    summary = archive.archive_bundle(manifest, output_dir)

    assert summary["ready"] is False
    assert summary["missing_report_count"] == 1
    assert summary["missing_reports"] == [
        {
            "name": "missing report",
            "path": str(missing_report),
        }
    ]
    assert (output_dir / "archive-summary.json").is_file()
    assert not (output_dir / "bundle.json").exists()


def test_archive_bundle_can_write_partial_archive_for_diagnostics(tmp_path: Path) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"ready": True}) + "\n")
    missing_report = tmp_path / "missing.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [{"path": "ready", "equals": True}],
                    },
                    {
                        "name": "missing",
                        "path": str(missing_report),
                        "producer": "uv run --no-sync python scripts/missing.py",
                        "expect": [{"path": "ready", "equals": True}],
                    },
                ]
            }
        )
    )
    output_dir = tmp_path / "archive"

    summary = archive.archive_bundle(manifest, output_dir, allow_missing=True)

    assert summary["ready"] is False
    assert summary["copied_report_count"] == 1
    archived_payload = json.loads((output_dir / "bundle.json").read_text())
    assert archived_payload["reports"][0]["archive_status"] == "copied"
    assert archived_payload["reports"][1]["archive_status"] == "missing_source"
    assert archived_payload["reports"][1]["path"] == "reports/0002-missing.json"
    assert archived_payload["reports"][1]["archive_source_path"] == str(missing_report)

    audit = bundle.audit_bundle(output_dir / "bundle.json", require_portable_paths=True)

    assert audit["ready"] is False
    assert audit["issue_count"] == 1
    assert audit["issues"][0]["check"] == "exists"
    assert audit["absolute_path_count"] == 0
    assert audit["volatile_path_count"] == 0
    assert audit["portable_paths_ready"] is True


def test_archive_bundle_can_write_existing_only_partial_archive(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps({"ready": True}) + "\n")
    missing_report = tmp_path / "missing.json"
    manifest = tmp_path / "bundle.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "coverage",
                        "path": str(report_path),
                        "producer": "uv run --no-sync python scripts/example.py",
                        "expect": [{"path": "ready", "equals": True}],
                    },
                    {
                        "name": "missing",
                        "path": str(missing_report),
                        "producer": "uv run --no-sync python scripts/missing.py",
                        "expect": [{"path": "ready", "equals": True}],
                    },
                ]
            }
        )
    )
    output_dir = tmp_path / "archive"

    summary = archive.archive_bundle(manifest, output_dir, only_existing=True)

    assert summary["ready"] is False
    assert summary["archive_mode"] == "existing_only"
    assert summary["archived_report_count"] == 1
    assert summary["copied_report_count"] == 1
    assert summary["missing_report_count"] == 1
    assert summary["omitted_missing_report_count"] == 1
    archived_manifest = output_dir / "bundle.json"
    archived_payload = json.loads(archived_manifest.read_text())
    assert [report["name"] for report in archived_payload["reports"]] == ["coverage"]
    assert archived_payload["archive"]["mode"] == "existing_only"
    assert archived_payload["archive"]["omitted_missing_report_count"] == 1

    audit = bundle.audit_bundle(archived_manifest, require_portable_paths=True)

    assert audit["ready"] is True
    assert audit["issue_count"] == 0
    assert audit["portable_paths_ready"] is True
