"""ThreadedComment value type for Excel 365 threaded comments (G08 step 2).

A ``ThreadedComment`` is either:

- **top-level** — ``parent`` is ``None``; lives at ``ws[coord].threaded_comment``.
- **reply** — ``parent`` is the top-level ``ThreadedComment``; appended to
  the parent's ``replies`` list.

The ``id`` is a Microsoft-style brace-wrapped GUID, auto-allocated at flush
time when ``None``. The ``created`` timestamp defaults to ``datetime.now()``
on flush. Construction does not allocate so unit tests can assert on stable
shape before save.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wolfxl.comments._person import Person


def _new_guid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


@dataclass
class ThreadedComment:
    """Excel 365 threaded comment.

    Top-level threaded comments carry a ``replies`` list; replies set
    ``parent`` to the top-level instance (the parent's ``replies`` list
    is the source of truth for ordering).
    """

    text: str
    person: "Person"
    parent: "ThreadedComment | None" = None
    created: datetime | None = None
    done: bool = False
    id: str | None = None  # noqa: A003 - mirror openpyxl public name
    replies: list["ThreadedComment"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.parent is not None and self.replies:
            raise ValueError(
                "reply ThreadedComment cannot itself have replies; "
                "Excel threading is two-tier"
            )

    def ensure_id(self) -> str:
        """Lazily assign a GUID when the writer needs one."""
        if self.id is None:
            self.id = _new_guid()
        return self.id

    def ensure_created(self) -> datetime:
        if self.created is None:
            self.created = datetime.now()
        return self.created
