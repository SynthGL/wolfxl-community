from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl._zip_safety import _validate_info, _validate_part_name, validate_zipfile


def _write_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


def test_rejects_oversized_zip_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "oversized.xlsx"
    _write_zip(path, {"xl/workbook.xml": b"x" * 128})
    monkeypatch.setenv("WOLFXL_MAX_ZIP_ENTRY_BYTES", "64")

    with pytest.raises(Exception, match="too large"):
        wolfxl.load_workbook(path)


def test_rejects_zip_bomb_ratio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ratio.xlsx"
    _write_zip(path, {"xl/workbook.xml": b"x" * 20_000})
    monkeypatch.setenv("WOLFXL_MAX_ZIP_ENTRY_BYTES", "1000000")
    monkeypatch.setenv("WOLFXL_MAX_ZIP_COMPRESSION_RATIO", "2")

    with pytest.raises(Exception, match="compression ratio"):
        wolfxl.load_workbook(path)


def test_rejects_fractional_zip_bomb_ratio(monkeypatch: pytest.MonkeyPatch) -> None:
    info = zipfile.ZipInfo("xl/workbook.xml")
    info.file_size = 11
    info.compress_size = 10
    monkeypatch.setenv("WOLFXL_MAX_ZIP_COMPRESSION_RATIO", "1")

    with pytest.raises(ValueError, match="compression ratio"):
        _validate_info(info)


def test_rejects_unsafe_part_path(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.xlsx"
    _write_zip(path, {"../xl/workbook.xml": b"<workbook/>"})

    with pytest.raises(Exception, match="unsafe OOXML package part path"):
        wolfxl.load_workbook(path)


@pytest.mark.parametrize(
    "part_name",
    [
        "/xl/workbook.xml",
        r"xl\workbook.xml",
        "xl/C:/workbook.xml",
    ],
)
def test_rejects_absolute_windows_or_backslash_part_paths(
    part_name: str,
) -> None:
    with pytest.raises(ValueError, match="unsafe OOXML package part path"):
        _validate_part_name(part_name)


def test_rejects_duplicate_zip_entry_names(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = "duplicate"
    wb.save(path)
    with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        with pytest.warns(UserWarning, match="Duplicate name"):
            zf.writestr("xl/workbook.xml", b"<workbook/>")

    with zipfile.ZipFile(path) as zf:
        with pytest.raises(Exception, match="duplicate ZIP entry"):
            validate_zipfile(zf)


def test_rejects_too_many_zip_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "too-many.xlsx"
    _write_zip(path, {"xl/workbook.xml": b"<workbook/>", "xl/styles.xml": b"<styleSheet/>"})
    monkeypatch.setenv("WOLFXL_MAX_ZIP_ENTRIES", "1")

    with pytest.raises(Exception, match="too many ZIP entries"):
        wolfxl.load_workbook(path)


def test_rejects_total_uncompressed_zip_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "too-large-total.xlsx"
    _write_zip(path, {"xl/workbook.xml": b"x" * 8, "xl/styles.xml": b"x" * 8})
    monkeypatch.setenv("WOLFXL_MAX_ZIP_ENTRY_BYTES", "100")
    monkeypatch.setenv("WOLFXL_MAX_ZIP_TOTAL_BYTES", "10")

    with pytest.raises(Exception, match="OOXML package is too large"):
        wolfxl.load_workbook(path)
