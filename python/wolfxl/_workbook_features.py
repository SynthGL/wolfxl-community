"""Workbook-level feature registration helpers."""

from __future__ import annotations

from typing import Any


def add_pivot_cache(wb: Any, cache: Any) -> Any:
    """Register a pivot cache against a modify-mode workbook.

    Args:
        wb: Workbook-like object carrying patcher and pivot-cache queues.
        cache: Pivot cache instance to allocate and queue.

    Returns:
        The same cache with ``_cache_id`` populated.

    Raises:
        RuntimeError: If ``wb`` is not in modify mode.
        ValueError: If the cache is already registered or lacks a worksheet.
    """
    if wb._rust_patcher is None and wb._rust_writer is None:  # noqa: SLF001
        raise RuntimeError(
            "add_pivot_cache requires a Workbook in write or modify mode"
        )
    if getattr(cache, "_cache_id", None) is not None:
        raise ValueError(
            f"Pivot cache already registered with cache_id={cache._cache_id}"
        )
    cache._cache_id = wb._next_pivot_cache_id  # noqa: SLF001
    wb._next_pivot_cache_id += 1  # noqa: SLF001
    if cache._fields is None:
        ws_obj = cache.source.worksheet
        if ws_obj is None:
            raise ValueError(
                "PivotCache.source.worksheet is None — pivot cache "
                "must reference a real worksheet"
            )
        cache._materialize(ws_obj)
    wb._pending_pivot_caches.append(cache)  # noqa: SLF001
    return cache


def add_slicer_cache(wb: Any, cache: Any) -> Any:
    """Register a slicer cache against a modify-mode workbook.

    Args:
        wb: Workbook-like object carrying patcher and slicer-cache queues.
        cache: Slicer cache instance to allocate and queue.

    Returns:
        The same cache with ``_slicer_cache_id`` populated.

    Raises:
        RuntimeError: If ``wb`` is not in modify mode.
        ValueError: If the cache is already registered or its source pivot
            cache is not registered.
    """
    if wb._rust_patcher is None:  # noqa: SLF001
        raise RuntimeError(
            "add_slicer_cache requires modify mode — open the "
            "workbook with load_workbook(..., modify=True)"
        )
    if getattr(cache, "_slicer_cache_id", None) is not None:
        raise ValueError(
            f"Slicer cache already registered with id={cache._slicer_cache_id}"
        )
    if cache.source_pivot_cache._cache_id is None:
        raise ValueError(
            "SlicerCache.source_pivot_cache must be registered "
            "via Workbook.add_pivot_cache(...) before "
            "add_slicer_cache(...)"
        )
    cache._slicer_cache_id = wb._next_slicer_cache_id  # noqa: SLF001
    wb._next_slicer_cache_id += 1  # noqa: SLF001
    if not cache.items:
        try:
            cache.populate_items_from_cache()
        except Exception:
            pass
    wb._pending_slicer_caches.append(cache)  # noqa: SLF001
    return cache


def add_chart_modify_mode(
    wb: Any,
    sheet_title: str,
    chart_xml: bytes,
    anchor_a1: str,
    width_emu: int,
    height_emu: int,
) -> None:
    """Queue serialized chart XML for modify-mode insertion.

    Args:
        wb: Workbook-like object carrying patcher and chart queues.
        sheet_title: Target worksheet title.
        chart_xml: Serialized chart XML bytes.
        anchor_a1: A1-style chart anchor.
        width_emu: Chart width in EMU.
        height_emu: Chart height in EMU.

    Raises:
        NotImplementedError: If ``wb`` is not in modify mode.
        ValueError: If the sheet or anchor is invalid.
        TypeError: If ``chart_xml`` is not bytes-like.
    """
    if wb._rust_patcher is None:  # noqa: SLF001
        raise NotImplementedError(
            "add_chart_modify_mode requires modify mode "
            "(load_workbook(path, modify=True))"
        )
    if sheet_title not in wb._sheets:  # noqa: SLF001
        raise ValueError(f"add_chart_modify_mode: no such sheet: {sheet_title!r}")
    if not isinstance(chart_xml, (bytes, bytearray)):
        raise TypeError(
            "add_chart_modify_mode: chart_xml must be bytes "
            f"(got {type(chart_xml).__name__})"
        )
    if not anchor_a1 or not isinstance(anchor_a1, str):
        raise ValueError(
            "add_chart_modify_mode: anchor_a1 must be a non-empty A1 string"
        )
    bucket = wb._pending_chart_adds.setdefault(sheet_title, [])  # noqa: SLF001
    bucket.append((bytes(chart_xml), anchor_a1, int(width_emu), int(height_emu)))
