from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType

import pytest


def _load_interactive_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_ooxml_interactive_evidence.py"
    spec = importlib.util.spec_from_file_location("audit_ooxml_interactive_evidence", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


interactive = _load_interactive_module()


def _load_probe_runner_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_ooxml_interactive_probe.py"
    spec = importlib.util.spec_from_file_location("run_ooxml_interactive_probe", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe_runner = _load_probe_runner_module()


def test_excel_active_workbook_name_treats_timeout_as_not_ready(monkeypatch) -> None:
    def fake_run_osascript(_script: str, timeout: int):
        assert timeout == 5
        raise subprocess.TimeoutExpired(["osascript"], timeout)

    monkeypatch.setattr(probe_runner.run_ooxml_app_smoke, "_run_osascript", fake_run_osascript)

    assert probe_runner.run_ooxml_app_smoke._excel_active_workbook_name() is None


def test_interactive_audit_marks_absent_probes_not_applicable(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    _write_plain_workbook(fixture_dir / "plain.xlsx")
    _write_manifest(fixture_dir, "plain.xlsx")

    report = interactive.audit_interactive_evidence(fixture_dir)

    assert report["ready"] is True
    assert report["probes"]["slicer_selection_state"]["status"] == "not_applicable"
    assert report["probes"]["macro_project_presence"]["status"] == "not_applicable"


def test_interactive_audit_requires_probe_for_applicable_feature(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_manifest(fixture_dir, "macro.xlsm")

    report = interactive.audit_interactive_evidence(fixture_dir)

    assert report["ready"] is False
    macro = report["probes"]["macro_project_presence"]
    assert macro["status"] == "missing"
    assert macro["candidate_fixtures"] == ["macro.xlsm"]
    assert macro["missing"] == ["interactive_presence_probe_pass"]
    assert macro["probe_kind"] == "ooxml_state_presence"


def test_interactive_audit_accepts_passing_probe_report(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_manifest(fixture_dir, "macro.xlsm")
    probe_report = tmp_path / "interactive-report.json"
    probe_report.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "fixture": "macro.xlsm",
                        "probe": "macro_project_presence",
                        "status": "passed",
                    }
                ]
            }
        )
    )

    report = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[probe_report],
    )

    assert report["ready"] is True
    macro = report["probes"]["macro_project_presence"]
    assert macro["status"] == "clear"
    assert macro["passed_fixtures"] == ["macro.xlsm"]
    assert macro["probe_kind"] == "ooxml_state_presence"
    assert report["probe_kind"] == "ooxml_state_presence"


def test_interactive_audit_accepts_expected_unsupported_content_prompt(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    _write_powerview_data_model_workbook(fixture_dir / "powerview.xlsx")
    _write_manifest(fixture_dir, "powerview.xlsx")
    probe_report = tmp_path / "interactive-report.json"
    probe_report.write_text(
        json.dumps(
            {
                "probe_kind": "excel_ui_interaction",
                "results": [
                    {
                        "fixture": "powerview.xlsx",
                        "probe": "unsupported_content_prompt",
                        "probe_kind": "excel_ui_interaction",
                        "status": "passed",
                    }
                ],
            }
        )
    )

    report = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[probe_report],
        probe_kind=interactive.UI_INTERACTION_PROBE_KIND,
        required_probes=("unsupported_content_prompt",),
    )

    assert report["ready"] is True
    unsupported = report["probes"]["unsupported_content_prompt"]
    assert unsupported["status"] == "clear"
    assert unsupported["passed_fixtures"] == ["powerview.xlsx"]
    assert unsupported["probe_kind"] == "excel_ui_interaction"


def test_interactive_audit_does_not_go_ready_on_incomplete_report(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_manifest(fixture_dir, "macro.xlsm")
    probe_report = tmp_path / "interactive-report.json"
    probe_report.write_text(
        json.dumps(
            {
                "completed": False,
                "results": [
                    {
                        "fixture": "macro.xlsm",
                        "probe": "macro_project_presence",
                        "status": "passed",
                    }
                ],
            }
        )
    )

    report = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[probe_report],
    )

    assert report["ready"] is False
    assert report["incomplete_report_count"] == 1
    assert report["probes"]["macro_project_presence"]["status"] == "clear"


def test_interactive_audit_rejects_mismatched_probe_kind(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_manifest(fixture_dir, "macro.xlsm")
    probe_report = tmp_path / "interactive-report.json"
    probe_report.write_text(
        json.dumps(
            {
                "probe_kind": "click_level_interaction",
                "results": [
                    {
                        "fixture": "macro.xlsm",
                        "probe": "macro_project_presence",
                        "probe_kind": "click_level_interaction",
                        "status": "passed",
                    }
                ],
            }
        )
    )

    report = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[probe_report],
    )

    macro = report["probes"]["macro_project_presence"]
    assert report["ready"] is False
    assert macro["status"] == "missing"
    assert macro["missing"] == ["interactive_presence_probe_pass"]


def test_interactive_audit_can_require_ui_interaction_report(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    _write_slicer_workbook(fixture_dir / "slicer.xlsx")
    _write_manifest(fixture_dir, "slicer.xlsx")
    presence_report = tmp_path / "presence-report.json"
    presence_report.write_text(
        json.dumps(
            {
                "probe_kind": "ooxml_state_presence",
                "results": [
                    {
                        "fixture": "slicer.xlsx",
                        "probe": "slicer_selection_state",
                        "probe_kind": "ooxml_state_presence",
                        "status": "passed",
                    }
                ],
            }
        )
    )
    ui_report = tmp_path / "ui-report.json"
    ui_report.write_text(
        json.dumps(
            {
                "probe_kind": "excel_ui_interaction",
                "results": [
                    {
                        "fixture": "slicer.xlsx",
                        "probe": "slicer_selection_state",
                        "probe_kind": "excel_ui_interaction",
                        "status": "passed",
                        "ui_actions": ["clicked Excel slicer item"],
                    }
                ],
            }
        )
    )

    missing = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[presence_report],
        probe_kind="excel_ui_interaction",
    )
    clear = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[presence_report, ui_report],
        probe_kind="excel_ui_interaction",
    )

    assert missing["ready"] is False
    assert missing["probe_kind"] == "excel_ui_interaction"
    assert missing["probes"]["slicer_selection_state"]["missing"] == [
        "excel_ui_interaction_pass"
    ]
    assert clear["ready"] is True
    assert clear["probes"]["slicer_selection_state"]["status"] == "clear"
    assert clear["probes"]["slicer_selection_state"]["probe_kind"] == "excel_ui_interaction"


def test_interactive_audit_can_scope_required_probes_for_mixed_fixture(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    mixed = fixture_dir / "mixed-slicer-pivot.xlsx"
    _write_slicer_workbook(mixed)
    _add_pivot_parts(mixed)
    _write_manifest(fixture_dir, mixed.name)
    ui_report = tmp_path / "ui-report.json"
    ui_report.write_text(
        json.dumps(
            {
                "completed": True,
                "probe_kind": "excel_ui_interaction",
                "probes": ["slicer_selection_state"],
                "results": [
                    {
                        "fixture": mixed.name,
                        "probe": "slicer_selection_state",
                        "probe_kind": "excel_ui_interaction",
                        "status": "passed",
                        "ui_actions": ["clicked Excel slicer item"],
                    }
                ],
            }
        )
    )

    unfiltered = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[ui_report],
        probe_kind="excel_ui_interaction",
    )
    scoped = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[ui_report],
        probe_kind="excel_ui_interaction",
        required_probes=("slicer_selection_state",),
    )

    assert unfiltered["ready"] is False
    assert unfiltered["probes"]["pivot_refresh_state"]["status"] == "missing"
    assert scoped["ready"] is True
    assert scoped["required_probes"] == ["slicer_selection_state"]
    assert list(scoped["probes"]) == ["slicer_selection_state"]
    assert scoped["probes"]["slicer_selection_state"]["status"] == "clear"


def test_interactive_audit_rejects_unknown_required_probe(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()

    try:
        interactive.audit_interactive_evidence(
            fixture_dir,
            required_probes=("not_a_probe",),
        )
    except ValueError as exc:
        assert "unsupported interactive probe(s): not_a_probe" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_interactive_audit_scopes_incomplete_reports_to_probe_kind(
    tmp_path: Path,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    _write_slicer_workbook(fixture_dir / "slicer.xlsx")
    _write_manifest(fixture_dir, "slicer.xlsx")
    incomplete_presence_report = tmp_path / "incomplete-presence-report.json"
    incomplete_presence_report.write_text(
        json.dumps(
            {
                "completed": False,
                "probe_kind": "ooxml_state_presence",
                "results": [
                    {
                        "fixture": "slicer.xlsx",
                        "probe": "slicer_selection_state",
                        "probe_kind": "ooxml_state_presence",
                        "status": "passed",
                    }
                ],
            }
        )
    )
    incomplete_ui_report = tmp_path / "incomplete-ui-report.json"
    incomplete_ui_report.write_text(
        json.dumps(
            {
                "completed": False,
                "probe_kind": "excel_ui_interaction",
                "results": [
                    {
                        "fixture": "slicer.xlsx",
                        "probe": "slicer_selection_state",
                        "probe_kind": "excel_ui_interaction",
                        "status": "passed",
                    }
                ],
            }
        )
    )
    complete_ui_report = tmp_path / "complete-ui-report.json"
    complete_ui_report.write_text(
        json.dumps(
            {
                "completed": True,
                "probe_kind": "excel_ui_interaction",
                "results": [
                    {
                        "fixture": "slicer.xlsx",
                        "probe": "slicer_selection_state",
                        "probe_kind": "excel_ui_interaction",
                        "status": "passed",
                    }
                ],
            }
        )
    )

    clear = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[incomplete_presence_report, complete_ui_report],
        probe_kind="excel_ui_interaction",
    )
    blocked = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[incomplete_presence_report, incomplete_ui_report],
        probe_kind="excel_ui_interaction",
    )

    assert clear["ready"] is True
    assert clear["incomplete_report_count"] == 0
    assert blocked["ready"] is False
    assert blocked["incomplete_report_count"] == 1
    assert blocked["probes"]["slicer_selection_state"]["status"] == "clear"


def test_interactive_strict_cli_fails_when_probe_missing(tmp_path: Path, capsys) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_manifest(fixture_dir, "macro.xlsm")

    code = interactive.main([str(fixture_dir), "--strict"])

    captured = capsys.readouterr()
    assert code == 1
    payload = json.loads(captured.out)
    assert payload["ready"] is False


def test_interactive_strict_cli_accepts_scoped_probe(
    tmp_path: Path,
    capsys,
) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    mixed = fixture_dir / "mixed-slicer-pivot.xlsx"
    _write_slicer_workbook(mixed)
    _add_pivot_parts(mixed)
    _write_manifest(fixture_dir, mixed.name)
    ui_report = tmp_path / "ui-report.json"
    ui_report.write_text(
        json.dumps(
            {
                "completed": True,
                "probe_kind": "excel_ui_interaction",
                "probes": ["slicer_selection_state"],
                "results": [
                    {
                        "fixture": mixed.name,
                        "probe": "slicer_selection_state",
                        "probe_kind": "excel_ui_interaction",
                        "status": "passed",
                    }
                ],
            }
        )
    )

    code = interactive.main(
        [
            str(fixture_dir),
            "--probe-kind",
            "excel_ui_interaction",
            "--probe",
            "slicer_selection_state",
            "--report",
            str(ui_report),
            "--strict",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert payload["ready"] is True
    assert payload["required_probes"] == ["slicer_selection_state"]


def test_macro_probe_runner_emits_passing_interactive_report(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_manifest(fixture_dir, "macro.xlsm")

    def fake_smoke_excel(src: Path, _output_dir: Path, _timeout: int):
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        fake_smoke_excel,
    )

    report = probe_runner.run_interactive_probes(fixture_dir, output_dir)

    assert report["failure_count"] == 0
    assert report["results"][0]["fixture"] == "macro.xlsm"
    assert report["results"][0]["probe"] == "macro_project_presence"
    assert report["results"][0]["probe_kind"] == "ooxml_state_presence"
    assert report["results"][0]["status"] == "passed"
    audit = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[output_dir / "interactive-probe-report.json"],
    )
    assert audit["probes"]["macro_project_presence"]["status"] == "clear"


def test_probe_runner_writes_incremental_report(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_external_link_workbook(fixture_dir / "external.xlsx")
    fixture_dir.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {"filename": "macro.xlsm", "fixture_id": "macro", "tool": "excel"},
                    {"filename": "external.xlsx", "fixture_id": "external", "tool": "excel"},
                ]
            }
        )
    )
    calls: list[tuple[str, str]] = []

    def fake_run_probe(
        fixture_path: Path,
        fixture_label: str,
        _output_dir: Path,
        *,
        probe: str,
        mutation: str,
        timeout: int,
        probe_kind: str,
        external_link_prompt_mode: str,
    ) -> object:
        report_path = output_dir / "interactive-probe-report.json"
        if calls:
            partial = json.loads(report_path.read_text())
            assert partial["completed"] is False
            assert partial["result_count"] == len(calls)
            assert partial["results"][-1]["fixture"] == calls[-1][0]
        calls.append((fixture_label, probe))
        return probe_runner.InteractiveProbeResult(
            fixture=fixture_label,
            probe=probe,
            probe_kind=probe_kind,
            mutation=mutation,
            app="excel",
            status="passed",
            output=str(fixture_path),
            message=f"timeout={timeout}",
        )

    monkeypatch.setattr(probe_runner, "_run_probe", fake_run_probe)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("macro_project_presence", "external_link_update_prompt"),
    )

    assert calls == [
        ("macro.xlsm", "macro_project_presence"),
        ("external.xlsx", "external_link_update_prompt"),
    ]
    assert report["completed"] is True
    assert report["result_count"] == 2


def test_probe_runner_filters_fixtures(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_external_link_workbook(fixture_dir / "external.xlsx")
    fixture_dir.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {"filename": "macro.xlsm", "fixture_id": "macro", "tool": "excel"},
                    {"filename": "external.xlsx", "fixture_id": "external", "tool": "excel"},
                ]
            }
        )
    )
    calls: list[str] = []

    def fake_run_probe(
        fixture_path: Path,
        fixture_label: str,
        _output_dir: Path,
        *,
        probe: str,
        mutation: str,
        timeout: int,
        probe_kind: str,
        external_link_prompt_mode: str,
    ) -> object:
        calls.append(fixture_label)
        return probe_runner.InteractiveProbeResult(
            fixture=fixture_label,
            probe=probe,
            probe_kind=probe_kind,
            mutation=mutation,
            app="excel",
            status="passed",
            output=str(fixture_path),
            message=f"timeout={timeout}",
        )

    monkeypatch.setattr(probe_runner, "_run_probe", fake_run_probe)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("macro_project_presence", "external_link_update_prompt"),
        include_fixture_patterns=("external.*",),
    )

    assert calls == ["external.xlsx"]
    assert report["include_fixture_patterns"] == ["external.*"]
    assert report["result_count"] == 1


def test_macro_probe_runner_fails_when_vba_project_missing(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_manifest(fixture_dir, "macro.xlsm")

    def remove_vba_during_smoke(src: Path, _output_dir: Path, _timeout: int):
        _rewrite_without_vba(src)
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        remove_vba_during_smoke,
    )

    report = probe_runner.run_interactive_probes(fixture_dir, output_dir)

    assert report["failure_count"] == 1
    assert report["results"][0]["status"] == "failed"
    assert "missing after Excel open" in report["results"][0]["message"]


def test_embedded_control_probe_runner_emits_passing_interactive_report(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_embedded_control_workbook(fixture_dir / "control.xlsx")
    _write_manifest(fixture_dir, "control.xlsx")

    def fake_smoke_excel(src: Path, _output_dir: Path, _timeout: int):
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        fake_smoke_excel,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("embedded_control_openability",),
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["fixture"] == "control.xlsx"
    assert report["results"][0]["probe"] == "embedded_control_openability"
    assert report["results"][0]["status"] == "passed"
    audit = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[output_dir / "interactive-probe-report.json"],
    )
    assert audit["probes"]["embedded_control_openability"]["status"] == "clear"


def test_embedded_control_probe_runner_fails_when_control_part_missing(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_embedded_control_workbook(fixture_dir / "control.xlsx")
    _write_manifest(fixture_dir, "control.xlsx")

    def remove_control_during_smoke(src: Path, _output_dir: Path, _timeout: int):
        _rewrite_without_prefixes(src, ("xl/ctrlProps/",))
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        remove_control_during_smoke,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("embedded_control_openability",),
    )

    assert report["failure_count"] == 1
    assert report["results"][0]["status"] == "failed"
    assert "missing after Excel open" in report["results"][0]["message"]


def test_external_link_probe_runner_emits_passing_interactive_report(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_external_link_workbook(fixture_dir / "external-link.xlsx")
    _write_manifest(fixture_dir, "external-link.xlsx")

    def fake_smoke_excel(src: Path, _output_dir: Path, _timeout: int):
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        fake_smoke_excel,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("external_link_update_prompt",),
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["fixture"] == "external-link.xlsx"
    assert report["results"][0]["probe"] == "external_link_update_prompt"
    assert report["results"][0]["status"] == "passed"
    audit = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[output_dir / "interactive-probe-report.json"],
    )
    assert audit["probes"]["external_link_update_prompt"]["status"] == "clear"


def test_external_link_probe_runner_fails_when_link_part_missing(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_external_link_workbook(fixture_dir / "external-link.xlsx")
    _write_manifest(fixture_dir, "external-link.xlsx")

    def remove_external_link_during_smoke(src: Path, _output_dir: Path, _timeout: int):
        _rewrite_without_prefixes(src, ("xl/externalLinks/",))
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        remove_external_link_during_smoke,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("external_link_update_prompt",),
    )

    assert report["failure_count"] == 1
    assert report["results"][0]["status"] == "failed"
    assert "missing after Excel open" in report["results"][0]["message"]


def test_ui_interaction_probe_records_macro_button_click(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_vba_workbook(fixture_dir / "macro.xlsm")
    _write_manifest(fixture_dir, "macro.xlsm")

    def fake_open_with_ui(src: Path, probe: str, timeout: int):
        assert src.name == "macro.xlsm"
        assert probe == "macro_project_presence"
        assert timeout == 90
        return "macro.xlsm", ["clicked button: Disable Macros"]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("macro_project_presence",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["probe_kind"] == "excel_ui_interaction"
    assert report["failure_count"] == 0
    result = report["results"][0]
    assert result["probe"] == "macro_project_presence"
    assert result["probe_kind"] == "excel_ui_interaction"
    assert result["status"] == "passed"
    assert result["ui_actions"] == ["clicked button: Disable Macros"]


def test_unsupported_content_ui_probe_records_open_read_only_click(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_powerview_data_model_workbook(fixture_dir / "powerview.xlsx")
    _write_manifest(fixture_dir, "powerview.xlsx")

    def fake_open_with_ui(src: Path, probe: str, timeout: int):
        assert src.name == "powerview.xlsx"
        assert probe == "unsupported_content_prompt"
        assert timeout == 90
        return "powerview.xlsx", ["clicked button: Open as Read-Only"]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("unsupported_content_prompt",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 0
    result = report["results"][0]
    assert result["fixture"] == "powerview.xlsx"
    assert result["probe"] == "unsupported_content_prompt"
    assert result["probe_kind"] == "excel_ui_interaction"
    assert result["status"] == "passed"
    assert result["ui_actions"] == ["clicked button: Open as Read-Only"]


def test_external_link_ui_probe_forces_and_restores_update_prompt(
    tmp_path: Path, monkeypatch
) -> None:
    fixture = tmp_path / "external-link.xlsx"
    fixture.write_bytes(b"placeholder")
    settings: list[bool] = []

    monkeypatch.setattr(probe_runner, "_mac_screen_is_locked", lambda: False)
    monkeypatch.setattr(probe_runner, "_excel_ask_to_update_links", lambda: False)
    monkeypatch.setattr(probe_runner, "_set_excel_ask_to_update_links", settings.append)
    monkeypatch.setattr(
        probe_runner,
        "_open_excel_with_ui_interaction_impl",
        lambda src, probe, timeout: (
            src.name,
            [f"{probe}:{timeout}", "clicked button: Don't Update"],
        ),
    )

    active_name, actions = probe_runner._open_excel_with_ui_interaction(
        fixture,
        "external_link_update_prompt",
        45,
    )

    assert active_name == "external-link.xlsx"
    assert actions == ["external_link_update_prompt:45", "clicked button: Don't Update"]
    assert settings == [True, False]


def test_external_link_ui_probe_restores_update_prompt_after_failure(
    tmp_path: Path, monkeypatch
) -> None:
    fixture = tmp_path / "external-link.xlsx"
    fixture.write_bytes(b"placeholder")
    settings: list[bool] = []

    def fail_open(_src: Path, _probe: str, _timeout: int) -> tuple[str, list[str]]:
        raise RuntimeError("boom")

    monkeypatch.setattr(probe_runner, "_mac_screen_is_locked", lambda: False)
    monkeypatch.setattr(probe_runner, "_excel_ask_to_update_links", lambda: False)
    monkeypatch.setattr(probe_runner, "_set_excel_ask_to_update_links", settings.append)
    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction_impl", fail_open)

    try:
        probe_runner._open_excel_with_ui_interaction(
            fixture,
            "external_link_update_prompt",
            45,
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected RuntimeError")

    assert settings == [True, False]


def test_external_link_ui_probe_does_not_force_unknown_update_prompt(
    tmp_path: Path, monkeypatch
) -> None:
    fixture = tmp_path / "external-link.xlsx"
    fixture.write_bytes(b"placeholder")
    settings: list[bool] = []
    opened = False

    def open_with_ui(_src: Path, _probe: str, _timeout: int) -> tuple[str, list[str]]:
        nonlocal opened
        opened = True
        return "external-link.xlsx", []

    monkeypatch.setattr(probe_runner, "_mac_screen_is_locked", lambda: False)
    monkeypatch.setattr(probe_runner, "_excel_ask_to_update_links", lambda: None)
    monkeypatch.setattr(probe_runner, "_set_excel_ask_to_update_links", settings.append)
    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction_impl", open_with_ui)

    try:
        probe_runner._open_excel_with_ui_interaction(
            fixture,
            "external_link_update_prompt",
            45,
        )
    except RuntimeError as exc:
        assert "could not read Excel ask to update links setting" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert settings == []
    assert opened is False


def test_external_link_ui_probe_current_prompt_mode_does_not_force_setting(
    tmp_path: Path, monkeypatch
) -> None:
    fixture = tmp_path / "external-link.xlsx"
    fixture.write_bytes(b"placeholder")
    settings: list[bool] = []

    monkeypatch.setattr(probe_runner, "_mac_screen_is_locked", lambda: False)
    monkeypatch.setattr(probe_runner, "_excel_ask_to_update_links", lambda: False)
    monkeypatch.setattr(probe_runner, "_set_excel_ask_to_update_links", settings.append)
    monkeypatch.setattr(
        probe_runner,
        "_open_excel_with_ui_interaction_impl",
        lambda src, probe, timeout: (
            src.name,
            [f"{probe}:{timeout}", "clicked button: Don't Update"],
        ),
    )

    active_name, actions = probe_runner._open_excel_with_ui_interaction(
        fixture,
        "external_link_update_prompt",
        45,
        external_link_prompt_mode=probe_runner.EXTERNAL_LINK_PROMPT_MODE_CURRENT,
    )

    assert active_name == "external-link.xlsx"
    assert actions == ["external_link_update_prompt:45", "clicked button: Don't Update"]
    assert settings == []


def test_ui_interaction_probe_requires_observed_button_click(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_external_link_workbook(fixture_dir / "external-link.xlsx")
    _write_manifest(fixture_dir, "external-link.xlsx")

    def fake_open_with_ui(
        _src: Path,
        _probe: str,
        _timeout: int,
        *,
        external_link_prompt_mode: str,
    ):
        assert external_link_prompt_mode == probe_runner.EXTERNAL_LINK_PROMPT_MODE_FORCE
        return "external-link.xlsx", []

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("external_link_update_prompt",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 1
    result = report["results"][0]
    assert result["status"] == "failed"
    assert "required UI action was not observed" in result["message"]
    assert result["ui_actions"] == []


def test_current_external_link_ui_probe_allows_absent_prompt_click(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_external_link_workbook(fixture_dir / "external-link.xlsx")
    _write_manifest(fixture_dir, "external-link.xlsx")

    def fake_open_with_ui(
        _src: Path,
        _probe: str,
        _timeout: int,
        *,
        external_link_prompt_mode: str,
    ):
        assert external_link_prompt_mode == probe_runner.EXTERNAL_LINK_PROMPT_MODE_CURRENT
        return "external-link.xlsx", []

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("external_link_update_prompt",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
        external_link_prompt_mode=probe_runner.EXTERNAL_LINK_PROMPT_MODE_CURRENT,
    )

    assert report["failure_count"] == 0
    result = report["results"][0]
    assert result["status"] == "passed"
    assert "preserved the current Excel external-link prompt setting" in result["message"]
    assert result["ui_actions"] == []


def test_ui_interaction_probe_records_embedded_control_click(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_embedded_control_workbook(fixture_dir / "control.xlsx")
    _write_manifest(fixture_dir, "control.xlsx")

    def fake_open_with_ui(src: Path, probe: str, _timeout: int):
        assert probe == "embedded_control_openability"
        _rewrite_control_selection(src, value="2")
        return "control.xlsx", [
            "clicked Excel embedded/control object",
            "clicked Excel embedded/control object: List Box 1",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("embedded_control_openability",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["ui_actions"] == [
        "clicked Excel embedded/control object",
        "clicked Excel embedded/control object: List Box 1",
        "saved active workbook",
    ]


def test_embedded_control_ui_interaction_requires_persisted_state_change(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_embedded_control_workbook(fixture_dir / "control.xlsx")
    _write_manifest(fixture_dir, "control.xlsx")

    def fake_open_with_ui(_src: Path, probe: str, _timeout: int):
        assert probe == "embedded_control_openability"
        return "control.xlsx", [
            "clicked Excel embedded/control object",
            "clicked Excel embedded/control object: List Box 1",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("embedded_control_openability",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 1
    assert "did not change persisted control-property state" in report["results"][0]["message"]


def test_embedded_control_ui_interaction_accepts_stateless_button_click(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_button_control_workbook(fixture_dir / "button.xlsx")
    _write_manifest(fixture_dir, "button.xlsx")

    def fake_open_with_ui(_src: Path, probe: str, _timeout: int):
        assert probe == "embedded_control_openability"
        return "button.xlsx", [
            "clicked Excel embedded/control object",
            "clicked Excel embedded/control object: Button 1",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("embedded_control_openability",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["status"] == "passed"


def test_ui_interaction_probe_records_pivot_refresh_command(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_pivot_workbook(fixture_dir / "pivot.xlsx")
    _write_manifest(fixture_dir, "pivot.xlsx")

    def fake_open_with_ui(_src: Path, probe: str, _timeout: int):
        assert probe == "pivot_refresh_state"
        return "pivot.xlsx", ["executed Excel command: refresh all"]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("pivot_refresh_state",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 0
    result = report["results"][0]
    assert result["probe"] == "pivot_refresh_state"
    assert result["ui_actions"] == ["executed Excel command: refresh all"]


def test_ui_interaction_probe_records_slicer_item_click(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_slicer_workbook(fixture_dir / "slicer.xlsx")
    _write_manifest(fixture_dir, "slicer.xlsx")

    def fake_open_with_ui(src: Path, probe: str, _timeout: int):
        assert probe == "slicer_selection_state"
        _rewrite_slicer_filter(src, value="EAST")
        return "slicer.xlsx", [
            "selected Excel slicer shape",
            "selected Excel slicer shape: Slicer_Region",
            "clicked Excel slicer item",
            "clicked Excel slicer item: Slicer_Region",
            "clicked Excel slicer item: Slicer_Year",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("slicer_selection_state",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["ui_actions"] == [
        "selected Excel slicer shape",
        "selected Excel slicer shape: Slicer_Region",
        "clicked Excel slicer item",
        "clicked Excel slicer item: Slicer_Region",
        "clicked Excel slicer item: Slicer_Year",
        "saved active workbook",
    ]


def test_ui_interaction_probe_records_timeline_shape_selection(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_timeline_workbook(fixture_dir / "timeline.xlsx")
    _write_manifest(fixture_dir, "timeline.xlsx")

    def fake_open_with_ui(_src: Path, probe: str, _timeout: int):
        assert probe == "timeline_selection_state"
        return "timeline.xlsx", [
            "selected Excel timeline shape",
            "selected Excel timeline shape: Timeline_Date",
            "clicked Excel timeline month",
            "clicked Excel timeline month: May",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("timeline_selection_state",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["ui_actions"] == [
        "selected Excel timeline shape",
        "selected Excel timeline shape: Timeline_Date",
        "clicked Excel timeline month",
        "clicked Excel timeline month: May",
        "saved active workbook",
    ]


def test_probe_shape_names_come_from_authored_slicer_and_timeline_parts(tmp_path: Path) -> None:
    slicer = tmp_path / "slicer.xlsx"
    timeline = tmp_path / "timeline.xlsx"
    _write_slicer_workbook(slicer)
    _write_timeline_workbook(timeline)

    assert probe_runner._probe_shape_names(slicer, "slicer_selection_state") == [
        "Slicer_Region",
        "Slicer_Year",
    ]
    assert probe_runner._probe_shape_names(timeline, "timeline_selection_state") == [
        "Timeline_Date"
    ]


def test_control_shape_names_come_from_authored_worksheet_controls(tmp_path: Path) -> None:
    control = tmp_path / "control.xlsx"
    _write_embedded_control_workbook(control)

    assert probe_runner._control_shape_names(control) == ["List Box 1"]


def test_mouse_click_rejects_locked_screen(monkeypatch) -> None:
    monkeypatch.setattr(probe_runner, "_mac_screen_is_locked", lambda: True)

    with pytest.raises(RuntimeError, match="screen is locked"):
        probe_runner._post_mouse_click(10, 10)


def test_screen_lock_probe_skips_timed_out_quartz_candidate(monkeypatch) -> None:
    candidates = [Path("/slow/python"), Path("/working/python")]
    calls: list[Path] = []

    def fake_run(args, **_kwargs):
        candidate = Path(args[0])
        calls.append(candidate)
        if candidate == candidates[0]:
            raise subprocess.TimeoutExpired(args, 3)
        return SimpleNamespace(returncode=0, stdout="0\n", stderr="")

    monkeypatch.setattr(probe_runner, "_SCREEN_LOCKED_CACHE", None)
    monkeypatch.setattr(probe_runner, "_python_candidates_for_quartz", lambda: candidates)
    monkeypatch.setattr(probe_runner.subprocess, "run", fake_run)

    assert probe_runner._mac_screen_is_locked() is False
    assert calls == candidates


def test_ui_interaction_open_rejects_locked_screen(monkeypatch, tmp_path: Path) -> None:
    workbook = tmp_path / "simple.xlsx"
    workbook.write_bytes(b"placeholder")
    monkeypatch.setattr(probe_runner, "_mac_screen_is_locked", lambda: True)

    def fail_popen(*_args, **_kwargs):
        raise AssertionError("Excel should not be launched while the screen is locked")

    monkeypatch.setattr(probe_runner.subprocess, "Popen", fail_popen)

    with pytest.raises(RuntimeError, match="unlock before Excel UI interaction probes"):
        probe_runner._open_excel_with_ui_interaction_impl(
            workbook,
            "macro_project_presence",
            timeout=1,
        )


def test_ui_interaction_wrapper_rejects_locked_screen_before_applescript(
    monkeypatch, tmp_path: Path
) -> None:
    workbook = tmp_path / "simple.xlsx"
    workbook.write_bytes(b"placeholder")
    monkeypatch.setattr(probe_runner, "_mac_screen_is_locked", lambda: True)

    def fail_excel_setting(*_args, **_kwargs):
        raise AssertionError("Excel AppleScript helpers should not run while locked")

    monkeypatch.setattr(probe_runner, "_excel_ask_to_update_links", fail_excel_setting)
    monkeypatch.setattr(probe_runner, "_set_excel_ask_to_update_links", fail_excel_setting)
    monkeypatch.setattr(probe_runner.subprocess, "Popen", fail_excel_setting)

    with pytest.raises(RuntimeError, match="unlock before Excel UI interaction probes"):
        probe_runner._open_excel_with_ui_interaction(
            workbook,
            "external_link_update_prompt",
            timeout=1,
        )


def test_ui_interaction_reports_locked_screen_blocker(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_embedded_control_workbook(fixture_dir / "control.xlsx")
    _write_manifest(fixture_dir, "control.xlsx")

    def fake_open_with_ui(_src: Path, probe: str, _timeout: int):
        assert probe == "embedded_control_openability"
        return "control.xlsx", [
            "failed Excel embedded/control click: macOS screen is locked; "
            "unlock before Excel UI mouse probes"
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("embedded_control_openability",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 1
    assert "macOS screen is locked" in report["results"][0]["message"]


def test_slicer_ui_interaction_requires_persisted_filter_change(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_slicer_workbook(fixture_dir / "slicer.xlsx")
    _write_manifest(fixture_dir, "slicer.xlsx")

    def fake_open_with_ui(_src: Path, probe: str, _timeout: int):
        assert probe == "slicer_selection_state"
        return "slicer.xlsx", [
            "selected Excel slicer shape",
            "selected Excel slicer shape: Slicer_Region",
            "clicked Excel slicer item",
            "clicked Excel slicer item: Slicer_Region",
            "clicked Excel slicer item: Slicer_Year",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("slicer_selection_state",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 1
    assert "did not change persisted table filter or slicer-cache item state" in (
        report["results"][0]["message"]
    )


def test_slicer_ui_interaction_accepts_persisted_filter_change(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_slicer_workbook(fixture_dir / "slicer.xlsx")
    _write_manifest(fixture_dir, "slicer.xlsx")

    def fake_open_with_ui(src: Path, probe: str, _timeout: int):
        assert probe == "slicer_selection_state"
        _rewrite_slicer_filter(src, value="EAST")
        return "slicer.xlsx", [
            "selected Excel slicer shape",
            "selected Excel slicer shape: Slicer_Region",
            "clicked Excel slicer item",
            "clicked Excel slicer item: Slicer_Region",
            "clicked Excel slicer item: Slicer_Year",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("slicer_selection_state",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["ui_actions"] == [
        "selected Excel slicer shape",
        "selected Excel slicer shape: Slicer_Region",
        "clicked Excel slicer item",
        "clicked Excel slicer item: Slicer_Region",
        "clicked Excel slicer item: Slicer_Year",
        "saved active workbook",
    ]


def test_slicer_ui_interaction_accepts_persisted_slicer_cache_change(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_pivot_slicer_workbook(fixture_dir / "pivot-slicer.xlsx")
    _write_manifest(fixture_dir, "pivot-slicer.xlsx")

    def fake_open_with_ui(src: Path, probe: str, _timeout: int):
        assert probe == "slicer_selection_state"
        _rewrite_slicer_cache_selection(src)
        return "pivot-slicer.xlsx", [
            "selected Excel slicer shape",
            "selected Excel slicer shape: Slicer_Month",
            "clicked Excel slicer item",
            "clicked Excel slicer item: Slicer_Month",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("slicer_selection_state",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["status"] == "passed"


def test_timeline_ui_interaction_requires_persisted_selection_change(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_timeline_workbook_with_selection(fixture_dir / "timeline.xlsx")
    _write_manifest(fixture_dir, "timeline.xlsx")

    def fake_open_with_ui(_src: Path, probe: str, _timeout: int):
        assert probe == "timeline_selection_state"
        return "timeline.xlsx", [
            "selected Excel timeline shape",
            "selected Excel timeline shape: Timeline_Date",
            "clicked Excel timeline month",
            "clicked Excel timeline month: May",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("timeline_selection_state",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 1
    assert "did not change persisted timeline selection" in report["results"][0]["message"]


def test_timeline_ui_interaction_accepts_persisted_selection_change(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_timeline_workbook_with_selection(fixture_dir / "timeline.xlsx")
    _write_manifest(fixture_dir, "timeline.xlsx")

    def fake_open_with_ui(src: Path, probe: str, _timeout: int):
        assert probe == "timeline_selection_state"
        _rewrite_timeline_selection(
            src,
            start="2012-05-01T00:00:00",
            end="2012-05-31T00:00:00",
        )
        return "timeline.xlsx", [
            "selected Excel timeline shape",
            "selected Excel timeline shape: Timeline_Date",
            "clicked Excel timeline month",
            "clicked Excel timeline month: May",
            "saved active workbook",
        ]

    monkeypatch.setattr(probe_runner, "_open_excel_with_ui_interaction", fake_open_with_ui)

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("timeline_selection_state",),
        probe_kind=probe_runner.UI_INTERACTION_PROBE_KIND,
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["ui_actions"] == [
        "selected Excel timeline shape",
        "selected Excel timeline shape: Timeline_Date",
        "clicked Excel timeline month",
        "clicked Excel timeline month: May",
        "saved active workbook",
    ]


def test_pivot_probe_runner_emits_passing_interactive_report(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_pivot_workbook(fixture_dir / "pivot.xlsx")
    _write_manifest(fixture_dir, "pivot.xlsx")

    def fake_smoke_excel(src: Path, _output_dir: Path, _timeout: int):
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        fake_smoke_excel,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("pivot_refresh_state",),
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["fixture"] == "pivot.xlsx"
    assert report["results"][0]["probe"] == "pivot_refresh_state"
    assert report["results"][0]["status"] == "passed"
    audit = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[output_dir / "interactive-probe-report.json"],
    )
    assert audit["probes"]["pivot_refresh_state"]["status"] == "clear"


def test_pivot_probe_runner_fails_when_pivot_part_missing(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_pivot_workbook(fixture_dir / "pivot.xlsx")
    _write_manifest(fixture_dir, "pivot.xlsx")

    def remove_pivot_during_smoke(src: Path, _output_dir: Path, _timeout: int):
        _rewrite_without_prefixes(src, ("xl/pivotCache/", "xl/pivotTables/"))
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        remove_pivot_during_smoke,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("pivot_refresh_state",),
    )

    assert report["failure_count"] == 1
    assert report["results"][0]["status"] == "failed"
    assert "missing after Excel open" in report["results"][0]["message"]


def test_slicer_probe_runner_emits_passing_interactive_report(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_slicer_workbook(fixture_dir / "slicer.xlsx")
    _write_manifest(fixture_dir, "slicer.xlsx")

    def fake_smoke_excel(src: Path, _output_dir: Path, _timeout: int):
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        fake_smoke_excel,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("slicer_selection_state",),
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["fixture"] == "slicer.xlsx"
    assert report["results"][0]["probe"] == "slicer_selection_state"
    assert report["results"][0]["probe_kind"] == "ooxml_state_presence"
    assert report["results"][0]["status"] == "passed"
    audit = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[output_dir / "interactive-probe-report.json"],
    )
    assert audit["probes"]["slicer_selection_state"]["status"] == "clear"
    assert (
        audit["probes"]["slicer_selection_state"]["label"]
        == "Slicer OOXML state remains present after Excel open/save"
    )
    assert audit["probes"]["slicer_selection_state"]["probe_kind"] == "ooxml_state_presence"


def test_slicer_probe_runner_fails_when_slicer_part_missing(tmp_path: Path, monkeypatch) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_slicer_workbook(fixture_dir / "slicer.xlsx")
    _write_manifest(fixture_dir, "slicer.xlsx")

    def remove_slicer_during_smoke(src: Path, _output_dir: Path, _timeout: int):
        _rewrite_without_prefixes(src, ("xl/slicers/", "xl/slicerCaches/"))
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        remove_slicer_during_smoke,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("slicer_selection_state",),
    )

    assert report["failure_count"] == 1
    assert report["results"][0]["status"] == "failed"
    assert "missing after Excel open" in report["results"][0]["message"]


def test_timeline_probe_runner_emits_passing_interactive_report(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_timeline_workbook(fixture_dir / "timeline.xlsx")
    _write_manifest(fixture_dir, "timeline.xlsx")

    def fake_smoke_excel(src: Path, _output_dir: Path, _timeout: int):
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        fake_smoke_excel,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("timeline_selection_state",),
    )

    assert report["failure_count"] == 0
    assert report["results"][0]["fixture"] == "timeline.xlsx"
    assert report["results"][0]["probe"] == "timeline_selection_state"
    assert report["results"][0]["probe_kind"] == "ooxml_state_presence"
    assert report["results"][0]["status"] == "passed"
    audit = interactive.audit_interactive_evidence(
        fixture_dir,
        reports=[output_dir / "interactive-probe-report.json"],
    )
    assert audit["probes"]["timeline_selection_state"]["status"] == "clear"
    assert (
        audit["probes"]["timeline_selection_state"]["label"]
        == "Timeline OOXML state remains present after Excel open/save"
    )
    assert audit["probes"]["timeline_selection_state"]["probe_kind"] == "ooxml_state_presence"


def test_timeline_probe_runner_fails_when_timeline_part_missing(
    tmp_path: Path, monkeypatch
) -> None:
    fixture_dir = tmp_path / "fixtures"
    output_dir = tmp_path / "out"
    fixture_dir.mkdir()
    _write_timeline_workbook(fixture_dir / "timeline.xlsx")
    _write_manifest(fixture_dir, "timeline.xlsx")

    def remove_timeline_during_smoke(src: Path, _output_dir: Path, _timeout: int):
        _rewrite_without_prefixes(src, ("xl/timelines/", "xl/timelineCaches/"))
        return SimpleNamespace(
            status="passed",
            output=str(src),
            message="opened",
        )

    monkeypatch.setattr(
        probe_runner.run_ooxml_app_smoke,
        "_smoke_excel",
        remove_timeline_during_smoke,
    )

    report = probe_runner.run_interactive_probes(
        fixture_dir,
        output_dir,
        probes=("timeline_selection_state",),
    )

    assert report["failure_count"] == 1
    assert report["results"][0]["status"] == "failed"
    assert "missing after Excel open" in report["results"][0]["message"]


def _write_manifest(fixture_dir: Path, filename: str) -> None:
    fixture_dir.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "fixtures": [
                    {
                        "filename": filename,
                        "fixture_id": Path(filename).stem,
                        "tool": "excel",
                    }
                ]
            }
        )
    )


def _write_plain_workbook(path: Path) -> None:
    entries = _base_entries()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_vba_workbook(path: Path) -> None:
    entries = _base_entries()
    entries["xl/vbaProject.bin"] = b"vba-project"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_embedded_control_workbook(path: Path) -> None:
    entries = _base_entries()
    entries["xl/worksheets/sheet1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData/>
  <controls><control name="List Box 1"/></controls>
</worksheet>"""
    entries["xl/ctrlProps/ctrlProp1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<formControlPr xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" objectType="List" sel="0" val="0"/>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_button_control_workbook(path: Path) -> None:
    entries = _base_entries()
    entries["xl/worksheets/sheet1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData/>
  <controls><control name="Button 1"/></controls>
</worksheet>"""
    entries["xl/ctrlProps/ctrlProp1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<formControlPr xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" objectType="Button" lockText="1"/>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_external_link_workbook(path: Path) -> None:
    entries = _base_entries()
    entries["xl/_rels/workbook.xml.rels"] = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLink" Target="externalLinks/externalLink1.xml"/>
</Relationships>"""
    entries["xl/externalLinks/externalLink1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <externalBook><sheetNames><sheetName val="Sheet1"/></sheetNames></externalBook>
</externalLink>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_powerview_data_model_workbook(path: Path) -> None:
    entries = _base_entries()
    entries["xl/sharedStrings.xml"] = "<sst>PowerView report</sst>"
    entries["xl/model/item.data"] = b"powerpivot-model"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_pivot_workbook(path: Path) -> None:
    entries = _base_entries()
    entries["xl/pivotCache/pivotCacheDefinition1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                      refreshOnLoad="1">
  <cacheSource type="worksheet"><worksheetSource ref="A1:B4" sheet="Sheet1"/></cacheSource>
  <cacheFields count="2"><cacheField name="Account"/><cacheField name="Amount"/></cacheFields>
</pivotCacheDefinition>"""
    entries["xl/pivotTables/pivotTable1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                      name="PivotTable1" cacheId="1">
  <location ref="A3:B6" firstHeaderRow="1" firstDataRow="2" firstDataCol="1"/>
  <rowFields count="1"><field x="0"/></rowFields>
</pivotTableDefinition>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _add_pivot_parts(path: Path) -> None:
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/pivotCache/pivotCacheDefinition1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                      refreshOnLoad="1">
  <cacheSource type="worksheet"><worksheetSource ref="A1:B4" sheet="Sheet1"/></cacheSource>
  <cacheFields count="2"><cacheField name="Account"/><cacheField name="Amount"/></cacheFields>
</pivotCacheDefinition>""",
        )
        archive.writestr(
            "xl/pivotTables/pivotTable1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                      name="PivotTable1" cacheId="1">
  <location ref="A3:B6" firstHeaderRow="1" firstDataRow="2" firstDataCol="1"/>
  <rowFields count="1"><field x="0"/></rowFields>
</pivotTableDefinition>""",
        )


def _write_slicer_workbook(path: Path) -> None:
    entries = _base_entries()
    entries["xl/tables/table1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
       id="1" name="Table1" displayName="Table1" ref="A1:C4">
  <autoFilter ref="A1:C4"/>
  <tableColumns count="3">
    <tableColumn id="1" name="Customer"/>
    <tableColumn id="2" name="Region"/>
    <tableColumn id="3" name="Year"/>
  </tableColumns>
</table>"""
    entries["xl/slicerCaches/slicerCache1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<slicerCacheDefinition xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" name="Slicer_Region"/>"""
    entries["xl/slicerCaches/slicerCache2.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<slicerCacheDefinition xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" name="Slicer_Year"/>"""
    entries["xl/slicers/slicer1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<slicer xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" name="Slicer_Region" cache="Slicer_Region"/>"""
    entries["xl/slicers/slicer2.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<slicer xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" name="Slicer_Year" cache="Slicer_Year"/>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_pivot_slicer_workbook(path: Path) -> None:
    entries = _base_entries()
    entries["xl/slicerCaches/slicerCache1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<slicerCacheDefinition xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
                       name="Slicer_Month" sourceName="Month">
  <data>
    <tabular pivotCacheId="1">
      <items count="3">
        <i x="0" s="1"/>
        <i x="1" s="1"/>
        <i x="2" s="1"/>
      </items>
    </tabular>
  </data>
</slicerCacheDefinition>"""
    entries["xl/slicers/slicer1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<slicer xmlns="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main" name="Slicer_Month" cache="Slicer_Month"/>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_timeline_workbook(path: Path) -> None:
    entries = _base_entries()
    entries["xl/timelineCaches/timelineCache1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<timelineCacheDefinition xmlns="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main" name="Timeline_Date"/>"""
    entries["xl/timelines/timeline1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<timeline xmlns="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main" name="Timeline_Date" cache="Timeline_Date"/>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _write_timeline_workbook_with_selection(path: Path) -> None:
    entries = _base_entries()
    entries["xl/timelineCaches/timelineCache1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<timelineCacheDefinition xmlns="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main" name="Timeline_Date">
  <state filterType="dateBetween">
    <selection startDate="2012-01-01T00:00:00" endDate="2012-03-31T00:00:00"/>
  </state>
</timelineCacheDefinition>"""
    entries["xl/timelines/timeline1.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<timeline xmlns="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main" name="Timeline_Date" cache="Timeline_Date"/>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _base_entries() -> dict[str, str | bytes]:
    return {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>""",
    }


def _rewrite_without_vba(path: Path) -> None:
    _rewrite_without_prefixes(path, ("xl/vbaProject.bin",))


def _rewrite_without_prefixes(path: Path, prefixes: tuple[str, ...]) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = {
            name: archive.read(name)
            for name in archive.namelist()
            if not any(name.startswith(prefix) for prefix in prefixes)
        }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _rewrite_timeline_selection(path: Path, *, start: str, end: str) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    timeline = entries["xl/timelineCaches/timelineCache1.xml"].decode()
    timeline = timeline.replace(
        'startDate="2012-01-01T00:00:00" endDate="2012-03-31T00:00:00"',
        f'startDate="{start}" endDate="{end}"',
    )
    entries["xl/timelineCaches/timelineCache1.xml"] = timeline.encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _rewrite_slicer_filter(path: Path, *, value: str) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    table = entries["xl/tables/table1.xml"].decode()
    table = table.replace(
        '<autoFilter ref="A1:C4"/>',
        (
            '<autoFilter ref="A1:C4">'
            f'<filterColumn colId="1"><filters><filter val="{value}"/></filters></filterColumn>'
            '<filterColumn colId="2"><filters><filter val="2014"/></filters></filterColumn>'
            "</autoFilter>"
        ),
    )
    entries["xl/tables/table1.xml"] = table.encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _rewrite_slicer_cache_selection(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    cache = entries["xl/slicerCaches/slicerCache1.xml"].decode()
    cache = cache.replace('<i x="1" s="1"/>', '<i x="1"/>')
    cache = cache.replace('<i x="2" s="1"/>', '<i x="2"/>')
    entries["xl/slicerCaches/slicerCache1.xml"] = cache.encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def _rewrite_control_selection(path: Path, *, value: str) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    control = entries["xl/ctrlProps/ctrlProp1.xml"].decode()
    control = control.replace('sel="0"', f'sel="{value}"')
    entries["xl/ctrlProps/ctrlProp1.xml"] = control.encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
