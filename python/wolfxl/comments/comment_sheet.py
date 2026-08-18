"""``openpyxl.comments.comment_sheet`` import shim."""

from __future__ import annotations

from wolfxl._compat import _install_openpyxl_iter, _openpyxl_name_fallback
from wolfxl.comments import Comment
from wolfxl.comments.author import AuthorList
from wolfxl.cell.text import Text
from wolfxl.utils.indexed_list import IndexedList
from wolfxl.xml.constants import SHEET_MAIN_NS
from wolfxl.xml.functions import Element, localname


class CommentRecord(Comment):
    tagname = "comment"
    __attrs__ = ("ref", "authorId", "guid", "shapeId")
    __elements__ = ("text", "commentPr")

    def __init__(
        self,
        ref: str = "",
        authorId: int = 0,  # noqa: N803
        guid: str | None = None,
        shapeId: int = 0,  # noqa: N803
        text: Text | None = None,
        commentPr: object | None = None,  # noqa: N803
        author: str | None = None,
        height: int = 79,
        width: int = 144,
    ) -> None:
        super().__init__(
            text=text if text is not None else Text(),
            author=author,
            height=height,
            width=width,
        )
        self.ref = ref
        self.authorId = authorId
        self.guid = guid
        self.shapeId = shapeId
        self.commentPr = commentPr

    @property
    def content(self) -> str:
        return self.text.content

    @content.setter
    def content(self, value: str) -> None:
        if isinstance(self.text, Text):
            self.text.t = value

    @classmethod
    def from_cell(cls, cell) -> "CommentRecord":  # type: ignore[no-untyped-def]
        comment = getattr(cell, "_comment", None)
        if comment is None:
            raise ValueError(f"cell {cell.coordinate} has no comment")
        record = cls(ref=cell.coordinate, author=comment.author)
        record.text.t = comment.content
        record.height = comment.height
        record.width = comment.width
        return record

    def to_tree(self):  # type: ignore[no-untyped-def]
        node = Element(self.tagname)
        node.set("authorId", str(self.authorId))
        node.set("ref", self.ref)
        if self.guid is not None:
            node.set("guid", self.guid)
        if self.shapeId is not None:
            node.set("shapeId", str(self.shapeId))
        node.append(self.text.to_tree())
        if self.commentPr is not None and hasattr(self.commentPr, "to_tree"):
            node.append(self.commentPr.to_tree())
        return node

    @classmethod
    def from_tree(cls, node) -> "CommentRecord":  # type: ignore[no-untyped-def]
        text = None
        comment_pr = None
        for child in list(node):
            name = localname(child)
            if name == "text":
                text = Text.from_tree(child)
            elif name == "commentPr":
                comment_pr = child
        return cls(
            ref=node.get("ref", ""),
            authorId=int(node.get("authorId", 0)),
            guid=node.get("guid"),
            shapeId=int(node.get("shapeId", 0)),
            text=text,
            commentPr=comment_pr,
        )


class CommentSheet:
    tagname = "comments"
    _id = None
    _path = "/xl/comments/comment{0}.xml"
    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"
    _rel_type = "comments"
    _rel_id = None

    def __init__(
        self,
        authors: AuthorList | None = None,
        commentList=None,  # noqa: N803, ANN001
        extLst=None,  # noqa: N803, ANN001
    ) -> None:
        self.authors = authors if authors is not None else AuthorList()
        self.commentList = tuple(commentList or ())
        self.extLst = extLst

    @classmethod
    def from_tree(cls, node):  # type: ignore[no-untyped-def]
        authors = AuthorList()
        comments: list[CommentRecord] = []
        for child in list(node):
            name = localname(child)
            if name == "authors":
                authors = AuthorList.from_tree(child)
            elif name == "commentList":
                comments = [
                    CommentRecord.from_tree(grandchild)
                    for grandchild in list(child)
                    if localname(grandchild) == "comment"
                ]
        return cls(authors=authors, commentList=comments)

    @classmethod
    def from_comments(cls, comments):  # type: ignore[no-untyped-def]
        authors = IndexedList()
        for comment in comments:
            comment.authorId = authors.add(comment.author)
        return cls(authors=AuthorList(authors), commentList=comments)

    @property
    def comments(self):  # type: ignore[no-untyped-def]
        authors = self.authors.author
        for comment in self.commentList:
            author = authors[comment.authorId] if comment.authorId < len(authors) else None
            yield comment.ref, Comment(comment.content, author, comment.height, comment.width)

    @property
    def path(self) -> str:
        return self._path.format(self._id)

    def to_tree(self):  # type: ignore[no-untyped-def]
        node = Element(self.tagname)
        node.set("xmlns", SHEET_MAIN_NS)
        node.append(self.authors.to_tree())
        comments = Element("commentList")
        for comment in self.commentList:
            comments.append(comment.to_tree())
        node.append(comments)
        return node


_install_openpyxl_iter(CommentRecord)

__all__ = ["AuthorList", "Comment", "CommentRecord", "CommentSheet", "IndexedList"]

__getattr__ = _openpyxl_name_fallback(globals())
