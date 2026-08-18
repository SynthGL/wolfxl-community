"""Smoke test: every openpyxl symbol SynthGL imports has a wolfxl equivalent.

This is the cheapest, loudest contract: if ``import wolfxl`` fails to expose a
name that SynthGL needs, CI goes red immediately — before any cell-level diff
runs. Gaps documented in ``KNOWN_GAPS.md`` are marked ``xfail(strict=True)``
so that accidentally shipping a gap-closer flips the test green and forces an
update to the contract.
"""

from __future__ import annotations

import importlib

import pytest

from .openpyxl_surface import (
    SURFACE_ENTRIES,
    SurfaceEntry,
    known_gap_entries,
    supported_entries,
)


def _import_symbol(dotted_path: str) -> object:
    """Resolve ``'pkg.mod.ClassName'`` to the object, or raise ``ImportError``.

    Supports instance-method dotted paths (e.g. ``'wolfxl._cell.Cell.value'``).
    The last attribute is treated as a name on the penultimate module.
    """
    parts = dotted_path.split(".")
    # Try treating the whole path as an attribute chain under the first
    # importable prefix.
    for pivot in range(len(parts), 0, -1):
        module_path = ".".join(parts[:pivot])
        try:
            mod = importlib.import_module(module_path)
        except ImportError:
            continue
        obj: object = mod
        for attr in parts[pivot:]:
            if not hasattr(obj, attr):
                raise ImportError(f"{module_path} has no attribute {attr!r}")
            obj = getattr(obj, attr)
        return obj
    raise ImportError(f"No importable prefix in {dotted_path!r}")


@pytest.mark.parametrize(
    "entry",
    supported_entries(),
    ids=lambda e: e.openpyxl_path,
)
def test_supported_symbol_is_importable(entry: SurfaceEntry) -> None:
    """Every entry marked ``wolfxl_supported=True`` must resolve."""
    assert entry.wolfxl_path is not None, (
        f"{entry.openpyxl_path} is marked supported but has no wolfxl_path"
    )
    # Only verify the openpyxl side when the entry uses a fully-qualified
    # ``openpyxl.*`` path. Some entries describe instance attributes
    # (e.g. ``"Cell.value"``) that are conceptually openpyxl's API but not
    # individually importable as a top-level symbol — covered by
    # test_read_parity / test_write_parity instead.
    op_token = entry.openpyxl_path.split(" ")[0]
    if op_token.startswith("openpyxl."):
        _import_symbol(op_token)
    # The wolfxl equivalent must resolve. "Cell.value (setter)" and similar
    # parenthesized annotations are descriptive; strip them for the import.
    wolfxl_path = entry.wolfxl_path.split(" ")[0]
    _import_symbol(wolfxl_path)


@pytest.mark.parametrize(
    "entry",
    known_gap_entries(),
    ids=lambda e: e.openpyxl_path,
)
def test_known_gap_still_gaps(entry: SurfaceEntry) -> None:
    """Known gaps stay gaps until a phase ships the fix + flips the flag.

    If the import accidentally starts working, this test goes RED on purpose
    — the maintainer must flip ``wolfxl_supported=True`` and remove the
    KNOWN_GAPS.md entry before CI passes again.
    """
    wolfxl_path = entry.wolfxl_path
    if wolfxl_path is None:
        pytest.xfail(f"{entry.openpyxl_path} is a known gap; no wolfxl alias yet")
    assert wolfxl_path is not None  # narrowing for type checker
    try:
        _import_symbol(wolfxl_path.split(" ")[0])
    except ImportError:
        pytest.xfail(f"{entry.openpyxl_path} is a known gap: {entry.parity_note}")
    else:
        pytest.fail(
            f"{entry.openpyxl_path} unexpectedly works via {wolfxl_path}. "
            "Flip wolfxl_supported=True in openpyxl_surface.py and remove from "
            "KNOWN_GAPS.md.",
        )


def test_surface_coverage_sanity() -> None:
    """The contract is non-empty and every entry lists SynthGL usage or notes."""
    assert SURFACE_ENTRIES, "openpyxl_surface must enumerate at least one entry"
    for entry in SURFACE_ENTRIES:
        assert entry.parity_note, f"{entry.openpyxl_path} missing parity_note"
        assert entry.category, f"{entry.openpyxl_path} missing category"
