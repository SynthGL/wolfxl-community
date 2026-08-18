"""Fixture discovery for the parity harness.

Sources:

1. ``tests/parity/fixtures/synthgl_snapshot/`` — committed snapshot of real
   SynthGL fixtures (copied by ``scripts/copy_synthgl_fixtures.py``).
2. ``$SYNTHGL_FIXTURES`` env var — live directory (typically
   ``$HOME/Projects/SynthGL/tests/app/fixtures/ingestion``). Optional; when set,
   runs the harness against the freshest real corpus.
3. ``tests/parity/fixtures/xls/`` and ``xlsb/`` — format-specific fixtures
   surfaced as their own parametrize groups.

Each discovered xlsx becomes a parametrized test case identified by a stable
ID (the relative path), so pytest-xdist can shard them safely.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

HERE = Path(__file__).parent
FIXTURES_DIR = HERE / "fixtures"
SNAPSHOT_DIR = FIXTURES_DIR / "synthgl_snapshot"
ENCRYPTED_DIR = FIXTURES_DIR / "encrypted"
XLS_DIR = FIXTURES_DIR / "xls"
XLSB_DIR = FIXTURES_DIR / "xlsb"


def _discover_xlsx(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*.xlsx")):
        # Excel opens files with a ``~$`` prefix as lock files; skip them.
        if path.name.startswith("~$"):
            continue
        yield path


def _live_synthgl_fixtures() -> Iterator[Path]:
    env = os.environ.get("SYNTHGL_FIXTURES")
    if not env:
        return
    root = Path(env).expanduser()
    if not root.exists():
        return
    yield from _discover_xlsx(root)


def _fixture_id(path: Path) -> str:
    """A short, stable pytest ID for a fixture path."""
    # Use the last two path segments to keep IDs readable but unique.
    parts = path.parts[-2:]
    return "/".join(parts)


def _all_xlsx_fixtures() -> list[Path]:
    seen: dict[str, Path] = {}
    sources = (
        (SNAPSHOT_DIR, _discover_xlsx(SNAPSHOT_DIR)),
        (_live_synthgl_root(), _live_synthgl_fixtures()),
    )
    for root, source in sources:
        for path in source:
            # Dedupe on the path *relative to the source root* + size. Using
            # `path.name` alone collapses distinct fixtures that share a
            # filename across categories (e.g. two `summary.xlsx` files in
            # different snapshot subfolders), which silently shrinks coverage.
            try:
                rel = path.relative_to(root) if root is not None else path
            except ValueError:
                rel = path
            key = f"{rel.as_posix()}:{path.stat().st_size}"
            seen.setdefault(key, path)
    return list(seen.values())


def _live_synthgl_root() -> Path | None:
    env = os.environ.get("SYNTHGL_FIXTURES")
    if not env:
        return None
    root = Path(env).expanduser()
    return root if root.exists() else None


@pytest.fixture(
    scope="session",
    params=_all_xlsx_fixtures(),
    ids=_fixture_id,
)
def xlsx_fixture(request: pytest.FixtureRequest) -> Path:
    """One xlsx file from the combined snapshot + live corpus."""
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(
    scope="session",
    params=list(_discover_xlsx(ENCRYPTED_DIR)),
    ids=_fixture_id,
)
def encrypted_fixture(request: pytest.FixtureRequest) -> Path:
    """One password-protected xlsx (Phase 2 target)."""
    return request.param  # type: ignore[no-any-return]


def _discover_xls(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    yield from sorted(root.rglob("*.xls"))


def _discover_xlsb(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    yield from sorted(root.rglob("*.xlsb"))


@pytest.fixture(
    scope="session",
    params=list(_discover_xls(XLS_DIR)),
    ids=_fixture_id,
)
def xls_fixture(request: pytest.FixtureRequest) -> Path:
    """One legacy xls fixture (Phase 5 target)."""
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(
    scope="session",
    params=list(_discover_xlsb(XLSB_DIR)),
    ids=_fixture_id,
)
def xlsb_fixture(request: pytest.FixtureRequest) -> Path:
    """One xlsb binary fixture (Phase 5 target)."""
    return request.param  # type: ignore[no-any-return]


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item],
) -> None:
    """Auto-skip format-specific tests when no fixtures exist.

    Avoids pytest reporting red on a fresh checkout before Phase 2/5 fixtures
    are seeded.
    """
    for item in items:
        fn = getattr(item, "function", None)
        if fn is None:
            continue
        if "encrypted_fixture" in item.fixturenames and not any(
            _discover_xlsx(ENCRYPTED_DIR)
        ):
            item.add_marker(pytest.mark.skip(
                reason="No encrypted fixtures present (Phase 2)",
            ))
        if "xls_fixture" in item.fixturenames and not any(_discover_xls(XLS_DIR)):
            item.add_marker(pytest.mark.skip(
                reason="No .xls fixtures present (Phase 5)",
            ))
        if "xlsb_fixture" in item.fixturenames and not any(
            _discover_xlsb(XLSB_DIR)
        ):
            item.add_marker(pytest.mark.skip(
                reason="No .xlsb fixtures present (Phase 5)",
            ))
