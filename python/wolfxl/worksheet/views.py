"""Sheet view classes (RFC-055 §2.5).

Backs ``ws.sheet_view``. Provides ``Pane``, ``Selection``, ``SheetView``,
and ``SheetViewList`` per OOXML CT_SheetView.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wolfxl._compat import _install_openpyxl_iter, _openpyxl_name_fallback
from wolfxl.xml.functions import Element


_VALID_PANE_NAMES = ("bottomLeft", "bottomRight", "topLeft", "topRight")
_VALID_PANE_STATES = ("frozen", "split", "frozenSplit")
_VALID_VIEWS = ("normal", "pageBreakPreview", "pageLayout")


@dataclass
class Pane:
    """A pane within a sheet view (CT_Pane)."""

    xSplit: float | None = 0.0  # noqa: N815
    ySplit: float | None = 0.0  # noqa: N815
    topLeftCell: str = "A1"  # noqa: N815
    activePane: str = "topLeft"  # noqa: N815
    state: str = "frozen"

    @property
    def x_split(self) -> float | None:
        return self.xSplit

    @x_split.setter
    def x_split(self, value: float | None) -> None:
        self.xSplit = None if value is None else float(value)

    @property
    def y_split(self) -> float | None:
        return self.ySplit

    @y_split.setter
    def y_split(self, value: float | None) -> None:
        self.ySplit = None if value is None else float(value)

    @property
    def top_left_cell(self) -> str:
        return self.topLeftCell

    @top_left_cell.setter
    def top_left_cell(self, value: str) -> None:
        self.topLeftCell = value

    @property
    def active_pane(self) -> str:
        return self.activePane

    @active_pane.setter
    def active_pane(self, value: str) -> None:
        if value not in _VALID_PANE_NAMES:
            raise ValueError(
                f"active_pane must be one of {_VALID_PANE_NAMES}, got {value!r}"
            )
        self.activePane = value

    def __post_init__(self) -> None:
        if self.activePane not in _VALID_PANE_NAMES:
            raise ValueError(
                f"activePane must be one of {_VALID_PANE_NAMES}, got {self.activePane!r}"
            )
        if self.state not in _VALID_PANE_STATES:
            raise ValueError(
                f"state must be one of {_VALID_PANE_STATES}, got {self.state!r}"
            )

    def to_rust_dict(self) -> dict[str, Any]:
        return {
            "x_split": float(self.xSplit or 0.0),
            "y_split": float(self.ySplit or 0.0),
            "top_left_cell": self.topLeftCell,
            "active_pane": self.activePane,
            "state": self.state,
        }

    def to_tree(self, tagname: str | None = None) -> Any:
        return Element(tagname or "pane", dict(self))

    @classmethod
    def from_tree(cls, node: Any) -> "Pane":
        attrs = dict(node.attrib)
        for key in ("xSplit", "ySplit"):
            if key in attrs:
                attrs[key] = float(attrs[key])
        return cls(**attrs)


@dataclass
class Selection:
    """Cell selection within a pane (CT_Selection)."""

    activeCell: str | None = "A1"  # noqa: N815
    sqref: str | None = "A1"
    pane: str | None = None
    activeCellId: int | None = None  # noqa: N815

    @property
    def active_cell(self) -> str | None:
        return self.activeCell

    @active_cell.setter
    def active_cell(self, value: str | None) -> None:
        self.activeCell = value

    def __post_init__(self) -> None:
        if self.pane is not None and self.pane not in _VALID_PANE_NAMES:
            raise ValueError(
                f"pane must be one of {_VALID_PANE_NAMES} or None, got {self.pane!r}"
            )

    def to_rust_dict(self) -> dict[str, Any]:
        return {
            "active_cell": self.activeCell,
            "sqref": self.sqref,
            "pane": self.pane,
        }

    def to_tree(self, tagname: str | None = None) -> Any:
        return Element(tagname or "selection", dict(self))

    @classmethod
    def from_tree(cls, node: Any) -> "Selection":
        attrs = dict(node.attrib)
        if "activeCellId" in attrs:
            attrs["activeCellId"] = int(attrs["activeCellId"])
        return cls(**attrs)


@dataclass(init=False)
class SheetView:
    """Single sheet view (CT_SheetView)."""

    zoomScale: int = 100  # noqa: N815
    zoomScaleNormal: int = 100  # noqa: N815
    view: str = "normal"
    showGridLines: bool | None = None  # noqa: N815
    showRowColHeaders: bool | None = None  # noqa: N815
    showOutlineSymbols: bool | None = None  # noqa: N815
    showZeros: bool | None = None  # noqa: N815
    rightToLeft: bool | None = None  # noqa: N815
    tabSelected: bool | None = None  # noqa: N815
    topLeftCell: str | None = None  # noqa: N815
    workbookViewId: int = 0  # noqa: N815
    pane: Pane | None = None
    selection: list[Selection] = field(default_factory=lambda: [Selection()])

    _ATTRS = (
        "windowProtection",
        "showFormulas",
        "showGridLines",
        "showRowColHeaders",
        "showZeros",
        "rightToLeft",
        "tabSelected",
        "showRuler",
        "showOutlineSymbols",
        "defaultGridColor",
        "showWhiteSpace",
        "view",
        "topLeftCell",
        "colorId",
        "zoomScale",
        "zoomScaleNormal",
        "zoomScaleSheetLayoutView",
        "zoomScalePageLayoutView",
        "zoomToFit",
        "workbookViewId",
    )

    def __init__(
        self,
        zoomScale: int = 100,  # noqa: N803
        zoomScaleNormal: int = 100,  # noqa: N803
        view: str = "normal",
        showGridLines: bool | None = None,  # noqa: N803
        showRowColHeaders: bool | None = None,  # noqa: N803
        showOutlineSymbols: bool | None = None,  # noqa: N803
        showZeros: bool | None = None,  # noqa: N803
        rightToLeft: bool | None = None,  # noqa: N803
        tabSelected: bool | None = None,  # noqa: N803
        topLeftCell: str | None = None,  # noqa: N803
        workbookViewId: int = 0,  # noqa: N803
        pane: Pane | None = None,
        selection: list[Selection] | tuple[Selection, ...] | Selection | None = None,
        **kw: Any,
    ) -> None:
        self.zoomScale = zoomScale
        self.zoomScaleNormal = zoomScaleNormal
        self.view = view
        self.showGridLines = showGridLines
        self.showRowColHeaders = showRowColHeaders
        self.showOutlineSymbols = showOutlineSymbols
        self.showZeros = showZeros
        self.rightToLeft = rightToLeft
        self.tabSelected = tabSelected
        self.topLeftCell = topLeftCell
        self.workbookViewId = workbookViewId
        self.pane = pane
        if selection is None:
            self.selection = [Selection()]
        elif isinstance(selection, Selection):
            self.selection = [selection]
        else:
            self.selection = list(selection)
        for key, value in kw.items():
            setattr(self, key, value)
        self.__post_init__()

    # snake_case aliases
    @property
    def zoom_scale(self) -> int:
        return self.zoomScale

    @zoom_scale.setter
    def zoom_scale(self, value: int) -> None:
        if not (10 <= int(value) <= 400):
            raise ValueError(f"zoom_scale must be between 10 and 400, got {value}")
        self.zoomScale = int(value)

    @property
    def zoom_scale_normal(self) -> int:
        return self.zoomScaleNormal

    @zoom_scale_normal.setter
    def zoom_scale_normal(self, value: int) -> None:
        self.zoomScaleNormal = int(value)

    @property
    def show_grid_lines(self) -> bool | None:
        return self.showGridLines

    @show_grid_lines.setter
    def show_grid_lines(self, value: bool | None) -> None:
        self.showGridLines = None if value is None else bool(value)

    @property
    def show_row_col_headers(self) -> bool | None:
        return self.showRowColHeaders

    @show_row_col_headers.setter
    def show_row_col_headers(self, value: bool | None) -> None:
        self.showRowColHeaders = None if value is None else bool(value)

    @property
    def show_outline_symbols(self) -> bool | None:
        return self.showOutlineSymbols

    @show_outline_symbols.setter
    def show_outline_symbols(self, value: bool | None) -> None:
        self.showOutlineSymbols = None if value is None else bool(value)

    @property
    def show_zeros(self) -> bool | None:
        return self.showZeros

    @show_zeros.setter
    def show_zeros(self, value: bool | None) -> None:
        self.showZeros = None if value is None else bool(value)

    @property
    def right_to_left(self) -> bool | None:
        return self.rightToLeft

    @right_to_left.setter
    def right_to_left(self, value: bool | None) -> None:
        self.rightToLeft = None if value is None else bool(value)

    @property
    def tab_selected(self) -> bool | None:
        return self.tabSelected

    @tab_selected.setter
    def tab_selected(self, value: bool | None) -> None:
        self.tabSelected = None if value is None else bool(value)

    @property
    def top_left_cell(self) -> str | None:
        return self.topLeftCell

    @top_left_cell.setter
    def top_left_cell(self, value: str | None) -> None:
        self.topLeftCell = value

    def __post_init__(self) -> None:
        if self.view is not None and self.view not in _VALID_VIEWS:
            raise ValueError(
                f"view must be one of {_VALID_VIEWS}, got {self.view!r}"
            )
        if self.zoomScale is not None and not (10 <= int(self.zoomScale) <= 400):
            raise ValueError(f"zoomScale must be between 10 and 400, got {self.zoomScale}")

    def to_rust_dict(self) -> dict[str, Any]:
        return {
            "zoom_scale": int(self.zoomScale) if self.zoomScale is not None else 100,
            "zoom_scale_normal": (
                int(self.zoomScaleNormal) if self.zoomScaleNormal is not None else 100
            ),
            "view": self.view,
            "show_grid_lines": self.showGridLines,
            "show_row_col_headers": self.showRowColHeaders,
            "show_outline_symbols": self.showOutlineSymbols,
            "show_zeros": self.showZeros,
            "right_to_left": self.rightToLeft,
            "tab_selected": self.tabSelected,
            "top_left_cell": self.topLeftCell,
            "pane": self.pane.to_rust_dict() if self.pane is not None else None,
            "selection": [s.to_rust_dict() for s in self.selection],
        }

    def __iter__(self):
        for name in self._ATTRS:
            if not hasattr(self, name):
                continue
            value = getattr(self, name)
            if value is None:
                continue
            if name in {"zoomScale", "zoomScaleNormal"} and int(value) == 100:
                continue
            if name == "view" and value == "normal":
                continue
            if isinstance(value, bool):
                value = "1" if value else "0"
            else:
                value = str(value)
            yield name, value

    def to_tree(self, tagname: str | None = None) -> Any:
        node = Element(tagname or "sheetView", dict(self))
        if self.pane is not None:
            node.append(self.pane.to_tree())
        for selection in self.selection:
            node.append(selection.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "SheetView":
        attrs: dict[str, Any] = dict(node.attrib)
        for key in (
            "windowProtection",
            "showFormulas",
            "showGridLines",
            "showRowColHeaders",
            "showZeros",
            "rightToLeft",
            "tabSelected",
            "showRuler",
            "showOutlineSymbols",
            "defaultGridColor",
            "showWhiteSpace",
            "zoomToFit",
        ):
            if key in attrs:
                attrs[key] = _xml_bool(attrs[key])
        for key in (
            "colorId",
            "zoomScale",
            "zoomScaleNormal",
            "zoomScaleSheetLayoutView",
            "zoomScalePageLayoutView",
            "workbookViewId",
        ):
            if key in attrs:
                attrs[key] = int(attrs[key])
        pane = None
        selections = []
        for child in node:
            local = getattr(child, "tag", "").rsplit("}", 1)[-1]
            if local == "pane":
                pane = Pane.from_tree(child)
            elif local == "selection":
                selections.append(Selection.from_tree(child))
        attrs["pane"] = pane
        if selections:
            attrs["selection"] = selections
        return cls(**attrs)

    def is_default(self) -> bool:
        default_selection = (
            len(self.selection) == 1
            and self.selection[0].activeCell == "A1"
            and self.selection[0].sqref == "A1"
            and self.selection[0].pane is None
            and self.selection[0].activeCellId is None
        )
        return (
            self.zoomScale == 100
            and self.zoomScaleNormal == 100
            and self.view == "normal"
            and self.showGridLines is None
            and self.showRowColHeaders is None
            and self.showOutlineSymbols is None
            and self.showZeros is None
            and self.rightToLeft is None
            and self.tabSelected is None
            and self.topLeftCell is None
            and self.pane is None
            and default_selection
        )


class SheetViewList:
    """Container for a worksheet's sheet views.

    openpyxl exposes this as ``ws.sheet_view`` (singular property
    returning the first / only view) plus
    ``ws.views.sheetView`` (a list). Wolfxl mirrors both: the
    ``views`` accessor returns a SheetViewList, while ``sheet_view``
    returns the first SheetView (creating one if absent).
    """

    __slots__ = ("sheetView", "extLst")

    def __init__(
        self,
        views: list[SheetView] | None = None,
        sheetView: list[SheetView] | SheetView | None = None,  # noqa: N803
        extLst: Any = None,  # noqa: N803
    ) -> None:
        # openpyxl naming: list attribute is ``sheetView`` (singular).
        if sheetView is not None:
            views = [sheetView] if isinstance(sheetView, SheetView) else list(sheetView)
        self.sheetView = list(views or [SheetView()])  # noqa: N815
        self.extLst = extLst

    def __iter__(self):
        return iter(self.sheetView)

    def __len__(self) -> int:
        return len(self.sheetView)

    def __getitem__(self, idx: int) -> SheetView:
        return self.sheetView[idx]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SheetViewList):
            return NotImplemented
        return self.sheetView == other.sheetView and self.extLst == other.extLst

    @property
    def active(self) -> SheetView:
        if not self.sheetView:
            self.sheetView.append(SheetView())
        return self.sheetView[0]

    @active.setter
    def active(self, value: SheetView) -> None:
        if not self.sheetView:
            self.sheetView.append(value)
        else:
            self.sheetView[0] = value

    def to_tree(self, tagname: str | None = None) -> Any:
        node = Element(tagname or "sheetViews")
        for view in self.sheetView:
            node.append(view.to_tree())
        return node

    @classmethod
    def from_tree(cls, node: Any) -> "SheetViewList":
        views = []
        for child in node:
            local = getattr(child, "tag", "").rsplit("}", 1)[-1]
            if local == "sheetView":
                views.append(SheetView.from_tree(child))
        return cls(sheetView=views or None)


def _xml_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "on"}


_install_openpyxl_iter(Pane, Selection)

__all__ = [
    "Pane",
    "Selection",
    "SheetView",
    "SheetViewList",
]

__getattr__ = _openpyxl_name_fallback(globals())
