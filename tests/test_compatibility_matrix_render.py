from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "migration" / "compatibility-matrix.md"


def _load_render_module() -> ModuleType:
    script = ROOT / "scripts" / "render_compat_matrix.py"
    spec = importlib.util.spec_from_file_location("render_compat_matrix", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _normalize_render_date(markdown: str) -> str:
    return re.sub(
        r"_Last rendered: \*\*\d{4}-\d{2}-\d{2}\*\*",
        "_Last rendered: **<date>**",
        markdown,
        count=1,
    )


def test_compatibility_matrix_matches_source_spec_except_render_date() -> None:
    renderer = _load_render_module()
    rendered = renderer.render(renderer._load_spec_module())
    checked_in = MATRIX_PATH.read_text(encoding="utf-8")

    assert _normalize_render_date(checked_in) == _normalize_render_date(rendered)
