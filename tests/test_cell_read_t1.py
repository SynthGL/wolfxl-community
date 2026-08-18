"""T1 PR1 — cell-level read parity for comments and hyperlinks.

openpyxl builds the fixture file; wolfxl reads it back. Any divergence
in the cross-library contract (missing field, wrong type, silent None)
surfaces here rather than deep in a user script.

Tests also pin the lazy-caching contract: the Rust reader must be hit
exactly once per sheet no matter how many cells we probe. This prevents
silent regressions where somebody accidentally swaps the dict lookup
for a per-cell FFI call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from wolfxl.comments import Comment
from wolfxl.worksheet.hyperlink import Hyperlink

from wolfxl import Workbook

openpyxl = pytest.importorskip("openpyxl")


@pytest.fixture()
def fixture_with_comments_and_links(tmp_path: Path) -> Path:
    """Build an xlsx via openpyxl that has both comments and hyperlinks."""
    path = tmp_path / "fixture.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "has comment"
    ws["A1"].comment = openpyxl.comments.Comment("first note", "Alice")
    ws["A2"] = "also commented"
    ws["A2"].comment = openpyxl.comments.Comment("second note", "Bob")
    ws["B1"] = "Google"
    ws["B1"].hyperlink = "https://google.com"
    ws["B2"] = "Click me"
    ws["B2"].hyperlink = "https://example.com/page?q=1"
    wb.save(path)
    return path


def test_comment_read(fixture_with_comments_and_links: Path) -> None:
    wb = Workbook._from_reader(str(fixture_with_comments_and_links))
    ws = wb.active

    c1 = ws["A1"].comment
    assert c1 is not None
    assert isinstance(c1, Comment)
    assert c1.text == "first note"
    assert c1.author == "Alice"

    c2 = ws["A2"].comment
    assert c2 is not None
    assert c2.text == "second note"
    assert c2.author == "Bob"

    # A cell without a comment returns None (openpyxl parity).
    assert ws["Z99"].comment is None


def test_hyperlink_read(fixture_with_comments_and_links: Path) -> None:
    wb = Workbook._from_reader(str(fixture_with_comments_and_links))
    ws = wb.active

    h1 = ws["B1"].hyperlink
    assert h1 is not None
    assert isinstance(h1, Hyperlink)
    assert h1.target == "https://google.com"

    h2 = ws["B2"].hyperlink
    assert h2 is not None
    assert h2.target == "https://example.com/page?q=1"

    assert ws["Z99"].hyperlink is None


def test_cells_without_comments_return_none_in_write_mode() -> None:
    """A fresh Workbook() has no comments/hyperlinks — every cell reads None."""
    wb = Workbook()
    ws = wb.active
    ws["A1"] = 1
    # These reads should succeed (and return None), not raise.
    assert ws["A1"].comment is None
    assert ws["A1"].hyperlink is None


def test_comment_is_mutable() -> None:
    """openpyxl treats Comment as mutable; wolfxl must too."""
    c = Comment(text="original", author="a")
    c.text = "mutated"
    assert c.text == "mutated"
    # ``.content`` is the openpyxl alias for .text.
    c.content = "via content"
    assert c.text == "via content"


class _CountingReader:
    """Proxy that forwards attribute access and counts calls to read_comments/read_hyperlinks."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.comment_calls = 0
        self.hyperlink_calls = 0

    def read_comments(self, sheet: str) -> Any:
        self.comment_calls += 1
        return self._inner.read_comments(sheet)

    def read_hyperlinks(self, sheet: str) -> Any:
        self.hyperlink_calls += 1
        return self._inner.read_hyperlinks(sheet)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def test_per_sheet_cache_is_single_shot(fixture_with_comments_and_links: Path) -> None:
    """Probing comments/hyperlinks on many cells should hit Rust once per sheet."""
    wb = Workbook._from_reader(str(fixture_with_comments_and_links))
    counter = _CountingReader(wb._rust_reader)
    wb._rust_reader = counter

    ws = wb.active
    for row in range(1, 20):
        for col_letter in ("A", "B", "C"):
            _ = ws[f"{col_letter}{row}"].comment
            _ = ws[f"{col_letter}{row}"].hyperlink

    assert counter.comment_calls == 1, (
        f"expected exactly 1 call to read_comments (cache), got {counter.comment_calls}"
    )
    assert counter.hyperlink_calls == 1, (
        f"expected exactly 1 call to read_hyperlinks (cache), got {counter.hyperlink_calls}"
    )


def test_modify_mode_comment_setter_queues(fixture_with_comments_and_links: Path) -> None:
    """RFC-023: cell.comment is now supported in modify mode."""
    wb = Workbook._from_patcher(str(fixture_with_comments_and_links))
    ws = wb.active
    ws["C1"].comment = Comment(text="new", author="x")
    # Pending dict captured the assignment.
    assert ws._pending_comments["C1"].text == "new"  # noqa: SLF001
