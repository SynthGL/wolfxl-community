from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "trust" / "release-artifact-proof-runbook.md"


def test_release_artifact_proof_runbook_has_strict_import_flow() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "current registered release lanes are already proven" in text
    assert "same missing lanes" not in text
    assert "14 planned GitHub release-proof lanes" not in text
    assert "`workflow_dispatch` only works after the workflow file exists on the default branch" in text
    assert "For the first proof run from this feature branch, use the branch `push` trigger" in text
    assert "gh api \"repos/SynthGL/wolfxl/actions/runs?branch=$branch&event=push&per_page=20\"" in text
    assert ".github/workflows/release-artifact-proof.yml" in text
    assert "select(.path ==" in text
    assert "select(.head_sha ==" in text
    assert "cannot be found reliably with" in text
    assert "until the workflow file also\nexists on the default branch" in text
    assert "gh workflow run release-artifact-proof.yml" in text
    assert "gh run watch \"$run_id\" --exit-status" in text
    assert "gh run download \"$run_id\"" in text
    assert "--pattern 'release-proof-*'" in text
    assert "json_count=$(find \"$artifact_dir\" -name 'release-artifact-wheel-smoke-*.json'" in text
    assert "markdown_count=$(find \"$artifact_dir\" -name 'release-artifact-wheel-smoke-*.md'" in text
    assert 'test "$json_count" = 14' in text
    assert 'test "$markdown_count" = 14' in text
    assert "scripts/import_release_artifact_proof_reports.py" in text
    assert "--dry-run" in text
    assert "--require-all-current-missing" in text
    assert "--strict" in text
    assert "scripts/audit_release_artifact_coverage.py" in text
    assert "scripts/audit_public_claim_dimensions.py" in text
    assert "scripts/audit_final_sota_blockers.py" in text
    assert "scripts/audit_trust_report_freshness.py" in text


def test_release_artifact_proof_runbook_keeps_excel_out_of_batch() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "No Microsoft Excel GUI step is required for this batch." in text
    assert "run_ooxml_app_smoke.py --app excel" not in text
    assert "run_ooxml_render_compare.py --render-engine excel" not in text
    assert "open -a \"Microsoft Excel\"" not in text
    assert "AppleScript" not in text
