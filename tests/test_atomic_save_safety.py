from __future__ import annotations

from pathlib import Path

import pytest

import wolfxl


def test_failed_native_save_preserves_existing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.xlsx"

    original = wolfxl.Workbook()
    original.active["A1"] = "original"
    original.save(target)
    before = target.read_bytes()

    replacement = wolfxl.Workbook()
    replacement.active["A1"] = "replacement"
    monkeypatch.setenv("WOLFXL_MAX_ZIP_ENTRY_BYTES", "1")

    with pytest.raises(Exception, match="too large"):
        replacement.save(target)

    assert target.read_bytes() == before


def test_modify_save_in_place_replaces_existing_target(tmp_path: Path) -> None:
    target = tmp_path / "in_place.xlsx"

    wb = wolfxl.Workbook()
    wb.active["A1"] = "before"
    wb.save(target)
    wb.close()

    loaded = wolfxl.load_workbook(target, modify=True)
    loaded.active["A1"] = "after"
    loaded.save(target)
    loaded.close()

    reloaded = wolfxl.load_workbook(target, read_only=True)
    assert next(reloaded.active.iter_rows(values_only=True))[0] == "after"


def test_native_save_over_existing_target_succeeds(tmp_path: Path) -> None:
    target = tmp_path / "overwrite.xlsx"

    first = wolfxl.Workbook()
    first.active["A1"] = "first"
    first.save(target)
    first.close()

    second = wolfxl.Workbook()
    second.active["A1"] = "second"
    second.save(target)
    second.close()

    reloaded = wolfxl.load_workbook(target, read_only=True)
    assert next(reloaded.active.iter_rows(values_only=True))[0] == "second"
