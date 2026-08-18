"""Layer 3 — semantic diff via ``tests/parity/_scoring.py`` (BLOCKING on HARD).

Reuses the ``DIMENSION_TIERS`` / ``ParityReport`` machinery from the read
parity harness — same scoring, same tiers, same fuzzy-equality rules. The
only delta is that both inputs are openpyxl workbooks (not openpyxl-vs-wolfxl).

HARD-tier failures fail the test; SOFT-tier mismatches are recorded but not
fatal (the existing ratchet pattern from ``tests/parity/`` keeps them
bounded). INFO-tier is informational only.
"""
from __future__ import annotations

from pathlib import Path

from tests.parity._scoring import ParityReport, compare_two_workbooks


def compute_report(oracle_path: Path, native_path: Path) -> ParityReport:
    """Return the full ``ParityReport`` (HARD + SOFT + INFO mismatches)."""
    return compare_two_workbooks(oracle_path, native_path)


def assert_semantic_clean(oracle_path: Path, native_path: Path) -> None:
    """Assert no HARD-tier semantic differences. SOFT/INFO not asserted here."""
    report = compute_report(oracle_path, native_path)
    hard = report.hard_failures()
    if hard:
        # Cap the message so it stays readable in pytest output.
        head = hard[:20]
        tail_n = len(hard) - len(head)
        body = "\n".join(str(m) for m in head)
        suffix = f"\n... +{tail_n} more" if tail_n > 0 else ""
        raise AssertionError(
            f"{len(hard)} Layer 3 HARD-tier mismatches "
            f"({oracle_path.name} vs {native_path.name}):\n{body}{suffix}"
        )
