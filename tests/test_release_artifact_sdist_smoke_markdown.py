from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_release_artifact_sdist_smoke.py"
    )
    spec = importlib.util.spec_from_file_location("run_release_artifact_sdist_smoke", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sdist = _load_module()


def test_markdown_lists_sdist_identity_and_enabled_backends() -> None:
    report = {
        "ready": True,
        "source_git_sha": "abc123",
        "source_git_dirty": False,
        "report_repo_git_dirty": False,
        "sdist": {
            "filename": "wolfxl-2.0.0.tar.gz",
            "metadata_version": "2.0.0",
            "sha256": "d" * 64,
            "size_bytes": 4321,
        },
        "venv_smoke": {
            "wolfxl_version": "2.0.0",
            "openpyxl_version": "3.1.5",
            "write_workbook_exists": True,
            "modified_workbook_exists": True,
            "openpyxl_read_modified_a2": "modified",
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

    markdown = sdist.format_markdown(report)

    assert f"| Sdist SHA-256 | `{'d' * 64}` |" in markdown
    assert "| Sdist size bytes | 4321 |" in markdown
    assert "| Enabled backends | native-xlsx, native-xlsb, calamine-xls, wolfxl |" in markdown


def test_optional_bool_parser_is_reused_for_metadata_overrides() -> None:
    assert sdist.run_release_artifact_smoke._optional_bool(None) is None
    assert sdist.run_release_artifact_smoke._optional_bool("true") is True
    assert sdist.run_release_artifact_smoke._optional_bool("false") is False
