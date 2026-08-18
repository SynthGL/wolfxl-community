from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "smoke_release_wheel_artifact.py"
    spec = importlib.util.spec_from_file_location("smoke_release_wheel_artifact", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


wheel_smoke = _load_module()


def test_venv_python_path_is_windows_aware(monkeypatch) -> None:
    monkeypatch.setattr(wheel_smoke.sys, "platform", "win32")

    assert wheel_smoke._venv_python(Path("venv")) == Path("venv") / "Scripts" / "python.exe"


def test_venv_python_path_uses_bin_on_posix(monkeypatch) -> None:
    monkeypatch.setattr(wheel_smoke.sys, "platform", "darwin")

    assert wheel_smoke._venv_python(Path("venv")) == Path("venv") / "bin" / "python"


def test_select_wheel_requires_exactly_one_glob_match(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    dist = tmp_path / "dist"
    dist.mkdir()
    first = dist / "wolfxl-2.0.0-cp39-cp39-win_amd64.whl"
    first.write_text("not a real wheel", encoding="utf-8")

    assert wheel_smoke._select_wheel(None, "dist/wolfxl-*.whl") == first

    (dist / "wolfxl-2.0.0-cp310-cp310-win_amd64.whl").write_text(
        "not a real wheel",
        encoding="utf-8",
    )
    try:
        wheel_smoke._select_wheel(None, "dist/wolfxl-*.whl")
    except ValueError as exc:
        assert "expected exactly one wheel" in str(exc)
    else:
        raise AssertionError("multiple wheel matches should fail")
