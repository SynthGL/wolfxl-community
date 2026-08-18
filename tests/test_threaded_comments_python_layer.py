"""G08 step 2: Python class layer for threaded comments.

These tests pin the public surface — ``Person``, ``PersonRegistry``,
``ThreadedComment``, ``wb.persons``, and ``cell.threaded_comment`` — before
the writer/reader layers land in steps 3-4. They run against the in-memory
Python state only; round-trip through wolfxl save will start passing once
RFC-068 step 3 lands.
"""
from __future__ import annotations

import pytest

import wolfxl
from wolfxl.comments import Comment, Person, PersonRegistry, ThreadedComment


def test_person_dataclass_default_provider_id() -> None:
    p = Person(name="Alice")
    assert p.name == "Alice"
    assert p.user_id == ""
    assert p.provider_id == "None"
    assert p.id is None  # GUID allocated by registry, not constructor


def test_person_registry_allocates_guid_on_add() -> None:
    reg = PersonRegistry()
    alice = reg.add(name="Alice")
    assert alice.id is not None and alice.id.startswith("{") and alice.id.endswith("}")
    assert len(reg) == 1
    assert reg.by_id(alice.id) is alice


def test_person_registry_idempotent_on_user_id_provider_id() -> None:
    """Calling add() twice with the same (user_id, provider_id) returns same Person."""
    reg = PersonRegistry()
    a1 = reg.add(name="Alice", user_id="alice@example.com", provider_id="AD")
    a2 = reg.add(name="Alice (display)", user_id="alice@example.com", provider_id="AD")
    assert a1 is a2
    assert len(reg) == 1


def test_person_registry_allocates_distinct_guids_when_user_id_empty() -> None:
    reg = PersonRegistry()
    a = reg.add(name="Anon-1")
    b = reg.add(name="Anon-2")
    assert a is not b
    assert a.id != b.id


def test_threaded_comment_parent_default_is_none() -> None:
    p = Person(name="A", id="{X}")
    tc = ThreadedComment(text="hi", person=p)
    assert tc.parent is None
    assert tc.replies == []
    assert tc.id is None  # lazy
    assert tc.created is None  # lazy


def test_threaded_comment_reply_must_not_have_replies() -> None:
    """Excel threading is two-tier — replies cannot themselves have replies."""
    p = Person(name="A", id="{X}")
    parent = ThreadedComment(text="t", person=p)
    with pytest.raises(ValueError, match="two-tier"):
        ThreadedComment(
            text="r",
            person=p,
            parent=parent,
            replies=[ThreadedComment(text="rr", person=p)],
        )


def test_threaded_comment_ensure_id_is_lazy() -> None:
    p = Person(name="A", id="{X}")
    tc = ThreadedComment(text="hi", person=p)
    assert tc.id is None
    g1 = tc.ensure_id()
    assert tc.id == g1 and g1.startswith("{") and g1.endswith("}")
    assert tc.ensure_id() == g1  # idempotent


def test_workbook_persons_lazy_seeded() -> None:
    wb = wolfxl.Workbook()
    persons = wb.persons
    assert isinstance(persons, PersonRegistry)
    assert wb.persons is persons  # same instance on re-access
    assert len(persons) == 0


def test_cell_threaded_comment_set_and_clear() -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "topic"
    alice = wb.persons.add(name="Alice")
    tc = ThreadedComment(text="Looks wrong", person=alice)
    ws["A1"].threaded_comment = tc
    assert ws["A1"].threaded_comment is tc

    ws["A1"].threaded_comment = None
    assert ws["A1"].threaded_comment is None


def test_cell_threaded_comment_rejects_reply_at_top_level() -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    alice = wb.persons.add(name="Alice")
    parent = ThreadedComment(text="t", person=alice)
    reply = ThreadedComment(text="r", person=alice, parent=parent)
    with pytest.raises(ValueError, match="top-level"):
        ws["A1"].threaded_comment = reply


def test_cell_threaded_comment_rejects_non_threaded_comment_value() -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    with pytest.raises(TypeError, match="ThreadedComment"):
        ws["A1"].threaded_comment = Comment(text="legacy", author="me")  # type: ignore[assignment]


def test_cell_threaded_comment_conflicts_with_legacy_comment() -> None:
    """Setting threaded on a cell with a pending legacy comment raises."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    ws["A1"].comment = Comment(text="legacy", author="me")
    alice = wb.persons.add(name="Alice")
    with pytest.raises(ValueError, match="legacy comment"):
        ws["A1"].threaded_comment = ThreadedComment(text="t", person=alice)


def test_cell_legacy_comment_conflicts_with_pending_threaded() -> None:
    """The reverse: setting legacy after a pending threaded raises."""
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    alice = wb.persons.add(name="Alice")
    ws["A1"].threaded_comment = ThreadedComment(text="t", person=alice)
    with pytest.raises(ValueError, match="threaded comment"):
        ws["A1"].comment = Comment(text="legacy", author="me")


def test_threaded_comment_replies_accumulate_on_top_level() -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = "x"
    alice = wb.persons.add(name="Alice")
    parent = ThreadedComment(text="parent", person=alice)
    parent.replies.append(ThreadedComment(text="r1", person=alice, parent=parent))
    parent.replies.append(ThreadedComment(text="r2", person=alice, parent=parent))
    ws["A1"].threaded_comment = parent
    got = ws["A1"].threaded_comment
    assert got is parent
    assert [r.text for r in got.replies] == ["r1", "r2"]
