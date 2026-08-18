"""``openpyxl.writer.excel`` compatibility."""

from __future__ import annotations

import datetime
import re
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from wolfxl._compat import _openpyxl_name_fallback
from wolfxl.comments.comment_sheet import CommentRecord, CommentSheet
from wolfxl.comments.shape_writer import ShapeWriter
from wolfxl.drawing.spreadsheet_drawing import SpreadsheetDrawing
from wolfxl._workbook_save import save_workbook as _save_workbook
from wolfxl.packaging.manifest import Manifest
from wolfxl.packaging.relationship import Relationship, RelationshipList, get_rels_path
from wolfxl.styles.stylesheet import write_stylesheet
from wolfxl.writer.theme import theme_xml
from wolfxl.utils.exceptions import InvalidFileException
from wolfxl.workbook._writer import WorkbookWriter
from wolfxl.worksheet._writer import WorksheetWriter
from wolfxl.xml.functions import fromstring, tostring
from wolfxl.xml.constants import (
    ARC_APP,
    ARC_CORE,
    ARC_CUSTOM,
    ARC_ROOT_RELS,
    ARC_STYLE,
    ARC_THEME,
    ARC_WORKBOOK,
    ARC_WORKBOOK_RELS,
    CPROPS_TYPE,
)


class ExcelWriter:
    """Openpyxl-shaped package writer used by compatibility tests.

    WolfXL normally saves through its Rust-backed workbook pipeline. The
    vendored openpyxl tests also reach into ``openpyxl.writer.excel`` and call
    private methods directly, so this class mirrors those package-writing
    helpers closely enough for that surface.
    """

    def __init__(self, workbook: Any, archive: Any) -> None:
        """Create a writer around an already-open zip archive."""
        self._archive = archive
        self.workbook = workbook
        self.archive = archive
        self.manifest = Manifest()
        self.vba_modified = set()
        self._tables = []
        self._charts = []
        self._images = []
        self._drawings = []
        self._comments = []
        self._pivots = []

    def save(self) -> None:
        """Write workbook data and close the archive, matching openpyxl."""
        if self.workbook is None:
            self._archive.close()
            return
        target = getattr(self.archive, "filename", self.archive)
        if target is self.archive:
            self.write_data()
            self._archive.close()
        else:
            _save_workbook(self.workbook, target)

    def write_data(self) -> None:
        """Write the workbook package parts managed by this facade."""
        self._write_worksheets()
        self._write_chartsheets()
        self._write_images()
        self._write_charts()
        self._merge_vba()
        self.manifest._write(self._archive, self.workbook)

    def _merge_vba(self) -> None:
        """Copy macro-related parts from the source workbook archive."""
        arc_vba = re.compile(
            "|".join(
                (
                    "xl/vba",
                    r"xl/drawings/.*vmlDrawing\d\.vml",
                    "xl/ctrlProps",
                    "customUI",
                    "xl/activeX",
                    r"xl/media/.*\.emf",
                )
            )
        )
        vba_archive = getattr(self.workbook, "vba_archive", None)
        if not vba_archive:
            return
        for name in set(vba_archive.namelist()) - self.vba_modified:
            if arc_vba.match(name):
                self._archive.writestr(name, vba_archive.read(name))

    def _write_images(self) -> None:
        """Write media image payloads collected while writing drawings."""
        for idx, img in enumerate(self._images, 1):
            img._id = idx
            self._archive.writestr(_image_archive_path(img, idx), img._data())

    def _write_charts(self) -> None:
        """Write chart XML parts and reject reused chart objects."""
        if len(self._charts) != len(set(self._charts)):
            raise InvalidFileException(
                "The same chart cannot be used in more than one worksheet"
            )
        for idx, chart in enumerate(self._charts, 1):
            chart._id = idx
            self._archive.writestr(chart.path[1:], tostring(chart._write()))
            self.manifest.append(chart)

    def _write_drawing(self, drawing: Any) -> None:
        """Write one drawing plus its relationship file."""
        self._drawings.append(drawing)
        drawing._id = len(self._drawings)
        for chart in getattr(drawing, "charts", []):
            self._charts.append(chart)
            chart._id = len(self._charts)
        for img in getattr(drawing, "images", []):
            self._images.append(img)
            img._id = len(self._images)
        self._archive.writestr(drawing.path[1:], tostring(drawing._write()))
        self._archive.writestr(
            get_rels_path(drawing.path)[1:],
            tostring(drawing._write_rels()),
        )
        self.manifest.append(drawing)

    def _write_chartsheets(self) -> None:
        """Write all chartsheet XML parts in workbook order."""
        for idx, sheet in enumerate(getattr(self.workbook, "chartsheets", []), 1):
            sheet._id = idx
            self._archive.writestr(sheet.path[1:], tostring(sheet.to_tree()))
            self.manifest.append(sheet)
            drawing = getattr(sheet, "_drawing", None)
            if drawing:
                self._write_drawing(drawing)
                rels = RelationshipList()
                rels.append(Relationship(type="drawing", Target=drawing.path))
                self._archive.writestr(
                    get_rels_path(sheet.path[1:]),
                    tostring(rels.to_tree()),
                )

    def _write_comment(self, ws: Any) -> None:
        """Write worksheet comments and their legacy VML drawing part."""
        comments = _collect_comments(ws)
        cs = CommentSheet.from_comments(comments)
        self._comments.append(cs)
        cs._id = len(self._comments)
        self._archive.writestr(cs.path[1:], tostring(cs.to_tree()))
        self.manifest.append(cs)

        vml = None
        vba_archive = getattr(self.workbook, "vba_archive", None)
        if getattr(ws, "legacy_drawing", None) is None or vba_archive is None:
            ws.legacy_drawing = f"xl/drawings/commentsDrawing{cs._id}.vml"
        else:
            vml = fromstring(vba_archive.read(ws.legacy_drawing))
        vml = ShapeWriter(cs.comments).write(vml)
        self._archive.writestr(ws.legacy_drawing, vml)
        self.vba_modified.add(ws.legacy_drawing)

        ws._rels.append(Relationship(Id="comments", type=cs._rel_type, Target=cs.path))

    def write_worksheet(self, ws: Any) -> SpreadsheetDrawing | None:
        """Write a worksheet XML part and return its drawing, if any."""
        drawing = SpreadsheetDrawing()
        drawing.charts = ws._charts
        drawing.images = ws._images
        if getattr(self.workbook, "write_only", False):
            if not ws.closed:
                ws.close()
            writer = ws._writer
        else:
            writer = WorksheetWriter(ws)
            writer.write()

        ws._rels = writer._rels
        self._archive.write(writer.out, ws.path[1:])
        self.manifest.append(ws)
        writer.cleanup()
        return drawing if drawing.charts or drawing.images else None

    def _write_worksheets(self) -> None:
        """Write worksheet XML parts and their dependent package parts."""
        for ws in self.workbook.worksheets:
            drawing = self.write_worksheet(ws)

            self._write_worksheet_drawing(ws, drawing)
            self._write_worksheet_comments(ws)
            self._write_worksheet_tables(ws)
            self._write_worksheet_rels(ws)

    def _write_worksheet_drawing(
        self,
        ws: Any,
        drawing: SpreadsheetDrawing | None,
    ) -> None:
        """Write a worksheet drawing and point the worksheet rel at it."""
        if not drawing:
            return
        self._write_drawing(drawing)
        for rel in ws._rels:
            if "drawing" in rel.Type:
                rel.Target = drawing.path

    def _write_worksheet_comments(self, ws: Any) -> None:
        """Write comments and attach the legacy VML relationship."""
        if ws._comments:
            self._write_comment(ws)

        if ws.legacy_drawing is not None:
            ws._rels.append(
                Relationship(
                    type="vmlDrawing",
                    Id="anysvml",
                    Target="/" + ws.legacy_drawing,
                )
            )

    def _write_worksheet_tables(self, ws: Any) -> None:
        """Write table XML parts and update worksheet table relationships."""
        for table in ws._tables.values():
            self._tables.append(table)
            table.id = len(self._tables)
            table._write(self._archive)
            self.manifest.append(table)
            ws._rels.get(table._rel_id).Target = table.path

    def _write_worksheet_rels(self, ws: Any) -> None:
        """Write the worksheet relationship file when rels were created."""
        if ws._rels:
            self._archive.writestr(
                get_rels_path(ws.path)[1:],
                tostring(ws._rels.to_tree()),
            )


def _collect_comments(ws: Any) -> list[Any]:
    """Collect cell comments in the shape ``CommentSheet`` expects."""
    comments = []
    for cell in getattr(ws, "_cells", {}).values():
        if getattr(cell, "_comment", None) is not None:
            comments.append(CommentRecord.from_cell(cell))
    ws._comments = comments
    return comments


def _image_archive_path(img: Any, idx: int) -> str:
    """Return the OOXML package path for an image payload."""
    ext = getattr(img, "format", "png") or "png"
    return f"xl/media/image{idx}.{ext}"


def save_workbook(workbook: Any, filename: Any) -> None:
    """Save ``workbook`` while preserving openpyxl's modified timestamp behavior."""
    if getattr(workbook, "_rust_writer", None) is not None:
        workbook.properties.modified = datetime.datetime.now()
    _save_workbook(workbook, filename)


__all__ = [
    "ARC_APP",
    "ARC_CORE",
    "ARC_CUSTOM",
    "ARC_ROOT_RELS",
    "ARC_STYLE",
    "ARC_THEME",
    "ARC_WORKBOOK",
    "ARC_WORKBOOK_RELS",
    "CPROPS_TYPE",
    "CommentSheet",
    "ExcelWriter",
    "InvalidFileException",
    "Manifest",
    "Relationship",
    "RelationshipList",
    "SpreadsheetDrawing",
    "WorkbookWriter",
    "WorksheetWriter",
    "ZIP_DEFLATED",
    "ZipFile",
    "datetime",
    "fromstring",
    "get_rels_path",
    "re",
    "save_workbook",
    "theme_xml",
    "tostring",
    "write_stylesheet",
]

__getattr__ = _openpyxl_name_fallback(globals())
