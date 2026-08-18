"""RFC-068 G08 step 5 — Threaded comments + persons round-trip in modify mode.

The save-time path threads three layers (mirrors RFC-023 / comments):

1. ``Cell.threaded_comment`` setter (Python) drops the value into
   ``ws._pending_threaded_comments[coord]``. ``None`` is the
   explicit-delete sentinel.
2. ``Workbook._flush_pending_threaded_comments_to_patcher`` +
   ``_flush_pending_persons_to_patcher`` (Python) drain each sheet's
   pending dict into ``XlsxPatcher.queue_threaded_comment`` /
   ``queue_threaded_comment_delete`` and the workbook's persons into
   ``queue_person``.
3. ``XlsxPatcher::do_save`` Phase 2.5g0 (Rust) extracts the existing
   ``threadedCommentsN.xml`` + ``personList.xml`` (if any), merges
   queued ops, emits fresh bytes, mutates the rels graph, registers
   content-type overrides, and synthesizes ``tc={topId}`` placeholder
   comments into ``queued_comments`` so the legacy comments phase emits
   the matching ``[Threaded comment]`` body.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import wolfxl
from wolfxl import load_workbook
from wolfxl.comments import ThreadedComment


def _make_clean_fixture(path: Path) -> None:
    """A wolfxl-authored workbook with no threaded comments."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Sheet1"
    ws["A1"] = "header"
    wb.save(str(path))


def _make_one_thread_fixture(path: Path) -> None:
    """A wolfxl-authored workbook with one top-level threaded comment."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Sheet1"
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice", user_id="alice@example.com")
    ws["A1"].threaded_comment = ThreadedComment(text="needs review", person=alice)
    wb.save(str(path))


def test_add_thread_to_clean_file_lights_up_parts(tmp_path: Path) -> None:
    """Open a file with no threaded payload, add one, parts appear."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    _make_clean_fixture(src)

    wb = load_workbook(str(src), modify=True)
    ws = wb["Sheet1"]
    bob = wb.persons.add(name="Bob", user_id="bob@example.com")
    ws["B2"].threaded_comment = ThreadedComment(text="from modify", person=bob)
    wb.save(str(dst))

    with zipfile.ZipFile(dst) as zf:
        names = zf.namelist()
        assert any(
            n.startswith("xl/threadedComments/threadedComments")
            and n.endswith(".xml")
            for n in names
        ), names
        assert any(n == "xl/persons/personList.xml" for n in names), names
        # Synthetic legacy placeholder must still be emitted.
        assert any(n.startswith("xl/comments") and n.endswith(".xml") for n in names), names

    wb2 = load_workbook(str(dst), modify=False)
    ws2 = wb2["Sheet1"]
    tc = ws2["B2"].threaded_comment
    assert tc is not None
    assert tc.text == "from modify"
    assert tc.person is not None
    assert tc.person.name == "Bob"


def test_replace_existing_thread(tmp_path: Path) -> None:
    """Set on a cell that already has a thread replaces the whole thread."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    _make_one_thread_fixture(src)

    wb = load_workbook(str(src), modify=True)
    ws = wb["Sheet1"]
    # Reuse an existing person from the round-tripped registry.
    persons = list(wb.persons)
    assert persons, "fixture should have seeded at least one person"
    ws["A1"].threaded_comment = ThreadedComment(text="updated", person=persons[0])
    wb.save(str(dst))

    wb2 = load_workbook(str(dst), modify=False)
    tc = wb2["Sheet1"]["A1"].threaded_comment
    assert tc is not None
    assert tc.text == "updated"


def test_delete_thread(tmp_path: Path) -> None:
    """``cell.threaded_comment = None`` drops the thread + legacy placeholder."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    _make_one_thread_fixture(src)

    wb = load_workbook(str(src), modify=True)
    ws = wb["Sheet1"]
    ws["A1"].threaded_comment = None
    wb.save(str(dst))

    wb2 = load_workbook(str(dst), modify=False)
    assert wb2["Sheet1"]["A1"].threaded_comment is None


def test_persons_registry_round_trips_through_modify(tmp_path: Path) -> None:
    """Persons added in modify mode are visible after re-open."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    _make_one_thread_fixture(src)

    wb = load_workbook(str(src), modify=True)
    pre_count = len(list(wb.persons))
    carol = wb.persons.add(name="Carol", user_id="carol@example.com")
    ws = wb["Sheet1"]
    ws["B5"].threaded_comment = ThreadedComment(
        text="second thread", person=carol
    )
    wb.save(str(dst))

    wb2 = load_workbook(str(dst), modify=False)
    names = {p.name for p in wb2.persons}
    assert "Alice" in names
    assert "Carol" in names
    # Should be exactly one more person than the source.
    assert len(list(wb2.persons)) == pre_count + 1


def test_no_threaded_op_save_preserves_existing(tmp_path: Path) -> None:
    """Open + save without touching threaded payload preserves the thread."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    _make_one_thread_fixture(src)

    wb = load_workbook(str(src), modify=True)
    # Mutate something unrelated so do_save runs but threaded_comments queue
    # stays empty for Sheet1.
    wb["Sheet1"]["Z9"] = "noop"
    wb.save(str(dst))

    wb2 = load_workbook(str(dst), modify=False)
    tc = wb2["Sheet1"]["A1"].threaded_comment
    assert tc is not None, "round-trip dropped the existing thread"
    assert tc.text == "needs review"
