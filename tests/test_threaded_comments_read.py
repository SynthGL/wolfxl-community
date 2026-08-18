"""G08 step 4: read-after-save closes the threaded-comments round trip.

These tests prove the full path: ``wb.save()`` -> ``load_workbook()`` ->
``ws[coord].threaded_comment`` recovers the top-level + replies tree
with the exact text, person attribution, and GUIDs from the writer.
"""
from __future__ import annotations

import wolfxl
from wolfxl.comments import ThreadedComment


def test_round_trip_top_level_threaded_comment(tmp_path) -> None:
    out = tmp_path / "tc.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice", user_id="alice@example.com")
    top = ThreadedComment(text="Looks wrong", person=alice)
    ws["A1"].threaded_comment = top
    wb.save(str(out))
    saved_top_id = top.id
    saved_alice_id = alice.id
    assert saved_top_id is not None
    assert saved_alice_id is not None

    wb2 = wolfxl.load_workbook(str(out))
    ws2 = wb2.active
    assert ws2 is not None
    recovered = ws2["A1"].threaded_comment
    assert recovered is not None
    assert recovered.text == "Looks wrong"
    assert recovered.id == saved_top_id
    assert recovered.parent is None
    assert recovered.replies == []
    assert recovered.person.id == saved_alice_id
    assert recovered.person.name == "Alice"
    assert recovered.person.user_id == "alice@example.com"


def test_round_trip_thread_with_replies_preserves_order(tmp_path) -> None:
    out = tmp_path / "tc.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice")
    bob = wb.persons.add(name="Bob")
    parent = ThreadedComment(text="Q?", person=alice)
    parent.replies.append(ThreadedComment(text="A.", person=bob, parent=parent))
    parent.replies.append(ThreadedComment(text="C.", person=alice, parent=parent))
    ws["A1"].threaded_comment = parent
    wb.save(str(out))

    wb2 = wolfxl.load_workbook(str(out))
    ws2 = wb2.active
    assert ws2 is not None
    rec = ws2["A1"].threaded_comment
    assert rec is not None
    assert rec.text == "Q?"
    assert rec.person.name == "Alice"
    assert len(rec.replies) == 2
    assert [r.text for r in rec.replies] == ["A.", "C."]
    # Reply links back to parent via the GUID chain.
    for reply in rec.replies:
        assert reply.parent is rec
    # Person identity preserved across replies.
    assert rec.replies[0].person.name == "Bob"
    assert rec.replies[1].person.name == "Alice"


def test_persons_registry_hydrates_from_reader(tmp_path) -> None:
    out = tmp_path / "tc.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice Smith", user_id="alice@x.com", provider_id="AD")
    ws["A1"].threaded_comment = ThreadedComment(text="hi", person=alice)
    wb.save(str(out))
    saved_alice_id = alice.id

    wb2 = wolfxl.load_workbook(str(out))
    persons = list(wb2.persons)
    assert len(persons) == 1
    p = persons[0]
    assert p.id == saved_alice_id
    assert p.name == "Alice Smith"
    assert p.user_id == "alice@x.com"
    assert p.provider_id == "AD"


def test_workbook_with_no_threaded_comments_returns_none(tmp_path) -> None:
    out = tmp_path / "plain.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "hello"
    wb.save(str(out))

    wb2 = wolfxl.load_workbook(str(out))
    ws2 = wb2.active
    assert ws2 is not None
    assert ws2["A1"].threaded_comment is None
    assert len(list(wb2.persons)) == 0


def test_done_flag_round_trips(tmp_path) -> None:
    out = tmp_path / "tc.xlsx"
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice")
    tc = ThreadedComment(text="resolved", person=alice, done=True)
    ws["A1"].threaded_comment = tc
    wb.save(str(out))

    wb2 = wolfxl.load_workbook(str(out))
    ws2 = wb2.active
    assert ws2 is not None
    rec = ws2["A1"].threaded_comment
    assert rec is not None
    assert rec.done is True
