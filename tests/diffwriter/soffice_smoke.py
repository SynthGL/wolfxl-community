"""Layer 4 — LibreOffice headless smoke for diffwriter cases.

Round-trips every native-emitted xlsx through ``soffice --headless
--convert-to xlsx`` and asserts:

  1. soffice exit code is 0
  2. soffice stderr does not contain ``corrupt`` / ``repaired`` / ``error``
  3. the converted xlsx is a valid OOXML zip
     (``zipfile.is_zipfile`` + parses central directory)

Layer 4 is **gold-star, not blocking**. Acceptance gate is ≥95% pass rate
across the full case set (auto-discovered via ``_ALL_CASES``) + the 15
SynthGL fixtures under ``tests/parity/fixtures/synthgl_snapshot``. A
single failing case indicates a real-world interop bug that nightly
nag-post or a follow-up slice should resolve, but does NOT gate Wave 5
rip-out.

Skipped automatically unless ``WOLFXL_RUN_LIBREOFFICE_SMOKE=1`` is set,
so the test is harmless on machines without LibreOffice installed (CI
without LO, dev machines pre-install).

Setup:

    brew install --cask libreoffice    # macOS
    apt-get install libreoffice        # Linux
    WOLFXL_RUN_LIBREOFFICE_SMOKE=1 pytest tests/diffwriter/soffice_smoke.py -v
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Callable

import pytest

from . import cases as cases_pkg
from .cases import _SOFFICE_XFAIL_CASES

_SOFFICE_PATHS = (
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
)

_SMOKE_KEYWORDS = ("corrupt", "repaired", "error")
_SUBPROCESS_TIMEOUT_S = 60
_SYNTHGL_FIXTURES_ROOT = (
    Path(__file__).resolve().parents[1] / "parity" / "fixtures" / "synthgl_snapshot"
)
_RUN_ENV_FLAG = "WOLFXL_RUN_LIBREOFFICE_SMOKE"


def _find_soffice() -> str | None:
    """Return absolute path to ``soffice`` if available, else ``None``."""
    for candidate in _SOFFICE_PATHS:
        if Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    on_path = shutil.which("soffice")
    return on_path


def _smoke_one(soffice: str, src: Path, work: Path) -> tuple[bool, str]:
    """Convert ``src`` to xlsx via headless LO into ``work``. Return (ok, msg).

    ``ok=True`` only when exit==0, stderr contains no ``corrupt|repaired|error``
    substring (case-insensitive), the converted file lands at ``work/<src.name>``,
    and that file is a valid zip.
    """
    proc = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(work),
            str(src),
        ],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_S,
    )
    if proc.returncode != 0:
        return False, f"exit {proc.returncode}: {proc.stderr[:200]}"
    stderr_lc = proc.stderr.lower()
    for kw in _SMOKE_KEYWORDS:
        if kw in stderr_lc:
            return False, f"stderr contained {kw!r}: {proc.stderr[:200]}"
    converted = work / src.name
    if not converted.exists():
        return False, f"no output file at {converted}"
    if not zipfile.is_zipfile(converted):
        return False, "output is not a valid zip"
    try:
        with zipfile.ZipFile(converted) as zf:
            _ = zf.namelist()
    except zipfile.BadZipFile as exc:
        return False, f"bad central directory: {exc}"
    return True, "ok"


def _discover_cases() -> list[tuple[str, Callable[[Any], None]]]:
    """Walk ``tests/diffwriter/cases`` and return every (id, build) pair."""
    out: list[tuple[str, Callable[[Any], None]]] = []
    for mod_info in pkgutil.iter_modules(cases_pkg.__path__):
        mod = importlib.import_module(f"tests.diffwriter.cases.{mod_info.name}")
        cases = getattr(mod, "CASES", None)
        if cases is None:
            continue
        for case_id, build_fn in cases:
            out.append((case_id, build_fn))
    return out


def _discover_synthgl_fixtures() -> list[Path]:
    """Return every ``.xlsx`` under ``tests/parity/fixtures/synthgl_snapshot``."""
    if not _SYNTHGL_FIXTURES_ROOT.is_dir():
        return []
    return sorted(_SYNTHGL_FIXTURES_ROOT.rglob("*.xlsx"))


_ALL_CASES = _discover_cases()
_SYNTHGL_FIXTURES = _discover_synthgl_fixtures()


@pytest.mark.libreoffice_smoke
@pytest.mark.skipif(
    os.environ.get(_RUN_ENV_FLAG) != "1",
    reason=f"{_RUN_ENV_FLAG}=1 not set (gold-star, opt-in)",
)
@pytest.mark.parametrize(
    "case_id,build_fn",
    _ALL_CASES,
    ids=[c[0] for c in _ALL_CASES],
)
def test_libreoffice_smoke_native_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    build_fn: Callable[[Any], None],
) -> None:
    """Build the case under ``WOLFXL_WRITER=native`` and round-trip via LO."""
    soffice = _find_soffice()
    if soffice is None:
        pytest.skip(
            "soffice not found in any of "
            f"{_SOFFICE_PATHS} or $PATH — install LibreOffice to enable Layer 4"
        )
    assert soffice is not None  # narrow for type checkers; pytest.skip raised above

    monkeypatch.setenv("WOLFXL_WRITER", "native")
    import wolfxl

    wb = wolfxl.Workbook()
    build_fn(wb)
    src = tmp_path / "src.xlsx"
    wb.save(str(src))
    assert src.exists(), f"native writer did not produce {src}"

    if case_id in _SOFFICE_XFAIL_CASES:
        pytest.xfail(_SOFFICE_XFAIL_CASES[case_id])

    work = tmp_path / "lo_out"
    work.mkdir()
    ok, msg = _smoke_one(soffice, src, work)
    assert ok, f"{case_id}: LibreOffice round-trip failed: {msg}"


@pytest.mark.libreoffice_smoke
@pytest.mark.skipif(
    os.environ.get(_RUN_ENV_FLAG) != "1",
    reason=f"{_RUN_ENV_FLAG}=1 not set (gold-star, opt-in)",
)
@pytest.mark.skipif(
    not _SYNTHGL_FIXTURES,
    reason="No SynthGL fixtures found at tests/parity/fixtures/synthgl_snapshot/",
)
@pytest.mark.parametrize(
    "fixture_path",
    _SYNTHGL_FIXTURES,
    ids=[p.relative_to(_SYNTHGL_FIXTURES_ROOT).as_posix() for p in _SYNTHGL_FIXTURES],
)
def test_libreoffice_smoke_synthgl_fixture(
    tmp_path: Path,
    fixture_path: Path,
) -> None:
    """Round-trip an existing SynthGL real-world fixture through LO."""
    soffice = _find_soffice()
    if soffice is None:
        pytest.skip(
            "soffice not found in any of "
            f"{_SOFFICE_PATHS} or $PATH — install LibreOffice to enable Layer 4"
        )
    assert soffice is not None  # narrow for type checkers; pytest.skip raised above

    work = tmp_path / "lo_out"
    work.mkdir()
    ok, msg = _smoke_one(soffice, fixture_path, work)
    rel = fixture_path.relative_to(_SYNTHGL_FIXTURES_ROOT).as_posix()
    assert ok, f"{rel}: LibreOffice round-trip failed: {msg}"
