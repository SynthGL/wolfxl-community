"""Worksheet reader compatibility exports."""

from __future__ import annotations

from copy import copy
from typing import Any
from warnings import warn

from wolfxl.cell.cell import Cell, MergedCell
from wolfxl.cell.rich_text import CellRichText, InlineFont, TextBlock
from wolfxl.cell._writer import ArrayFormula, DataTableFormula
from wolfxl._compat import _make_serialisable
from wolfxl.formatting import ConditionalFormatting
from wolfxl.formatting.rule import Rule
from wolfxl.formula.translate import Translator
from wolfxl.styles.colors import Color
from wolfxl.styles.styleable import StyleArray
from wolfxl.utils.datetime import WINDOWS_EPOCH, from_excel, from_ISO8601
from wolfxl.utils.cell import coordinate_to_tuple, get_column_letter, range_boundaries
from wolfxl.worksheet.datavalidation import DataValidationList
from wolfxl.worksheet.dimensions import ColumnDimension, RowDimension, SheetDimension, SheetFormatProperties
from wolfxl.worksheet.filters import AutoFilter
from wolfxl.worksheet.header_footer import HeaderFooter
from wolfxl.worksheet.hyperlink import Hyperlink, HyperlinkList
from wolfxl.worksheet.merge import MergeCell, MergeCells
from wolfxl.worksheet.page import PageMargins, PrintOptions, PrintPageSetup
from wolfxl.worksheet.pagebreak import Break, ColBreak, RowBreak
from wolfxl.worksheet.properties import Outline, PageSetupProperties, WorksheetProperties
from wolfxl.worksheet.protection import SheetProtection
from wolfxl.worksheet.related import Related
from wolfxl.worksheet.scenario import InputCells, Scenario, ScenarioList
from wolfxl.worksheet.table import TablePartList
from wolfxl.worksheet.views import Pane, Selection, SheetView, SheetViewList
from wolfxl.xml.constants import SHEET_MAIN_NS
from wolfxl.xml.functions import fromstring, iterparse

_TAG_NAMES = {
    "CELL_TAG": "c",
    "CF_TAG": "conditionalFormatting",
    "COL_BREAK_TAG": "colBreaks",
    "COL_TAG": "col",
    "CUSTOM_VIEWS_TAG": "customSheetViews",
    "DATA_TAG": "sheetData",
    "DIMENSION_TAG": "dimension",
    "EXT_TAG": "extLst",
    "FILTER_TAG": "autoFilter",
    "FORMAT_TAG": "sheetFormatPr",
    "FORMULA_TAG": "f",
    "HEADER_TAG": "headerFooter",
    "HYPERLINK_TAG": "hyperlinks",
    "LEGACY_TAG": "legacyDrawing",
    "MARGINS_TAG": "pageMargins",
    "MERGE_TAG": "mergeCells",
    "PAGE_TAG": "pageSetup",
    "PRINT_TAG": "printOptions",
    "PROPERTIES_TAG": "sheetPr",
    "PROT_TAG": "sheetProtection",
    "ROW_BREAK_TAG": "rowBreaks",
    "ROW_TAG": "row",
    "SCENARIOS_TAG": "scenarios",
    "TABLE_TAG": "tableParts",
    "VALIDATION_TAG": "dataValidations",
    "VALUE_TAG": "v",
    "VIEWS_TAG": "sheetViews",
}
globals().update(
    {name: f"{{{SHEET_MAIN_NS}}}{tag}" for name, tag in _TAG_NAMES.items()}
)
INLINE_STRING = f"{{{SHEET_MAIN_NS}}}is"

ExtensionList = _make_serialisable("ExtensionList")
Text = _make_serialisable("Text")
EXT_TYPES = {}


def _cast_number(value: str) -> int | float:
    """Convert an OOXML numeric cell value to openpyxl's int/float shape."""
    if "." in value or "E" in value or "e" in value:
        return float(value)
    return int(value)


class WorkSheetParser:
    """Small openpyxl-compatible worksheet XML parser surface."""

    def __init__(
        self,
        src,
        shared_strings,
        data_only: bool = False,
        epoch=WINDOWS_EPOCH,
        date_formats: set[int] | None = None,
        timedelta_formats: set[int] | None = None,
        rich_text: bool = False,
    ) -> None:
        self.min_row = self.min_col = None
        self.epoch = epoch
        self.source = src
        self.shared_strings = shared_strings
        self.data_only = data_only
        self.shared_formulae: dict[str, Any] = {}
        self.row_counter = self.col_counter = 0
        self.tables = TablePartList()
        self.date_formats = set(date_formats or ())
        self.timedelta_formats = set(timedelta_formats or ())
        self.row_dimensions: dict[str, dict[str, str]] = {}
        self.column_dimensions: dict[str, dict[str, str]] = {}
        self.number_formats: list[Any] = []
        self.keep_vba = False
        self.hyperlinks = HyperlinkList()
        self.formatting: list[Any] = []
        self.legacy_drawing = None
        self.merged_cells = None
        self.row_breaks = RowBreak()
        self.col_breaks = ColBreak()
        self.rich_text = rich_text

    def parse(self):
        dispatcher = {
            COL_TAG: self.parse_column_dimensions,
            PROT_TAG: self.parse_sheet_protection,
            EXT_TAG: self.parse_extensions,
            CF_TAG: self.parse_formatting,
            LEGACY_TAG: self.parse_legacy,
            ROW_BREAK_TAG: self.parse_row_breaks,
            COL_BREAK_TAG: self.parse_col_breaks,
            CUSTOM_VIEWS_TAG: self.parse_custom_views,
        }

        properties = {
            PRINT_TAG: ("print_options", PrintOptions),
            MARGINS_TAG: ("page_margins", PageMargins),
            PAGE_TAG: ("page_setup", PrintPageSetup),
            HEADER_TAG: ("HeaderFooter", HeaderFooter),
            FILTER_TAG: ("auto_filter", AutoFilter),
            VALIDATION_TAG: ("data_validations", DataValidationList),
            PROPERTIES_TAG: ("sheet_properties", WorksheetProperties),
            VIEWS_TAG: ("views", SheetViewList),
            FORMAT_TAG: ("sheet_format", SheetFormatProperties),
            SCENARIOS_TAG: ("scenarios", ScenarioList),
            TABLE_TAG: ("tables", TablePartList),
            HYPERLINK_TAG: ("hyperlinks", HyperlinkList),
            MERGE_TAG: ("merged_cells", MergeCells),
        }

        for _, element in iterparse(self.source):
            tag_name = element.tag
            if tag_name in dispatcher:
                dispatcher[tag_name](element)
                element.clear()
            elif tag_name in properties:
                prop_name, cls = properties[tag_name]
                setattr(self, prop_name, _from_tree(cls, element))
                element.clear()
            elif tag_name == ROW_TAG:
                row = self.parse_row(element)
                element.clear()
                yield row

    def parse_dimensions(self):
        """Return worksheet boundaries from the optional dimension element."""
        for _, element in iterparse(self.source):
            if element.tag == DIMENSION_TAG:
                ref = element.get("ref")
                return range_boundaries(ref) if ref is not None else None
            if element.tag == DATA_TAG:
                break
            element.clear()
        return None

    def parse_cell(self, element):
        data_type = element.get("t", "n")
        coordinate = element.get("r")
        style_id = element.get("s", 0)
        if style_id:
            style_id = int(style_id)

        if data_type == "inlineStr":
            value = None
        else:
            value = element.findtext(VALUE_TAG, None) or None

        if coordinate:
            row, column = coordinate_to_tuple(coordinate)
            self.col_counter = column
        else:
            self.col_counter += 1
            row, column = self.row_counter, self.col_counter

        if not self.data_only and element.find(FORMULA_TAG) is not None:
            data_type = "f"
            value = self.parse_formula(element)
        elif value is not None:
            if data_type == "n":
                value = _cast_number(value)
                if style_id in self.date_formats:
                    data_type = "d"
                    try:
                        value = from_excel(
                            value,
                            self.epoch,
                            timedelta=style_id in self.timedelta_formats,
                        )
                    except (OverflowError, ValueError):
                        msg = (
                            f"Cell {coordinate} is marked as a date but the serial "
                            f"value {value} is outside the limits for dates. The "
                            "cell will be treated as an error."
                        )
                        warn(msg)
                        data_type = "e"
                        value = "#VALUE!"
            elif data_type == "s":
                value = self.shared_strings[int(value)]
            elif data_type == "b":
                value = bool(int(value))
            elif data_type == "str":
                data_type = "s"
            elif data_type == "d":
                value = from_ISO8601(value)
        elif data_type == "inlineStr":
            child = element.find(INLINE_STRING)
            if child is not None:
                data_type = "s"
                if self.rich_text:
                    value = parse_richtext_string(child)
                else:
                    value = _plain_richtext_string(child)

        return {
            "row": row,
            "column": column,
            "value": value,
            "data_type": data_type,
            "style_id": style_id,
        }

    def parse_formula(self, element):
        """Return the openpyxl-shaped value for shared, array, or table formulae."""
        formula = element.find(FORMULA_TAG)
        formula_type = formula.get("t")
        coordinate = element.get("r")
        value = "="
        if formula.text is not None:
            value += formula.text

        if formula_type == "array":
            array_formula = ArrayFormula(ref=formula.get("ref"), text=value)
            array_formula.text = value
            value = array_formula
        elif formula_type == "shared":
            idx = formula.get("si")
            if idx in self.shared_formulae:
                value = self.shared_formulae[idx].translate_formula(coordinate)
            elif value != "=":
                self.shared_formulae[idx] = Translator(value, coordinate)
        elif formula_type == "dataTable":
            value = DataTableFormula(**formula.attrib)

        return value

    def parse_column_dimensions(self, col) -> None:
        attrs = dict(col.attrib)
        column = get_column_letter(int(attrs["min"]))
        attrs["index"] = column
        self.column_dimensions[column] = attrs

    def parse_formatting(self, element) -> None:
        try:
            rules = [_parse_cf_rule(child) for child in element if _local_name(child.tag) == "cfRule"]
            self.formatting.append(
                ConditionalFormatting(sqref=element.get("sqref", ""), rules=rules)
            )
        except TypeError as exc:
            warn(
                "Failed to load a conditional formatting rule. It will be "
                f"discarded. Cause: {exc}"
            )

    def parse_extensions(self, element) -> None:
        for child in element:
            uri = child.get("uri", "").upper()
            ext_type = EXT_TYPES.get(uri, "Unknown")
            warn(f"{ext_type} extension is not supported and will be removed")

    def parse_legacy(self, element) -> None:
        self.legacy_drawing = _relationship_id(element)

    def parse_row_breaks(self, element) -> None:
        self.row_breaks = _parse_breaks(element, RowBreak)

    def parse_col_breaks(self, element) -> None:
        self.col_breaks = _parse_breaks(element, ColBreak)

    def parse_custom_views(self, element) -> None:  # noqa: ARG002
        self.row_breaks = RowBreak()
        self.col_breaks = ColBreak()

    def parse_row(self, row):
        attrs = dict(row.attrib)
        if "r" in attrs:
            try:
                self.row_counter = int(attrs["r"])
            except ValueError:
                value = float(attrs["r"])
                if not value.is_integer():
                    raise ValueError(f"{attrs['r']} is not a valid row number")
                self.row_counter = int(value)
        else:
            self.row_counter += 1
        self.col_counter = 0

        keys = {key for key in attrs if not key.startswith("{")}
        if keys - {"r", "spans"}:
            self.row_dimensions[str(self.row_counter)] = attrs

        cells = [self.parse_cell(el) for el in row]
        return self.row_counter, cells

    def parse_sheet_protection(self, element) -> None:
        attrs = dict(element.attrib)
        password = attrs.pop("password", None)
        protection = SheetProtection(**attrs)
        if password is not None:
            protection.set_password(password, already_hashed=True)
        self.protection = protection


class WorksheetReader:
    """Apply a parsed worksheet XML stream to an openpyxl-shaped worksheet."""

    def __init__(self, ws, xml_source, shared_strings, data_only, rich_text) -> None:
        self.ws = ws
        self.parser = WorkSheetParser(
            xml_source,
            shared_strings,
            data_only,
            ws.parent.epoch,
            ws.parent._date_formats,
            ws.parent._timedelta_formats,
            rich_text,
        )
        self.tables = []

    def bind_cells(self) -> None:
        for _, row in self.parser.parse():
            for cell in row:
                style = self.ws.parent._cell_styles[cell["style_id"]]
                c = Cell(
                    self.ws,
                    row=cell["row"],
                    column=cell["column"],
                    style_array=style,
                )
                c._value = cell["value"]
                c.data_type = cell["data_type"]
                self.ws._cells[(cell["row"], cell["column"])] = c

        if self.ws._cells:
            self.ws._current_row = max(row for row, _ in self.ws._cells)

    def bind_formatting(self) -> None:
        formatting = self.ws.conditional_formatting
        for cf in self.parser.formatting:
            for rule in cf.rules:
                if getattr(rule, "dxfId", None) is not None:
                    rule.dxf = self.ws.parent._differential_styles[rule.dxfId]
            formatting._append_entry(cf)

    def bind_tables(self) -> None:
        for table in self.parser.tables.tablePart:
            rel = self.ws._rels.get(table.id)
            self.tables.append(rel.Target)

    def bind_merged_cells(self) -> None:
        if not self.parser.merged_cells:
            return
        ranges = {cell.ref for cell in self.parser.merged_cells.mergeCell}
        if hasattr(self.ws, "_merged_ranges"):
            self.ws._merged_ranges = set(ranges)
            self.ws._collection_merged_ranges = set()
            return
        self.ws.merged_cells = " ".join(sorted(ranges))

    def bind_hyperlinks(self) -> None:
        for link in self.parser.hyperlinks.hyperlink:
            if link.id:
                rel = self.ws._rels.get(link.id)
                link.target = rel.Target
            if ":" in link.ref:
                for row in self.ws[link.ref]:
                    for cell in row:
                        try:
                            copied = copy(link)
                            copied.ref = cell.coordinate
                            cell._hyperlink = copied
                            self.ws._pending_hyperlinks[cell.coordinate] = copied
                        except AttributeError:
                            pass
            else:
                cell = self.ws[link.ref]
                if isinstance(cell, MergedCell):
                    cell = self.normalize_merged_cell_link(cell.coordinate)
                    if cell is None:
                        continue
                cell._hyperlink = link
                self.ws._pending_hyperlinks[cell.coordinate] = link

    def normalize_merged_cell_link(self, coord):
        for rng in self.ws.merged_cells:
            if coord in rng:
                return self.ws.cell(row=rng.min_row, column=rng.min_col)
        return None

    def bind_col_dimensions(self) -> None:
        for col, cd in self.parser.column_dimensions.items():
            dimension = ColumnDimension(self.ws, col)
            if "width" in cd:
                self.ws._col_widths[col] = float(cd["width"])
            if "hidden" in cd:
                self.ws._col_hidden[col] = cd["hidden"] in {"1", "true", "True"}
            self.ws._col_dimensions.add(col)
            self.ws._column_dimension_cache[col] = dimension

    def bind_row_dimensions(self) -> None:
        for row, rd in self.parser.row_dimensions.items():
            row_idx = int(row)
            if "ht" in rd:
                self.ws._row_heights[row_idx] = float(rd["ht"])
            if "hidden" in rd:
                self.ws._row_hidden[row_idx] = rd["hidden"] in {"1", "true", "True"}
            self.ws._row_dimensions.add(row_idx)

    def bind_properties(self) -> None:
        for key in (
            "print_options",
            "page_margins",
            "page_setup",
            "HeaderFooter",
            "auto_filter",
            "data_validations",
            "sheet_properties",
            "views",
            "sheet_format",
            "row_breaks",
            "col_breaks",
            "scenarios",
            "legacy_drawing",
            "protection",
        ):
            value = getattr(self.parser, key, None)
            if value is not None:
                if key == "HeaderFooter":
                    self.ws.header_footer = value
                elif key == "data_validations":
                    self.ws._data_validations_cache = value
                else:
                    setattr(self.ws, key, value)

    def bind_all(self) -> None:
        self.bind_cells()
        self.bind_merged_cells()
        self.bind_hyperlinks()
        self.bind_formatting()
        self.bind_col_dimensions()
        self.bind_row_dimensions()
        self.bind_tables()
        self.bind_properties()


def parse_richtext_string(value):  # noqa: ANN001
    runs = CellRichText()
    for child in value:
        if _local_name(child.tag) == "t":
            if child.text:
                runs.append(child.text)
        elif _local_name(child.tag) == "r":
            text = ""
            font = InlineFont()
            for run_child in child:
                name = _local_name(run_child.tag)
                if name == "t":
                    text = run_child.text or ""
                elif name == "rPr":
                    font = _parse_inline_font(run_child)
            runs.append(TextBlock(font=font, text=text))
    return runs


def _plain_richtext_string(element) -> str:  # noqa: ANN001
    text = []
    for child in element.iter():
        if _local_name(child.tag) == "t" and child.text:
            text.append(child.text)
    return "".join(text)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_inline_font(element) -> InlineFont:  # noqa: ANN001
    attrs: dict[str, Any] = {}
    for child in element:
        name = _local_name(child.tag)
        if name == "sz":
            attrs["sz"] = child.get("val")
        elif name == "rFont":
            attrs["rFont"] = child.get("val")
        elif name in {"b", "i", "strike", "outline", "shadow", "condense", "extend"}:
            attrs[name] = child.get("val", "1") != "0"
        elif name in {"charset", "family"}:
            value = child.get("val")
            attrs[name] = int(value) if value is not None else None
        elif name in {"color", "u", "vertAlign", "scheme"}:
            attrs[name] = child.get("val")
    return InlineFont(**attrs)


def _from_tree(cls, element):  # noqa: ANN001
    if cls is SheetViewList:
        return _parse_sheet_views(element)
    if cls is WorksheetProperties:
        return _parse_sheet_properties(element)
    if cls is SheetFormatProperties:
        return SheetFormatProperties(**_typed_attrs(element))
    if cls is AutoFilter:
        return AutoFilter.from_tree(element)
    if cls is TablePartList:
        parts = [
            Related(id=_relationship_id(child))
            for child in element
            if _local_name(child.tag) == "tablePart"
        ]
        return TablePartList(count=len(parts), tablePart=parts)
    if cls is HyperlinkList:
        links = HyperlinkList()
        links.hyperlink = links
        for child in element:
            if _local_name(child.tag) == "hyperlink":
                links.append(Hyperlink(**_relationship_attrs(child)))
        return links
    if cls is MergeCells:
        return MergeCells(
            mergeCell=[
                MergeCell(ref=child.get("ref"))
                for child in element
                if _local_name(child.tag) == "mergeCell"
            ]
        )
    if cls is ScenarioList:
        return _parse_scenarios(element)
    if hasattr(cls, "from_tree"):
        return cls.from_tree(element)
    return cls(**_typed_attrs(element))


def _parse_sheet_views(element):  # noqa: ANN001
    views = []
    for child in element:
        if _local_name(child.tag) != "sheetView":
            continue
        attrs = _typed_attrs(child)
        pane = None
        selections = []
        for grandchild in child:
            name = _local_name(grandchild.tag)
            if name == "pane":
                pane = Pane(**_typed_attrs(grandchild))
            elif name == "selection":
                selections.append(Selection(**_typed_attrs(grandchild)))
        if pane is not None:
            attrs["pane"] = pane
        if selections:
            attrs["selection"] = selections
        views.append(SheetView(**attrs))
    return SheetViewList(sheetView=views)


def _parse_sheet_properties(element):  # noqa: ANN001
    attrs = _typed_attrs(element)
    outline = None
    page_setup = None
    tab_color = None
    for child in element:
        name = _local_name(child.tag)
        if name == "tabColor":
            tab_color = Color(**_typed_attrs(child))
        elif name == "outlinePr":
            outline = Outline(**_typed_attrs(child))
        elif name == "pageSetUpPr":
            page_setup = PageSetupProperties(**_typed_attrs(child))
    if tab_color is not None:
        attrs["tabColor"] = tab_color
    if outline is not None:
        attrs["outlinePr"] = outline
    if page_setup is not None:
        attrs["pageSetUpPr"] = page_setup
    return WorksheetProperties(**attrs)


def _parse_scenarios(element):  # noqa: ANN001
    scenarios = []
    for child in element:
        if _local_name(child.tag) != "scenario":
            continue
        attrs = dict(child.attrib)
        for key in ("locked", "hidden"):
            if key in attrs:
                attrs[key] = attrs[key] in {"1", "true", "True"}
        inputs = [
            InputCells(**dict(grandchild.attrib))
            for grandchild in child
            if _local_name(grandchild.tag) == "inputCells"
        ]
        attrs["inputCells"] = inputs
        scenarios.append(Scenario(**attrs))
    attrs = dict(element.attrib)
    attrs["scenario"] = scenarios
    return ScenarioList(**attrs)


def _parse_breaks(element, cls):  # noqa: ANN001
    breaks = cls()
    for child in element:
        if _local_name(child.tag) == "brk":
            breaks.append(Break(id=int(child.get("id", 0))))
    return breaks


def _parse_cf_rule(element):  # noqa: ANN001
    for child in element.iter():
        if _local_name(child.tag) == "cfvo" and "<>" in (child.get("val") or ""):
            raise TypeError("Value must be a sequence")
    attrs = _typed_attrs(element)
    formula = [
        child.text
        for child in element
        if _local_name(child.tag) == "formula" and child.text is not None
    ]
    if formula:
        attrs["formula"] = formula
    return Rule(**attrs)


def _relationship_attrs(element) -> dict[str, Any]:  # noqa: ANN001
    attrs = {
        _local_name(key): _typed_value(value)
        for key, value in element.attrib.items()
        if _local_name(key) != "id"
    }
    rel_id = _relationship_id(element)
    if rel_id is not None:
        attrs["id"] = rel_id
    return attrs


def _relationship_id(element) -> str | None:  # noqa: ANN001
    for key, value in element.attrib.items():
        if _local_name(key) == "id":
            return value
    return None


def _typed_attrs(element) -> dict[str, Any]:  # noqa: ANN001
    return {
        key: _typed_value(value)
        for key, value in element.attrib.items()
        if "}" not in key
    }


def _typed_value(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"0", "1"}:
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if number.is_integer() and "." not in value and "e" not in value.lower():
        return int(number)
    return number


__all__ = [name for name in list(globals()) if not name.startswith("_")]
