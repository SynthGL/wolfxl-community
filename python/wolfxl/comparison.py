"""Path-free public models for workbook fidelity comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkbookIdentity:
    """Path-free identity for one compared workbook."""

    filename: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, str | int]:
        """Return a JSON-safe, path-free identity."""
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class WorkbookComparison:
    """Immutable, path-free result of one Guard fidelity comparison."""

    status: str
    passed: bool
    issue_count: int
    issue_codes: tuple[str, ...]
    issue_categories: tuple[str, ...]
    before: WorkbookIdentity
    after: WorkbookIdentity

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe comparison summary."""
        return {
            "status": self.status,
            "passed": self.passed,
            "issue_count": self.issue_count,
            "issue_codes": list(self.issue_codes),
            "issue_categories": list(self.issue_categories),
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
        }
