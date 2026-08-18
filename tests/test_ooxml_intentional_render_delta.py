from __future__ import annotations

import importlib.util
import json
import sys
from base64 import b64decode
from pathlib import Path
from types import ModuleType
from typing import Optional

import pytest


def _load_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "audit_ooxml_intentional_render_delta.py"
    )
    spec = importlib.util.spec_from_file_location(
        "audit_ooxml_intentional_render_delta", script
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
    mutation: str = "move_formula_range",
    page_count: int = 1,
    compared_pages: Optional[list[int]] = None,
    density: int = 96,
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
                "status": "rendered",
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


@pytest.mark.parametrize(
    ("mutation", "label"),
    [
        ("delete_marker_tail_col", "delete-marker-tail-col"),
        ("delete_marker_tail_row", "delete-marker-tail-row"),
        ("move_formula_range", "move-formula-range"),
        ("move_marker_range", "move-marker-range"),
        ("delete_first_row", "delete-first-row"),
        ("delete_first_col", "delete-first-col"),
    ],
)
def test_intentional_render_delta_accepts_observed_visual_change(
    tmp_path: Path,
    monkeypatch,
    mutation: str,
    label: str,
) -> None:
    report = _write_fake_render_result(tmp_path, mutation=mutation)
    work = tmp_path / "book" / mutation
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

    result = audit.audit_intentional_render_delta(
        report,
        mutation=mutation,
        min_changed_count=1,
    )

    assert result["ready"] is True
    assert result["changed_count"] == 1
    assert result["unchanged_count"] == 0
    assert result["results"][0]["status"] == "changed"
    assert f"{label} intentional render delta observed" in result["results"][0][
        "message"
    ]


def test_intentional_render_delta_can_allow_unchanged_sampled_pages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path)
    work = tmp_path / "book" / "move_formula_range"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)

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

    result = audit.audit_intentional_render_delta(
        report,
        mutation="move_formula_range",
        min_changed_count=0,
        max_unchanged_count=1,
    )

    assert result["ready"] is True
    assert result["changed_count"] == 0
    assert result["unchanged_count"] == 1
    assert result["results"][0]["status"] == "unchanged"


@pytest.mark.parametrize(
    ("mutation", "label"),
    [
        ("delete_first_row", "delete-first-row"),
        ("insert_tail_col", "insert-tail-col"),
        ("insert_tail_row", "insert-tail-row"),
        ("marker_cell", "marker-cell"),
        ("move_marker_range", "move-marker-range"),
        ("style_cell", "style-cell"),
    ],
)
def test_intentional_render_delta_accepts_page_count_delta(
    tmp_path: Path,
    monkeypatch,
    mutation: str,
    label: str,
) -> None:
    report = _write_fake_render_result(tmp_path, mutation=mutation)
    work = tmp_path / "book" / mutation
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)

    def fake_export_pdf(_engine, _soffice, _src, outdir, _timeout):
        outdir.mkdir(parents=True)
        pdf = outdir / "before-book.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    _patch_required_tools(tmp_path, monkeypatch)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_export_pdf", fake_export_pdf)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_pdf_page_count", lambda _pdf: 2)

    result = audit.audit_intentional_render_delta(
        report,
        mutation=mutation,
        min_changed_count=1,
    )

    assert result["ready"] is True
    assert result["changed_count"] == 1
    assert result["failure_count"] == 0
    assert result["results"][0]["status"] == "changed"
    assert f"{label} intentional page-count delta observed" in result["results"][0][
        "message"
    ]


def test_intentional_render_delta_rejects_unexpected_page_count_delta(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, mutation="move_formula_range")
    work = tmp_path / "book" / "move_formula_range"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)

    def fake_export_pdf(_engine, _soffice, _src, outdir, _timeout):
        outdir.mkdir(parents=True)
        pdf = outdir / "before-book.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    _patch_required_tools(tmp_path, monkeypatch)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_export_pdf", fake_export_pdf)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_pdf_page_count", lambda _pdf: 2)

    result = audit.audit_intentional_render_delta(
        report,
        mutation="move_formula_range",
        min_changed_count=1,
    )

    assert result["ready"] is False
    assert result["changed_count"] == 0
    assert result["failure_count"] == 1
    assert result["results"][0]["status"] == "failed"
    assert result["results"][0]["message"].startswith("page-count mismatch:")


def test_intentional_render_delta_requires_requested_mutation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, mutation="add_data_validation")
    _patch_required_tools(tmp_path, monkeypatch)

    result = audit.audit_intentional_render_delta(
        report,
        mutation="move_formula_range",
        min_changed_count=1,
    )

    assert result["ready"] is False
    assert result["missing_mutation"] is True
    assert result["result_count"] == 0
