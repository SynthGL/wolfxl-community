from __future__ import annotations

import importlib.util
import json
import sys
from base64 import b64decode
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "audit_ooxml_render_page_multiset_equivalence.py"
    )
    spec = importlib.util.spec_from_file_location(
        "audit_ooxml_render_page_multiset_equivalence", script
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()

BLACK_PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGNgYGD4DwABBAEA"
    "gh9eJgAAAABJRU5ErkJggg=="
)
WHITE_PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/"
    "pLvAAAAAElFTkSuQmCC"
)


def _write_report(
    tmp_path: Path,
    *,
    side: str,
    fixture: str,
    mutation: str,
    status: str = "rendered",
    prefix: str,
    page_count: int | None = None,
    compared_page_count: int | None = None,
) -> tuple[Path, Path]:
    work = tmp_path / side / fixture / mutation
    pdf_dir = work / f"{prefix}-pdf"
    pdf_dir.mkdir(parents=True)
    pdf = pdf_dir / f"{prefix}-{fixture}.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    report = tmp_path / f"{side}-render-report.json"
    result = {
        "fixture": f"{fixture}.xlsx",
        "mutation": mutation,
        "status": status,
        f"{prefix}_pdf": str(pdf),
    }
    if page_count is not None:
        result["page_count"] = page_count
    if compared_page_count is not None:
        result["compared_page_count"] = compared_page_count
    report.write_text(json.dumps({"results": [result]}))
    return report, work


def test_page_multiset_equivalence_accepts_reordered_pages(tmp_path: Path) -> None:
    left_report, left_work = _write_report(
        tmp_path,
        side="left",
        fixture="book",
        mutation="copy_first_sheet",
        prefix="after",
    )
    right_report, right_work = _write_report(
        tmp_path,
        side="right",
        fixture="book-native",
        mutation="no_op",
        prefix="before",
    )
    (left_work / "after-pages-1-01.png").write_bytes(BLACK_PNG)
    (left_work / "after-pages-2-02.png").write_bytes(WHITE_PNG)
    (right_work / "before-pages-1-01.png").write_bytes(WHITE_PNG)
    (right_work / "before-pages-2-02.png").write_bytes(BLACK_PNG)

    result = audit.audit_render_page_multiset_equivalence(
        left_report,
        right_report,
        left_mutation="copy_first_sheet",
        right_mutation="no_op",
    )

    assert result["ready"] is True
    assert result["passed_count"] == 1
    assert result["results"][0]["left_page_count"] == 2
    assert result["results"][0]["right_page_count"] == 2
    assert result["results"][0]["differing_hash_count"] == 0
    assert {"left_page": 1, "right_page": 2} in result["results"][0]["remapped_pages"]


def test_page_multiset_equivalence_fails_different_pages(tmp_path: Path) -> None:
    left_report, left_work = _write_report(
        tmp_path,
        side="left",
        fixture="book",
        mutation="copy_first_sheet",
        prefix="after",
    )
    right_report, right_work = _write_report(
        tmp_path,
        side="right",
        fixture="book-native",
        mutation="no_op",
        prefix="before",
    )
    (left_work / "after-pages-1-01.png").write_bytes(BLACK_PNG)
    (right_work / "before-pages-1-01.png").write_bytes(WHITE_PNG)

    result = audit.audit_render_page_multiset_equivalence(
        left_report,
        right_report,
        left_mutation="copy_first_sheet",
        right_mutation="no_op",
    )

    assert result["ready"] is False
    assert result["failure_count"] == 1
    assert result["results"][0]["status"] == "failed"
    assert result["results"][0]["differing_hash_count"] == 2


def test_page_multiset_equivalence_rejects_sampled_reports(tmp_path: Path) -> None:
    left_report, left_work = _write_report(
        tmp_path,
        side="left",
        fixture="book",
        mutation="copy_first_sheet",
        status="sampled_rendered",
        prefix="after",
    )
    right_report, right_work = _write_report(
        tmp_path,
        side="right",
        fixture="book-native",
        mutation="no_op",
        prefix="before",
    )
    (left_work / "after-pages-1-01.png").write_bytes(BLACK_PNG)
    (right_work / "before-pages-1-01.png").write_bytes(BLACK_PNG)

    result = audit.audit_render_page_multiset_equivalence(
        left_report,
        right_report,
        left_mutation="copy_first_sheet",
        right_mutation="no_op",
    )

    assert result["ready"] is False
    assert result["inconclusive_count"] == 1
    assert result["results"][0]["status"] == "inconclusive"
    assert "sampled" in result["results"][0]["message"]


def test_page_multiset_equivalence_rejects_incomplete_page_exports(
    tmp_path: Path,
) -> None:
    left_report, left_work = _write_report(
        tmp_path,
        side="left",
        fixture="book",
        mutation="copy_first_sheet",
        prefix="after",
        page_count=2,
        compared_page_count=2,
    )
    right_report, right_work = _write_report(
        tmp_path,
        side="right",
        fixture="book-native",
        mutation="no_op",
        prefix="before",
        page_count=2,
        compared_page_count=1,
    )
    (left_work / "after-pages-1-01.png").write_bytes(BLACK_PNG)
    (left_work / "after-pages-2-02.png").write_bytes(WHITE_PNG)
    (right_work / "before-pages-1-01.png").write_bytes(BLACK_PNG)

    result = audit.audit_render_page_multiset_equivalence(
        left_report,
        right_report,
        left_mutation="copy_first_sheet",
        right_mutation="no_op",
    )

    assert result["ready"] is False
    assert result["inconclusive_count"] == 1
    assert result["results"][0]["status"] == "inconclusive"
    assert "incomplete" in result["results"][0]["message"]


def test_remapped_pages_are_one_to_one_with_duplicate_hashes() -> None:
    remapped = audit._remapped_pages(
        {1: "same", 2: "same", 3: "other"},
        {1: "other", 2: "same", 3: "same"},
    )

    assert remapped == [
        {"left_page": 1, "right_page": 3},
        {"left_page": 3, "right_page": 1},
    ]
