from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_historical_claim_wording.py"
    spec = importlib.util.spec_from_file_location("audit_historical_claim_wording", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def test_historical_claim_wording_current_repo_is_ready() -> None:
    report = audit.audit_historical_claim_wording()

    assert report["ready"] is True
    assert report["issue_count"] == 0


def test_historical_claim_wording_flags_quotable_overclaim(tmp_path: Path) -> None:
    path = tmp_path / "Plans" / "sprint-nu.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "> Historical planning note: not current public claim evidence.\n\n"
        "Headline target: full openpyxl replacement, period.\n",
        encoding="utf-8",
    )

    report = audit.audit_historical_claim_wording(tmp_path)
    markdown = audit.format_markdown(report)

    assert report["ready"] is False
    assert report["issue_count"] == 1
    assert report["issues"][0]["file"] == "Plans/sprint-nu.md"
    assert report["issues"][0]["phrase"] == "full openpyxl replacement"
    assert "| Issue count | 1 |" in markdown


def test_historical_claim_wording_flags_first_only_library_wording(tmp_path: Path) -> None:
    path = tmp_path / "Plans" / "worktree-branch-audit.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "> Historical planning note: not current public claim evidence.\n\n"
        "Launch draft: the only Python OOXML library with pivotCacheRecords.\n",
        encoding="utf-8",
    )

    report = audit.audit_historical_claim_wording(tmp_path)

    assert report["ready"] is False
    assert report["issue_count"] == 1
    assert report["issues"][0]["file"] == "Plans/worktree-branch-audit.md"
    assert report["issues"][0]["phrase"] == "first/only Python OOXML library"


def test_historical_claim_wording_allows_scoped_rewrite(tmp_path: Path) -> None:
    path = tmp_path / "Plans" / "sprint-nu.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "> Historical planning note: not current public claim evidence.\n\n"
        "Historical target was a broad replacement claim, superseded by "
        "docs/trust/launch-claim-brief.md.\n",
        encoding="utf-8",
    )

    report = audit.audit_historical_claim_wording(tmp_path)

    assert report["ready"] is True
