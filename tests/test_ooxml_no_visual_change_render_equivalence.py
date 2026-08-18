from __future__ import annotations

import importlib.util
import json
import sys
from base64 import b64decode
from pathlib import Path
from types import ModuleType
from typing import Optional


def _load_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "audit_ooxml_no_visual_change_render_equivalence.py"
    )
    spec = importlib.util.spec_from_file_location(
        "audit_ooxml_no_visual_change_render_equivalence", script
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
    fixture: str = "book.xlsx",
    mutation: str = "add_data_validation",
    status: str = "rendered",
    page_count: int = 1,
    compared_pages: Optional[list[int]] = None,
    density: int = 96,
    excel_print_area: str | None = None,
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
        "excel_print_area": excel_print_area,
        "results": [
            {
                "fixture": fixture,
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


def test_no_visual_change_render_equivalence_accepts_identical_pages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, density=144)
    work = tmp_path / "book" / "add_data_validation"
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
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare, "_export_pdf", fake_export_pdf
    )
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare, "_pdf_page_count", lambda _pdf: 1
    )
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_rasterize_pdf_pages",
        fake_rasterize,
    )

    result = audit.audit_no_visual_change_render_equivalence(report)

    assert result["ready"] is True
    assert result["mutations"] == ["add_data_validation"]
    assert result["observed_mutations"] == ["add_data_validation"]
    assert result["passed_count"] == 1
    assert result["failure_count"] == 0
    assert result["results"][0]["max_normalized_rmse"] == 0.0
    assert "add-data-validation render equivalent" in result["results"][0]["message"]


def test_no_visual_change_render_equivalence_reuses_excel_print_area(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, excel_print_area="$A$1:$AC$20")
    work = tmp_path / "book" / "add_data_validation"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)
    seen_print_areas: list[str | None] = []

    def fake_export_pdf(_engine, _soffice, _src, outdir, _timeout):
        seen_print_areas.append(
            audit.base.run_ooxml_render_compare._EXCEL_PRINT_AREA_LIMIT
        )
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

    result = audit.audit_no_visual_change_render_equivalence(report)

    assert result["ready"] is True
    assert result["excel_print_area"] == "$A$1:$AC$20"
    assert seen_print_areas == ["$A$1:$AC$20"]
    assert audit.base.run_ooxml_render_compare._EXCEL_PRINT_AREA_LIMIT is None


def test_no_visual_change_render_equivalence_normalizes_blank_print_area(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, excel_print_area="   ")
    work = tmp_path / "book" / "add_data_validation"
    (work / "after-pages-1-1.png").write_bytes(BLACK_PNG)
    seen_print_areas: list[str | None] = []

    def fake_export_pdf(_engine, _soffice, _src, outdir, _timeout):
        seen_print_areas.append(
            audit.base.run_ooxml_render_compare._EXCEL_PRINT_AREA_LIMIT
        )
        outdir.mkdir(parents=True)
        pdf = outdir / "before-book.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    def fake_rasterize(_pdftoppm, _pdf, prefix, _pages, _density, _timeout):
        path = prefix.parent / "before-equivalence-pages-1-1.png"
        path.write_bytes(BLACK_PNG)
        return [path]

    _patch_required_tools(tmp_path, monkeypatch)
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare, "_export_pdf", fake_export_pdf
    )
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare, "_pdf_page_count", lambda _pdf: 1
    )
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_rasterize_pdf_pages",
        fake_rasterize,
    )

    result = audit.audit_no_visual_change_render_equivalence(report)

    assert result["ready"] is True
    assert result["excel_print_area"] is None
    assert seen_print_areas == [None]


def test_no_visual_change_render_equivalence_fails_on_render_drift(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path)
    work = tmp_path / "book" / "add_data_validation"
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

    result = audit.audit_no_visual_change_render_equivalence(report)

    assert result["ready"] is False
    assert result["failure_count"] == 1
    assert result["results"][0]["status"] == "failed"
    assert "render drift above threshold" in result["results"][0]["message"]


def test_no_visual_change_render_equivalence_accepts_bounded_known_excel_noise(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(
        tmp_path,
        fixture="real-excel-table-slicers.xlsx",
        compared_pages=[1, 2],
        page_count=2,
    )
    work = tmp_path / "book" / "add_data_validation"
    (work / "after-pages-1-1.png").write_bytes(WHITE_PNG)
    (work / "after-pages-2-2.png").write_bytes(WHITE_PNG)

    def fake_export_pdf(_engine, _soffice, _src, outdir, _timeout):
        outdir.mkdir(parents=True)
        pdf = outdir / "before-book.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    def fake_rasterize(_pdftoppm, _pdf, prefix, pages, _density, _timeout):
        paths = []
        for page in pages:
            path = prefix.parent / f"before-equivalence-pages-{page}-{page}.png"
            path.write_bytes(BLACK_PNG)
            paths.append(path)
        return paths

    _patch_required_tools(tmp_path, monkeypatch)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_export_pdf", fake_export_pdf)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_pdf_page_count", lambda _pdf: 2)
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_rasterize_pdf_pages",
        fake_rasterize,
    )
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_normalized_rmse",
        lambda *args, **kwargs: 0.00635894,
    )

    result = audit.audit_no_visual_change_render_equivalence(report)

    assert result["ready"] is True
    assert result["passed_count"] == 0
    assert result["known_noise_count"] == 1
    assert result["failure_count"] == 0
    assert result["results"][0]["status"] == "known_render_noise"
    assert "known Excel render noise accepted" in result["results"][0]["message"]
    assert "add_data_validation:real-excel-table-slicers.xlsx" in result[
        "known_excel_render_noise_policy"
    ]


def test_no_visual_change_render_equivalence_rejects_unknown_or_excessive_noise(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(
        tmp_path,
        fixture="real-excel-table-slicers.xlsx",
        compared_pages=[1, 2],
        page_count=2,
    )
    work = tmp_path / "book" / "add_data_validation"
    (work / "after-pages-1-1.png").write_bytes(WHITE_PNG)
    (work / "after-pages-2-2.png").write_bytes(WHITE_PNG)

    def fake_export_pdf(_engine, _soffice, _src, outdir, _timeout):
        outdir.mkdir(parents=True)
        pdf = outdir / "before-book.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    def fake_rasterize(_pdftoppm, _pdf, prefix, pages, _density, _timeout):
        paths = []
        for page in pages:
            path = prefix.parent / f"before-equivalence-pages-{page}-{page}.png"
            path.write_bytes(BLACK_PNG)
            paths.append(path)
        return paths

    _patch_required_tools(tmp_path, monkeypatch)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_export_pdf", fake_export_pdf)
    monkeypatch.setattr(audit.base.run_ooxml_render_compare, "_pdf_page_count", lambda _pdf: 2)
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_rasterize_pdf_pages",
        fake_rasterize,
    )
    monkeypatch.setattr(
        audit.base.run_ooxml_render_compare,
        "_normalized_rmse",
        lambda *args, **kwargs: 0.008,
    )

    result = audit.audit_no_visual_change_render_equivalence(report)

    assert result["ready"] is False
    assert result["known_noise_count"] == 0
    assert result["failure_count"] == 1
    assert result["results"][0]["status"] == "failed"


def test_no_visual_change_render_equivalence_requires_requested_mutation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, mutation="rename_first_sheet")
    _patch_required_tools(tmp_path, monkeypatch)

    result = audit.audit_no_visual_change_render_equivalence(report)

    assert result["ready"] is False
    assert result["result_count"] == 0
    assert result["missing_mutations"] == ["add_data_validation"]


def test_no_visual_change_render_equivalence_accepts_explicit_mutation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, mutation="rename_first_sheet")
    work = tmp_path / "book" / "rename_first_sheet"
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

    result = audit.audit_no_visual_change_render_equivalence(
        report,
        mutations=("rename_first_sheet",),
    )

    assert result["ready"] is True
    assert result["mutations"] == ["rename_first_sheet"]
    assert result["observed_mutations"] == ["rename_first_sheet"]
    assert "rename-sheet render equivalent" in result["results"][0]["message"]


def test_no_visual_change_render_equivalence_labels_conditional_formatting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = _write_fake_render_result(tmp_path, mutation="add_conditional_formatting")
    work = tmp_path / "book" / "add_conditional_formatting"
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

    result = audit.audit_no_visual_change_render_equivalence(
        report,
        mutations=("add_conditional_formatting",),
    )

    assert result["ready"] is True
    assert result["mutations"] == ["add_conditional_formatting"]
    assert result["observed_mutations"] == ["add_conditional_formatting"]
    assert "add-conditional-formatting render equivalent" in result["results"][0][
        "message"
    ]


def _assert_explicit_neutral_mutation_label(
    tmp_path: Path,
    monkeypatch,
    *,
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

    result = audit.audit_no_visual_change_render_equivalence(
        report,
        mutations=(mutation,),
    )

    assert result["ready"] is True
    assert result["mutations"] == [mutation]
    assert result["observed_mutations"] == [mutation]
    assert f"{label} render equivalent" in result["results"][0]["message"]


def test_no_visual_change_render_equivalence_labels_add_remove_chart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _assert_explicit_neutral_mutation_label(
        tmp_path,
        monkeypatch,
        mutation="add_remove_chart",
        label="add-remove-chart",
    )


def test_no_visual_change_render_equivalence_labels_copy_remove_sheet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _assert_explicit_neutral_mutation_label(
        tmp_path,
        monkeypatch,
        mutation="copy_remove_sheet",
        label="copy-remove-sheet",
    )
