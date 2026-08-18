"""Sheet protection.

Backs ``ws.protection``. Mirrors openpyxl's
``openpyxl.worksheet.protection.SheetProtection`` field surface
including the ``set_password`` / ``check_password`` helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from wolfxl._compat import _iter_openpyxl_attrs, _openpyxl_name_fallback
from wolfxl.utils.protection import hash_password as _hash_password
from wolfxl.utils.protection import check_password as _check_password
from wolfxl.xml.functions import Element


@dataclass
class SheetProtection:
    """SheetProtection (CT_SheetProtection, ECMA-376 §18.3.1.85).

    Defaults match Excel's behaviour when ``Tools → Protection → Protect Sheet``
    is invoked with no further options: the sheet is locked but every "allow
    these actions" toggle defaults to allowed (because the sheet's underlying
    ``locked`` cell-level flag still gates each operation).
    """

    sheet: bool = False
    objects: bool = False
    scenarios: bool = False
    formatCells: bool = True  # noqa: N815
    formatColumns: bool = True  # noqa: N815
    formatRows: bool = True  # noqa: N815
    insertColumns: bool = True  # noqa: N815
    insertRows: bool = True  # noqa: N815
    insertHyperlinks: bool = True  # noqa: N815
    deleteColumns: bool = True  # noqa: N815
    deleteRows: bool = True  # noqa: N815
    selectLockedCells: bool = False  # noqa: N815
    sort: bool = True
    autoFilter: bool = True  # noqa: N815
    pivotTables: bool = True  # noqa: N815
    selectUnlockedCells: bool = False  # noqa: N815
    password: str | None = None  # already-hashed (4-char uppercase hex)
    algorithmName: str | None = None  # noqa: N815
    saltValue: str | None = None  # noqa: N815
    spinCount: int | None = None  # noqa: N815
    hashValue: str | None = None  # noqa: N815

    __attrs__: ClassVar[tuple[str, ...]] = (
        "selectLockedCells",
        "selectUnlockedCells",
        "algorithmName",
        "sheet",
        "objects",
        "insertRows",
        "insertHyperlinks",
        "autoFilter",
        "scenarios",
        "formatColumns",
        "deleteColumns",
        "insertColumns",
        "pivotTables",
        "deleteRows",
        "formatCells",
        "saltValue",
        "formatRows",
        "sort",
        "spinCount",
        "password",
        "hashValue",
    )

    def __post_init__(self) -> None:
        if self.password is not None:
            self.set_password(self.password)

    # snake_case aliases (the canonical openpyxl attr names use camelCase
    # but several call sites in the wider Python ecosystem use snake_case).
    @property
    def format_cells(self) -> bool:
        """Return whether users may format cells on a protected sheet.

        Returns:
            ``True`` when cell-formatting operations are allowed.
        """
        return self.formatCells

    @format_cells.setter
    def format_cells(self, value: bool) -> None:
        """Set whether users may format cells on a protected sheet.

        Args:
            value: Truthy value to allow cell-formatting operations.
        """
        self.formatCells = bool(value)

    @property
    def format_columns(self) -> bool:
        return self.formatColumns

    @format_columns.setter
    def format_columns(self, value: bool) -> None:
        self.formatColumns = bool(value)

    @property
    def format_rows(self) -> bool:
        return self.formatRows

    @format_rows.setter
    def format_rows(self, value: bool) -> None:
        self.formatRows = bool(value)

    @property
    def insert_columns(self) -> bool:
        return self.insertColumns

    @insert_columns.setter
    def insert_columns(self, value: bool) -> None:
        self.insertColumns = bool(value)

    @property
    def insert_rows(self) -> bool:
        return self.insertRows

    @insert_rows.setter
    def insert_rows(self, value: bool) -> None:
        self.insertRows = bool(value)

    @property
    def insert_hyperlinks(self) -> bool:
        return self.insertHyperlinks

    @insert_hyperlinks.setter
    def insert_hyperlinks(self, value: bool) -> None:
        self.insertHyperlinks = bool(value)

    @property
    def delete_columns(self) -> bool:
        return self.deleteColumns

    @delete_columns.setter
    def delete_columns(self, value: bool) -> None:
        self.deleteColumns = bool(value)

    @property
    def delete_rows(self) -> bool:
        return self.deleteRows

    @delete_rows.setter
    def delete_rows(self, value: bool) -> None:
        self.deleteRows = bool(value)

    @property
    def select_locked_cells(self) -> bool:
        return self.selectLockedCells

    @select_locked_cells.setter
    def select_locked_cells(self, value: bool) -> None:
        self.selectLockedCells = bool(value)

    @property
    def auto_filter(self) -> bool:
        return self.autoFilter

    @auto_filter.setter
    def auto_filter(self, value: bool) -> None:
        self.autoFilter = bool(value)

    @property
    def pivot_tables(self) -> bool:
        return self.pivotTables

    @pivot_tables.setter
    def pivot_tables(self, value: bool) -> None:
        self.pivotTables = bool(value)

    @property
    def select_unlocked_cells(self) -> bool:
        return self.selectUnlockedCells

    @select_unlocked_cells.setter
    def select_unlocked_cells(self, value: bool) -> None:
        self.selectUnlockedCells = bool(value)

    def enable(self) -> None:
        """Turn protection on. ``ws.protection.enable()`` is the single-call
        idiom most users reach for after constructing the SheetProtection.
        """
        self.sheet = True

    def disable(self) -> None:
        self.sheet = False

    def set_password(self, value: str | None = "", already_hashed: bool = False) -> None:
        """Hash ``plaintext`` and store the 4-hex result in ``password``.

        Matches openpyxl's high-use behavior: setting any password
        also enables sheet protection. Empty input hashes to the legacy
        ``CE4B`` value rather than clearing protection.
        """
        plaintext = "" if value is None else value
        if already_hashed:
            self.password = plaintext
            self.enable()
            return
        self.password = _hash_password(plaintext)
        self.enable()

    def check_password(self, plaintext: str) -> bool:
        if self.password is None:
            return False
        return _check_password(plaintext, self.password)

    def to_rust_dict(self) -> dict[str, Any]:
        return {
            "sheet": bool(self.sheet),
            "objects": bool(self.objects),
            "scenarios": bool(self.scenarios),
            "format_cells": bool(self.formatCells),
            "format_columns": bool(self.formatColumns),
            "format_rows": bool(self.formatRows),
            "insert_columns": bool(self.insertColumns),
            "insert_rows": bool(self.insertRows),
            "insert_hyperlinks": bool(self.insertHyperlinks),
            "delete_columns": bool(self.deleteColumns),
            "delete_rows": bool(self.deleteRows),
            "select_locked_cells": bool(self.selectLockedCells),
            "sort": bool(self.sort),
            "auto_filter": bool(self.autoFilter),
            "pivot_tables": bool(self.pivotTables),
            "select_unlocked_cells": bool(self.selectUnlockedCells),
            "password_hash": self.password,
        }

    def is_default(self) -> bool:
        return self == SheetProtection()

    def __bool__(self) -> bool:
        return self.sheet

    def __iter__(self):
        yield from _iter_openpyxl_attrs(self, self.__attrs__)

    def to_tree(
        self,
        tagname: str | None = None,
        idx: int | None = None,  # noqa: ARG002 - openpyxl signature
        namespace: str | None = None,  # noqa: ARG002 - openpyxl signature
    ) -> Any:
        node = Element(tagname or "sheetProtection")
        for name, value in self:
            node.set(name, value)
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "SheetProtection":
        kwargs: dict[str, Any] = {}
        for name in cls.__attrs__:
            value = node.get(name)
            if value is None:
                continue
            if name in {"algorithmName", "saltValue", "password", "hashValue"}:
                kwargs[name] = value
            elif name == "spinCount":
                kwargs[name] = int(value)
            else:
                kwargs[name] = value.lower() in {"1", "true"}

        password = kwargs.pop("password", None)
        protection = cls(**kwargs)
        if password is not None:
            protection.password = password
        return protection


__all__ = ["SheetProtection"]

__getattr__ = _openpyxl_name_fallback(globals())
