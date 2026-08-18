"""openpyxl.comments compatibility.

T1 makes ``Comment`` a real, mutable dataclass. Construction works in any
mode; attaching to a cell via ``cell.comment = Comment(...)`` works in
write mode (T1 PR4). Read access — ``cell.comment.text`` — works on any
file opened in read or modify mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import inspect as _inspect
from typing import Any


@dataclass
class Comment:
    """A cell comment (note).

    openpyxl keeps comments mutable — users commonly do
    ``cell.comment.text = "updated"`` after attaching. Width/height are
    preserved on round-trip but not authored from Python; wolfxl stores
    them as pass-throughs.
    """

    text: str
    author: str | None = None
    height: int | None = 79
    width: int | None = 144
    parent: Any = None

    @property
    def content(self) -> str:
        return self.text

    @content.setter
    def content(self, value: str) -> None:
        self.text = value

    def bind(self, parent: Any | None = None, *, cell: Any | None = None) -> None:
        """Bind this comment to a parent cell, matching openpyxl's public surface."""
        parent = parent if parent is not None else cell
        self.parent = parent

    def unbind(self) -> None:
        """Clear the parent-cell binding."""
        self.parent = None

    def __copy__(self) -> "Comment":
        return self.__class__(self.content, self.author, self.height, self.width)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Comment):
            return NotImplemented
        return (
            self.content,
            self.author,
            self.height,
            self.width,
        ) == (
            other.content,
            other.author,
            other.height,
            other.width,
        )

    def __repr__(self) -> str:
        return f"Comment: {self.content} by {self.author}"


from wolfxl.comments._person import Person, PersonRegistry
from wolfxl.comments._threaded_comment import ThreadedComment
author = import_module("wolfxl.comments.author")
comment_sheet = import_module("wolfxl.comments.comment_sheet")
comments = import_module("wolfxl.comments.comments")
shape_writer = import_module("wolfxl.comments.shape_writer")

Comment.bind.__signature__ = _inspect.Signature(
    [
        _inspect.Parameter("self", _inspect.Parameter.POSITIONAL_OR_KEYWORD),
        _inspect.Parameter("cell", _inspect.Parameter.POSITIONAL_OR_KEYWORD),
    ]
)

__all__ = [
    "Comment",
    "Person",
    "PersonRegistry",
    "ThreadedComment",
    "author",
    "comment_sheet",
    "comments",
    "shape_writer",
]
