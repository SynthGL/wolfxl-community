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
        / "audit_ooxml_retarget_external_links_render_equivalence.py"
    )
    spec = importlib.util.spec_from_file_location(
        "audit_ooxml_retarget_external_links_render_equivalence", script
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


def _patch_required_tools(tmp_path: Path, monkeypatch) -> None:
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()
    monkeypatch.setattr(audit.base.run_ooxml_app_smoke, "EXCEL_APP", str(excel_app))
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_find_imagemagick_compare",
        lambda: ("compare",),
    )
    monkeypatch.setattr(audit.shutil, "which", lambda name: f"/usr/bin/{name}")


def _write_fake_render_result(
    tmp_path: Path,
    *,
    status: str = "rendered",
    page_count: int = 1,
    compared_pages: list[int] | None = None,
    density: int = 96,
    mutation: str = "retarget_external_links",
) -> Path:
    work = tmp_path / "book" / mutation
    after_pdf_dir = work / "after-pdf"
    after_pdf_dir.mkdir(parents=True)
    after_pdf = after_pdf_dir / "after-book.pdf"
    after_pdf.write_bytes(b"%PDF-1.4\n")
    (work / "before-book.xlsx").write_bytes(b"xlsx")
    compared_pages = [1] if compared_pages is None else compared_pages
    payload = {
        "render_engine": "excel",
        "density": density,
        "results": [
            {
                "fixture": "book.xlsx",
                "mutation": mutation,
                "status": status,
                "after_pdf": str(after_pdf),
                "page_count": page_count,
                "compared_page_count": len(compared_pages),
                "compared_pages": compared_pages,
            }
        ],
    }
    report = tmp_path / "render-report.json"
    report.write_text(json.dumps(payload))
    return report


def test_retarget_external_links_render_equivalence_accepts_identical_pages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, density=144)
    work = tmp_path / "book" / "retarget_external_links"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)

    def fake_export_pdf(_engine, _soffice, _src, outdir, _timeout):
        outdir.mkdir(parents=True)
        pdf = outdir / "before-book.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    def fake_rasterize(_pdftoppm, _pdf, prefix, _pages, density, _timeout):
        assert density == 144
        path = prefix.parent / "before-equivalence-pages-1-1.png"
        path.write_bytes(BLACK_PNG)
        return [path]

    _patch_required_tools(tmp_path, monkeypatch)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_export_pdf", fake_export_pdf)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_pdf_page_count", lambda _pdf: 1)
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_rasterize_pdf_pages",
        fake_rasterize,
    )

    result = audit.audit_retarget_external_links_render_equivalence(report)

    assert result["ready"] is True
    assert result["mutation"] == "retarget_external_links"
    assert result["passed_count"] == 1
    assert result["failure_count"] == 0
    assert result["results"][0]["max_normalized_rmse"] == 0.0
    assert "external-link retarget render equivalent" in result["results"][0]["message"]


def test_retarget_external_links_render_equivalence_fails_on_render_drift(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path)
    work = tmp_path / "book" / "retarget_external_links"
    (work / "after-pages-1-1.png").write_bytes(WHITE_PNG)

    def fake_export_pdf(_engine, _soffice, _src, outdir, _timeout):
        outdir.mkdir(parents=True)
        pdf = outdir / "before-book.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    def fake_rasterize(_pdftoppm, _pdf, prefix, _pages, _density, _timeout):
        path = prefix.parent / "before-equivalence-pages-1-1.png"
        path.write_bytes(BLACK_PNG)
        return [path]

    _patch_required_tools(tmp_path, monkeypatch)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_export_pdf", fake_export_pdf)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_pdf_page_count", lambda _pdf: 1)
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_rasterize_pdf_pages",
        fake_rasterize,
    )
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_normalized_rmse",
        lambda *args, **kwargs: 0.2,
    )

    result = audit.audit_retarget_external_links_render_equivalence(report)

    assert result["ready"] is False
    assert result["failure_count"] == 1
    assert result["results"][0]["status"] == "failed"
    assert "render drift above threshold" in result["results"][0]["message"]


def test_retarget_external_links_render_equivalence_fails_on_source_render_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, status="failed")
    _patch_required_tools(tmp_path, monkeypatch)

    result = audit.audit_retarget_external_links_render_equivalence(report)

    assert result["ready"] is False
    assert result["failure_count"] == 1
    assert "render result status is not passing" in result["results"][0]["message"]


def test_retarget_external_links_render_equivalence_marks_missing_before_workbook_inconclusive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path)
    work = tmp_path / "book" / "retarget_external_links"
    (work / "before-book.xlsx").unlink()
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)

    _patch_required_tools(tmp_path, monkeypatch)

    result = audit.audit_retarget_external_links_render_equivalence(report)

    assert result["ready"] is False
    assert result["inconclusive_count"] == 1
    assert "before workbook is missing" in result["results"][0]["message"]


def test_retarget_external_links_render_equivalence_marks_missing_after_page_inconclusive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, compared_pages=[1, 3])
    work = tmp_path / "book" / "retarget_external_links"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)
    _patch_required_tools(tmp_path, monkeypatch)

    result = audit.audit_retarget_external_links_render_equivalence(report)

    assert result["ready"] is False
    assert result["inconclusive_count"] == 1
    assert "after page image(s) missing: [3]" in result["results"][0]["message"]


def test_retarget_external_links_render_equivalence_fails_on_page_count_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, page_count=2)
    work = tmp_path / "book" / "retarget_external_links"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)

    def fake_export_pdf(_engine, _soffice, _src, outdir, _timeout):
        outdir.mkdir(parents=True)
        pdf = outdir / "before-book.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    _patch_required_tools(tmp_path, monkeypatch)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_export_pdf", fake_export_pdf)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_pdf_page_count", lambda _pdf: 1)

    result = audit.audit_retarget_external_links_render_equivalence(report)

    assert result["ready"] is False
    assert result["failure_count"] == 1
    assert "page-count mismatch" in result["results"][0]["message"]


def test_retarget_external_links_render_equivalence_ignores_other_mutations(
    tmp_path: Path,
) -> None:
    report = _write_fake_render_result(tmp_path, mutation="marker_cell")

    result = audit.audit_retarget_external_links_render_equivalence(report)

    assert result["ready"] is False
    assert result["result_count"] == 0
