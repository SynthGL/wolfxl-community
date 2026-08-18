from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_public_claim_wording.py"
    spec = importlib.util.spec_from_file_location("audit_public_claim_wording", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


MIGRATION_BOUNDARY_TEXT = (
    "Registered release-artifact lanes are proven, but not every future package route or installer. "
    "Openpyxl still has ecosystem maturity and long-tail workflow history. "
    "High-risk render variant space remains open-ended. "
    "Click-level Excel interaction variant space remains open-ended. "
    "Future or unseen real-world Excel surfaces cannot be fully exhausted. "
    "organizational dependency familiarity staff familiarity\n"
)


def test_public_claim_wording_current_repo_is_evidence_bound() -> None:
    report = audit.audit_public_claims()
    script_content = (
        Path(__file__).resolve().parents[1] / "scripts" / "audit_public_claim_wording.py"
    ).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    assert report["ready"] is True
    assert report["issue_count"] == 0
    assert report["generator"] == {
        "script_source": "current report repository",
        "script_path": "scripts/audit_public_claim_wording.py",
        "script_sha256": hashlib.sha256(script_content).hexdigest(),
    }
    assert set(report["scanned_files"]) == set(audit.PUBLIC_CLAIM_FILES)
    assert "docs/docs.json" in report["scanned_files"]
    assert (
        "docs/performance/baselines/2026-06-05-current-sota-claim-audit.md"
        in report["scanned_files"]
    )
    assert (
        "docs/performance/baselines/2026-06-05-rust-competitor-set-live-recheck.md"
        in report["scanned_files"]
    )
    assert (
        "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/README.md"
        in report["scanned_files"]
    )
    assert (
        "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/sota-proof-flow-status.md"
        in report["scanned_files"]
    )
    assert (
        "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/sota-proof-operator-checklist.md"
        in report["scanned_files"]
    )
    assert (
        "docs/performance/baselines/2026-06-10-required-rust-10k-with-memory-clean.md"
        in report["scanned_linked_proof_files"]
    )
    assert (
        "docs/performance/baselines/2026-06-05-sota-proof-flow-status.md"
        in report["scanned_linked_proof_files"]
    )
    assert (
        "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/worker-status.md"
        in report["scanned_linked_proof_files"]
    )
    assert set(report["scanned_context_files"]) >= set(audit.PUBLIC_CONTEXT_FILES)
    assert "CHANGELOG.md" in report["scanned_context_files"]
    assert "mkdocs.yml" in report["scanned_context_files"]
    assert "Cargo.toml" in report["scanned_context_files"]
    assert ".github/workflows/ci.yml" in report["scanned_context_files"]
    assert ".github/workflows/release.yml" in report["scanned_context_files"]
    assert "docs/trust/final-sota-blockers.json" in report["scanned_context_files"]
    assert "docs/trust/public-claim-wording-audit.json" not in report[
        "scanned_context_files"
    ]
    assert (
        "docs/trust/final-sota-blockers-after-openpyxl-corpus.json"
        in report["scanned_context_files"]
    )
    assert (
        "docs/trust/office-oxide-modify-phase-diagnostic-10k-sota-audit.json"
        in report["scanned_context_files"]
    )
    assert "docs/trust/public-claim-dimensions-audit.json" in report["scanned_context_files"]
    assert "docs/trust/sota-snapshot-wording-audit.json" in report["scanned_context_files"]
    assert "docs/trust/release-artifact-coverage-audit.json" in report["scanned_context_files"]
    assert (
        "docs/trust/release-artifact-proof-workflow-audit.json"
        in report["scanned_context_files"]
    )
    assert (
        "docs/trust/release-artifact-trigger-readiness-audit.json"
        in report["scanned_context_files"]
    )
    assert (
        "docs/trust/real-world-fidelity-plan-state-audit.json"
        in report["scanned_context_files"]
    )
    assert "docs/trust/trust-report-freshness-audit.json" in report["scanned_context_files"]
    assert "crates/wolfxl-core/README.md" in report["scanned_context_files"]
    assert "crates/wolfxl-cli/Cargo.toml" in report["scanned_context_files"]
    assert "crates/wolfxl-cli/README.md" in report["scanned_context_files"]
    assert "crates/wolfxl-formula/Cargo.toml" in report["scanned_context_files"]
    assert "crates/wolfxl-writer/Cargo.toml" in report["scanned_context_files"]
    assert "docs/migration/compatibility-matrix.md" in report["scanned_context_files"]
    assert "docs/performance/methodology.md" in report["scanned_context_files"]
    assert "docs/performance/run-on-your-files.md" in report["scanned_context_files"]
    assert "docs/trust/rc-validation-2.0.md" in report["scanned_context_files"]
    assert "Plans/rfcs/073-write-only-streaming.md" in report["scanned_context_files"]
    assert report["sota_alignment"]["checked"] is True
    assert report["sota_alignment"]["supported_scope_sota_gate_ready"] is True
    assert report["sota_alignment"]["sota_claim_ready"] is False
    assert report["sota_alignment"]["required_rust_competitors"] == [
        "rust_xlsxwriter",
        "xlsxwriter",
        "calamine",
        "umya-spreadsheet",
        "fastexcel",
        "python-calamine",
    ]
    assert report["sota_alignment"]["required_competitor_aliases"] == {
        "xlsxwriter": ["xlsxwriter-rs"]
    }
    assert (
        report["sota_alignment"]["requested_competitor_name_resolutions"][0][
            "exact_package_version"
        ]
        == "0.1.0"
    )
    assert report["sota_alignment"]["pypi_discovery_fetched"] is True
    assert report["sota_alignment"]["unclassified_pypi_discovery_hit_count"] == 0
    assert report["public_dimensions_alignment"]["checked"] is True
    assert (
        report["public_dimensions_alignment"]["broad_no_reason_claim_ready"]
        is False
    )
    assert report["public_dimensions_alignment"]["supported_scope_ready"] is True
    assert (
        report["public_dimensions_alignment"][
            "expected_broad_claim_boundary_gap_count"
        ]
        == 0
    )
    assert report["public_dimensions_alignment"][
        "missing_expected_broad_claim_boundaries"
    ] == []
    assert set(
        report["public_dimensions_alignment"]["expected_broad_claim_boundaries"]
    ) >= set(audit.EXPECTED_BROAD_CLAIM_BOUNDARIES)


def test_public_claim_wording_generator_hash_is_line_ending_stable(tmp_path: Path) -> None:
    lf_script = tmp_path / "script_lf.py"
    crlf_script = tmp_path / "script_crlf.py"
    lf_script.write_bytes(b"print('hello')\nprint('world')\n")
    crlf_script.write_bytes(b"print('hello')\r\nprint('world')\r\n")

    assert audit._git_blob_sha256_or_file_sha256(
        lf_script
    ) == audit._git_blob_sha256_or_file_sha256(crlf_script)


def test_public_claim_wording_markdown_lists_claim_boundary() -> None:
    report = audit.audit_public_claims()

    markdown = audit.format_markdown(report)

    assert "# Public Claim Wording Audit" in markdown
    assert "| Ready | true |" in markdown
    assert "| SOTA claim ready | false |" in markdown
    assert "| Scanned linked proof files | " in markdown
    assert "| Supported-scope SOTA gate ready | true |" in markdown
    assert "| Required Rust competitors | rust_xlsxwriter, xlsxwriter" in markdown
    assert "| Captured Rust competitor versions | rust_xlsxwriter" in markdown
    assert "| Required Rust aliases | xlsxwriter: xlsxwriter-rs |" in markdown
    assert "| Requested Rust name resolutions | 1 |" in markdown
    assert "| PyPI Rust-backed discovery fetched | true |" in markdown
    assert "| Unclassified PyPI Rust-backed discovery hits | 0 |" in markdown
    assert "| Public dimensions broad no-reason ready | false |" in markdown
    assert "| Public dimensions supported-scope ready | true |" in markdown
    assert "| Expected broad claim boundary gaps | 0 |" in markdown
    assert "| Generator script | scripts/audit_public_claim_wording.py |" in markdown
    assert "| Generator script SHA-256 | " in markdown
    assert "- none" in markdown


def test_public_claim_wording_requires_current_sota_snapshot_boundary(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    snapshot = (
        tmp_path
        / "docs"
        / "performance"
        / "baselines"
        / "2026-06-05-current-sota-claim-audit.md"
    )
    snapshot.write_text(
        snapshot.read_text(encoding="utf-8").replace(
            "| Overall SOTA claim ready | false |\n",
            "",
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/performance/baselines/2026-06-05-current-sota-claim-audit.md",
        "line": None,
        "phrase": "| Overall SOTA claim ready | false |",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_requires_current_rust_competitor_report_boundary(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    rust_report = (
        tmp_path
        / "docs"
        / "performance"
        / "baselines"
        / "2026-06-05-rust-competitor-set-live-recheck.md"
    )
    rust_report.write_text(
        rust_report.read_text(encoding="utf-8").replace(
            "| Missing competitors | none |\n",
            "",
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/performance/baselines/2026-06-05-rust-competitor-set-live-recheck.md",
        "line": None,
        "phrase": "| Missing competitors | none |",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_requires_current_proof_readme_sota_snapshot(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = (
        tmp_path
        / "docs"
        / "fidelity"
        / "evidence"
        / "2026-05-31-current-evidence-recovery-plan"
        / "README.md"
    )
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(
            "docs/performance/baselines/2026-06-05-current-sota-claim-audit.json",
            "docs/performance/baselines/2026-06-01-current-sota-claim-audit.json",
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/README.md",
        "line": None,
        "phrase": "docs/performance/baselines/2026-06-05-current-sota-claim-audit.json",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_scans_linked_current_proof_markdown(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    linked = (
        tmp_path
        / "docs"
        / "fidelity"
        / "evidence"
        / "2026-05-31-current-evidence-recovery-plan"
        / "linked-current-proof.md"
    )
    linked.parent.mkdir(parents=True, exist_ok=True)
    linked.write_text("There is no reason to keep using openpyxl.\n", encoding="utf-8")
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "[Linked proof](docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/linked-current-proof.md)\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert (
        "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/linked-current-proof.md"
        in report["scanned_linked_proof_files"]
    )
    assert any(
        issue["file"]
        == "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/linked-current-proof.md"
        and issue["reason"] == "no-reason-to-use-openpyxl wording is still gated"
        for issue in report["issues"]
    )


def test_public_claim_wording_flags_missing_linked_current_proof_markdown(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    missing = (
        "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/"
        "missing-current-proof.md"
    )
    readme.write_text(
        readme.read_text(encoding="utf-8") + f"[Missing proof]({missing})\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": None,
        "phrase": missing,
        "reason": "current proof Markdown link is missing",
    } in report["issues"]


def test_public_claim_wording_blocks_launch_benchmark_placeholders(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    launch_posts = tmp_path / "Plans" / "launch-posts.md"
    launch_posts.parent.mkdir(parents=True, exist_ok=True)
    launch_posts.write_text(
        "Touch one cell and save: <!-- TBD: BENCHMARK NUMBERS --> vs openpyxl.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "Plans/launch-posts.md",
        "line": 1,
        "phrase": "Touch one cell and save: <!-- TBD: BENCHMARK NUMBERS --> vs openpyxl.",
        "reason": "launch-facing benchmark placeholders must be filled or removed",
    } in report["issues"]


def test_public_claim_wording_blocks_launch_sha_placeholders(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    launch_posts = tmp_path / "Plans" / "launch-posts.md"
    launch_posts.parent.mkdir(parents=True, exist_ok=True)
    launch_posts.write_text(
        "Release commit: <!-- TBD: SHA -->\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "Plans/launch-posts.md",
        "line": 1,
        "phrase": "Release commit: <!-- TBD: SHA -->",
        "reason": "launch-facing SHA placeholders must be filled or removed",
    } in report["issues"]


def test_public_claim_wording_blocks_stale_live_harness_version(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    harness = tmp_path / "docs" / "performance" / "run-on-your-files.md"
    harness.parent.mkdir(parents=True, exist_ok=True)
    harness.write_text(
        "# Run Benchmarks on Your Files\n\n"
        "This harness compares read / write / modify-mode and (NEW in v1.7) "
        "chart-construction against openpyxl.\n\n"
        '"""Benchmark wolfxl 1.7 vs openpyxl 3.1 on a single workbook."""\n',
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/performance/run-on-your-files.md",
        "line": 3,
        "phrase": (
            "This harness compares read / write / modify-mode and (NEW in v1.7) "
            "chart-construction against openpyxl."
        ),
        "reason": "live benchmark harness docs must not present a stale WolfXL version",
    } in report["issues"]
    assert {
        "file": "docs/performance/run-on-your-files.md",
        "line": 5,
        "phrase": '"""Benchmark wolfxl 1.7 vs openpyxl 3.1 on a single workbook."""',
        "reason": "live benchmark harness docs must not present a stale WolfXL version",
    } in report["issues"]


def test_public_claim_wording_blocks_stale_methodology_version(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    methodology = tmp_path / "docs" / "performance" / "methodology.md"
    methodology.parent.mkdir(parents=True, exist_ok=True)
    methodology.write_text(
        "# Benchmark Methodology\n\n"
        "> **Reference**: WolfXL **v1.7.0**.\n\n"
        "Compares against openpyxl.\n\n"
        "## Construction-side benchmarks (NEW in v1.7)\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/performance/methodology.md",
        "line": 3,
        "phrase": "> **Reference**: WolfXL **v1.7.0**.",
        "reason": "live benchmark harness docs must not present a stale WolfXL version",
    } in report["issues"]
    assert {
        "file": "docs/performance/methodology.md",
        "line": 7,
        "phrase": "## Construction-side benchmarks (NEW in v1.7)",
        "reason": "live benchmark harness docs must not present a stale WolfXL version",
    } in report["issues"]


def test_public_claim_wording_allows_historical_methodology_version(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    methodology = tmp_path / "docs" / "performance" / "methodology.md"
    methodology.parent.mkdir(parents=True, exist_ok=True)
    methodology.write_text(
        "# Benchmark Methodology\n\n"
        "> Historical snapshot, not current evidence: WolfXL **v1.7.0**.\n\n"
        "Compares against openpyxl.\n\n"
        "## Historical construction-side benchmarks\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_blocks_fresh_excelbench_release_artifact_checklist(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "Fresh ExcelBench fidelity rerun against the WolfXL 2.0 release artifact\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "Fresh ExcelBench fidelity rerun against the WolfXL 2.0 release artifact",
        "reason": "fresh ExcelBench release-artifact wording should point to dated current reports",
    } in report["issues"]


def test_public_claim_wording_blocks_broad_drop_in_replacement(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    migration = tmp_path / "docs" / "migration" / "openpyxl-migration.md"
    migration.write_text(
        "supported-scope gate as currently green\n"
        "broader all-future-surface claim is still not ready\n"
        "tracked supported openpyxl API surface\n"
        f"{MIGRATION_BOUNDARY_TEXT}"
        "For everything else, v2.0 is a drop-in replacement.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/migration/openpyxl-migration.md",
        "line": 5,
        "phrase": "For everything else, v2.0 is a drop-in replacement.",
        "reason": "broad drop-in replacement claim is not scoped",
    } in report["issues"]


def test_public_claim_wording_blocks_complete_replacement_variant(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is a complete openpyxl replacement.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL is a complete openpyxl replacement.",
        "reason": "broad replacement wording is broader than the current audit",
    } in report["issues"]


def test_public_claim_wording_blocks_drop_in_compatible_variant(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    migration = tmp_path / "docs" / "migration" / "openpyxl-migration.md"
    migration.write_text(
        migration.read_text(encoding="utf-8")
        + "WolfXL is drop-in compatible with openpyxl.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/migration/openpyxl-migration.md",
        "line": 5,
        "phrase": "WolfXL is drop-in compatible with openpyxl.",
        "reason": "broad replacement wording is broader than the current audit",
    } in report["issues"]


def test_public_claim_wording_blocks_unhyphenated_drop_in_variants(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    docs_index = tmp_path / "docs" / "index.md"
    docs_index.write_text(
        "WolfXL is a drop in replacement for openpyxl.\n"
        "WolfXL is a drop in compatible openpyxl alternative.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/index.md",
        "line": 1,
        "phrase": "WolfXL is a drop in replacement for openpyxl.",
        "reason": "broad replacement wording is broader than the current audit",
    } in report["issues"]
    assert {
        "file": "docs/index.md",
        "line": 2,
        "phrase": "WolfXL is a drop in compatible openpyxl alternative.",
        "reason": "broad replacement wording is broader than the current audit",
    } in report["issues"]


def test_public_claim_wording_blocks_unscoped_drop_in_replacement_context(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    migration = tmp_path / "docs" / "migration" / "openpyxl-migration.md"
    migration.write_text(
        "supported-scope gate as currently green\n"
        "broader all-future-surface claim is still not ready\n"
        "tracked supported openpyxl API surface\n"
        f"{MIGRATION_BOUNDARY_TEXT}"
        "When migrating from openpyxl.\n"
        "WolfXL is intended as a drop-in replacement.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/migration/openpyxl-migration.md",
        "line": 6,
        "phrase": "WolfXL is intended as a drop-in replacement.",
        "reason": "broad replacement wording is broader than the current audit",
    } in report["issues"]


def test_public_claim_wording_allows_supported_scope_drop_in_replacement(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    migration = tmp_path / "docs" / "migration" / "openpyxl-migration.md"
    migration.write_text(
        "supported-scope gate as currently green\n"
        "broader all-future-surface claim is still not ready\n"
        "tracked supported openpyxl API surface\n"
        f"{MIGRATION_BOUNDARY_TEXT}"
        "For the tracked supported openpyxl API surface, v2.0 is intended "
        "as a drop-in replacement.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_scans_optional_launch_context(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    launch = tmp_path / "Plans" / "launch-posts.md"
    launch.parent.mkdir(parents=True, exist_ok=True)
    launch.write_text("WolfXL is a full openpyxl replacement.\n", encoding="utf-8")

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert report["scanned_context_files"] == ["Plans/launch-posts.md"]
    assert report["issues"] == [
        {
            "file": "Plans/launch-posts.md",
            "line": 1,
            "phrase": "WolfXL is a full openpyxl replacement.",
            "reason": "full replacement wording is broader than the current audit",
        }
    ]


def test_public_claim_wording_scans_root_changelog_context(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("WolfXL is a full openpyxl replacement.\n", encoding="utf-8")

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert report["scanned_context_files"] == ["CHANGELOG.md"]
    assert report["issues"] == [
        {
            "file": "CHANGELOG.md",
            "line": 1,
            "phrase": "WolfXL is a full openpyxl replacement.",
            "reason": "full replacement wording is broader than the current audit",
        }
    ]


def test_public_claim_wording_scans_mkdocs_metadata_context(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    mkdocs = tmp_path / "mkdocs.yml"
    mkdocs.write_text(
        "site_name: WolfXL\n"
        "site_description: WolfXL is the best Python Excel library.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert report["scanned_context_files"] == ["mkdocs.yml"]
    assert report["issues"] == [
        {
            "file": "mkdocs.yml",
            "line": 2,
            "phrase": "site_description: WolfXL is the best Python Excel library.",
            "reason": "best wording needs a measured supported-scope caveat",
        }
    ]


def test_public_claim_wording_scans_workflow_metadata_context(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    workflow = tmp_path / ".github" / "workflows" / "release.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: WolfXL is the best Python Excel library\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert report["scanned_context_files"] == [".github/workflows/release.yml"]
    assert report["issues"] == [
        {
            "file": ".github/workflows/release.yml",
            "line": 1,
            "phrase": "name: WolfXL is the best Python Excel library",
            "reason": "best wording needs a measured supported-scope caveat",
        }
    ]


def test_public_claim_wording_scans_public_trust_json_values(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    report_json = tmp_path / "docs" / "trust" / "final-sota-blockers.json"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps({"public_note": "WolfXL is better than openpyxl in every dimension."}),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert report["scanned_context_files"] == ["docs/trust/final-sota-blockers.json"]
    assert report["issues"] == [
        {
            "file": "docs/trust/final-sota-blockers.json",
            "line": 1,
            "phrase": "WolfXL is better than openpyxl in every dimension.",
            "reason": "every-dimension wording is broader than the current audit",
        }
    ]


def test_public_claim_wording_ignores_public_trust_json_keys(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    report_json = tmp_path / "docs" / "trust" / "final-sota-blockers.json"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps({"sota_claim_ready": False, "path": "docs/trust/final-sota-blockers.md"}),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True
    assert report["scanned_context_files"] == ["docs/trust/final-sota-blockers.json"]


def test_public_claim_wording_ignores_trust_freshness_hash_diff_strings(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    report_json = tmp_path / "docs" / "trust" / "trust-report-freshness-audit.json"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps(
            {
                "issues": [
                    (
                        "line 32: actual='| proof_flow_report | "
                        "`docs/performance/baselines/2026-06-04-sota-proof-flow-status.json` "
                        "| true | oldhash'; generated='| proof_flow_report | "
                        "`docs/performance/baselines/2026-06-04-sota-proof-flow-status.json` "
                        "| true | newhash'"
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True
    assert report["scanned_context_files"] == [
        "docs/trust/trust-report-freshness-audit.json"
    ]


def test_public_claim_wording_scans_release_coverage_json_values(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    report_json = tmp_path / "docs" / "trust" / "release-artifact-coverage-audit.json"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps({"public_note": "WolfXL is the best Python Excel library."}),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert report["scanned_context_files"] == [
        "docs/trust/release-artifact-coverage-audit.json"
    ]
    assert report["issues"] == [
        {
            "file": "docs/trust/release-artifact-coverage-audit.json",
            "line": 1,
            "phrase": "WolfXL is the best Python Excel library.",
            "reason": "best wording needs a measured supported-scope caveat",
        }
    ]


def test_public_claim_wording_discovers_claim_bearing_trust_json(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    report_json = tmp_path / "docs" / "trust" / "new-generated-trust-report.json"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps({"summary": "WolfXL is better than openpyxl in every dimension."}),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert report["scanned_context_files"] == [
        "docs/trust/new-generated-trust-report.json"
    ]
    assert report["issues"] == [
        {
            "file": "docs/trust/new-generated-trust-report.json",
            "line": 1,
            "phrase": "WolfXL is better than openpyxl in every dimension.",
            "reason": "every-dimension wording is broader than the current audit",
        }
    ]


def test_public_claim_wording_excludes_worker_report_json_discovery(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    worker_json = tmp_path / "docs" / "trust" / "worker-reports" / "scratch.json"
    worker_json.parent.mkdir(parents=True, exist_ok=True)
    worker_json.write_text(
        json.dumps({"summary": "WolfXL is better than openpyxl in every dimension."}),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True
    assert report["scanned_context_files"] == []


def test_public_claim_wording_discovers_package_context_files(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    root_cargo = tmp_path / "Cargo.toml"
    root_cargo.write_text(
        '[package]\ndescription = "Fast, openpyxl-compatible Excel I/O backed by Rust"\n',
        encoding="utf-8",
    )
    crate_readme = tmp_path / "crates" / "wolfxl-core" / "README.md"
    crate_readme.parent.mkdir(parents=True, exist_ok=True)
    crate_readme.write_text(
        "Best-effort style extraction for workbook previews.\n",
        encoding="utf-8",
    )
    crate_cargo = tmp_path / "crates" / "wolfxl-writer" / "Cargo.toml"
    crate_cargo.parent.mkdir(parents=True, exist_ok=True)
    crate_cargo.write_text(
        '[package]\ndescription = "Native writer with no rust_xlsxwriter dependency."\n',
        encoding="utf-8",
    )
    cli_cargo = tmp_path / "crates" / "wolfxl-cli" / "Cargo.toml"
    cli_cargo.parent.mkdir(parents=True, exist_ok=True)
    cli_cargo.write_text(
        '[package]\ndescription = "Spreadsheet previewer for AI agents."\n',
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True
    assert report["scanned_context_files"] == [
        "Cargo.toml",
        "crates/wolfxl-cli/Cargo.toml",
        "crates/wolfxl-core/README.md",
        "crates/wolfxl-writer/Cargo.toml",
    ]


def test_public_claim_wording_blocks_package_context_overclaim(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    crate_readme = tmp_path / "crates" / "wolfxl-core" / "README.md"
    crate_readme.parent.mkdir(parents=True, exist_ok=True)
    crate_readme.write_text(
        "WolfXL is the best Python Excel library.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert report["scanned_context_files"] == ["crates/wolfxl-core/README.md"]
    assert report["issues"] == [
        {
            "file": "crates/wolfxl-core/README.md",
            "line": 1,
            "phrase": "WolfXL is the best Python Excel library.",
            "reason": "best wording needs a measured supported-scope caveat",
        }
    ]


def test_public_claim_wording_blocks_industry_leading_workbook_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    crate_readme = tmp_path / "crates" / "wolfxl-core" / "README.md"
    crate_readme.parent.mkdir(parents=True, exist_ok=True)
    crate_readme.write_text(
        "WolfXL is the industry-leading Python workbook automation library.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "crates/wolfxl-core/README.md",
        "line": 1,
        "phrase": "WolfXL is the industry-leading Python workbook automation library.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_blocks_unscoped_marketing_superlatives(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is the ultimate Python Excel library.\n"
        + "WolfXL offers unmatched workbook automation.\n"
        + "WolfXL is the undisputed Excel library for Python.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    expected = [
        "WolfXL is the ultimate Python Excel library.",
        "WolfXL offers unmatched workbook automation.",
        "WolfXL is the undisputed Excel library for Python.",
    ]
    for offset, phrase in enumerate(expected, start=8):
        assert {
            "file": "docs/trust/public-evidence.md",
            "line": offset,
            "phrase": phrase,
            "reason": "best wording needs a measured supported-scope caveat",
        } in report["issues"]


def test_public_claim_wording_allows_measured_marketing_superlative_boundary(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + (
            "Measured supported-scope evidence shows unmatched Python Excel "
            "performance on the tracked benchmark lanes.\n"
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_discovers_unscoped_marketing_superlative_context(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    api_doc = tmp_path / "docs" / "api" / "new-marketing.md"
    api_doc.parent.mkdir(parents=True, exist_ok=True)
    api_doc.write_text(
        "WolfXL is the ultimate Python Excel library.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["scanned_context_files"] == ["docs/api/new-marketing.md"]
    assert {
        "file": "docs/api/new-marketing.md",
        "line": 1,
        "phrase": "WolfXL is the ultimate Python Excel library.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_blocks_broad_python_excel_superiority(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL dominates Python Excel automation.\n"
        + "WolfXL is better for Python Excel workflows.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL dominates Python Excel automation.",
        "reason": "broad superiority wording needs a measured supported-scope caveat",
    } in report["issues"]
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 9,
        "phrase": "WolfXL is better for Python Excel workflows.",
        "reason": "broad superiority wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_allows_measured_industry_leading_boundary(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + (
            "Measured supported-scope evidence shows industry-leading Python "
            "workbook automation on the tracked benchmark lanes.\n"
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_discovers_claim_bearing_docs_and_plans(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    api_doc = tmp_path / "docs" / "api" / "worksheet.md"
    api_doc.parent.mkdir(parents=True, exist_ok=True)
    api_doc.write_text(
        "WolfXL follows the tracked supported openpyxl API surface here.\n",
        encoding="utf-8",
    )
    rfc = tmp_path / "Plans" / "rfcs" / "999-new-rfc.md"
    rfc.parent.mkdir(parents=True, exist_ok=True)
    rfc.write_text(
        "Historical planning note, not current public claim.\n"
        "WolfXL is a full openpyxl replacement.\n",
        encoding="utf-8",
    )
    generated = tmp_path / "docs" / "trust" / "worker-reports" / "report.md"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(
        "WolfXL is a full openpyxl replacement.\n",
        encoding="utf-8",
    )
    generated_underscore = (
        tmp_path / "docs" / "trust" / "worker_reports" / "report.md"
    )
    generated_underscore.parent.mkdir(parents=True, exist_ok=True)
    generated_underscore.write_text(
        "WolfXL is a full openpyxl replacement.\n",
        encoding="utf-8",
    )
    perf_worker = (
        tmp_path / "docs" / "performance" / "worker_reports" / "report.md"
    )
    perf_worker.parent.mkdir(parents=True, exist_ok=True)
    perf_worker.write_text(
        "WolfXL is the fastest Excel library.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True
    assert "docs/api/worksheet.md" in report["scanned_context_files"]
    assert "Plans/rfcs/999-new-rfc.md" in report["scanned_context_files"]
    assert "docs/trust/worker-reports/report.md" not in report["scanned_context_files"]
    assert "docs/trust/worker_reports/report.md" not in report["scanned_context_files"]
    assert (
        "docs/performance/worker_reports/report.md"
        not in report["scanned_context_files"]
    )


def test_public_claim_wording_allows_best_effort_language(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    rfc = tmp_path / "Plans" / "rfcs" / "070-pivot-table-mutation.md"
    rfc.parent.mkdir(parents=True, exist_ok=True)
    rfc.write_text(
        "Foreign-authored pivot: reopen with openpyxl. Best-effort if the "
        "fixture has unsupported parser features.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True
    assert "Plans/rfcs/070-pivot-table-mutation.md" in report["scanned_context_files"]


def test_public_claim_wording_blocks_every_dimension_claim(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is better than openpyxl in every dimension.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL is better than openpyxl in every dimension.",
        "reason": "every-dimension wording is broader than the current audit",
    } in report["issues"]


def test_public_claim_wording_blocks_every_dimension_synonyms(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is better than openpyxl in all dimensions.\n"
        + "WolfXL is better than openpyxl in every way.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL is better than openpyxl in all dimensions.",
        "reason": "every-dimension wording is broader than the current audit",
    } in report["issues"]
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 9,
        "phrase": "WolfXL is better than openpyxl in every way.",
        "reason": "every-dimension wording is broader than the current audit",
    } in report["issues"]


def test_public_claim_wording_blocks_no_reason_variant(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is so good there is no reason to use openpyxl.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL is so good there is no reason to use openpyxl.",
        "reason": "no-reason-to-use-openpyxl wording is still gated",
    } in report["issues"]


def test_public_claim_wording_blocks_openpyxl_as_non_openpyxl_caveat_tool() -> None:
    issues = audit._line_issues(
        "docs/trust/limitations.md",
        (
            "| Pivot-table styling beyond PivotArea and pivot-CF | Limited | "
            "Keep openpyxl or a file-specific Excel review in the loop if "
            "that visual styling is business-critical. |\n"
        ),
    )

    assert {
        "file": "docs/trust/limitations.md",
        "line": 1,
        "phrase": (
            "| Pivot-table styling beyond PivotArea and pivot-CF | Limited | "
            "Keep openpyxl or a file-specific Excel review in the loop if "
            "that visual styling is business-critical. |"
        ),
        "reason": "non-openpyxl caveat should not recommend openpyxl as the fallback tool",
    } in issues


def test_public_claim_wording_blocks_no_need_openpyxl_variants(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "There is no need to use openpyxl.\n"
        + "There is no need for openpyxl.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "There is no need to use openpyxl.",
        "reason": "openpyxl-abandonment wording is still gated",
    } in report["issues"]
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 9,
        "phrase": "There is no need for openpyxl.",
        "reason": "openpyxl-abandonment wording is still gated",
    } in report["issues"]


def test_public_claim_wording_blocks_dont_need_openpyxl_variants(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "You don't need openpyxl anymore.\n"
        + "Teams do not need to use openpyxl now.\n"
        + "There is no need to keep using openpyxl.\n"
        + "Openpyxl is no longer necessary.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    expected = [
        "You don't need openpyxl anymore.",
        "Teams do not need to use openpyxl now.",
        "There is no need to keep using openpyxl.",
        "Openpyxl is no longer necessary.",
    ]
    for offset, phrase in enumerate(expected, start=8):
        assert {
            "file": "docs/trust/public-evidence.md",
            "line": offset,
            "phrase": phrase,
            "reason": "openpyxl-abandonment wording is still gated",
        } in report["issues"]


def test_public_claim_wording_strict_cli_fails_on_issues(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is better than openpyxl in every dimension.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "audit_public_claim_wording.py"),
            "--root",
            str(tmp_path),
            "--strict",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1


def test_public_claim_wording_blocks_no_reason_choose_variant(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "There is no reason for anyone to choose openpyxl now.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "There is no reason for anyone to choose openpyxl now.",
        "reason": "no-reason-to-use-openpyxl wording is still gated",
    } in report["issues"]


def test_public_claim_wording_blocks_openpyxl_abandonment_variants(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "Openpyxl is obsolete now that WolfXL exists.\n"
        + "You can stop using openpyxl.\n"
        + "Teams no longer need openpyxl.\n"
        + "Replace openpyxl everywhere with WolfXL.\n"
        + "WolfXL makes openpyxl unnecessary.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    expected = [
        "Openpyxl is obsolete now that WolfXL exists.",
        "You can stop using openpyxl.",
        "Teams no longer need openpyxl.",
        "Replace openpyxl everywhere with WolfXL.",
        "WolfXL makes openpyxl unnecessary.",
    ]
    for offset, phrase in enumerate(expected, start=4):
        assert {
            "file": "README.md",
            "line": offset,
            "phrase": phrase,
            "reason": "openpyxl-abandonment wording is still gated",
        } in report["issues"]


def test_public_claim_wording_blocks_migrate_off_openpyxl_variants(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "Migrate off openpyxl now.\n"
        + "Drop openpyxl from your stack.\n"
        + "Remove openpyxl from production pipelines.\n"
        + "Switch away from openpyxl.\n"
        + "Openpyxl is legacy.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    expected = [
        "Migrate off openpyxl now.",
        "Drop openpyxl from your stack.",
        "Remove openpyxl from production pipelines.",
        "Switch away from openpyxl.",
        "Openpyxl is legacy.",
    ]
    for offset, phrase in enumerate(expected, start=4):
        assert {
            "file": "README.md",
            "line": offset,
            "phrase": phrase,
            "reason": "openpyxl-abandonment wording is still gated",
        } in report["issues"]


def test_public_claim_wording_allows_guarded_openpyxl_removal_caveat(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    launch = tmp_path / "docs" / "trust" / "launch-claim-brief.md"
    launch.write_text(
        launch.read_text(encoding="utf-8")
        + "Do not remove openpyxl from a production pipeline until your own "
        "business-critical templates pass.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_blocks_soft_openpyxl_abandonment_variants(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL should be your default choice over openpyxl.\n"
        + "Choose WolfXL instead of openpyxl.\n"
        + "WolfXL is the obvious choice over openpyxl.\n"
        + "WolfXL makes openpyxl irrelevant.\n"
        + "Openpyxl is irrelevant now.\n"
        + "WolfXL obsoletes openpyxl.\n"
        + "WolfXL supersedes openpyxl.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    expected = [
        "WolfXL should be your default choice over openpyxl.",
        "Choose WolfXL instead of openpyxl.",
        "WolfXL is the obvious choice over openpyxl.",
        "WolfXL makes openpyxl irrelevant.",
        "Openpyxl is irrelevant now.",
        "WolfXL obsoletes openpyxl.",
        "WolfXL supersedes openpyxl.",
    ]
    for offset, phrase in enumerate(expected, start=4):
        assert {
            "file": "README.md",
            "line": offset,
            "phrase": phrase,
            "reason": "openpyxl-abandonment wording is still gated",
        } in report["issues"]


def test_public_claim_wording_blocks_broad_superiority_variants(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL is strictly better than openpyxl.\n"
        + "WolfXL beats openpyxl across the board.\n"
        + "WolfXL is the clear winner over openpyxl.\n"
        + "WolfXL is the superior Excel automation library.\n"
        + "WolfXL is superior to openpyxl.\n"
        + "WolfXL beats openpyxl everywhere.\n"
        + "WolfXL wins across all Excel workflows.\n"
        + "WolfXL is better for all Excel workflows.\n"
        + "WolfXL is better across all workbook workloads.\n"
        + "WolfXL leads Python Excel automation.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    expected = [
        "WolfXL is strictly better than openpyxl.",
        "WolfXL beats openpyxl across the board.",
        "WolfXL is the clear winner over openpyxl.",
        "WolfXL is the superior Excel automation library.",
        "WolfXL is superior to openpyxl.",
        "WolfXL beats openpyxl everywhere.",
        "WolfXL wins across all Excel workflows.",
        "WolfXL is better for all Excel workflows.",
        "WolfXL is better across all workbook workloads.",
        "WolfXL leads Python Excel automation.",
    ]
    for offset, phrase in enumerate(expected, start=4):
        assert {
            "file": "README.md",
            "line": offset,
            "phrase": phrase,
            "reason": "broad superiority wording needs a measured supported-scope caveat",
        } in report["issues"]


def test_public_claim_wording_allows_measured_superiority_context(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "In the measured supported-scope benchmark workflows, WolfXL is "
        "strictly better than openpyxl.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_blocks_unscoped_sota_claim(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL is SOTA for Excel automation.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": "WolfXL is SOTA for Excel automation.",
        "reason": "SOTA wording needs a supported-scope or not-ready boundary",
    } in report["issues"]


def test_public_claim_wording_blocks_unscoped_state_of_art_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL is state of the art for Excel automation.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": "WolfXL is state of the art for Excel automation.",
        "reason": "SOTA wording needs a supported-scope or not-ready boundary",
    } in report["issues"]


def test_public_claim_wording_requires_scoped_docs_metadata(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    docs_json = tmp_path / "docs" / "docs.json"
    docs_json.write_text(
        '{"description": "Rust-backed, openpyxl-compatible Excel library for Python. Up to 5x faster with one import change."}\n',
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/docs.json",
        "line": None,
            "phrase": "supported-scope performance evidence is fresh and source-relevant",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]
    assert {
        "file": "docs/docs.json",
        "line": None,
        "phrase": "all-future-surface SOTA remains gated",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_allows_supported_scope_sota_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
            + "The supported-scope SOTA gate is currently green for the measured, tracked workflow surface.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_blocks_unscoped_fastest_claim(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL is the fastest way to automate Excel from Python.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": "WolfXL is the fastest way to automate Excel from Python.",
        "reason": "fastest wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_allows_measured_fastest_claim(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "For the measured supported-scope benchmark workflows, WolfXL is the "
        "fastest option in this comparison.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_blocks_unmeasured_large_workbook_speed_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "Opening a 10M-cell file stays fast.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": "Opening a 10M-cell file stays fast.",
        "reason": "scale-speed wording needs measured workload evidence",
    } in report["issues"]


def test_public_claim_wording_blocks_unmeasured_instant_workbook_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL opens million-cell workbooks instantly.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": "WolfXL opens million-cell workbooks instantly.",
        "reason": "scale-speed wording needs measured workload evidence",
    } in report["issues"]


def test_public_claim_wording_allows_measured_large_workbook_speed_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "For the measured supported-scope benchmark workflows, WolfXL opened "
        "the sampled million-cell workbook within the dated benchmark target.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_blocks_unscoped_best_claim(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is the best Python Excel library.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL is the best Python Excel library.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_blocks_top_and_market_leading_claims(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is the top Python Excel library.\n"
        + "WolfXL is market-leading Excel automation.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL is the top Python Excel library.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 9,
        "phrase": "WolfXL is market-leading Excel automation.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_blocks_top_workbook_and_top_for_excel_claims(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is top for Excel automation.\n"
        + "WolfXL is the top workbook automation library.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL is top for Excel automation.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 9,
        "phrase": "WolfXL is the top workbook automation library.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_blocks_dominates_and_world_class_claims(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL dominates openpyxl.\n"
        + "WolfXL is world-class Excel automation.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL dominates openpyxl.",
        "reason": "broad superiority wording needs a measured supported-scope caveat",
    } in report["issues"]
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 9,
        "phrase": "WolfXL is world-class Excel automation.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_blocks_standard_and_leading_choice_claims(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is the new standard for Python Excel automation.\n"
        + "WolfXL is the gold standard for Python Excel automation.\n"
        + "WolfXL is the leading choice for workbook automation.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    expected = [
        "WolfXL is the new standard for Python Excel automation.",
        "WolfXL is the gold standard for Python Excel automation.",
        "WolfXL is the leading choice for workbook automation.",
    ]
    for offset, phrase in enumerate(expected, start=8):
        assert {
            "file": "docs/trust/public-evidence.md",
            "line": offset,
            "phrase": phrase,
            "reason": "best wording needs a measured supported-scope caveat",
        } in report["issues"]


def test_public_claim_wording_blocks_best_in_class_claim(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL is best-in-class Excel automation.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": "WolfXL is best-in-class Excel automation.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_blocks_best_choice_claim(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL is the best choice for Excel automation.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": "WolfXL is the best choice for Excel automation.",
        "reason": "best wording needs a measured supported-scope caveat",
    } in report["issues"]


def test_public_claim_wording_blocks_complete_excel_workflow_replacement(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL is a complete replacement for Python Excel workflows.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": "WolfXL is a complete replacement for Python Excel workflows.",
        "reason": "broad replacement wording is broader than the current audit",
    } in report["issues"]


def test_public_claim_wording_blocks_soft_openpyxl_replacement_variants(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL is the modern replacement for openpyxl.\n"
        + "WolfXL is the modern openpyxl replacement.\n"
        + "WolfXL is an openpyxl replacement for production Excel automation.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    expected = [
        "WolfXL is the modern replacement for openpyxl.",
        "WolfXL is the modern openpyxl replacement.",
        "WolfXL is an openpyxl replacement for production Excel automation.",
    ]
    for offset, phrase in enumerate(expected, start=4):
        assert {
            "file": "README.md",
            "line": offset,
            "phrase": phrase,
            "reason": "broad replacement wording is broader than the current audit",
        } in report["issues"]


def test_public_claim_wording_blocks_unscoped_only_library_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "WolfXL is the only library with this coverage.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/trust/public-evidence.md",
        "line": 8,
        "phrase": "WolfXL is the only library with this coverage.",
        "reason": "first/only ecosystem wording must stay scoped to comparison evidence",
    } in report["issues"]


def test_public_claim_wording_allows_scoped_only_library_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + "Inside the listed comparison scope, WolfXL is the only library with "
        "this measured workflow coverage.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_blocks_fresh_excelbench_snapshot_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "Fresh WolfXL 2.0 release-artifact evidence is available in ExcelBench: "
        "wheel-backed rerun.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": (
            "Fresh WolfXL 2.0 release-artifact evidence is available in ExcelBench: "
            "wheel-backed rerun."
        ),
        "reason": "dated ExcelBench release snapshots must not be described as fresh",
    } in report["issues"]


def test_public_claim_wording_blocks_future_surface_proof_claim(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "WolfXL has proven every future Excel surface.\n"
        + "WolfXL covers all future workbooks.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "README.md",
        "line": 4,
        "phrase": "WolfXL has proven every future Excel surface.",
        "reason": "future-surface proof wording is broader than current evidence",
    } in report["issues"]
    assert {
        "file": "README.md",
        "line": 5,
        "phrase": "WolfXL covers all future workbooks.",
        "reason": "future-surface proof wording is broader than current evidence",
    } in report["issues"]


def test_public_claim_wording_blocks_stale_release_note_truth_pass(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    release_notes = tmp_path / "docs" / "release-notes-2.0.md"
    release_notes.write_text(
        "supported-scope evidence is tracked in the trust reports.\n"
        "public first/only wording remains gated on the final truth pass.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/release-notes-2.0.md",
        "line": 2,
        "phrase": "public first/only wording remains gated on the final truth pass.",
        "reason": "stale launch truth-pass wording should name the current trust reports",
    } in report["issues"]


def test_public_claim_wording_blocks_stale_migration_truth_pass(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    migration = tmp_path / "docs" / "migration" / "openpyxl-migration.md"
    migration.write_text(
        "supported-scope gate as currently green\n"
        "broader all-future-surface claim is still not ready\n"
        "tracked supported openpyxl API surface\n"
        f"{MIGRATION_BOUNDARY_TEXT}"
        'Keep public "first/only" wording behind the final launch truth pass.\n',
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/migration/openpyxl-migration.md",
        "line": 5,
        "phrase": 'Keep public "first/only" wording behind the final launch truth pass.',
        "reason": "stale launch truth-pass wording should name the current trust reports",
    } in report["issues"]


def test_public_claim_wording_blocks_current_rust_gate_not_ready_wording(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    plan = tmp_path / "docs" / "performance" / "rust-competitor-benchmark-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "Current Rust comparison note.\n"
        "The Rust speed gate still fails.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/performance/rust-competitor-benchmark-plan.md",
        "line": 2,
        "phrase": "The Rust speed gate still fails.",
        "reason": "stale Rust-gate-not-ready wording should be marked historical",
    } in report["issues"]


def test_public_claim_wording_allows_historical_rust_gate_not_ready_wording(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    plan = tmp_path / "docs" / "performance" / "rust-competitor-benchmark-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "Historical optimization log.\n"
        "At that checkpoint, the Rust speed gate still fails.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_requires_historical_benchmark_boundary(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    benchmark_results = tmp_path / "docs" / "performance" / "benchmark-results.md"
    benchmark_results.parent.mkdir(parents=True, exist_ok=True)
    benchmark_results.write_text(
        "This page is historical context, not the final WolfXL 2.0 release proof.\n"
        "The numbers compare WolfXL with openpyxl.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/performance/benchmark-results.md",
        "line": None,
        "phrase": "including the required Rust/Rust-backed comparator set",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_requires_case_study_scope_boundary(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    case_study = tmp_path / "docs" / "case-study-synthgl.md"
    case_study.write_text(
        "SynthGL replaced openpyxl with WolfXL in one import change.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/case-study-synthgl.md",
        "line": None,
        "phrase": "not a Rust/Rust-backed competitor benchmark",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_blocks_stale_benchmark_pending_wording(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    release_notes = tmp_path / "docs" / "release-notes-2.0.md"
    release_notes.write_text(
        "Current release note.\n"
        "The speedup headline is withheld until the release benchmark refresh lands.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/release-notes-2.0.md",
        "line": 2,
        "phrase": (
            "The speedup headline is withheld until the release benchmark refresh lands."
        ),
        "reason": "stale benchmark-pending wording should point to current trust reports",
    } in report["issues"]


def test_public_claim_wording_allows_historical_benchmark_pending_wording(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    release_notes = tmp_path / "docs" / "release-notes-2.0.md"
    release_notes.write_text(
        "Historical planning note, not current public claim.\n"
        "The speedup headline is withheld until the release benchmark refresh lands.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_blocks_stale_rust_competitor_pending_wording(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    plan = tmp_path / "docs" / "performance" / "rust-competitor-benchmark-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "# Rust Competitor Benchmark Plan\n\n"
        "WolfXL cannot make a state-of-the-art claim from openpyxl comparisons alone.\n"
        "Before the claim audit can pass, WolfXL also needs benchmark evidence "
        "against the main Rust-based Excel libraries.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/performance/rust-competitor-benchmark-plan.md",
        "line": 4,
        "phrase": (
            "Before the claim audit can pass, WolfXL also needs benchmark evidence "
            "against the main Rust-based Excel libraries."
        ),
        "reason": "stale Rust competitor pending wording should point to current trust reports",
    } in report["issues"]


def test_public_claim_wording_allows_historical_rust_competitor_pending_wording(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    plan = tmp_path / "docs" / "performance" / "rust-competitor-benchmark-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "# Rust Competitor Benchmark Plan\n\n"
        "Historical checkpoint, not current evidence.\n"
        "Before the claim audit can pass, WolfXL also needs benchmark evidence "
        "against the main Rust-based Excel libraries.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_blocks_stale_release_lane_gating_wording(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    release_notes = tmp_path / "docs" / "release-notes-2.0.md"
    release_notes.write_text(
        "Current release-artifact coverage note.\n"
        "Windows wheel release-artifact coverage remains gated until the "
        "missing Windows lanes pass in CI.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert {
        "file": "docs/release-notes-2.0.md",
        "line": 2,
        "phrase": (
            "Windows wheel release-artifact coverage remains gated until the "
            "missing Windows lanes pass in CI."
        ),
        "reason": "stale release-lane gating wording should point to current trust reports",
    } in report["issues"]


def test_public_claim_wording_allows_historical_release_lane_gating_wording(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    release_notes = tmp_path / "docs" / "release-notes-2.0.md"
    release_notes.write_text(
        "Historical planning note, not current public claim.\n"
        "Windows wheel release-artifact coverage remains gated until the "
        "missing Windows lanes pass in CI.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_allows_gated_draft_claim_context(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    launch = tmp_path / "Plans" / "launch-posts.md"
    launch.parent.mkdir(parents=True, exist_ok=True)
    launch.write_text(
        "Draft only. Do not publish.\n"
        "WolfXL is a full openpyxl replacement.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True
    assert report["scanned_context_files"] == ["Plans/launch-posts.md"]


def test_public_claim_wording_allows_historical_file_level_context(tmp_path: Path) -> None:
    _write_public_claim_files(tmp_path)
    sprint = tmp_path / "Plans" / "sprint-nu.md"
    sprint.parent.mkdir(parents=True, exist_ok=True)
    sprint.write_text(
        "# Sprint Nu\n\n"
        "> Historical planning note: not current public claim evidence.\n\n"
        "After this sprint, call it a full openpyxl replacement.\n",
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True
    assert report["scanned_context_files"] == ["Plans/sprint-nu.md"]


def test_public_claim_wording_allows_explicitly_gated_no_reason_phrase(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        "Dated release-artifact benchmark snapshot\n"
            "Current supported-scope SOTA gate: green\n"
            "Overall all-future-surface SOTA claim: not ready\n"
            "fresh clean-source benchmark reruns are source-relevant\n"
        "dated 2026-04-28 WolfXL 2.0 wheel-backed ExcelBench rerun\n"
        "repo alias `xlsxwriter-rs`\n"
        "separate crates.io `xlsxwriter-rs` package\n"
        "Registered release-artifact lanes are proven, but not every future package route or installer.\n"
        "Openpyxl still has ecosystem maturity and long-tail workflow history.\n"
        "High-risk render variant space remains open-ended.\n"
        "Click-level Excel interaction variant space remains open-ended.\n"
        "Future or unseen real-world Excel surfaces cannot be fully exhausted.\n"
        "Still-unproven families "
        "unregistered_future_wheel_lanes "
        "installer_and_resolver_contexts "
        "alternate_distribution_channels "
        "workflow_topology_and_trigger_paths "
        "unsupported_openpyxl_api "
        "unvalidated_business_template "
        "olap_external_cache_or_pivot_visuals "
        "adjacent_spreadsheet_surfaces "
        "organizational_dependency_familiarity "
        "unseen_feature_edit_combinations "
        "template_specific_visual_acceptance "
        "excel_renderer_version_variants "
        "slicer_timeline_control_variants "
        "prompt_and_dialog_variants "
        "destructive_axis_external_tool_boundaries "
        "unseen_ooxml_part_families "
        "unseen_relationship_or_content_types "
        "future_excel_feature_extensions\n"
        '- Avoid until the strict audit is fully green: "there is no reason '
        'to keep using openpyxl."\n',
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_requires_current_rust_comparator_versions(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    _write_sota_audit_report(tmp_path)

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": None,
        "phrase": "calamine 0.35.0",
        "reason": "required Rust comparator version is missing from public evidence",
    } in report["issues"]


def test_public_claim_wording_accepts_current_rust_comparator_versions(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    _write_sota_audit_report(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        + (
            "\nRequired Rust comparators: rust_xlsxwriter 0.95.0, "
            "xlsxwriter 0.6.1 with repo alias `xlsxwriter-rs`, "
            "not the separate crates.io `xlsxwriter-rs` package, "
            "calamine 0.35.0.\n"
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is True


def test_public_claim_wording_requires_requested_name_resolution_details(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    _write_sota_audit_report(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8").replace(" at 0.1.0", ""),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": None,
        "phrase": "separate crates.io `xlsxwriter-rs` package at 0.1.0",
        "reason": "requested Rust comparator name resolution is missing from public evidence",
    } in report["issues"]


def test_public_claim_wording_requires_pypi_rust_backed_discovery_details(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    _write_sota_audit_report(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8")
        .replace("PyPI Rust-backed discovery fetched", "PyPI discovery ran")
        .replace(
            "0 unclassified PyPI Rust-backed discovery hits",
            "no unclassified PyPI hits",
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": None,
        "phrase": "PyPI Rust-backed discovery fetched",
        "reason": "PyPI Rust-backed discovery status is missing from public evidence",
    } in report["issues"]
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": None,
        "phrase": "0 unclassified PyPI Rust-backed discovery hits",
        "reason": "PyPI Rust-backed discovery triage result is missing from public evidence",
    } in report["issues"]


def test_public_claim_wording_requires_launch_rust_boundary_details(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    launch = tmp_path / "docs" / "trust" / "launch-claim-brief.md"
    launch.write_text(
        launch.read_text(encoding="utf-8")
        .replace("separate crates.io `xlsxwriter-rs` package at `0.1.0`\n", "")
        .replace("PyPI Rust-backed discovery fetched\n", ""),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/launch-claim-brief.md",
        "line": None,
        "phrase": "separate crates.io `xlsxwriter-rs` package at `0.1.0`",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]
    assert {
        "file": "docs/trust/launch-claim-brief.md",
        "line": None,
        "phrase": "PyPI Rust-backed discovery fetched",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_requires_launch_rust_comparator_versions(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    _write_sota_audit_report(tmp_path)
    launch = tmp_path / "docs" / "trust" / "launch-claim-brief.md"
    launch.write_text(
        launch.read_text(encoding="utf-8").replace("calamine 0.35.0", "calamine 0.28.0"),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/launch-claim-brief.md",
        "line": None,
        "phrase": "calamine 0.35.0",
        "reason": "required Rust comparator version is missing from launch claim brief",
    } in report["issues"]


def test_public_claim_wording_requires_final_blocker_release_details(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    final_blockers = tmp_path / "docs" / "trust" / "final-sota-blockers.md"
    final_blockers.write_text(
        final_blockers.read_text(encoding="utf-8").replace(
            "| Rust weak cases | 0 |\n",
            "",
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/final-sota-blockers.md",
        "line": None,
        "phrase": "| Rust weak cases | 0 |",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_requires_broad_boundary_invariant(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    _write_sota_audit_report(tmp_path)
    _write_public_claim_dimensions_report(
        tmp_path,
        expected_broad_claim_boundaries=[
            boundary
            for boundary in audit.EXPECTED_BROAD_CLAIM_BOUNDARIES
            if boundary != "future_real_world_excel_surfaces"
        ],
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/public-claim-dimensions-audit.json",
        "line": None,
        "phrase": "future_real_world_excel_surfaces",
        "reason": "expected broad claim boundary is missing from public dimensions audit",
    } in report["issues"]


def test_public_claim_wording_rejects_broad_boundary_gaps(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    _write_sota_audit_report(tmp_path)
    _write_public_claim_dimensions_report(
        tmp_path,
        expected_broad_claim_boundary_gap_count=1,
        expected_broad_claim_boundary_gaps=[
            {
                "claim_basis": "future_real_world_excel_surfaces",
                "reason": "missing blocker explanation",
            }
        ],
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/public-claim-dimensions-audit.json",
        "line": None,
        "phrase": "expected_broad_claim_boundary_gap_count",
        "reason": "public dimensions audit reports broad claim boundary gaps",
    } in report["issues"]
    assert {
        "file": "docs/trust/public-claim-dimensions-audit.json",
        "line": None,
        "phrase": "expected_broad_claim_boundary_gaps",
        "reason": "public dimensions audit includes broad claim boundary gap details",
    } in report["issues"]


def test_public_claim_wording_requires_public_boundary_plain_english(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    public_evidence = tmp_path / "docs" / "trust" / "public-evidence.md"
    public_evidence.write_text(
        public_evidence.read_text(encoding="utf-8").replace(
            "Openpyxl still has ecosystem maturity and long-tail workflow history. ",
            "",
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/trust/public-evidence.md",
        "line": None,
        "phrase": "Openpyxl still has ecosystem maturity and long-tail workflow history.",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_requires_migration_boundary_plain_english(
    tmp_path: Path,
) -> None:
    _write_public_claim_files(tmp_path)
    migration = tmp_path / "docs" / "migration" / "openpyxl-migration.md"
    migration.write_text(
        migration.read_text(encoding="utf-8").replace(
            "Openpyxl still has ecosystem maturity and long-tail workflow history. ",
            "",
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert report["ready"] is False
    assert {
        "file": "docs/migration/openpyxl-migration.md",
        "line": None,
        "phrase": "Openpyxl still has ecosystem maturity and long-tail workflow history.",
        "reason": "required public evidence boundary is missing",
    } in report["issues"]


def test_public_claim_wording_tolerates_unhealthy_final_sota_health_values(
    tmp_path: Path,
) -> None:
    # The health values depend on this audit's own result via proof-flow
    # headless_work_available; flagging them would make a transient wording
    # failure self-sustaining.
    _write_public_claim_files(tmp_path)
    blockers = tmp_path / "docs" / "trust" / "final-sota-blockers.md"
    blockers.write_text(
        blockers.read_text(encoding="utf-8")
        .replace(
            "| Final blocker audit healthy | true |",
            "| Final blocker audit healthy | false |",
        )
        .replace(
            "| Audit failed checks | none |",
            "| Audit failed checks | no_direct_headless_work_remains |",
        ),
        encoding="utf-8",
    )

    report = audit.audit_public_claims(tmp_path)

    assert not [
        issue
        for issue in report["issues"]
        if issue.get("file") == "docs/trust/final-sota-blockers.md"
    ]


def _write_public_claim_files(root: Path) -> None:
    payload_by_file = {
        "README.md": (
            "supported-scope gate is currently green; documented pivot caveats; "
            "The measured Rust/Rust-backed benchmark gate is separate from this table. "
            "rust_xlsxwriter 0.95.0; xlsxwriter 0.6.1; "
            "repo alias `xlsxwriter-rs`; calamine 0.35.0; "
            "umya-spreadsheet 3.0.0; fastexcel 0.20.2; "
            "python-calamine 0.6.2\n"
            "broader all-future-surface SOTA claim is still not ready; "
            "Public Evidence Status; external-link refresh behavior\n"
            "Dated WolfXL 2.0 release-artifact evidence with 67 functions "
            "across 7 categories; | **Date / Time** (12) |\n"
        ),
        "pyproject.toml": 'description = "openpyxl-compatible Excel I/O"\n',
        "docs/docs.json": (
            '{"description": "Rust-backed, openpyxl-compatible Excel library for Python. '
            'Current supported-scope performance evidence is fresh and source-relevant; '
            'the all-future-surface SOTA remains gated."}\n'
        ),
        "docs/case-study-synthgl.md": (
            "Case-study boundary: this is one GL export workload, not universal SOTA proof.\n"
            "It compares WolfXL with openpyxl for SynthGL's measured write/read path.\n"
            "It is not a Rust/Rust-backed competitor benchmark, and it is not proof "
            "that every current or future Excel workflow should move to WolfXL.\n"
        ),
        "docs/index.md": "# Docs\n",
        "docs/performance/benchmark-results.md": (
            "This page is historical context, not the final WolfXL 2.0 release proof.\n"
            "Current claim boundary: the current supported-scope SOTA gate is green "
            "in the trust reports, including the required Rust/Rust-backed comparator set, "
            "but the overall all-future-surface SOTA claim is still not ready. "
            "Do not use this historical v1.7 page as proof.\n"
        ),
        "docs/performance/baselines/2026-06-05-current-sota-claim-audit.md": (
            "| Overall SOTA claim ready | false |\n"
            "| Supported-scope SOTA gate ready | true |\n"
            "| Rust competitor gate ready | true |\n"
            "| Exhaustive all-future-surface claim ready | false |\n"
            "| Next required proof mode | none |\n"
            "The required Rust/Rust-backed comparator set is current and complete.\n"
            "The remaining SOTA blocker is the open-ended exhaustiveness boundary, "
            "not a missing queued evidence report.\n"
        ),
        "docs/performance/baselines/2026-06-05-rust-competitor-set-live-recheck.md": (
            "- Ready: `true`\n"
            "## Required Benchmark Competitors\n"
            "| calamine | crates.io |\n"
            "| rust_xlsxwriter | crates.io |\n"
            "| xlsxwriter | crates.io | xlsxwriter-rs |\n"
            "| umya-spreadsheet | crates.io |\n"
            "| fastexcel | crates.io |\n"
            "| python-calamine | pypi |\n"
            "| Missing competitors | none |\n"
            "| Missing resolved versions | none |\n"
            "| Missing required case families | 0 |\n"
            "## Requested Competitor Name Resolution\n"
            "| xlsxwriter-rs | watchlist | 0.1.0 | remain_watchlist | xlsxwriter |\n"
            "## Watchlist Promotion Review\n"
            "| Promotion review ready | yes |\n"
            "| Missing adoption evidence | none |\n"
        ),
        "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/README.md": (
            "The backlog is now consumed.\n"
            "The Rust comparison gate is ready, and the current supported OOXML evidence "
            "bundle is ready. The remaining SOTA blocker is narrower and more honest "
            "than an unfinished batch: "
            "WolfXL still cannot prove that every possible future Excel surface has no gap.\n"
            "docs/performance/baselines/2026-06-05-current-sota-claim-audit.json\n"
            "docs/performance/baselines/2026-06-05-current-sota-claim-audit.md\n"
            "`none` as the next required proof mode\n"
        ),
        "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/sota-proof-flow-status.md": (
            "# WolfXL SOTA Proof Flow Status (Supported Scope Ready; Broad Claim Not Ready)\n"
            "| Ready | false |\n"
            "| Current phase | final_sota_audit_blockers |\n"
            "| Excel approval required | false |\n"
            "| Headless work available | false |\n"
            "supported-scope SOTA is ready\n"
            "exhaustive no-gap claim is still unproven\n"
            "| All-future SOTA claim still gated | true |\n"
            "| Required Rust competitors | rust_xlsxwriter, xlsxwriter, calamine, "
            "umya-spreadsheet, fastexcel, python-calamine |\n"
        ),
        "docs/fidelity/evidence/2026-05-31-current-evidence-recovery-plan/sota-proof-operator-checklist.md": (
            "# SOTA Proof Operator Checklist (Supported Scope Ready; Broad Claim Not Ready)\n"
            "This checklist is historical provenance for the evidence recovery batch.\n"
            "The current supported OOXML evidence bundle is ready.\n"
            "The remaining SOTA blocker is the open-ended exhaustiveness boundary.\n"
            "The reports still cannot prove that every future or unseen Excel surface has no gap.\n"
            "`sota-proof-flow-status.md`, which keeps the broad all-future SOTA claim gated.\n"
        ),
        "docs/migration/openpyxl-migration.md": (
            "supported-scope gate as currently green\n"
            "broader all-future-surface claim is still not ready\n"
            "tracked supported openpyxl API surface\n"
            f"{MIGRATION_BOUNDARY_TEXT}"
        ),
        "docs/trust/public-evidence.md": (
            "Dated release-artifact benchmark snapshot\n"
            "Current supported-scope SOTA gate: green; fresh clean-source benchmark reruns are source-relevant\n"
            "Overall all-future-surface SOTA claim: not ready\n"
            "dated 2026-04-28 WolfXL 2.0 wheel-backed ExcelBench rerun\n"
            "repo alias `xlsxwriter-rs`\n"
            "separate crates.io `xlsxwriter-rs` package at 0.1.0; "
            "PyPI Rust-backed discovery fetched; "
            "0 unclassified PyPI Rust-backed discovery hits; "
            "Registered release-artifact lanes are proven, but not every future package route or installer. "
            "Openpyxl still has ecosystem maturity and long-tail workflow history. "
            "High-risk render variant space remains open-ended. "
            "Click-level Excel interaction variant space remains open-ended. "
            "Future or unseen real-world Excel surfaces cannot be fully exhausted. "
            "Still-unproven families "
            "unregistered_future_wheel_lanes "
            "installer_and_resolver_contexts "
            "alternate_distribution_channels "
            "workflow_topology_and_trigger_paths "
            "unsupported_openpyxl_api "
            "unvalidated_business_template "
            "olap_external_cache_or_pivot_visuals "
            "adjacent_spreadsheet_surfaces "
            "organizational_dependency_familiarity "
            "unseen_feature_edit_combinations "
            "template_specific_visual_acceptance "
            "excel_renderer_version_variants "
            "slicer_timeline_control_variants "
            "prompt_and_dialog_variants "
            "destructive_axis_external_tool_boundaries "
            "unseen_ooxml_part_families "
            "unseen_relationship_or_content_types "
            "future_excel_feature_extensions\n"
            '- Avoid until the strict audit is fully green: "there is no reason '
            'to keep using openpyxl."\n'
        ),
        "docs/trust/launch-claim-brief.md": (
            "supported-scope SOTA gate is currently green\n"
            "broader all-future-surface SOTA claim is still not ready\n"
            "## When To Keep Openpyxl Alongside\n"
            "business-critical template\n"
            "not listed as supported in the compatibility matrix\n"
            "rust_xlsxwriter 0.95.0\n"
            "xlsxwriter 0.6.1\n"
            "calamine 0.35.0\n"
            "repo alias `xlsxwriter-rs`\n"
            "separate crates.io `xlsxwriter-rs` package at `0.1.0`\n"
            "PyPI Rust-backed discovery fetched\n"
            "unclassified PyPI Rust-backed discovery hits\n"
            "Registered release-artifact lanes are proven, but not every future package route or installer.\n"
            "Openpyxl still has ecosystem maturity and long-tail workflow history.\n"
            "High-risk render variant space remains open-ended.\n"
            "Click-level Excel interaction variant space remains open-ended.\n"
            "Future or unseen real-world Excel surfaces cannot be fully exhausted.\n"
            "organizational dependency familiarity\n"
            "staff familiarity\n"
            "future wheel lanes\n"
            "installer/resolver contexts\n"
            "alternate distribution channels\n"
            "workflow trigger paths\n"
            "Unsupported openpyxl APIs\n"
            "unvalidated business templates\n"
            "OLAP/external pivot caches\n"
            "adjacent spreadsheet surfaces\n"
            "Unseen feature-edit combinations\n"
            "template-specific visual acceptance\n"
            "Excel renderer version variants\n"
            "Slicer/timeline/control variants\n"
            "prompt/dialog variants\n"
            "destructive-axis external-tool boundaries\n"
            "Unseen OOXML part families\n"
            "unseen relationship/content types\n"
            "future Excel feature extensions\n"
            'Avoid: "There is no reason to keep using openpyxl."\n'
            'Avoid: "WolfXL is better in every dimension."\n'
            "tracked supported openpyxl API surface\n"
        ),
        "docs/trust/public-claim-dimensions-audit.md": (
            "| Broad no-reason claim ready | false |\n"
            "| Supported-scope ready | true |\n"
            "| Not fully proven | 7 |\n"
            "| Promising but not fully proven | 3 |\n"
            "| Blocked on Excel evidence | 0 |\n"
            "| Blocked on other required evidence | 0 |\n"
            "| Known limitations | 4 |\n"
            "| Expected broad claim boundaries | 5 |\n"
            "| Expected broad claim boundary gaps | 0 |\n"
            "| Expected broad claim boundary ids | all_click_level_interaction_variants, "
            "all_high_risk_render_variants, cross_platform_release_artifact_coverage, "
            "ecosystem_maturity_and_long_tail_workflows, future_real_world_excel_surfaces |\n"
            "## Input Reports\n"
            "| sota_report |\n"
            "| public_claim_report |\n"
            "## Rust Competitor Evidence\n"
            "| xlsxwriter lane |\n"
            "| Required aliases |\n"
            "| Current audit competitor versions |\n"
            "| Competitor-set report |\n"
            "| Competitor-set versions |\n"
            "| Missing required case families | 0 |\n"
            "| Competitor-set missing required case families | 0 |\n"
            "| Competitor-set missing benchmark competitors | none |\n"
            "| Competitor-set missing benchmark versions | none |\n"
            "| Competitor-set unclassified discovery hits | 0 |\n"
            "| Competitor-set unclassified PyPI Rust-backed hits | 0 |\n"
            "## Requested Rust Name Resolution\n"
            "## Python Public API vs Direct Rust\n"
            "| Public cross-surface weak cases | 0 |\n"
            "| Claim basis counts |\n"
            "## Rust Memory Evidence\n"
            "| Current audit Rust memory comparison rows | 18 |\n"
            "| Current audit Rust weak memory cases | 0 |\n"
            "| Release-artifact Rust memory comparison rows | 17 |\n"
            "| Release-artifact Rust weak memory cases | 0 |\n"
            "## Release Artifact Evidence\n"
            "| Full release-artifact rerun ready | true |\n"
            "| Wheel metadata ready | true |\n"
            "| Wheel SHA-256 |\n"
            "| Wheel size bytes |\n"
            "| Source git dirty | false |\n"
            "| Report repo git SHA |\n"
            "| Report repo git dirty | false |\n"
            "| Generator script source |\n"
            "| OpenPyXL speed ready | true |\n"
            "| OpenPyXL memory ready | true |\n"
            "| OpenPyXL weak memory cases | 0 |\n"
            "| Rust superiority ready | true |\n"
            "| Rust memory ready | true |\n"
            "| Rust weak memory rows | 0 |\n"
            "| Rust skipped required competitors | none |\n"
        ),
        "docs/trust/release-artifact-smoke.md": (
            "| Ready | true |\n"
            "| Wheel SHA-256 |\n"
            "| Wheel size bytes |\n"
            "| Enabled backends |\n"
            "Headless local wheel build and fresh-venv smoke only.\n"
            "It does not replace cross-platform wheel CI or release-artifact benchmark reruns.\n"
        ),
        "docs/trust/release-artifact-sdist-smoke.md": (
            "| Ready | true |\n"
            "| Sdist SHA-256 |\n"
            "| Sdist size bytes |\n"
            "| Enabled backends |\n"
            "Headless local sdist build and fresh-venv install smoke only.\n"
            "This proves the source distribution lane from the recorded committed source.\n"
        ),
        "docs/trust/release-artifact-benchmark-smoke.md": (
            "| Ready | true |\n"
            "| Broad speed superiority ready | true |\n"
            "This is not the full release-artifact SOTA benchmark grid.\n"
        ),
        "docs/trust/release-artifact-benchmark-rerun.md": (
            "| Profile | full |\n"
            "| Full release-artifact rerun ready | true |\n"
            "| Openpyxl memory ready | true |\n"
            "| Openpyxl weak memory rows | 0 |\n"
            "| Rust superiority ready | true |\n"
            "| Wheel SHA-256 |\n"
            "| Wheel size bytes |\n"
            "| Rust claim basis counts |\n"
        ),
        "docs/trust/final-sota-blockers.md": (
            "| Final blocker audit healthy | true |\n"
            "| Final broad claim ready | false |\n"
            "| Audit failed checks | none |\n"
            "| Release-artifact benchmark rerun ready | true |\n"
            "| SOTA claim ready | false |\n"
            "| Supported-scope ready | true |\n"
            "| Remaining direct headless steps | 12 |\n"
            "| Remaining deferred Excel steps | 0 |\n"
            "| Proof-flow current phase | final_sota_audit_blockers |\n"
            "| Proof-flow headless work available | true |\n"
            "| Proof-flow Excel approval required | false |\n"
            "## Input Reports\n"
            "| sota_report |\n"
            "| dimensions_report |\n"
            "## Rust Gate Evidence\n"
            "| User-requested competitor names |\n"
            "| User-requested competitor names satisfied | true |\n"
            "| User-requested competitor name blockers | none |\n"
            "| xlsxwriter lane |\n"
            "| Required aliases |\n"
            "| Current audit missing required case families | 0 |\n"
            "| Competitor-set missing required case families | 0 |\n"
            "| Competitor-set missing benchmark competitors | none |\n"
            "| Competitor-set missing benchmark versions | none |\n"
            "| Competitor-set stale benchmark versions | none |\n"
            "| Competitor-set unclassified discovery hits | 0 |\n"
            "| Competitor-set unclassified PyPI Rust-backed hits | 0 |\n"
            "## Requested Rust Name Resolution\n"
            "## User-Requested Rust Competitor Coverage\n"
            "## Remaining Shortcomings Inventory\n"
            "| cross_platform_release_artifact_coverage | promising_but_not_fully_proven | false |\n"
            "| ecosystem_maturity_and_long_tail_workflows | known_limitation | false |\n"
            "| all_high_risk_render_variants | known_limitation | false |\n"
            "| all_click_level_interaction_variants | known_limitation | false |\n"
            "| future_real_world_excel_surfaces | known_limitation | false |\n"
            "## Release Artifact Evidence\n"
            "| Full release-artifact rerun ready | true |\n"
            "| Wheel metadata ready | true |\n"
            "| OpenPyXL memory ready | true |\n"
            "| OpenPyXL weak speed cases | 0 |\n"
            "| OpenPyXL weak memory cases | 0 |\n"
            "| Rust weak cases | 0 |\n"
            "| Rust skipped required competitors | none |\n"
            "all_high_risk_render_variants\n"
            "all_click_level_interaction_variants\n"
            "unbounded_future_surface_boundary\n"
            "| Current audit competitor versions |\n"
            "| Competitor-set versions |\n"
            "| Release artifact versions |\n"
            "## Evidence Bundle\n"
            "| Report count |\n"
            "| Producer lane counts |\n"
            "| Wheel SHA-256 |\n"
            "| Wheel size bytes |\n"
            "| Source git SHA |\n"
            "| Report repo git SHA |\n"
            "| Report repo git dirty |\n"
            "| Generator script source |\n"
        ),
        "docs/trust/sota-snapshot-wording-audit.md": (
            "| Ready | true |\n"
            "| Current proof docs | 5 |\n"
            "| Issue count | 0 |\n"
            "## Current Proof Docs\n"
            "## Snapshot Archive Status\n"
            "Current snapshot\n"
        ),
        "docs/trust/followup-claim-blockers-audit.md": (
            "| Ready | true |\n"
            "| Open claim blocker notes | 0 |\n"
            "| Issue count | 0 |\n"
            "## Follow-ups\n"
        ),
        "docs/trust/historical-claim-wording-audit.md": (
            "| Ready | true |\n"
            "| Issue count | 0 |\n"
            "## Files\n"
            "## Issues\n"
        ),
        "docs/trust/trust-report-freshness-audit.md": (
            "| Ready | true |\n"
            "| Issue count | 0 |\n"
            "public_claim_dimensions\n"
            "final_sota_blockers\n"
        ),
        "docs/trust/limitations.md": (
            "# Limitations\n"
            "Pivot cache record regeneration after layout edits\n"
            "Pivot-table styling beyond PivotArea and pivot-CF\n"
            "External-link cached data is not dereferenced\n"
            "does not follow linked workbooks to refresh those values\n"
        ),
    }
    for relative, payload in payload_by_file.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def _write_sota_audit_report(root: Path) -> None:
    path = root / audit.SOTA_AUDIT_REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """{
  "sota_claim_ready": false,
  "supported_scope_sota_gate_ready": true,
  "rust_competitor_set": {
    "required_competitors": ["rust_xlsxwriter", "xlsxwriter", "calamine"],
    "required_competitor_aliases": {"xlsxwriter": ["xlsxwriter-rs"]},
    "benchmark_competitor_versions": {
      "rust_xlsxwriter": "0.95.0",
      "xlsxwriter": "0.6.1",
      "calamine": "0.35.0"
    },
    "requested_competitor_name_resolutions": [
      {
        "requested_name": "xlsxwriter-rs",
        "exact_package": "xlsxwriter-rs",
        "exact_package_version": "0.1.0",
        "requirement_satisfied": true
      }
    ],
    "pypi_discovery_fetched": true,
    "unclassified_pypi_discovery_hit_count": 0
  }
}
""",
        encoding="utf-8",
    )


def _write_public_claim_dimensions_report(
    root: Path,
    *,
    broad_no_reason_claim_ready: bool = False,
    supported_scope_ready: bool = True,
    expected_broad_claim_boundaries: list[str] | None = None,
    expected_broad_claim_boundary_gap_count: int = 0,
    expected_broad_claim_boundary_gaps: list[dict[str, str]] | None = None,
) -> None:
    path = root / audit.PUBLIC_DIMENSIONS_AUDIT_REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "broad_no_reason_claim_ready": broad_no_reason_claim_ready,
        "supported_scope_ready": supported_scope_ready,
        "expected_broad_claim_boundaries": (
            expected_broad_claim_boundaries
            if expected_broad_claim_boundaries is not None
            else list(audit.EXPECTED_BROAD_CLAIM_BOUNDARIES)
        ),
        "expected_broad_claim_boundary_gap_count": (
            expected_broad_claim_boundary_gap_count
        ),
        "expected_broad_claim_boundary_gaps": (
            expected_broad_claim_boundary_gaps
            if expected_broad_claim_boundary_gaps is not None
            else []
        ),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
