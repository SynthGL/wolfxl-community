"""Anchor primitives for ``Image`` placement — Sprint Λ Pod-β (RFC-045).

Mirrors the minimum slice of ``openpyxl.drawing.spreadsheet_drawing`` and
``openpyxl.drawing.xdr`` needed by ``Worksheet.add_image``: the three
anchor flavours plus the two coordinate value objects.

These are passive containers — they do not allocate part ids and do not
touch the writer / patcher. ``Worksheet.add_image`` reads their fields
when it queues the image.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wolfxl._compat import (
    _REAL_OPENPYXL,
    _install_openpyxl_iter,
    _openpyxl_name_fallback,
    _resolve_openpyxl_class,
)
from wolfxl.packaging.relationship import RelationshipList

# ---------------------------------------------------------------------------
# XDR coordinate primitives
# ---------------------------------------------------------------------------

@dataclass
class XDRPoint2D:
    """An (x, y) point in EMU (English Metric Units; 914400 EMU = 1 inch)."""

    x: int = 0
    y: int = 0


@dataclass
class XDRPositiveSize2D:
    """A positive (cx, cy) size in EMU."""

    cx: int = 0
    cy: int = 0


@dataclass
class AnchorMarker:
    """One corner of a cell-relative anchor.

    All four fields are 0-based: ``col=1, row=4`` means column B, row 5
    in 1-based Excel terms (matching openpyxl).
    """

    col: int = 0
    row: int = 0
    colOff: int = 0  # noqa: N815 — openpyxl name
    rowOff: int = 0  # noqa: N815 — openpyxl name


# ---------------------------------------------------------------------------
# Anchor types
# ---------------------------------------------------------------------------

@dataclass
class OneCellAnchor:
    """Pin the image's top-left to one cell; size set by image dims.

    ``ext`` (extent in EMU) is optional — when ``None``, the writer
    computes one from the image's pixel dimensions.
    """

    _from: AnchorMarker = None  # type: ignore[assignment]
    ext: XDRPositiveSize2D | None = None

    def __post_init__(self) -> None:
        if self._from is None:
            self._from = AnchorMarker()


@dataclass
class TwoCellAnchor:
    """Anchor the image at top-left AND bottom-right cells; image stretches."""

    _from: AnchorMarker = None  # type: ignore[assignment]
    to: AnchorMarker = None  # type: ignore[assignment]
    editAs: str = "oneCell"  # noqa: N815 — openpyxl uses "oneCell"/"twoCell"/"absolute"

    def __post_init__(self) -> None:
        if self._from is None:
            self._from = AnchorMarker()
        if self.to is None:
            self.to = AnchorMarker()


@dataclass
class AbsoluteAnchor:
    """EMU-coordinate anchor; image position is independent of cells."""

    pos: XDRPoint2D = None  # type: ignore[assignment]
    ext: XDRPositiveSize2D = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.pos is None:
            self.pos = XDRPoint2D()
        if self.ext is None:
            self.ext = XDRPositiveSize2D()


@dataclass
class SpreadsheetDrawing:
    """Passive drawing container matching openpyxl's constructor shape."""

    _path: str = "/xl/drawings/drawing{0}.xml"
    twoCellAnchor: list[Any] = field(default_factory=list)  # noqa: N815
    oneCellAnchor: list[Any] = field(default_factory=list)  # noqa: N815
    absoluteAnchor: list[Any] = field(default_factory=list)  # noqa: N815
    charts: list[Any] = field(default_factory=list)
    images: list[Any] = field(default_factory=list)
    _rels: list[Any] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self._path.format(getattr(self, "_id", None))

    @property
    def width(self) -> int:
        return 21

    @property
    def height(self) -> int:
        return 192

    @property
    def anchor(self) -> AbsoluteAnchor:
        return AbsoluteAnchor(ext=XDRPositiveSize2D(cx=200025, cy=1828800))


_install_openpyxl_iter(
    XDRPoint2D,
    XDRPositiveSize2D,
    AnchorMarker,
    OneCellAnchor,
    TwoCellAnchor,
    AbsoluteAnchor,
    SpreadsheetDrawing,
)


def _openpyxl_class(name: str, fallback: type) -> type:
    return _resolve_openpyxl_class(__name__, name) or fallback


XDRPoint2D = _openpyxl_class("XDRPoint2D", XDRPoint2D)
XDRPositiveSize2D = _openpyxl_class("XDRPositiveSize2D", XDRPositiveSize2D)
AnchorMarker = _openpyxl_class("AnchorMarker", AnchorMarker)
OneCellAnchor = _openpyxl_class("OneCellAnchor", OneCellAnchor)
TwoCellAnchor = _openpyxl_class("TwoCellAnchor", TwoCellAnchor)
AbsoluteAnchor = _openpyxl_class("AbsoluteAnchor", AbsoluteAnchor)
SpreadsheetDrawing = _openpyxl_class("SpreadsheetDrawing", SpreadsheetDrawing)

_upstream_spreadsheet_drawing = None
if _REAL_OPENPYXL is not None:
    _drawing = getattr(_REAL_OPENPYXL, "drawing", None)
    _upstream_spreadsheet_drawing = getattr(_drawing, "spreadsheet_drawing", None)
_AnchorBase = getattr(_upstream_spreadsheet_drawing, "_AnchorBase", ())

from wolfxl.chart._chart import ChartBase as _WolfxlChartBase
from wolfxl.drawing.image import Image as _WolfxlImage
from wolfxl.packaging.relationship import Relationship
from wolfxl.utils.cell import coordinate_to_tuple
from wolfxl.utils.units import cm_to_EMU, pixels_to_EMU


def _check_anchor(obj: Any) -> Any:
    anchor = getattr(obj, "anchor", None) or "A1"
    if isinstance(anchor, _AnchorBase):
        return anchor

    row, col = coordinate_to_tuple(str(anchor).upper())
    anchor = OneCellAnchor()
    anchor._from.row = row - 1
    anchor._from.col = col - 1
    if getattr(anchor, "ext", None) is None:
        anchor.ext = XDRPositiveSize2D()
    if isinstance(obj, _WolfxlChartBase):
        anchor.ext.width = cm_to_EMU(getattr(obj, "width", 15))
        anchor.ext.height = cm_to_EMU(getattr(obj, "height", 7.5))
    elif isinstance(obj, _WolfxlImage):
        anchor.ext.width = pixels_to_EMU(getattr(obj, "width", 0))
        anchor.ext.height = pixels_to_EMU(getattr(obj, "height", 0))
    return anchor


if _upstream_spreadsheet_drawing is not None:

    class _CompatSpreadsheetDrawing(SpreadsheetDrawing):
        __module__ = __name__
        tagname = getattr(SpreadsheetDrawing, "tagname", "wsDr")
        __attrs__ = getattr(SpreadsheetDrawing, "__attrs__", ())
        __elements__ = getattr(SpreadsheetDrawing, "__elements__", ())
        __nested__ = getattr(SpreadsheetDrawing, "__nested__", ())

        @property
        def width(self) -> int:
            return 21

        @property
        def height(self) -> int:
            return 192

        @property
        def anchor(self) -> AbsoluteAnchor:
            return AbsoluteAnchor(ext=XDRPositiveSize2D(cx=200025, cy=1828800))

        def _write(self) -> Any:
            anchors = []
            for idx, obj in enumerate(self.charts + self.images, 1):
                anchor = _check_anchor(obj)
                if isinstance(obj, _WolfxlChartBase):
                    rel = Relationship(type="chart", Target=obj.path)
                    anchor.graphicFrame = self._chart_frame(idx)
                elif isinstance(obj, _WolfxlImage):
                    rel = Relationship(type="image", Target=obj.path)
                    child = anchor.pic or anchor.groupShape and anchor.groupShape.pic
                    if not child:
                        anchor.pic = self._picture_frame(idx)
                    else:
                        child.blipFill.blip.embed = f"rId{idx}"
                else:
                    continue

                anchors.append(anchor)
                self._rels.append(rel)

            for anchor in anchors:
                if isinstance(anchor, OneCellAnchor):
                    self.oneCellAnchor.append(anchor)
                elif isinstance(anchor, TwoCellAnchor):
                    self.twoCellAnchor.append(anchor)
                else:
                    self.absoluteAnchor.append(anchor)

            tree = self.to_tree()
            tree.set(
                "xmlns",
                "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
            )
            return tree

        def _write_rels(self) -> Any:
            rels = RelationshipList()
            for rel in self._rels:
                rels.append(rel)
            return rels.to_tree()

    SpreadsheetDrawing = _CompatSpreadsheetDrawing

__all__ = [
    "AbsoluteAnchor",
    "AnchorMarker",
    "_check_anchor",
    "OneCellAnchor",
    "RelationshipList",
    "SpreadsheetDrawing",
    "TwoCellAnchor",
    "XDRPoint2D",
    "XDRPositiveSize2D",
]

__getattr__ = _openpyxl_name_fallback(globals())
