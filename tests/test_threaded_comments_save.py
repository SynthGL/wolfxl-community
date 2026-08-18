"""G08 step 3: end-to-end save through Python -> Rust -> XML.

These tests prove the writer emit path: take a wolfxl.Workbook with
threaded comments through ``wb.save(...)`` and assert the resulting
xlsx archive contains the canonical OOXML parts. The reader (step 4)
will land before round-trip equality tests can pass.
"""
from __future__ import annotations

import zipfile

import wolfxl
from wolfxl.comments import ThreadedComment


def _read_part(path: str, part_path: str) -> str:
    with zipfile.ZipFile(path) as zf:
        with zf.open(part_path) as f:
            return f.read().decode("utf-8")


def _list_parts(path: str) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


def test_threaded_comment_top_level_emits_canonical_parts(tmp_path) -> None:
    out = tmp_path / "tc.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice", user_id="alice@example.com")
    ws["A1"].threaded_comment = ThreadedComment(text="Looks wrong", person=alice)
    wb.save(str(out))

    parts = _list_parts(str(out))
    assert "xl/threadedComments/threadedComments1.xml" in parts
    assert "xl/persons/personList.xml" in parts
    # The legacy placeholder is synthesized by the writer to hold the
    # ``[Threaded comment]`` body.
    assert "xl/comments/comments1.xml" in parts
    # Per RFC-068 §3.1 the legacy VML drawing remains required when a
    # legacy comments part exists.
    assert "xl/drawings/vmlDrawing1.vml" in parts


def test_threaded_comment_payload_contains_text_and_person_id(tmp_path) -> None:
    out = tmp_path / "tc.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice")
    top = ThreadedComment(text="Looks wrong", person=alice)
    ws["A1"].threaded_comment = top
    wb.save(str(out))

    payload = _read_part(str(out), "xl/threadedComments/threadedComments1.xml")
    assert "Looks wrong" in payload
    assert f"personId=\"{alice.id}\"" in payload
    # GUID must have been allocated by ensure_id() at flush time.
    assert top.id is not None
    assert f"id=\"{top.id}\"" in payload
    # No parentId for top-level threads.
    assert "parentId=" not in payload


def test_threaded_comment_with_reply_emits_parent_id(tmp_path) -> None:
    out = tmp_path / "tc.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice")
    parent = ThreadedComment(text="Q?", person=alice)
    parent.replies.append(ThreadedComment(text="A.", person=alice, parent=parent))
    ws["A1"].threaded_comment = parent
    wb.save(str(out))

    payload = _read_part(str(out), "xl/threadedComments/threadedComments1.xml")
    assert "Q?" in payload
    assert "A." in payload
    # Parent precedes reply in emit order.
    assert payload.index("Q?") < payload.index("A.")
    # Parent's GUID appears as parentId on the reply.
    assert parent.id is not None
    assert f"parentId=\"{parent.id}\"" in payload


def test_person_list_round_trips_display_name_and_user_id(tmp_path) -> None:
    out = tmp_path / "tc.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(
        name="Alice Smith", user_id="alice@example.com", provider_id="AD"
    )
    ws["A1"].threaded_comment = ThreadedComment(text="hi", person=alice)
    wb.save(str(out))

    pl = _read_part(str(out), "xl/persons/personList.xml")
    assert "displayName=\"Alice Smith\"" in pl
    assert "userId=\"alice@example.com\"" in pl
    assert "providerId=\"AD\"" in pl
    assert f"id=\"{alice.id}\"" in pl


def test_legacy_placeholder_synthesized_with_tc_author(tmp_path) -> None:
    out = tmp_path / "tc.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice")
    top = ThreadedComment(text="Looks wrong", person=alice)
    ws["A1"].threaded_comment = top
    wb.save(str(out))

    legacy = _read_part(str(out), "xl/comments/comments1.xml")
    # The synthetic author is `tc={topId}` per RFC-068 §3.2 rule 5.
    assert top.id is not None
    assert f"<author>tc={top.id}</author>" in legacy
    # The placeholder body is the literal `[Threaded comment]`.
    assert "<t>[Threaded comment]</t>" in legacy


def test_workbook_with_no_threaded_comments_omits_new_parts(tmp_path) -> None:
    """Sanity check — empty paths stay empty so we don't bloat unused workbooks."""
    out = tmp_path / "plain.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "hello"
    wb.save(str(out))

    parts = _list_parts(str(out))
    assert not any(p.startswith("xl/threadedComments/") for p in parts)
    assert "xl/persons/personList.xml" not in parts
