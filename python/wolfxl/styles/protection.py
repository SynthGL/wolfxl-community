"""``openpyxl.styles.protection`` — cell-protection value type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar
from xml.etree import ElementTree as ET

from wolfxl._compat import _install_openpyxl_iter, _openpyxl_name_fallback


@dataclass(eq=False)
class Protection:
    """Cell protection flags.

    Matches openpyxl's lightweight ``Protection(locked=True, hidden=False)``
    construction surface. Sheet-level enforcement still lives in
    ``wolfxl.worksheet.protection.SheetProtection``.
    """

    locked: bool = True
    hidden: bool = False
    tagname: ClassVar[str] = "protection"
    namespace: ClassVar[str | None] = None
    idx_base: ClassVar[int] = 0

    def to_rust_dict(self) -> dict[str, bool]:
        return {"locked": self.locked, "hidden": self.hidden}

    def __eq__(self, other: object) -> bool:
        return (
            getattr(other, "__class__", object).__name__ == self.__class__.__name__
            and getattr(other, "locked", None) == self.locked
            and getattr(other, "hidden", None) == self.hidden
        )

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> ET.Element:
        node = ET.Element(tagname or self.tagname)
        node.set("locked", "1" if self.locked else "0")
        node.set("hidden", "1" if self.hidden else "0")
        return node

    @classmethod
    def from_tree(cls, node: ET.Element) -> Protection:
        return cls(
            locked=node.attrib.get("locked", "1") not in {"0", "false", "False"},
            hidden=node.attrib.get("hidden", "0") not in {"0", "false", "False"},
        )

_install_openpyxl_iter(Protection)

__all__ = ["Protection"]

__getattr__ = _openpyxl_name_fallback(globals())
