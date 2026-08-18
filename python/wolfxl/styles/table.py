"""Table style model compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wolfxl._compat import _OpenpyxlSerialisable, _make_serialisable, _resolve_openpyxl_class

TableStyleElement = _resolve_openpyxl_class(__name__, "TableStyleElement") or _make_serialisable(
    "TableStyleElement",
    module_name=__name__,
)
TableStyle = _resolve_openpyxl_class(__name__, "TableStyle") or _make_serialisable(
    "TableStyle",
    module_name=__name__,
)
_OpenpyxlTableStyleList = _resolve_openpyxl_class(__name__, "TableStyleList")


if _OpenpyxlTableStyleList is None:

    @dataclass
    class TableStyleList:
        count: int | None = None
        defaultTableStyle: str | None = "TableStyleMedium9"  # noqa: N815
        defaultPivotStyle: str | None = "PivotStyleLight16"  # noqa: N815
        tableStyle: list[TableStyle] = field(default_factory=list)  # noqa: N815

        def __post_init__(self) -> None:
            if self.count is None:
                self.count = len(self.tableStyle)

        def __iter__(self):
            return iter(self.tableStyle)

        def append(self, value: TableStyle) -> None:
            self.tableStyle.append(value)
            self.count = len(self.tableStyle)

else:

    class TableStyleList(_OpenpyxlTableStyleList):  # type: ignore[misc, valid-type]
        __attrs__ = _OpenpyxlTableStyleList.__attrs__
        __elements__ = _OpenpyxlTableStyleList.__elements__

        def append(self, value: TableStyle) -> None:
            self.tableStyle.append(value)
            self.count = len(self.tableStyle)


Bool = Color = Float = Integer = NoneSet = Sequence = Serialisable = Set = String = Typed = _OpenpyxlSerialisable

__all__ = [
    "Bool",
    "Color",
    "Float",
    "Integer",
    "NoneSet",
    "Sequence",
    "Serialisable",
    "Set",
    "String",
    "TableStyle",
    "TableStyleElement",
    "TableStyleList",
    "Typed",
]
