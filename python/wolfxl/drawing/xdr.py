"""``openpyxl.drawing.xdr`` import shim."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wolfxl.drawing.spreadsheet_drawing import XDRPoint2D, XDRPositiveSize2D


@dataclass(init=False)
class XDRTransform2D:
    off: XDRPoint2D | None = None
    ext: XDRPositiveSize2D | None = None
    rot: int = 0
    flipH: bool = False  # noqa: N815
    flipV: bool = False  # noqa: N815
    chOff: XDRPoint2D | None = None  # noqa: N815
    chExt: XDRPositiveSize2D | None = None  # noqa: N815

    def __init__(
        self,
        off: XDRPoint2D | None = None,
        ext: XDRPositiveSize2D | None = None,
        rot: int = 0,
        flipH: bool = False,  # noqa: N803
        flipV: bool = False,  # noqa: N803
        chOff: XDRPoint2D | None = None,  # noqa: N803
        chExt: XDRPositiveSize2D | None = None,  # noqa: N803
        **kw: Any,
    ) -> None:
        self.off = off
        self.ext = ext
        self.rot = rot
        self.flipH = flipH
        self.flipV = flipV
        self.chOff = chOff
        self.chExt = chExt
        for key, value in kw.items():
            setattr(self, key, value)


Point2D = XDRPoint2D
PositiveSize2D = XDRPositiveSize2D
Transform2D = XDRTransform2D

__all__ = [
    "Point2D",
    "PositiveSize2D",
    "Transform2D",
    "XDRPoint2D",
    "XDRPositiveSize2D",
    "XDRTransform2D",
]
