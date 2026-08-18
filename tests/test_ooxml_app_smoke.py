from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
import subprocess
import zipfile

import openpyxl


def _load_smoke_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_ooxml_app_smoke.py"
    spec = importlib.util.spec_from_file_location("run_ooxml_app_smoke", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke_module = _load_smoke_module()


def _make_fixture(path: Path) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet["A1"] = "ok"
    workbook.save(path)


def test_validate_xlsx_rejects_missing_output(tmp_path: Path) -> None:
    ok, message = smoke_module._validate_xlsx(tmp_path / "missing.xlsx")

    assert not ok
    assert "no output file" in message


def test_validate_xlsx_accepts_basic_workbook(tmp_path: Path) -> None:
    fixture = tmp_path / "simple.xlsx"
    _make_fixture(fixture)

    ok, message = smoke_module._validate_xlsx(fixture)

    assert ok
    assert message == "ok"


def test_contains_powerview_content_detects_package_text(tmp_path: Path) -> None:
    fixture = tmp_path / "powerview.xlsx"
    with zipfile.ZipFile(fixture, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("xl/sharedStrings.xml", "<sst>PowerView report</sst>")

    assert smoke_module._contains_powerview_content(fixture)


def test_contains_powerview_content_ignores_plain_workbook(tmp_path: Path) -> None:
    fixture = tmp_path / "simple.xlsx"
    _make_fixture(fixture)

    assert not smoke_module._contains_powerview_content(fixture)


def test_smoke_skips_libreoffice_when_missing(tmp_path: Path, monkeypatch) -> None:
    fixture = tmp_path / "simple.xlsx"
    _make_fixture(fixture)
    monkeypatch.setattr(smoke_module, "_find_libreoffice", lambda: None)

    result = smoke_module._smoke_libreoffice(fixture, tmp_path / "out", timeout=1)

    assert result.status == "skipped"
    assert result.app == "libreoffice"


def test_smoke_excel_rejects_unrelated_active_workbook(tmp_path: Path, monkeypatch) -> None:
    fixture = tmp_path / "simple.xlsx"
    _make_fixture(fixture)
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()
    monkeypatch.setattr(smoke_module, "EXCEL_APP", str(excel_app))
    monkeypatch.setattr(
        smoke_module,
        "_open_excel_with_finder_and_close",
        lambda _src, _timeout: "Book1",
    )

    result = smoke_module._smoke_excel(fixture, tmp_path / "out", timeout=1)

    assert result.status == "failed"
    assert "opened 'Book1', expected 'simple.xlsx'" in result.message


def test_smoke_excel_accepts_expected_active_workbook(tmp_path: Path, monkeypatch) -> None:
    fixture = tmp_path / "simple.xlsx"
    _make_fixture(fixture)
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()
    monkeypatch.setattr(smoke_module, "EXCEL_APP", str(excel_app))
    monkeypatch.setattr(
        smoke_module,
        "_open_excel_with_finder_and_close",
        lambda src, _timeout: src.name,
    )

    result = smoke_module._smoke_excel(fixture, tmp_path / "out", timeout=1)

    assert result.status == "passed"
    assert result.message == "opened and closed in Microsoft Excel: simple.xlsx"


def test_smoke_excel_rejects_powerview_before_launching_excel(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = tmp_path / "powerview.xlsx"
    with zipfile.ZipFile(fixture, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("xl/sharedStrings.xml", "<sst>Power View report</sst>")
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()
    monkeypatch.setattr(smoke_module, "EXCEL_APP", str(excel_app))

    def fail_open(_src, _timeout):
        raise AssertionError("Excel should not launch for PowerView preflight failures")

    monkeypatch.setattr(smoke_module, "_open_excel_with_finder_and_close", fail_open)

    result = smoke_module._smoke_excel(fixture, tmp_path / "out", timeout=1)

    assert result.status == "failed"
    assert smoke_module.EXCEL_UNSUPPORTED_CONTENT_MARKER in result.message
    assert "PowerView" in result.message


def test_smoke_excel_accepts_manifest_expected_powerview_as_nonpassing_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = tmp_path / "powerview.xlsx"
    with zipfile.ZipFile(fixture, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr("xl/sharedStrings.xml", "<sst>Power View report</sst>")
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()
    monkeypatch.setattr(smoke_module, "EXCEL_APP", str(excel_app))

    def fail_open(_src, _timeout):
        raise AssertionError("Excel should not launch for expected PowerView preflight")

    monkeypatch.setattr(smoke_module, "_open_excel_with_finder_and_close", fail_open)

    result = smoke_module._smoke_excel(
        fixture,
        tmp_path / "out",
        timeout=1,
        expected_app_unsupported_features=["power_view"],
    )

    assert result.status == "expected_app_unsupported"
    assert result.status not in {"passed", "skipped"}
    assert smoke_module.EXCEL_UNSUPPORTED_CONTENT_MARKER in result.message


def test_excel_active_workbook_name_treats_missing_value_as_none(monkeypatch) -> None:
    class FakeProc:
        stdout = "missing value\n"

    monkeypatch.setattr(
        smoke_module,
        "_run_osascript",
        lambda *_args, **_kwargs: FakeProc(),
    )

    assert smoke_module._excel_active_workbook_name() is None


def test_excel_repair_dialog_detection() -> None:
    dialog = (
        "windows=after-fixture.xlsx  -  Repaired\n"
        "buttons=ViewDelete\n"
        "text=Excel was able to open the file by repairing or removing "
        "the unreadable content."
    )

    assert smoke_module._is_excel_repair_dialog(dialog)
    assert not smoke_module._is_excel_repair_dialog("windows=fixture.xlsx")


def test_excel_recovery_prompt_is_not_repair_dialog() -> None:
    dialog = (
        "windows=Book1\n"
        "buttons=NoYes\n"
        "text=Your recent changes were saved. Do you want to continue "
        "working where you left off? Open recovered workbooks?"
    )

    assert smoke_module._is_excel_recovery_prompt(dialog)
    assert not smoke_module._is_excel_repair_dialog(dialog)


def test_excel_unsupported_content_dialog_detection() -> None:
    dialog = (
        "windows=real-excel-powerpivot-contoso-pnl.xlsx\n"
        "buttons=Open as Read-OnlyCancel\n"
        "text=This workbook contains content that isn't supported in this "
        "version of Excel. PowerView"
    )

    assert smoke_module._is_excel_unsupported_content_dialog(dialog)
    assert smoke_module._is_excel_unsupported_content_dialog(
        "buttons=Open as Read-OnlyCancel\ntext=Power View"
    )
    assert not smoke_module._is_excel_unsupported_content_dialog(
        "windows=Power View Dashboard.xlsx"
    )
    assert not smoke_module._is_excel_unsupported_content_dialog("windows=fixture.xlsx")


def test_dismiss_excel_repair_dialog_does_not_click_repair(monkeypatch) -> None:
    scripts: list[str] = []

    class FakeProc:
        stdout = ""
        stderr = ""
        returncode = 0

    def fake_run(script: str, **_kwargs):
        scripts.append(script)
        return FakeProc()

    monkeypatch.setattr(smoke_module, "_run_osascript", fake_run)

    smoke_module._dismiss_excel_repair_dialogs()

    script = scripts[0]
    assert 'button "No"' in script
    assert 'button "Delete"' in script
    assert 'button "Yes"' not in script
    assert 'button "Recover"' not in script


def test_dismiss_excel_unsupported_content_dialog_does_not_open_read_only(
    monkeypatch,
) -> None:
    scripts: list[str] = []

    class FakeProc:
        stdout = ""
        stderr = ""
        returncode = 0

    def fake_run(script: str, **_kwargs):
        scripts.append(script)
        return FakeProc()

    monkeypatch.setattr(smoke_module, "_run_osascript", fake_run)

    smoke_module._dismiss_excel_unsupported_content_dialogs()

    script = scripts[0]
    assert 'button "Cancel"' in script
    assert 'button "Open as Read-Only"' not in script


def test_run_osascript_timeout_tolerates_process_group_permission_error(
    monkeypatch,
) -> None:
    class FakeProc:
        args = ["osascript", "-e", "script"]
        pid = 12345

        def __init__(self) -> None:
            self.calls = 0
            self.killed = False

        def communicate(self, timeout: int | None = None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(self.args, timeout or 1)
            return "stdout", "stderr"

        def kill(self) -> None:
            self.killed = True

    fake_proc = FakeProc()
    monkeypatch.setattr(
        smoke_module.subprocess,
        "Popen",
        lambda *_args, **_kwargs: fake_proc,
    )

    def fake_killpg(_pid: int, _signal: int) -> None:
        raise PermissionError("operation not permitted")

    monkeypatch.setattr(smoke_module.os, "killpg", fake_killpg, raising=False)

    try:
        smoke_module._run_osascript("script", timeout=1)
    except subprocess.TimeoutExpired as exc:
        assert exc.output == "stdout"
        assert exc.stderr == "stderr"
    else:
        raise AssertionError("expected TimeoutExpired")
    assert fake_proc.killed is True


def test_run_osascript_timeout_falls_back_without_process_groups(
    monkeypatch,
) -> None:
    class FakeProc:
        args = ["osascript", "-e", "script"]
        pid = 12345

        def __init__(self) -> None:
            self.calls = 0
            self.killed = False

        def communicate(self, timeout: int | None = None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(self.args, timeout or 1)
            return "stdout", "stderr"

        def kill(self) -> None:
            self.killed = True

    fake_proc = FakeProc()
    monkeypatch.setattr(
        smoke_module.subprocess,
        "Popen",
        lambda *_args, **_kwargs: fake_proc,
    )
    monkeypatch.delattr(smoke_module.os, "killpg", raising=False)

    try:
        smoke_module._run_osascript("script", timeout=1)
    except subprocess.TimeoutExpired as exc:
        assert exc.output == "stdout"
        assert exc.stderr == "stderr"
    else:
        raise AssertionError("expected TimeoutExpired")
    assert fake_proc.killed is True


def test_run_osascript_timeout_falls_back_without_sigkill(
    monkeypatch,
) -> None:
    class FakeProc:
        args = ["osascript", "-e", "script"]
        pid = 12345

        def __init__(self) -> None:
            self.calls = 0
            self.killed = False

        def communicate(self, timeout: int | None = None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(self.args, timeout or 1)
            return "stdout", "stderr"

        def kill(self) -> None:
            self.killed = True

    fake_proc = FakeProc()
    monkeypatch.setattr(
        smoke_module.subprocess,
        "Popen",
        lambda *_args, **_kwargs: fake_proc,
    )
    monkeypatch.delattr(smoke_module.signal, "SIGKILL", raising=False)

    try:
        smoke_module._run_osascript("script", timeout=1)
    except subprocess.TimeoutExpired as exc:
        assert exc.output == "stdout"
        assert exc.stderr == "stderr"
    else:
        raise AssertionError("expected TimeoutExpired")
    assert fake_proc.killed is True


def test_run_smoke_reports_failure_count(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    fixture = fixture_dir / "simple.xlsx"
    _make_fixture(fixture)

    def fake_smoke(src: Path, _output_dir: Path, _timeout: int, **_kwargs):
        return smoke_module.AppSmokeResult(
            fixture=src.name,
            mutation="source",
            app="libreoffice",
            status="failed",
            output=None,
            message="simulated failure",
        )

    monkeypatch.setattr(smoke_module, "_smoke_libreoffice", fake_smoke)

    report = smoke_module.run_smoke(
        fixture_dir,
        output_dir,
        apps=("libreoffice",),
        timeout=1,
    )

    assert report["result_count"] == 1
    assert report["failure_count"] == 1
    assert report["clean_pass_count"] == 0
    assert report["skipped_count"] == 0
    assert report["expected_app_unsupported_count"] == 0
    assert report["unexpected_app_unsupported_count"] == 0
    assert report["non_clean_count"] == 1
    assert report["mutations"] == ["source"]
    assert report["aborted"] is False
    assert report["abort_reason"] is None
    assert (output_dir / "app-smoke-report.json").is_file()


def test_run_smoke_reports_expected_unsupported_separately(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    fixture = fixture_dir / "powerview.xlsx"
    _make_fixture(fixture)

    def fake_smoke(src: Path, _output_dir: Path, _timeout: int, **_kwargs):
        return smoke_module.AppSmokeResult(
            fixture=src.name,
            mutation="source",
            app="excel",
            status="expected_app_unsupported",
            output=str(src),
            message=f"{smoke_module.EXCEL_UNSUPPORTED_CONTENT_MARKER} simulated",
        )

    monkeypatch.setattr(smoke_module, "_smoke_excel", fake_smoke)

    report = smoke_module.run_smoke(
        fixture_dir,
        output_dir,
        apps=("excel",),
        timeout=1,
    )

    assert report["result_count"] == 1
    assert report["failure_count"] == 0
    assert report["clean_pass_count"] == 0
    assert report["skipped_count"] == 0
    assert report["expected_app_unsupported_count"] == 1
    assert report["unexpected_app_unsupported_count"] == 0
    assert report["non_clean_count"] == 1
    assert (output_dir / "app-smoke-report.json").is_file()


def test_run_smoke_aborts_after_first_excel_repair_dialog(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "a.xlsx")
    _make_fixture(fixture_dir / "b.xlsx")
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()
    monkeypatch.setattr(smoke_module, "EXCEL_APP", str(excel_app))

    seen_sources: list[str] = []

    def fake_smoke(src: Path, _output_dir: Path, _timeout: int, **_kwargs):
        seen_sources.append(src.name)
        return smoke_module.AppSmokeResult(
            fixture=src.name,
            mutation="source",
            app="excel",
            status="failed",
            output=None,
            message=f"{smoke_module.EXCEL_REPAIR_MARKER} simulated",
        )

    monkeypatch.setattr(smoke_module, "_smoke_excel", fake_smoke)

    report = smoke_module.run_smoke(
        fixture_dir,
        output_dir,
        apps=("excel",),
        timeout=1,
    )

    assert report["aborted"] is True
    assert "stopped after first Microsoft Excel repair dialog" in report["abort_reason"]
    assert report["result_count"] == 1
    assert report["failure_count"] == 1
    assert report["unexpected_app_unsupported_count"] == 0
    assert report["expected_app_unsupported_count"] == 0
    assert report["clean_pass_count"] == 0
    assert report["non_clean_count"] == 1
    assert len(seen_sources) == 1
    assert (output_dir / "app-smoke-report.json").is_file()


def test_run_smoke_aborts_after_first_excel_unsupported_content_dialog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "a.xlsx")
    _make_fixture(fixture_dir / "b.xlsx")
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()
    monkeypatch.setattr(smoke_module, "EXCEL_APP", str(excel_app))

    seen_sources: list[str] = []

    def fake_smoke(src: Path, _output_dir: Path, _timeout: int, **_kwargs):
        seen_sources.append(src.name)
        return smoke_module.AppSmokeResult(
            fixture=src.name,
            mutation="source",
            app="excel",
            status="failed",
            output=None,
            message=f"{smoke_module.EXCEL_UNSUPPORTED_CONTENT_MARKER} simulated",
        )

    monkeypatch.setattr(smoke_module, "_smoke_excel", fake_smoke)

    report = smoke_module.run_smoke(
        fixture_dir,
        output_dir,
        apps=("excel",),
        timeout=1,
    )

    assert report["aborted"] is True
    assert "unsupported-content dialog" in report["abort_reason"]
    assert report["result_count"] == 1
    assert report["failure_count"] == 1
    assert report["unexpected_app_unsupported_count"] == 1
    assert report["expected_app_unsupported_count"] == 0
    assert report["clean_pass_count"] == 0
    assert report["non_clean_count"] == 1
    assert len(seen_sources) == 1
    assert (output_dir / "app-smoke-report.json").is_file()


def test_run_smoke_can_continue_after_excel_repair_dialog(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _make_fixture(fixture_dir / "a.xlsx")
    _make_fixture(fixture_dir / "b.xlsx")
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()
    monkeypatch.setattr(smoke_module, "EXCEL_APP", str(excel_app))

    def fake_smoke(src: Path, _output_dir: Path, _timeout: int, **_kwargs):
        return smoke_module.AppSmokeResult(
            fixture=src.name,
            mutation="source",
            app="excel",
            status="failed",
            output=None,
            message=f"{smoke_module.EXCEL_REPAIR_MARKER} simulated",
        )

    monkeypatch.setattr(smoke_module, "_smoke_excel", fake_smoke)

    report = smoke_module.run_smoke(
        fixture_dir,
        output_dir,
        apps=("excel",),
        timeout=1,
        stop_on_excel_repair=False,
    )

    assert report["aborted"] is False
    assert report["result_count"] == 2
    assert report["failure_count"] == 2


def test_run_smoke_can_apply_mutation_before_app_smoke(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    fixture = fixture_dir / "simple.xlsx"
    _make_fixture(fixture)
    seen_sources: list[Path] = []

    def fake_smoke(src: Path, _output_dir: Path, _timeout: int):
        seen_sources.append(src)
        return smoke_module.AppSmokeResult(
            fixture=src.name,
            mutation="source",
            app="libreoffice",
            status="passed",
            output=str(src),
            message="ok",
        )

    monkeypatch.setattr(smoke_module, "_smoke_libreoffice", fake_smoke)

    report = smoke_module.run_smoke(
        fixture_dir,
        output_dir,
        apps=("libreoffice",),
        timeout=1,
        mutations=("marker_cell",),
    )

    assert report["result_count"] == 1
    assert report["failure_count"] == 0
    assert report["clean_pass_count"] == 1
    assert report["expected_app_unsupported_count"] == 0
    assert report["unexpected_app_unsupported_count"] == 0
    assert report["non_clean_count"] == 0
    assert report["mutations"] == ["marker_cell"]
    result = report["results"][0]
    assert result["fixture"] == "simple.xlsx"
    assert result["mutation"] == "marker_cell"
    assert seen_sources[0].name == "after-simple.xlsx"
    assert seen_sources[0].is_file()


def _write_executable(path: Path, body: str) -> str:
    path.write_text(body)
    path.chmod(0o755)
    return str(path)


def test_find_libreoffice_skips_broken_candidate(
    tmp_path: Path, monkeypatch
) -> None:
    broken = str(tmp_path / "broken-soffice")
    working = str(tmp_path / "working-soffice")
    Path(broken).touch()
    Path(working).touch()
    monkeypatch.setattr(smoke_module, "LIBREOFFICE_CANDIDATES", (broken,))
    monkeypatch.setattr(smoke_module.shutil, "which", lambda name: working)
    monkeypatch.setattr(
        smoke_module,
        "_is_usable_libreoffice",
        lambda path: str(path) == working,
    )
    smoke_module._find_libreoffice.cache_clear()

    assert smoke_module._find_libreoffice() == working


def test_find_libreoffice_returns_none_when_candidates_are_unusable(
    tmp_path: Path, monkeypatch
) -> None:
    broken = _write_executable(
        tmp_path / "broken-soffice",
        "#!/bin/sh\nexit 127\n",
    )
    monkeypatch.setattr(smoke_module, "LIBREOFFICE_CANDIDATES", (broken,))
    monkeypatch.setattr(smoke_module.shutil, "which", lambda name: None)
    smoke_module._find_libreoffice.cache_clear()

    assert smoke_module._find_libreoffice() is None
