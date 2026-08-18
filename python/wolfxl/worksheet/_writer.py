"""Worksheet writer compatibility exports."""

from __future__ import annotations

import atexit
import os
from collections import defaultdict
from io import BytesIO
from tempfile import NamedTemporaryFile
from warnings import warn

from wolfxl.cell._writer import write_cell
from wolfxl.comments.comment_sheet import CommentRecord
from wolfxl.formatting.rule import DifferentialStyle
from wolfxl.packaging.relationship import Relationship, RelationshipList
from wolfxl.worksheet.hyperlink import HyperlinkList
from wolfxl.worksheet.merge import MergeCell, MergeCells
from wolfxl.worksheet.related import Related
from wolfxl.worksheet.table import TablePartList
from wolfxl.worksheet.dimensions import SheetDimension
from wolfxl.xml.constants import SHEET_MAIN_NS
from wolfxl.xml.functions import Element, xmlfile

ALL_TEMP_FILES: list[str] = []


def _safe_string(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _append_attrs(node, attrs):
    for key, value in attrs:
        if value is None:
            continue
        node.set(key, _safe_string(value))
    return node


def _simple_tree(tagname, obj=None, attrs=None):
    node = Element(tagname)
    if attrs is None and obj is not None:
        attrs = dict(obj).items()
    _append_attrs(node, attrs or ())
    return node


def _is_default(obj) -> bool:
    checker = getattr(obj, "is_default", None)
    if callable(checker):
        return bool(checker())
    return False


def _worksheet_properties_tree(props):
    node = _simple_tree(
        "sheetPr",
        attrs=(
            (name, getattr(props, name))
            for name in (
                "codeName",
                "enableFormatConditionsCalculation",
                "filterMode",
                "published",
                "syncHorizontal",
                "syncRef",
                "syncVertical",
                "transitionEvaluation",
                "transitionEntry",
            )
        ),
    )
    tab_color = getattr(props, "tabColor", None)
    if tab_color is not None and hasattr(tab_color, "to_tree"):
        node.append(tab_color.to_tree("tabColor"))
    outline = getattr(props, "outlinePr", None)
    if outline is not None:
        node.append(_simple_tree("outlinePr", outline))
    page_setup = getattr(props, "pageSetUpPr", None)
    if page_setup is not None:
        node.append(_simple_tree("pageSetUpPr", page_setup))
    return node


def _sheet_format_tree(fmt):
    return _simple_tree(
        "sheetFormatPr",
        attrs=(
            ("baseColWidth", getattr(fmt, "baseColWidth", None)),
            ("defaultColWidth", getattr(fmt, "defaultColWidth", None)),
            ("defaultRowHeight", getattr(fmt, "defaultRowHeight", None)),
            ("customHeight", getattr(fmt, "customHeight", None)),
            ("zeroHeight", getattr(fmt, "zeroHeight", None)),
            ("thickTop", getattr(fmt, "thickTop", None)),
            ("thickBottom", getattr(fmt, "thickBottom", None)),
            (
                "outlineLevelRow",
                getattr(fmt, "outlineLevelRow", None) or None,
            ),
            (
                "outlineLevelCol",
                getattr(fmt, "outlineLevelCol", None) or None,
            ),
        ),
    )


def _merge_cells_tree(merged):
    node = Element("mergeCells")
    cells = list(merged)
    node.set("count", str(len(cells)))
    for cell in cells:
        child = cell.to_tree() if hasattr(cell, "to_tree") else _simple_tree("mergeCell")
        if "ref" not in child.attrib:
            child.set("ref", str(cell))
        node.append(child)
    return node


def _conditional_formatting_tree(cf):
    node = _simple_tree(
        "conditionalFormatting",
        attrs=(("sqref", getattr(cf, "sqref", None)), ("pivot", getattr(cf, "pivot", None))),
    )
    for rule in getattr(cf, "rules", []):
        node.append(rule.to_tree())
    return node


def _scenarios_tree(scenarios):
    node = Element("scenarios")
    for scenario in scenarios:
        node.append(scenario.to_tree())
    return node


def _hyperlinks_tree(links):
    node = Element("hyperlinks")
    for link in links:
        child = _simple_tree(
            "hyperlink",
            attrs=(
                ("ref", getattr(link, "ref", None)),
                (
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",
                    getattr(link, "id", None),
                ),
                ("location", getattr(link, "location", None)),
                ("tooltip", getattr(link, "tooltip", None)),
                ("display", getattr(link, "display", None)),
            ),
        )
        node.append(child)
    return node


def _breaks_tree(breaks, tagname):
    node = _simple_tree(
        tagname,
        attrs=(
            ("count", getattr(breaks, "count", None)),
            ("manualBreakCount", getattr(breaks, "manualBreakCount", None)),
        ),
    )
    items = getattr(breaks, "breaks", None)
    if items is None:
        items = getattr(breaks, "brk", [])
    for brk in items:
        child = _simple_tree(
            "brk",
            attrs=(
                ("id", getattr(brk, "id", None)),
                ("min", getattr(brk, "min", None)),
                ("max", getattr(brk, "max", None)),
                ("man", getattr(brk, "man", None)),
                ("pt", getattr(brk, "pt", None)),
            ),
        )
        node.append(child)
    return node


@atexit.register
def _openpyxl_shutdown() -> None:
    for path in ALL_TEMP_FILES:
        if os.path.exists(path):
            os.remove(path)


def create_temporary_file(suffix: str = "") -> str:
    handle = NamedTemporaryFile(mode="w+", prefix="openpyxl.", delete=False, suffix=suffix)
    handle.close()
    ALL_TEMP_FILES.append(handle.name)
    return handle.name


class WorksheetWriter:
    """openpyxl-shaped streaming worksheet XML writer."""

    def __init__(self, ws, out=None):
        self.ws = ws
        self.ws._hyperlinks = []
        self.ws._comments = []
        if out is None:
            out = create_temporary_file()
        self.out = out
        self._rels = RelationshipList()
        self.xf = self.get_stream()
        next(self.xf)

    def write_properties(self):
        props = self.ws.sheet_properties
        tree = props.to_tree() if hasattr(props, "to_tree") else _worksheet_properties_tree(props)
        self.xf.send(tree)

    def write_dimensions(self):
        """Write worksheet size if known."""
        ref = getattr(self.ws, "calculate_dimension", None)
        if ref:
            dim = SheetDimension(ref())
            tree = dim.to_tree() if hasattr(dim, "to_tree") else _simple_tree("dimension", dim)
            self.xf.send(tree)

    def write_format(self):
        self.ws.sheet_format.outlineLevelCol = self.ws.column_dimensions.max_outline
        fmt = self.ws.sheet_format
        tree = fmt.to_tree() if hasattr(fmt, "to_tree") else _sheet_format_tree(fmt)
        self.xf.send(tree)

    def write_views(self):
        views = self.ws.views
        self.xf.send(views.to_tree())

    def write_cols(self):
        cols = self.ws.column_dimensions
        self.xf.send(cols.to_tree())

    def write_top(self):
        """Write all elements up to rows."""
        self.write_properties()
        self.write_dimensions()
        self.write_views()
        self.write_format()
        self.write_cols()

    def rows(self):
        """Return all rows, and any cells that they contain."""
        rows = defaultdict(list)
        for (row, _col), cell in sorted(self.ws._cells.items()):
            rows[row].append(cell)

        for row in self.ws.row_dimensions.keys() - rows.keys():
            rows[row] = []

        return sorted(rows.items())

    def write_rows(self):
        xf = self.xf.send(True)

        with xf.element("sheetData"):
            for row_idx, row in self.rows():
                self.write_row(xf, row, row_idx)

        self.xf.send(None)

    def write_row(self, xf, row, row_idx):
        attrs = {"r": f"{row_idx}"}
        dims = self.ws.row_dimensions
        attrs.update(dims.get(row_idx, {}))

        with xf.element("row", attrs):
            for cell in row:
                comment = getattr(cell, "_comment", None)
                if comment is not None:
                    comment = CommentRecord.from_cell(cell)
                    self.ws._comments.append(comment)
                if cell._value is None and not cell.has_style and comment is None:
                    continue
                write_cell(xf, self.ws, cell, cell.has_style)

    def write_protection(self):
        prot = self.ws.protection
        if prot and not _is_default(prot):
            tree = prot.to_tree() if hasattr(prot, "to_tree") else _simple_tree("sheetProtection", prot)
            self.xf.send(tree)

    def write_scenarios(self):
        scenarios = self.ws.scenarios
        if scenarios:
            tree = (
                scenarios.to_tree()
                if hasattr(scenarios, "to_tree")
                else _scenarios_tree(scenarios)
            )
            self.xf.send(tree)

    def write_filter(self):
        flt = self.ws.auto_filter
        if flt and getattr(flt, "ref", None):
            self.xf.send(flt.to_tree())

    def write_sort(self):
        """Global sort state is intentionally not written by openpyxl."""

    def write_merged_cells(self):
        merged = self.ws.merged_cells
        if merged:
            cells = [MergeCell(str(ref)) for ref in self.ws.merged_cells]
            container = MergeCells(mergeCell=cells)
            tree = (
                container.to_tree()
                if hasattr(container, "to_tree")
                else _merge_cells_tree(container)
            )
            self.xf.send(tree)

    def write_formatting(self):
        df = DifferentialStyle()
        wb = self.ws.parent
        for cf in self.ws.conditional_formatting:
            for rule in cf.rules:
                if rule.dxf and rule.dxf != df:
                    rule.dxfId = wb._differential_styles.add(rule.dxf)
            tree = cf.to_tree() if hasattr(cf, "to_tree") else _conditional_formatting_tree(cf)
            self.xf.send(tree)

    def write_validations(self):
        dv = self.ws.data_validations
        if dv:
            self.xf.send(dv.to_tree())

    def write_hyperlinks(self):
        links = self.ws._hyperlinks

        for link in links:
            if link.target:
                rel = Relationship(
                    type="hyperlink", TargetMode="External", Target=link.target
                )
                self._rels.append(rel)
                link.id = rel.id

        if links:
            link_list = HyperlinkList(links)
            tree = link_list.to_tree() if hasattr(link_list, "to_tree") else _hyperlinks_tree(link_list)
            self.xf.send(tree)

    def write_print(self):
        print_options = self.ws.print_options
        if print_options and not _is_default(print_options):
            tree = (
                print_options.to_tree()
                if hasattr(print_options, "to_tree")
                else _simple_tree("printOptions", print_options)
            )
            self.xf.send(tree)

    def write_margins(self):
        margins = self.ws.page_margins
        if margins:
            tree = (
                margins.to_tree()
                if hasattr(margins, "to_tree")
                else _simple_tree("pageMargins", margins)
            )
            self.xf.send(tree)

    def write_page(self):
        setup = self.ws.page_setup
        if setup and not _is_default(setup):
            tree = (
                setup.to_tree()
                if hasattr(setup, "to_tree")
                else _simple_tree("pageSetup", setup)
            )
            self.xf.send(tree)

    def write_header(self):
        hf = self.ws.HeaderFooter
        if hf:
            self.xf.send(hf.to_tree())

    def write_breaks(self):
        for tagname, brk in (("rowBreaks", self.ws.row_breaks), ("colBreaks", self.ws.col_breaks)):
            if brk:
                tree = brk.to_tree() if hasattr(brk, "to_tree") else _breaks_tree(brk, tagname)
                self.xf.send(tree)

    def write_drawings(self):
        if self.ws._charts or self.ws._images:
            rel = Relationship(type="drawing", Target="")
            self._rels.append(rel)
            drawing = Related()
            drawing.id = rel.id
            self.xf.send(drawing.to_tree("drawing"))

    def write_legacy(self):
        """Comments and VBA controls use a legacy VML relationship element."""
        if self.ws.legacy_drawing is not None or self.ws._comments:
            legacy = Related(id="anysvml")
            self.xf.send(legacy.to_tree("legacyDrawing"))

    def write_tables(self):
        tables = TablePartList()

        for table in self.ws.tables.values():
            if not table.tableColumns:
                table._initialise_columns()
                if table.headerRowCount:
                    try:
                        row = self.ws[table.ref][0]
                        for cell, col in zip(row, table.tableColumns):
                            if cell.data_type != "s":
                                warn(
                                    "File may not be readable: column headings "
                                    "must be strings."
                                )
                            col.name = str(cell.value)
                    except TypeError:
                        warn("Column headings are missing, file may not be readable")
            rel = Relationship(Type=table._rel_type, Target="")
            self._rels.append(rel)
            table._rel_id = rel.Id
            tables.append(Related(id=rel.Id))

        if tables:
            self.xf.send(tables.to_tree())

    def get_stream(self):
        with xmlfile(self.out) as xf:
            with xf.element("worksheet", xmlns=SHEET_MAIN_NS):
                try:
                    while True:
                        el = yield
                        if el is True:
                            yield xf
                        elif el is None:
                            continue
                        else:
                            xf.write(el)
                except GeneratorExit:
                    pass

    def write_tail(self):
        """Write all elements after the rows."""
        self.write_protection()
        self.write_scenarios()
        self.write_filter()
        self.write_merged_cells()
        self.write_formatting()
        self.write_validations()
        self.write_hyperlinks()
        self.write_print()
        self.write_margins()
        self.write_page()
        self.write_header()
        self.write_breaks()
        self.write_drawings()
        self.write_legacy()
        self.write_tables()

    def write(self):
        """High-level worksheet write."""
        self.write_top()
        self.write_rows()
        self.write_tail()
        self.close()

    def close(self):
        """Close the XML stream."""
        if self.xf:
            self.xf.close()

    def read(self):
        """Close the stream and return serialized XML bytes."""
        self.close()
        if isinstance(self.out, BytesIO):
            return self.out.getvalue()
        with open(self.out, "rb") as src:
            return src.read()

    def cleanup(self):
        """Remove the temporary worksheet XML file."""
        os.remove(self.out)
        ALL_TEMP_FILES.remove(self.out)

__all__ = [name for name in list(globals()) if not name.startswith("_")]
