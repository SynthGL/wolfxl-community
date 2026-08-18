"""RFC-059 §2.2 (Sprint Ο Pod-1E): IndexedList contract.

Pins behavioral parity with openpyxl's
``openpyxl.utils.indexed_list.IndexedList``: O(1) ``index``
lookup via a backing dict, idempotent ``add``, and the ``clean``
instance flag.
"""

from __future__ import annotations

import time

import pytest

from wolfxl.utils.indexed_list import IndexedList


def test_indexed_list_init_from_iterable() -> None:
    il = IndexedList(["a", "b", "c"])
    assert list(il) == ["a", "b", "c"]
    assert il.index("b") == 1


def test_indexed_list_add_returns_index() -> None:
    il = IndexedList()
    assert il.add("x") == 0
    assert il.add("y") == 1
    assert il.add("z") == 2
    # Duplicate add returns existing index.
    assert il.add("x") == 0
    assert list(il) == ["x", "y", "z"]


def test_indexed_list_index_raises_for_missing() -> None:
    il = IndexedList(["a", "b"])
    with pytest.raises(ValueError):
        il.index("missing")


def test_indexed_list_contains_is_constant_time() -> None:
    """Smoke-test: ``in`` should be O(1) via the backing dict.

    We don't assert big-O directly but verify that membership on
    a 50k-entry list completes in well under a second — a plain
    ``list.__contains__`` would still be O(n) but on CPython 3.14
    that's also fast, so the bar is generous.
    """
    il = IndexedList(f"item_{i}" for i in range(50_000))
    start = time.perf_counter()
    for _ in range(10_000):
        assert "item_42" in il
        assert "missing" not in il
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"contains too slow: {elapsed:.3f}s"


def test_indexed_list_clean_class_attribute() -> None:
    """``clean`` is an instance flag; iterable construction starts dirty."""
    il = IndexedList()
    assert il.clean is True
    dirty = IndexedList(["a", "b", "a"])
    assert dirty.clean is False
    assert "a" in dirty
    assert dirty.clean is True
    il.clean = False
    assert il.clean is False


def test_indexed_list_preserves_initial_iterable_until_rebuild() -> None:
    """Initial duplicates are preserved; lookup rebuilds first indexes."""
    il = IndexedList(["a", "b", "a", "c", "b"])
    assert list(il) == ["a", "b", "a", "c", "b"]
    assert il.index("a") == 0
    assert il.index("b") == 1
    assert il.index("c") == 2
