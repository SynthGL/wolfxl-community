"""RFC-055 §6 + RFC-035 — Sheet-setup deep-clone tests for
``Workbook.copy_worksheet``.

Verifies that mutating a sheet-setup attribute on the source after
copy_worksheet does NOT propagate to the clone, and vice versa. This
guards against the "aliasing" failure mode where both sheets shared
the same dataclass instance.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.worksheet.header_footer import HeaderFooter, HeaderFooterItem
from wolfxl.worksheet.page_setup import PageMargins


@pytest.fixture(autouse=True)
def _force_test_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


def _read_sheet_xml(p: Path, name: str) -> str:
    with zipfile.ZipFile(p) as zf:
        return zf.read(name).decode("utf-8")


def test_page_setup_diverges_after_copy(tmp_path: Path) -> None:
    """src.page_setup.orientation = 'landscape' before copy → both
    initially landscape; mutating src after the copy does NOT affect
    the clone (and vice versa)."""
    wb = wolfxl.Workbook()
    src = wb.active
    src["A1"] = "x"
    src.page_setup.orientation = "landscape"

    dst = wb.copy_worksheet(src)

    # Both observed landscape immediately after the copy:
    assert dst.page_setup.orientation == "landscape"

    # Mutate dst → src must NOT change.
    dst.page_setup.orientation = "portrait"
    assert src.page_setup.orientation == "landscape"
    assert dst.page_setup.orientation == "portrait"


def test_page_margins_deep_cloned(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    src = wb.active
    src["A1"] = "x"
    src.page_margins = PageMargins(left=1.0, right=1.0)

    dst = wb.copy_worksheet(src)
    assert dst.page_margins.left == 1.0

    # Independent mutation:
    dst.page_margins.left = 2.0
    assert src.page_margins.left == 1.0
    assert dst.page_margins.left == 2.0


def test_header_footer_deep_cloned(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    src = wb.active
    src["A1"] = "x"
    src.header_footer = HeaderFooter(
        odd_header=HeaderFooterItem(center="Source Title"),
    )

    dst = wb.copy_worksheet(src)
    assert dst.header_footer.odd_header.center == "Source Title"

    dst.header_footer.odd_header.center = "Clone Title"
    assert src.header_footer.odd_header.center == "Source Title"
    assert dst.header_footer.odd_header.center == "Clone Title"


def test_protection_deep_cloned(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    src = wb.active
    src["A1"] = "x"
    src.protection.set_password("hunter2")
    src.protection.enable()

    dst = wb.copy_worksheet(src)
    assert dst.protection.sheet is True
    assert dst.protection.password == "C258"

    # Mutate clone — source unaffected.
    dst.protection.set_password("other")
    assert src.protection.password == "C258"
    assert dst.protection.password != "C258"


def test_sheet_view_deep_cloned(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    src = wb.active
    src["A1"] = "x"
    src.sheet_view.zoom_scale = 150

    dst = wb.copy_worksheet(src)
    assert dst.sheet_view.zoom_scale == 150

    dst.sheet_view.zoom_scale = 200
    assert src.sheet_view.zoom_scale == 150
    assert dst.sheet_view.zoom_scale == 200


def test_clone_save_emits_independent_blocks(tmp_path: Path) -> None:
    """Save the workbook after a copy + divergent mutations and verify
    the two sheet XMLs reflect the post-mutation state independently."""
    p = tmp_path / "diverged.xlsx"
    wb = wolfxl.Workbook()
    src = wb.active
    src["A1"] = "x"
    src.page_setup.orientation = "landscape"

    dst = wb.copy_worksheet(src, name="Copy")
    dst.page_setup.orientation = "portrait"

    wb.save(str(p))

    # Determine which sheet is which from workbook.xml ordering.
    src_xml = _read_sheet_xml(p, "xl/worksheets/sheet1.xml")
    dst_xml = _read_sheet_xml(p, "xl/worksheets/sheet2.xml")

    assert 'orientation="landscape"' in src_xml
    assert 'orientation="portrait"' in dst_xml


def test_print_titles_carry_over(tmp_path: Path) -> None:
    """print_title_rows / print_title_cols carry over by value (string)."""
    wb = wolfxl.Workbook()
    src = wb.active
    src["A1"] = "x"
    src.print_title_rows = "1:1"
    src.print_title_cols = "A:A"

    dst = wb.copy_worksheet(src)
    assert dst.print_title_rows == "$1:$1"
    assert dst.print_title_cols == "$A:$A"

    # Strings — assignment to dst doesn't change src either.
    dst.print_title_rows = "1:2"
    assert src.print_title_rows == "$1:$1"
