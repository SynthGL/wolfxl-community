from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_release_artifact_smoke.py"
    spec = importlib.util.spec_from_file_location("run_release_artifact_smoke", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke = _load_module()


def test_markdown_lists_wheel_identity_and_enabled_backends() -> None:
    report = {
        "ready": True,
        "source_git_sha": "abc123",
        "source_git_dirty": False,
        "report_repo_git_dirty": False,
        "wheel": {
            "filename": "wolfxl-2.0.0.whl",
            "metadata_version": "2.0.0",
            "wheel_tag": "cp312-cp312-macosx_11_0_arm64",
            "sha256": "c" * 64,
            "size_bytes": 1234,
        },
        "venv_smoke": {
            "wolfxl_version": "2.0.0",
            "openpyxl_version": "3.1.5",
            "write_workbook_exists": True,
            "modified_workbook_exists": True,
            "openpyxl_read_modified_a2": 42,
            "required_zip_parts_present": True,
            "rust_build_info": {
                "enabled_backends": [
                    "native-xlsx",
                    "native-xlsb",
                    "calamine-xls",
                    "wolfxl",
                ]
            },
        },
        "notes": [],
    }

    markdown = smoke.format_markdown(report)

    assert f"| Wheel SHA-256 | `{'c' * 64}` |" in markdown
    assert "| Wheel size bytes | 1234 |" in markdown
    assert "| Enabled backends | native-xlsx, native-xlsb, calamine-xls, wolfxl |" in markdown


def test_optional_bool_parser_keeps_missing_metadata_unset() -> None:
    assert smoke._optional_bool(None) is None
    assert smoke._optional_bool("true") is True
    assert smoke._optional_bool("false") is False


def test_python_command_can_force_macos_arch() -> None:
    python = Path("/usr/bin/python3")
    command = smoke._python_command(python, "x86_64", "-m", "venv", "venv")

    assert command == ["arch", "-x86_64", str(python), "-m", "venv", "venv"]
