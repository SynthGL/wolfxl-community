from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    script = scripts_dir / "audit_ooxml_random_holdout_replacement.py"
    spec = importlib.util.spec_from_file_location(
        "audit_ooxml_random_holdout_replacement",
        script,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


auditor = _load_module()


def test_replacement_audit_requires_old_thresholds_to_pass(tmp_path: Path) -> None:
    candidate = _write_candidate_portfolio(tmp_path, source_count=1, workbook_count=3)
    manifest = _write_manifest(tmp_path, min_sources=2)

    report = auditor.audit_replacement(
        manifest,
        legacy_upstream_path="/tmp/legacy-corpus.json",
        candidate_portfolio_path=candidate,
    )

    assert report["safe_to_repoint_legacy_producers"] is False
    assert report["decision"] == "repin_required"
    assert report["dependent_report_count"] == 1
    assert report["unique_config_count"] == 1
    config = report["configs"][0]
    assert config["dependent_reports"] == ["random_render"]
    assert config["replay_ready"] is False
    assert config["selected_source_count"] == 1
    assert config["threshold_failures"] == [
        {"actual": 1, "expected_at_least": 2, "id": "min_sources"}
    ]


def test_replacement_audit_cli_writes_json_and_markdown(
    tmp_path: Path,
    capsys,
) -> None:
    candidate = _write_candidate_portfolio(tmp_path, source_count=2, workbook_count=4)
    manifest = _write_manifest(tmp_path, min_sources=2)
    output = tmp_path / "replacement.json"
    markdown = tmp_path / "replacement.md"

    code = auditor.main(
        [
            str(manifest),
            "--legacy-upstream",
            "/tmp/legacy-corpus.json",
            "--candidate-portfolio",
            str(candidate),
            "--output",
            str(output),
            "--markdown-output",
            str(markdown),
            "--strict",
        ]
    )

    printed = json.loads(capsys.readouterr().out)
    written = json.loads(output.read_text())
    markdown_text = markdown.read_text()
    assert code == 0
    assert printed["safe_to_repoint_legacy_producers"] is True
    assert written["decision"] == "candidate_replays_legacy_thresholds"
    assert markdown_text.startswith("# Random Holdout Replacement Audit\n")
    assert "| 2 | 2 | 2 | `True` | `random_render` |" in markdown_text


def _write_manifest(tmp_path: Path, *, min_sources: int) -> Path:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "reports": [
                    {
                        "name": "random_render",
                        "path": str(tmp_path / "random-render.json"),
                        "producer": (
                            "uv run --no-sync python "
                            "scripts/audit_ooxml_random_corpus_holdout.py "
                            "/tmp/legacy-corpus.json "
                            "--sample-size 2 "
                            "--min-sample-size 2 "
                            f"--min-sources {min_sources} "
                            "--seed stable-test-seed "
                            "--stage-dir /tmp/stage "
                            "--strict > /tmp/staged.json"
                        ),
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_candidate_portfolio(
    tmp_path: Path,
    *,
    source_count: int,
    workbook_count: int,
) -> Path:
    workbook_rows = []
    for workbook_index in range(workbook_count):
        workbook = tmp_path / f"w{workbook_index}.xlsx"
        workbook.write_bytes(b"placeholder")
        workbook_rows.append(
            {
                "path": str(workbook),
                "buckets": ["excel_authored"],
            }
        )
    source_reports = []
    for source_index in range(source_count):
        source_report = tmp_path / f"source-{source_index}.json"
        source_report.write_text(
            json.dumps({"ready": True, "workbooks": workbook_rows}) + "\n",
            encoding="utf-8",
        )
        source_reports.append({"path": str(source_report), "contributes_source": True})
    portfolio = tmp_path / "portfolio.json"
    portfolio.write_text(
        json.dumps({"ready": True, "source_reports": source_reports}) + "\n",
        encoding="utf-8",
    )
    return portfolio
