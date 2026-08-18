from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from base64 import b64decode
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "audit_ooxml_copy_sheet_render_equivalence.py"
    )
    spec = importlib.util.spec_from_file_location(
        "audit_ooxml_copy_sheet_render_equivalence", script
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


def _write_fake_render_result(
    tmp_path: Path,
    *,
    fixture: str,
    status: str = "rendered",
    page_count: int = 2,
    compared_pages: list[int] | None = None,
) -> Path:
    work = tmp_path / fixture / "copy_first_sheet"
    after_pdf_dir = work / "after-pdf"
    after_pdf_dir.mkdir(parents=True)
    after_pdf = after_pdf_dir / f"after-{fixture}.pdf"
    after_pdf.write_bytes(b"%PDF-1.4\n")
    payload = {
        "render_engine": "excel",
        "results": [
            {
                "fixture": f"{fixture}.xlsx",
                "mutation": "copy_first_sheet",
                "status": status,
                "after_pdf": str(after_pdf),
                "page_count": page_count,
                "compared_page_count": len(compared_pages or [1, 2]),
                "compared_pages": compared_pages or [1, 2],
            }
        ]
    }
    report = tmp_path / "render-report.json"
    report.write_text(json.dumps(payload))
    return report


def test_copy_sheet_render_equivalence_accepts_duplicate_later_page(tmp_path: Path) -> None:
    report = _write_fake_render_result(tmp_path, fixture="book")
    work = tmp_path / "book" / "copy_first_sheet"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)
    (work / "after-pages-2-2.png").write_bytes(BLACK_PNG)

    result = audit.audit_copy_sheet_render_equivalence(report)

    assert result["ready"] is True
    assert result["render_engine"] == "excel"
    assert result["passed_count"] == 1
    assert result["failure_count"] == 0
    assert result["non_comparable_count"] == 0
    assert result["results"][0]["matched_page"] == 2
    assert result["results"][0]["normalized_rmse"] == 0.0


def test_copy_sheet_render_equivalence_fails_full_render_without_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        audit.run_ooxml_render_compare,
        "_find_imagemagick_compare",
        lambda: ("compare",),
    )
    monkeypatch.setattr(
        audit.run_ooxml_render_compare,
        "_normalized_rmse",
        lambda *args, **kwargs: 1.0,
    )
    report = _write_fake_render_result(tmp_path, fixture="book")
    work = tmp_path / "book" / "copy_first_sheet"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)
    (work / "after-pages-2-2.png").write_bytes(WHITE_PNG)

    result = audit.audit_copy_sheet_render_equivalence(report)

    assert result["ready"] is False
    assert result["failure_count"] == 1
    assert result["results"][0]["status"] == "failed"


def test_copy_sheet_render_equivalence_marks_sampled_without_match_inconclusive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        audit.run_ooxml_render_compare,
        "_find_imagemagick_compare",
        lambda: ("compare",),
    )
    monkeypatch.setattr(
        audit.run_ooxml_render_compare,
        "_normalized_rmse",
        lambda *args, **kwargs: 1.0,
    )
    report = _write_fake_render_result(
        tmp_path,
        fixture="book",
        status="sampled_rendered",
        page_count=5,
        compared_pages=[1, 3, 5],
    )
    work = tmp_path / "book" / "copy_first_sheet"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)
    (work / "after-pages-3-3.png").write_bytes(WHITE_PNG)
    (work / "after-pages-5-5.png").write_bytes(WHITE_PNG)

    result = audit.audit_copy_sheet_render_equivalence(report)

    assert result["ready"] is False
    assert result["failure_count"] == 0
    assert result["inconclusive_count"] == 1
    assert result["results"][0]["sampled"] is True


def test_copy_sheet_render_equivalence_marks_hidden_source_non_comparable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        audit.run_ooxml_render_compare,
        "_find_imagemagick_compare",
        lambda: ("compare",),
    )
    monkeypatch.setattr(
        audit.run_ooxml_render_compare,
        "_normalized_rmse",
        lambda *args, **kwargs: 1.0,
    )
    report = _write_fake_render_result(tmp_path, fixture="book")
    work = tmp_path / "book" / "copy_first_sheet"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)
    (work / "after-pages-2-2.png").write_bytes(WHITE_PNG)
    with zipfile.ZipFile(work / "after-book.xlsx", "w") as zf:
        zf.writestr(
            "xl/workbook.xml",
            (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Hidden" sheetId="1" state="hidden" r:id="rId1"/>'
                '<sheet name="Visible" sheetId="2" r:id="rId2"/></sheets></workbook>'
            ),
        )

    result = audit.audit_copy_sheet_render_equivalence(report)

    assert result["ready"] is False
    assert result["failure_count"] == 0
    assert result["inconclusive_count"] == 0
    assert result["non_comparable_count"] == 1
    assert result["results"][0]["status"] == "non_comparable"
    assert "source first sheet is hidden" in result["results"][0]["message"]


def test_copy_sheet_render_equivalence_marks_single_page_render_non_comparable(
    tmp_path: Path,
) -> None:
    report = _write_fake_render_result(tmp_path, fixture="book", page_count=1)
    work = tmp_path / "book" / "copy_first_sheet"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)

    result = audit.audit_copy_sheet_render_equivalence(report)

    assert result["ready"] is False
    assert result["failure_count"] == 0
    assert result["inconclusive_count"] == 0
    assert result["non_comparable_count"] == 1
    assert result["results"][0]["status"] == "non_comparable"
    assert "no later rendered page" in result["results"][0]["message"]


def test_copy_sheet_render_equivalence_ignores_other_mutations(tmp_path: Path) -> None:
    report = tmp_path / "render-report.json"
    report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": "book.xlsx",
                        "mutation": "marker_cell",
                        "status": "rendered",
                    }
                ]
            }
        )
    )

    result = audit.audit_copy_sheet_render_equivalence(report)

    assert result["ready"] is False
    assert result["result_count"] == 0
