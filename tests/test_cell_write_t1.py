"""T1 PR4 — Cell-level writes: Comment + Hyperlink setters.

Write mode (Workbook() + save) must accept
``cell.comment = Comment(...)`` and ``cell.hyperlink = Hyperlink(...)``.
Modify mode still raises ``NotImplementedError`` with a T1.5 pointer —
that path ships in a later patch.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from wolfxl.comments import Comment
from wolfxl.worksheet.hyperlink import Hyperlink

from wolfxl import Workbook

openpyxl = pytest.importorskip("openpyxl")


def test_cell_comment_write_round_trip(tmp_path: Path) -> None:
    """wolfxl write → openpyxl read cross-library parity."""
    path = tmp_path / "wolfxl_comments.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "hello"
    ws["A1"].comment = Comment(text="This is a comment", author="Alice")
    wb.save(str(path))

    op_wb = openpyxl.load_workbook(path)
    op_ws = op_wb.active
    assert op_ws["A1"].comment is not None
    assert op_ws["A1"].comment.text == "This is a comment"
    assert op_ws["A1"].comment.author == "Alice"


def test_cell_hyperlink_write_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "wolfxl_hyperlinks.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "Click me"
    ws["A1"].hyperlink = Hyperlink(
        target="https://example.com",
        display="Example",
        tooltip="Go to example",
    )
    wb.save(str(path))

    op_wb = openpyxl.load_workbook(path)
    op_ws = op_wb.active
    hl = op_ws["A1"].hyperlink
    assert hl is not None
    assert hl.target == "https://example.com"
    # openpyxl only carries .display when explicitly set; tooltip too.


def test_cell_hyperlink_bare_string_shortcut(tmp_path: Path) -> None:
    """``cell.hyperlink = "https://..."`` auto-wraps in ``Hyperlink``."""
    path = tmp_path / "wolfxl_hyperlink_short.xlsx"
    wb = Workbook()
    ws = wb.active
    ws["B2"] = "link"
    ws["B2"].hyperlink = "https://short.url/xyz"
    # Pre-save, the cell must already see the wrapped object.
    assert isinstance(ws["B2"].hyperlink, Hyperlink)
    assert ws["B2"].hyperlink.target == "https://short.url/xyz"
    wb.save(str(path))

    op_wb = openpyxl.load_workbook(path)
    assert op_wb.active["B2"].hyperlink.target == "https://short.url/xyz"


def test_comment_visible_before_save(tmp_path: Path) -> None:
    """Queued comments must be readable from the Cell property immediately."""
    wb = Workbook()
    ws = wb.active
    ws["C3"] = 42
    c = Comment(text="before save", author="Bob")
    ws["C3"].comment = c
    # The getter must surface the queued value without needing a flush.
    got = ws["C3"].comment
    assert got is c
    assert got.parent is ws["C3"]
    assert got.height == 79
    assert got.width == 144
    got.unbind()
    assert got.parent is None


def test_comment_assign_none_removes(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws["A1"].comment = Comment("temp", "me")
    assert ws["A1"].comment is not None
    ws["A1"].comment = None
    assert ws["A1"].comment is None


def test_modify_mode_comment_is_now_supported(tmp_path: Path) -> None:
    """Opening an existing file → comment setter queues the change.

    Both ``cell.hyperlink`` (RFC-022) and ``cell.comment`` (RFC-023)
    are now active in modify mode; this test guards the wiring.
    """
    path = tmp_path / "exists.xlsx"
    op_wb = openpyxl.Workbook()
    op_wb.active["A1"] = "seed"
    op_wb.save(path)

    wb = Workbook._from_patcher(str(path))
    ws = wb.active
    ws["A1"].comment = Comment(text="now works", author="me")
    assert ws._pending_comments["A1"].text == "now works"  # noqa: SLF001
    wb.close()
