"""``openpyxl.comments.comments`` — re-export shim for :class:`Comment`."""

from __future__ import annotations

from dataclasses import dataclass, field

from wolfxl.comments import Comment


@dataclass
class CommentSheet:
    """Passive comment-sheet container used for import compatibility."""

    comments: list[Comment] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)

    def append(self, comment: Comment) -> None:
        if not isinstance(comment, Comment):
            raise TypeError(f"CommentSheet.append expects Comment, got {type(comment).__name__}")
        self.comments.append(comment)
        if comment.author and comment.author not in self.authors:
            self.authors.append(comment.author)


__all__ = ["Comment", "CommentSheet"]
