from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_sota_snapshot_wording.py"
    spec = importlib.util.spec_from_file_location("audit_sota_snapshot_wording", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_sota_snapshot_wording_current_repo_is_ready() -> None:
    report = audit.audit_sota_snapshot_wording()

    assert report["ready"] is True
    assert report["issue_count"] == 0
    assert report["snapshot_count"] >= 1
    assert report["snapshot_json_count"] >= 1
    assert report["historical_snapshot_count"] >= 1
    assert all(
        row["broad_ready_claim"] is False
        for row in report["snapshot_jsons"]
        if row["exists"]
    )


def test_sota_snapshot_wording_blocks_current_stale_phrase(tmp_path: Path) -> None:
    current = tmp_path / "2026-06-01-current-sota-claim-audit.md"
    current.write_text(
        "# Current SOTA Claim Audit\n\n"
        "The remaining SOTA blocker is proof completeness for OOXML fidelity.\n",
        encoding="utf-8",
    )

    report = audit.audit_sota_snapshot_wording(
        baselines_dir=tmp_path,
        current_snapshot=current,
    )

    assert report["ready"] is False
    assert {
        "file": str(current),
        "phrase": "proof completeness for OOXML fidelity",
        "reason": "current SOTA snapshot uses stale blocker wording",
    } in report["issues"]


def test_sota_snapshot_wording_blocks_unmarked_historical_snapshot(tmp_path: Path) -> None:
    current = tmp_path / "2026-06-01-current-sota-claim-audit.md"
    historical = tmp_path / "2026-06-01-before-sota-claim-audit.md"
    current.write_text(
        "open-ended exhaustiveness boundary\n"
        "not by a missing queued evidence report\n",
        encoding="utf-8",
    )
    historical.write_text("# Current SOTA Claim Audit\n", encoding="utf-8")

    report = audit.audit_sota_snapshot_wording(
        baselines_dir=tmp_path,
        current_snapshot=current,
        historical_snapshot_paths=(historical,),
    )

    assert report["ready"] is False
    assert {
        "file": str(historical),
        "phrase": audit.ARCHIVE_NOTE,
        "reason": "historical SOTA snapshot lacks archive note",
    } in report["issues"]


def test_sota_snapshot_wording_blocks_current_looking_historical_title(
    tmp_path: Path,
) -> None:
    current = tmp_path / "2026-06-01-current-sota-claim-audit.md"
    historical = tmp_path / "2026-06-01-before-sota-claim-audit.md"
    current.write_text(
        "open-ended exhaustiveness boundary\n"
        "not by a missing queued evidence report\n",
        encoding="utf-8",
    )
    historical.write_text(
        "# Current SOTA Claim Audit\n\n"
        f"> {audit.ARCHIVE_NOTE}.\n",
        encoding="utf-8",
    )

    report = audit.audit_sota_snapshot_wording(
        baselines_dir=tmp_path,
        current_snapshot=current,
    )

    assert report["ready"] is False
    assert {
        "file": str(historical),
        "phrase": " or ".join(audit.HISTORICAL_TITLE_PREFIXES),
        "reason": "historical SOTA snapshot title still looks current",
    } in report["issues"]


def test_sota_snapshot_wording_blocks_unmarked_historical_trust_snapshot(
    tmp_path: Path,
) -> None:
    current = tmp_path / "2026-06-01-current-sota-claim-audit.md"
    trust_snapshot = tmp_path / "office-oxide-watchlist-clean-10k-sota-audit.md"
    current.write_text(
        "open-ended exhaustiveness boundary\n"
        "not by a missing queued evidence report\n",
        encoding="utf-8",
    )
    trust_snapshot.write_text("# Current SOTA Claim Audit\n", encoding="utf-8")

    report = audit.audit_sota_snapshot_wording(
        baselines_dir=tmp_path,
        current_snapshot=current,
        historical_snapshot_paths=(trust_snapshot,),
    )

    assert report["ready"] is False
    assert {
        "file": str(trust_snapshot),
        "phrase": audit.ARCHIVE_NOTE,
        "reason": "historical SOTA snapshot lacks archive note",
    } in report["issues"]


def test_sota_snapshot_wording_blocks_historical_json_broad_ready_claim(
    tmp_path: Path,
) -> None:
    current = tmp_path / "2026-06-01-current-sota-claim-audit.md"
    historical = tmp_path / "2026-06-01-before-sota-claim-audit.md"
    current.write_text(
        "open-ended exhaustiveness boundary\n"
        "not by a missing queued evidence report\n",
        encoding="utf-8",
    )
    current.with_suffix(".json").write_text(
        json.dumps(
            {
                "inputs": {
                    "rust_competitor_benchmark": (
                        audit.CURRENT_RUST_COMPETITOR_BENCHMARK
                    ),
                    "rust_competitor_set_report": (
                        audit.CURRENT_RUST_COMPETITOR_SET_REPORT
                    ),
                },
                "supported_scope_sota_gate_ready": True,
                "sota_claim_ready": False,
                "rust_competitors": {
                    "missing_competitors": [],
                    "missing_version_competitors": [],
                },
            }
        ),
        encoding="utf-8",
    )
    historical.write_text(
        f"{audit.HISTORICAL_TITLE_PREFIXES[0]}\n\n{audit.ARCHIVE_NOTE}\n",
        encoding="utf-8",
    )
    historical.with_suffix(".json").write_text(
        json.dumps({"ready": True, "sota_claim_ready": True}),
        encoding="utf-8",
    )

    report = audit.audit_sota_snapshot_wording(
        baselines_dir=tmp_path,
        current_snapshot=current,
    )

    assert report["ready"] is False
    assert {
        "file": str(historical.with_suffix(".json")),
        "phrase": "sota_claim_ready/sota_confidence_ready",
        "reason": "historical SOTA snapshot JSON claims broad SOTA readiness",
    } in report["issues"]


def test_sota_snapshot_wording_blocks_stale_current_proof_doc(tmp_path: Path) -> None:
    current = tmp_path / "2026-06-01-current-sota-claim-audit.md"
    proof_doc = tmp_path / "sota-proof-operator-checklist.md"
    current.write_text(
        "open-ended exhaustiveness boundary\n"
        "not by a missing queued evidence report\n",
        encoding="utf-8",
    )
    proof_doc.write_text(
        "It is written for the remaining SOTA blocker: durable OOXML fidelity evidence.\n",
        encoding="utf-8",
    )

    report = audit.audit_sota_snapshot_wording(
        baselines_dir=tmp_path,
        current_snapshot=current,
        current_proof_docs=(proof_doc,),
    )

    assert report["ready"] is False
    assert {
        "file": str(proof_doc),
        "phrase": "remaining SOTA blocker: durable OOXML fidelity evidence",
        "reason": "current SOTA proof document uses stale blocker wording",
    } in report["issues"]


def test_sota_snapshot_wording_blocks_current_stale_rust_inputs(
    tmp_path: Path,
) -> None:
    current = tmp_path / "2026-06-01-current-sota-claim-audit.md"
    current.write_text(
        "open-ended exhaustiveness boundary\n"
        "not by a missing queued evidence report\n",
        encoding="utf-8",
    )
    current.with_suffix(".json").write_text(
        json.dumps(
            {
                "inputs": {
                    "rust_competitor_benchmark": (
                        "docs/performance/baselines/2026-06-01-current-rust-competitors.json"
                    ),
                    "rust_competitor_set_report": (
                        "docs/performance/baselines/2026-06-01-rust-competitor-set-live-recheck.json"
                    ),
                },
                "supported_scope_sota_gate_ready": True,
                "sota_claim_ready": False,
                "rust_competitors": {
                    "missing_competitors": [],
                    "missing_version_competitors": [],
                },
            }
        ),
        encoding="utf-8",
    )

    report = audit.audit_sota_snapshot_wording(
        baselines_dir=tmp_path,
        current_snapshot=current,
    )

    assert report["ready"] is False
    assert {
        "file": str(current.with_suffix(".json")),
        "phrase": "docs/performance/baselines/2026-06-01-current-rust-competitors.json",
        "reason": (
            "current SOTA snapshot JSON uses stale rust_competitor_benchmark; "
            f"expected {audit.CURRENT_RUST_COMPETITOR_BENCHMARK}"
        ),
    } in report["issues"]


def test_sota_snapshot_wording_blocks_stale_rust_inputs_in_current_proof_doc(
    tmp_path: Path,
) -> None:
    current = tmp_path / "2026-06-01-current-sota-claim-audit.md"
    proof_doc = tmp_path / "sota-proof-operator-checklist.md"
    current.write_text(
        "open-ended exhaustiveness boundary\n"
        "not by a missing queued evidence report\n",
        encoding="utf-8",
    )
    proof_doc.write_text(
        "Use docs/performance/baselines/2026-06-01-rust-competitor-set-live-recheck.json\n",
        encoding="utf-8",
    )

    report = audit.audit_sota_snapshot_wording(
        baselines_dir=tmp_path,
        current_snapshot=current,
        current_proof_docs=(proof_doc,),
    )

    assert report["ready"] is False
    assert {
        "file": str(proof_doc),
        "phrase": "docs/performance/baselines/2026-06-01-rust-competitor-set-live-recheck.json",
        "reason": "current SOTA proof document uses stale Rust evidence input",
    } in report["issues"]


def test_sota_snapshot_wording_markdown_lists_no_issues(tmp_path: Path) -> None:
    current = tmp_path / "2026-06-01-current-sota-claim-audit.md"
    historical = tmp_path / "2026-06-01-before-sota-claim-audit.md"
    current.write_text(
        "open-ended exhaustiveness boundary\n"
        "not by a missing queued evidence report\n",
        encoding="utf-8",
    )
    current.with_suffix(".json").write_text(
        json.dumps(
            {
                "inputs": {
                    "rust_competitor_benchmark": (
                        audit.CURRENT_RUST_COMPETITOR_BENCHMARK
                    ),
                    "rust_competitor_set_report": (
                        audit.CURRENT_RUST_COMPETITOR_SET_REPORT
                    ),
                },
                "supported_scope_sota_gate_ready": True,
                "sota_claim_ready": False,
                "rust_competitors": {
                    "missing_competitors": [],
                    "missing_version_competitors": [],
                },
            }
        ),
        encoding="utf-8",
    )
    historical.write_text(
        f"{audit.HISTORICAL_TITLE_PREFIXES[0]}\n\n{audit.ARCHIVE_NOTE}\n",
        encoding="utf-8",
    )

    report = audit.audit_sota_snapshot_wording(
        baselines_dir=tmp_path,
        current_snapshot=current,
        historical_snapshot_paths=(historical,),
    )
    markdown = audit.format_markdown(report)

    assert "# SOTA Snapshot Wording Audit" in markdown
    assert "| Ready | true |" in markdown
    assert "| Snapshot JSON files | 1 |" in markdown
    assert "## Current Proof Docs" in markdown
    assert "## Snapshot JSON Status" in markdown
    assert "## Snapshot Archive Status" in markdown
    assert "| " + str(current.with_suffix(".json")) + " | true | true | true | none | false | none | false | false |" in markdown
    assert "| " + str(current) + " | true | false | true | 0 |" in markdown
    assert "- none" in markdown
