from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import openpyxl


def _load_render_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1] / "scripts" / "run_ooxml_render_compare.py"
    )
    spec = importlib.util.spec_from_file_location("run_ooxml_render_compare", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


render_module = _load_render_module()


def _make_fixture(path: Path) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet["A1"] = "ok"
    workbook.save(path)


def test_render_compare_skips_when_renderer_tools_missing(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "simple.xlsx")
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke,
        "_find_libreoffice",
        lambda: None,
    )

    report = render_module.run_render_compare(fixture_dir, output_dir, timeout=1)

    assert report["render_engine"] == "libreoffice"
    assert report["result_count"] == 1
    assert report["failure_count"] == 0
    assert report["results"][0]["status"] == "skipped"
    assert report["results"][0]["mutation"] == "no_op"
    assert "soffice not found" in report["results"][0]["message"]


def test_render_compare_can_discover_recursive_fixture_trees(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    nested_dir = fixture_dir / "nested" / "deep"
    nested_dir.mkdir(parents=True)
    _make_fixture(nested_dir / "simple.xlsx")

    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke,
        "_find_libreoffice",
        lambda: None,
    )

    report = render_module.run_render_compare(
        fixture_dir,
        output_dir,
        timeout=1,
        recursive=True,
    )

    assert report["recursive"] is True
    assert report["result_count"] == 1
    result = report["results"][0]
    assert result["fixture"] == "nested/deep/simple.xlsx"
    assert result["mutation"] == "no_op"
    assert result["status"] == "skipped"


def test_render_compare_reports_rmse_threshold_failure(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "simple.xlsx")
    before_pdf = tmp_path / "before.pdf"
    after_pdf = tmp_path / "after.pdf"
    before_pdf.write_bytes(b"%PDF-before")
    after_pdf.write_bytes(b"%PDF-after")
    before_page = tmp_path / "before-1.png"
    after_page = tmp_path / "after-1.png"
    before_page.write_bytes(b"before")
    after_page.write_bytes(b"after")

    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_find_libreoffice", lambda: "soffice"
    )
    monkeypatch.setattr(render_module.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        render_module,
        "_export_pdf",
        lambda _engine, _soffice, src, _outdir, _timeout: before_pdf
        if src.name.startswith("before-")
        else after_pdf,
    )
    monkeypatch.setattr(
        render_module,
        "_pdf_page_count",
        lambda _pdf: 1,
    )
    monkeypatch.setattr(
        render_module,
        "_rasterize_pdf_pages",
        lambda _pdftoppm, pdf, _prefix, _pages, _density, _timeout: [before_page]
        if pdf == before_pdf
        else [after_page],
    )
    monkeypatch.setattr(
        render_module,
        "_normalized_rmse",
        lambda _compare_cmd, _before_page, _after_page, _timeout: 0.25,
    )

    report = render_module.run_render_compare(
        fixture_dir,
        output_dir,
        timeout=1,
        max_normalized_rmse=0.01,
    )

    assert report["failure_count"] == 1
    result = report["results"][0]
    assert result["status"] == "failed"
    assert result["mutation"] == "no_op"
    assert result["max_normalized_rmse"] == 0.25
    assert "render drift above threshold" in result["message"]


def test_render_compare_samples_large_pdfs_when_page_limit_set(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "large.xlsx")
    before_pdf = tmp_path / "before.pdf"
    after_pdf = tmp_path / "after.pdf"
    before_pdf.write_bytes(b"%PDF-before")
    after_pdf.write_bytes(b"%PDF-after")
    before_page = tmp_path / "before-1.png"
    after_page = tmp_path / "after-1.png"
    before_page.write_bytes(b"before")
    after_page.write_bytes(b"after")
    seen_pages: list[list[int]] = []

    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_find_libreoffice", lambda: "soffice"
    )
    monkeypatch.setattr(render_module.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        render_module,
        "_export_pdf",
        lambda _engine, _soffice, src, _outdir, _timeout: before_pdf
        if src.name.startswith("before-")
        else after_pdf,
    )
    monkeypatch.setattr(render_module, "_pdf_page_count", lambda _pdf: 100)

    def fake_rasterize(_pdftoppm, pdf, _prefix, pages, _density, _timeout):
        seen_pages.append(pages)
        return [before_page] if pdf == before_pdf else [after_page]

    monkeypatch.setattr(render_module, "_rasterize_pdf_pages", fake_rasterize)
    monkeypatch.setattr(
        render_module,
        "_normalized_rmse",
        lambda _compare_cmd, _before_page, _after_page, _timeout: 0.0,
    )

    report = render_module.run_render_compare(
        fixture_dir,
        output_dir,
        timeout=1,
        max_pages_per_fixture=3,
    )

    assert report["failure_count"] == 0
    result = report["results"][0]
    assert result["status"] == "sampled_passed"
    assert result["mutation"] == "no_op"
    assert result["page_count"] == 100
    assert result["compared_page_count"] == 3
    assert result["compared_pages"] == [1, 50, 100]
    assert seen_pages == [[1, 50, 100], [1, 50, 100]]


def test_render_compare_can_sample_first_pages_for_copy_sheet_equivalence(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "large.xlsx")
    after_pdf = tmp_path / "after.pdf"
    after_pdf.write_bytes(b"%PDF-after")
    after_page = tmp_path / "after-1.png"
    after_page.write_bytes(b"after")
    seen_pages: list[list[int]] = []

    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_find_libreoffice", lambda: "soffice"
    )
    monkeypatch.setattr(render_module.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        render_module,
        "_export_pdf",
        lambda *_args, **_kwargs: after_pdf,
    )
    monkeypatch.setattr(render_module, "_pdf_page_count", lambda _pdf: 100)

    def fake_rasterize(_pdftoppm, _pdf, _prefix, pages, _density, _timeout):
        seen_pages.append(pages)
        return [after_page for _ in pages]

    monkeypatch.setattr(render_module, "_rasterize_pdf_pages", fake_rasterize)

    report = render_module.run_render_compare(
        fixture_dir,
        output_dir,
        timeout=1,
        max_pages_per_fixture=2,
        mutations=("copy_first_sheet",),
        page_selection="first-pages",
    )

    assert report["page_selection"] == "first-pages"
    assert report["failure_count"] == 0
    result = report["results"][0]
    assert result["status"] == "sampled_rendered"
    assert result["mutation"] == "copy_first_sheet"
    assert result["page_count"] == 100
    assert result["compared_page_count"] == 2
    assert result["compared_pages"] == [1, 2]
    assert seen_pages == [[1, 2]]


def test_render_compare_can_sample_first_and_last_pages_for_appended_copy(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "large.xlsx")
    after_pdf = tmp_path / "after.pdf"
    after_pdf.write_bytes(b"%PDF-after")
    after_page = tmp_path / "after-1.png"
    after_page.write_bytes(b"after")
    seen_pages: list[list[int]] = []

    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_find_libreoffice", lambda: "soffice"
    )
    monkeypatch.setattr(render_module.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        render_module,
        "_export_pdf",
        lambda *_args, **_kwargs: after_pdf,
    )
    monkeypatch.setattr(render_module, "_pdf_page_count", lambda _pdf: 74)

    def fake_rasterize(_pdftoppm, _pdf, _prefix, pages, _density, _timeout):
        seen_pages.append(pages)
        return [after_page for _ in pages]

    monkeypatch.setattr(render_module, "_rasterize_pdf_pages", fake_rasterize)

    report = render_module.run_render_compare(
        fixture_dir,
        output_dir,
        timeout=1,
        max_pages_per_fixture=4,
        mutations=("copy_first_sheet",),
        page_selection="first-and-last-pages",
    )

    assert report["page_selection"] == "first-and-last-pages"
    assert report["failure_count"] == 0
    result = report["results"][0]
    assert result["status"] == "sampled_rendered"
    assert result["mutation"] == "copy_first_sheet"
    assert result["page_count"] == 74
    assert result["compared_page_count"] == 4
    assert result["compared_pages"] == [1, 72, 73, 74]
    assert seen_pages == [[1, 72, 73, 74]]


def test_render_compare_can_pass_byte_identical_no_op_without_render(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "simple.xlsx")

    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_find_libreoffice", lambda: "soffice"
    )
    monkeypatch.setattr(render_module.shutil, "which", lambda name: name)
    monkeypatch.setattr(
        render_module,
        "_export_pdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("render should be skipped")
        ),
    )

    report = render_module.run_render_compare(
        fixture_dir,
        output_dir,
        timeout=1,
        pass_byte_identical_xlsx=True,
    )

    assert report["failure_count"] == 0
    result = report["results"][0]
    assert result["status"] == "passed"
    assert result["mutation"] == "no_op"
    assert result["max_normalized_rmse"] == 0.0
    assert "byte-identical xlsx" in result["message"]


def test_render_compare_smokes_intentional_mutation_without_rmse(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "simple.xlsx")
    after_pdf = tmp_path / "after.pdf"
    after_pdf.write_bytes(b"%PDF-after")
    after_page = tmp_path / "after-1.png"
    after_page.write_bytes(b"after")
    exported: list[str] = []

    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_find_libreoffice", lambda: "soffice"
    )
    monkeypatch.setattr(render_module.shutil, "which", lambda name: name)

    def fake_export(_engine, _soffice, src, _outdir, _timeout):
        exported.append(src.name)
        return after_pdf

    monkeypatch.setattr(render_module, "_export_pdf", fake_export)
    monkeypatch.setattr(render_module, "_pdf_page_count", lambda _pdf: 1)
    monkeypatch.setattr(
        render_module,
        "_rasterize_pdf_pages",
        lambda *_args, **_kwargs: [after_page],
    )
    monkeypatch.setattr(
        render_module,
        "_normalized_rmse",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("intentional mutation should not be RMSE-compared")
        ),
    )

    report = render_module.run_render_compare(
        fixture_dir,
        output_dir,
        timeout=1,
        mutations=("marker_cell",),
    )

    assert report["mutations"] == ["marker_cell"]
    assert report["failure_count"] == 0
    result = report["results"][0]
    assert result["fixture"] == "simple.xlsx"
    assert result["mutation"] == "marker_cell"
    assert result["status"] == "rendered"
    assert result["before_pdf"] is None
    assert result["after_pdf"] == str(after_pdf)
    assert result["max_normalized_rmse"] is None
    assert exported == ["after-simple.xlsx"]


def test_render_compare_can_use_excel_render_engine(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "simple.xlsx")
    fake_excel_app = tmp_path / "Microsoft Excel.app"
    fake_excel_app.mkdir()
    before_pdf = tmp_path / "before.pdf"
    after_pdf = tmp_path / "after.pdf"
    before_pdf.write_bytes(b"%PDF-before")
    after_pdf.write_bytes(b"%PDF-after")
    before_page = tmp_path / "before-1.png"
    after_page = tmp_path / "after-1.png"
    before_page.write_bytes(b"before")
    after_page.write_bytes(b"after")
    seen_engines: list[str] = []

    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke,
        "EXCEL_APP",
        str(fake_excel_app),
    )
    monkeypatch.setattr(render_module.shutil, "which", lambda name: name)

    def fake_export(engine, soffice, src, _outdir, _timeout):
        seen_engines.append(engine)
        assert soffice is None
        return before_pdf if src.name.startswith("before-") else after_pdf

    monkeypatch.setattr(render_module, "_export_pdf", fake_export)
    monkeypatch.setattr(render_module, "_pdf_page_count", lambda _pdf: 1)
    monkeypatch.setattr(
        render_module,
        "_rasterize_pdf_pages",
        lambda _pdftoppm, pdf, _prefix, _pages, _density, _timeout: [before_page]
        if pdf == before_pdf
        else [after_page],
    )
    monkeypatch.setattr(
        render_module,
        "_normalized_rmse",
        lambda _compare_cmd, _before_page, _after_page, _timeout: 0.0,
    )

    report = render_module.run_render_compare(
        fixture_dir,
        output_dir,
        timeout=1,
        render_engine="excel",
    )

    assert report["render_engine"] == "excel"
    assert report["failure_count"] == 0
    assert report["results"][0]["status"] == "passed"
    assert seen_engines == ["excel", "excel"]


def test_render_compare_can_limit_excel_print_area(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "wide.xlsx")
    fake_excel_app = tmp_path / "Microsoft Excel.app"
    fake_excel_app.mkdir()
    after_pdf = tmp_path / "after.pdf"
    after_pdf.write_bytes(b"%PDF-after")
    after_page = tmp_path / "after-1.png"
    after_page.write_bytes(b"after")
    seen_print_areas: list[str | None] = []

    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke,
        "EXCEL_APP",
        str(fake_excel_app),
    )
    monkeypatch.setattr(render_module.shutil, "which", lambda name: name)

    def fake_export(_engine, _soffice, _src, _outdir, _timeout):
        seen_print_areas.append(render_module._EXCEL_PRINT_AREA_LIMIT)
        return after_pdf

    monkeypatch.setattr(render_module, "_export_pdf", fake_export)
    monkeypatch.setattr(render_module, "_pdf_page_count", lambda _pdf: 1)
    monkeypatch.setattr(
        render_module,
        "_rasterize_pdf_pages",
        lambda _pdftoppm, _pdf, _prefix, pages, _density, _timeout: [
            after_page for _ in pages
        ],
    )

    report = render_module.run_render_compare(
        fixture_dir,
        output_dir,
        timeout=1,
        render_engine="excel",
        mutations=("add_data_validation",),
        excel_print_area="$A$1:$K$80",
    )

    assert report["excel_print_area"] == "$A$1:$K$80"
    assert report["failure_count"] == 0
    assert report["results"][0]["status"] == "rendered"
    assert seen_print_areas == ["$A$1:$K$80"]
    assert render_module._EXCEL_PRINT_AREA_LIMIT is None


def test_render_compare_rejects_print_area_for_non_excel_renderer(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "simple.xlsx")

    try:
        render_module.run_render_compare(
            fixture_dir,
            output_dir,
            timeout=1,
            render_engine="libreoffice",
            excel_print_area="$A$1:$K$80",
        )
    except ValueError as exc:
        assert "--excel-print-area" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_render_compare_rejects_blank_excel_print_area(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "simple.xlsx")

    try:
        render_module.run_render_compare(
            fixture_dir,
            output_dir,
            timeout=1,
            render_engine="excel",
            excel_print_area="   ",
        )
    except ValueError as exc:
        assert "--excel-print-area must not be empty" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_sample_page_numbers_are_stable() -> None:
    assert render_module._sample_page_numbers(1, 3) == [1]
    assert render_module._sample_page_numbers(100, 1) == [1]
    assert render_module._sample_page_numbers(100, 2) == [1, 100]
    assert render_module._sample_page_numbers(100, 5) == [1, 26, 50, 75, 100]
    assert render_module._first_page_numbers(100, 2) == [1, 2]
    assert render_module._first_and_last_page_numbers(100, 4) == [1, 98, 99, 100]


def test_rasterize_pdf_pages_honors_single_page_sample(
    tmp_path: Path, monkeypatch
) -> None:
    pdf = tmp_path / "many-pages.pdf"
    pdf.write_bytes(b"%PDF")
    calls: list[list[str]] = []

    class Completed:
        returncode = 0
        stderr = ""

    def fake_run(args, **_kwargs):
        calls.append(list(args))
        prefix = Path(args[-1])
        (prefix.parent / f"{prefix.name}-1.png").write_bytes(b"page")
        return Completed()

    monkeypatch.setattr(render_module.subprocess, "run", fake_run)

    pages = render_module._rasterize_pdf_pages(
        "pdftoppm",
        pdf,
        tmp_path / "out-pages",
        [1],
        density=96,
        timeout=1,
    )

    assert len(pages) == 1
    assert calls == [
        [
            "pdftoppm",
            "-png",
            "-r",
            "96",
            "-f",
            "1",
            "-l",
            "1",
            str(pdf),
            str(tmp_path / "out-pages-1"),
        ]
    ]


def test_normalized_rmse_parses_imagemagick_metric(tmp_path: Path, monkeypatch) -> None:
    before_page = tmp_path / "before.png"
    after_page = tmp_path / "after.png"
    before_page.write_bytes(b"before")
    after_page.write_bytes(b"after")

    class Completed:
        returncode = 1
        stderr = "123.4 (0.001883)"

    monkeypatch.setattr(
        render_module.subprocess,
        "run",
        lambda *args, **kwargs: Completed(),
    )

    assert (
        render_module._normalized_rmse(("compare",), before_page, after_page, timeout=1)
        == 0.001883
    )


def test_subprocess_context_formats_available_output() -> None:
    completed = render_module.subprocess.CompletedProcess(
        ["osascript"],
        0,
        stdout="hello\n",
        stderr="warning\n",
    )

    assert render_module._format_subprocess_context(completed) == (
        " (stdout='hello'; stderr='warning')"
    )


def test_excel_pdf_export_reports_timeout_dialog(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "book.xlsx"
    src.write_bytes(b"not-used")
    output_dir = tmp_path / "out"

    def fake_run_script(_script, timeout):
        raise RuntimeError(
            f"Microsoft Excel PDF export timed out after {timeout}s; "
            "Excel dialog: Grant File Access"
        )

    monkeypatch.setattr(
        render_module,
        "_run_excel_script_with_dialog_handling",
        fake_run_script,
    )

    try:
        render_module._export_pdf_excel(src, output_dir, timeout=3)
    except RuntimeError as exc:
        assert "timed out after 3s" in str(exc)
        assert "Grant File Access" in str(exc)
    else:
        raise AssertionError("expected Excel export timeout")


def test_excel_pdf_export_uses_short_internal_stage_names(
    tmp_path: Path, monkeypatch
) -> None:
    src = (
        tmp_path
        / "before-hdx_iran_iran_civilian_targeting_events_and_fatalities_by_month-year.xlsx"
    )
    src.write_bytes(b"not-used")
    output_dir = tmp_path / "out"
    stage_dir = tmp_path / "stage"
    seen_scripts: list[str] = []

    def fake_run_script(script, _timeout):
        seen_scripts.append(script)
        (stage_dir / "workbook.pdf").write_bytes(b"%PDF")
        return render_module.subprocess.CompletedProcess(
            ["osascript"],
            0,
            "",
            "",
        )

    monkeypatch.setattr(
        render_module,
        "_run_excel_script_with_dialog_handling",
        fake_run_script,
    )
    monkeypatch.setattr(
        render_module, "_excel_render_stage_dir", lambda _src: stage_dir
    )
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_excel_dialog_text", lambda: ""
    )
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_dismiss_excel_safe_dialogs", lambda: None
    )
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_close_excel_best_effort", lambda: None
    )
    monkeypatch.setattr(
        render_module, "_restore_excel_automation_security_best_effort", lambda: None
    )

    pdf = render_module._export_pdf_excel(src, output_dir, timeout=3)

    assert pdf == output_dir / f"{src.stem}.pdf"
    assert pdf.read_bytes() == b"%PDF"
    assert "workbook.xlsx" in seen_scripts[0]
    assert src.stem not in seen_scripts[0]


def test_excel_pdf_export_retries_after_recovery_prompt(
    tmp_path: Path, monkeypatch
) -> None:
    src = tmp_path / "book.xlsx"
    src.write_bytes(b"not-used")
    output_dir = tmp_path / "out"
    stage_dir = tmp_path / "stage"
    attempts = 0
    dialogs = [
        (
            "windows=Book1\n"
            "buttons=NoYes\n"
            "text=Your recent changes were saved. Open recovered workbooks?"
        ),
        "",
    ]

    def fake_run_script(_script, _timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            (stage_dir / "workbook.pdf").write_bytes(b"%PDF")
            return render_module.subprocess.CompletedProcess(["osascript"], 0, "", "")
        return render_module.subprocess.CompletedProcess(
            ["osascript"],
            1,
            "",
            "Microsoft Excel got an error: Connection is invalid. (-609)",
        )

    monkeypatch.setattr(
        render_module,
        "_run_excel_script_with_dialog_handling",
        fake_run_script,
    )
    monkeypatch.setattr(
        render_module, "_excel_render_stage_dir", lambda _src: stage_dir
    )
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke,
        "_excel_dialog_text",
        lambda: dialogs.pop(0),
    )
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_dismiss_excel_safe_dialogs", lambda: None
    )
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_close_excel_best_effort", lambda: None
    )
    monkeypatch.setattr(
        render_module, "_restore_excel_automation_security_best_effort", lambda: None
    )

    pdf = render_module._export_pdf_excel(src, output_dir, timeout=3)

    assert attempts == 2
    assert pdf.read_bytes() == b"%PDF"


def test_excel_pdf_export_retries_after_transient_automation_error(
    tmp_path: Path, monkeypatch
) -> None:
    src = tmp_path / "book.xlsx"
    src.write_bytes(b"not-used")
    output_dir = tmp_path / "out"
    stage_dir = tmp_path / "stage"
    attempts = 0

    def fake_run_script(_script, _timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            (stage_dir / "workbook.pdf").write_bytes(b"%PDF")
            return render_module.subprocess.CompletedProcess(["osascript"], 0, "", "")
        return render_module.subprocess.CompletedProcess(
            ["osascript"],
            1,
            "",
            "Microsoft Excel got an error: Application isn't running. (-600)",
        )

    monkeypatch.setattr(
        render_module,
        "_run_excel_script_with_dialog_handling",
        fake_run_script,
    )
    monkeypatch.setattr(
        render_module, "_excel_render_stage_dir", lambda _src: stage_dir
    )
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_excel_dialog_text", lambda: ""
    )
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_dismiss_excel_safe_dialogs", lambda: None
    )
    monkeypatch.setattr(
        render_module.run_ooxml_app_smoke, "_close_excel_best_effort", lambda: None
    )
    monkeypatch.setattr(
        render_module, "_restore_excel_automation_security_best_effort", lambda: None
    )

    pdf = render_module._export_pdf_excel(src, output_dir, timeout=3)

    assert attempts == 2
    assert pdf.read_bytes() == b"%PDF"
