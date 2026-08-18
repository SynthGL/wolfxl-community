"""Drop-in import compatibility for the openpyxl path surface (RFC-060).

Each entry is a (path, symbol) pair sourced verbatim from openpyxl 3.1.x's
``from openpyxl.X import Y`` surface — the search-and-replace from
``openpyxl`` to ``wolfxl`` must produce a working import.

The test only checks for *presence* of the symbol on the wolfxl-shaped
module; semantic divergence is allowed (some symbols land as
``NotImplementedError``-on-instantiation stubs, see
``wolfxl/_compat.py`` for the contract).  The drop-in claim is about
import statements, not behaviour.

Pod 2 (RFC-060), created during sprint Ο.
"""

from __future__ import annotations

import importlib

import pytest


# --------------------------------------------------------------------------
# Path table — authoritative for RFC-060.
# Each row is ``(openpyxl_path, symbol_name)``.  The wolfxl path is the
# straightforward ``openpyxl`` → ``wolfxl`` replacement.
# --------------------------------------------------------------------------

PATHS: list[tuple[str, str]] = [
    # ---- styles ----------------------------------------------------------
    ("openpyxl.styles.alignment", "Alignment"),
    ("openpyxl.styles.borders", "Border"),
    ("openpyxl.styles.borders", "Side"),
    ("openpyxl.styles.borders", "BORDER_STYLES"),
    ("openpyxl.styles.colors", "Color"),
    ("openpyxl.styles.colors", "COLOR_INDEX"),
    ("openpyxl.styles.fonts", "Font"),
    ("openpyxl.styles.fills", "PatternFill"),
    ("openpyxl.styles.fills", "GradientFill"),
    ("openpyxl.styles.fills", "Fill"),
    ("openpyxl.styles.fills", "fills"),
    ("openpyxl.styles.protection", "Protection"),
    ("openpyxl.styles.numbers", "BUILTIN_FORMATS"),
    ("openpyxl.styles.numbers", "is_date_format"),
    ("openpyxl.styles.numbers", "FORMAT_GENERAL"),
    ("openpyxl.styles.numbers", "FORMAT_DATE_DATETIME"),
    ("openpyxl.styles.named_styles", "NamedStyle"),
    ("openpyxl.styles.differential", "DifferentialStyle"),

    # ---- cell ------------------------------------------------------------
    ("openpyxl.cell.cell", "Cell"),
    ("openpyxl.cell.cell", "MergedCell"),
    ("openpyxl.cell.cell", "WriteOnlyCell"),
    ("openpyxl.cell.cell", "ArrayFormula"),
    ("openpyxl.cell.cell", "DataTableFormula"),
    ("openpyxl.cell.cell", "Hyperlink"),
    ("openpyxl.cell.cell", "IllegalCharacterError"),
    ("openpyxl.cell.rich_text", "CellRichText"),
    ("openpyxl.cell.rich_text", "InlineFont"),
    ("openpyxl.cell.rich_text", "TextBlock"),
    ("openpyxl.cell.text", "CellRichText"),
    ("openpyxl.cell.text", "InlineFont"),
    ("openpyxl.cell.text", "TextBlock"),

    # ---- worksheet -------------------------------------------------------
    ("openpyxl.worksheet.cell_range", "CellRange"),
    ("openpyxl.worksheet.cell_range", "MultiCellRange"),
    ("openpyxl.worksheet.dimensions", "ColumnDimension"),
    ("openpyxl.worksheet.dimensions", "RowDimension"),
    ("openpyxl.worksheet.dimensions", "DimensionHolder"),
    ("openpyxl.worksheet.dimensions", "SheetFormatProperties"),
    ("openpyxl.worksheet.dimensions", "SheetDimension"),
    ("openpyxl.worksheet.dimensions", "Dimension"),
    ("openpyxl.worksheet.merge", "MergedCell"),
    ("openpyxl.worksheet.merge", "MergedCellRange"),
    ("openpyxl.worksheet.merge", "MergeCell"),
    ("openpyxl.worksheet.merge", "MergeCells"),
    ("openpyxl.worksheet.views", "SheetView"),
    ("openpyxl.worksheet.views", "Pane"),
    ("openpyxl.worksheet.views", "Selection"),
    ("openpyxl.worksheet.views", "SheetViewList"),
    ("openpyxl.worksheet.pagebreak", "Break"),
    ("openpyxl.worksheet.pagebreak", "ColBreak"),
    ("openpyxl.worksheet.pagebreak", "RowBreak"),
    ("openpyxl.worksheet.pagebreak", "PageBreak"),
    ("openpyxl.worksheet.print_settings", "PrintArea"),
    ("openpyxl.worksheet.print_settings", "PrintTitles"),
    ("openpyxl.worksheet.print_settings", "ColRange"),
    ("openpyxl.worksheet.print_settings", "RowRange"),
    ("openpyxl.worksheet.formula", "ArrayFormula"),
    ("openpyxl.worksheet.formula", "DataTableFormula"),
    ("openpyxl.worksheet.hyperlink", "Hyperlink"),
    ("openpyxl.worksheet.hyperlink", "HyperlinkList"),
    ("openpyxl.worksheet.properties", "WorksheetProperties"),
    ("openpyxl.worksheet.properties", "PageSetupProperties"),
    ("openpyxl.worksheet.properties", "Outline"),
    ("openpyxl.worksheet.protection", "SheetProtection"),
    ("openpyxl.worksheet.table", "Table"),
    ("openpyxl.worksheet.table", "TableColumn"),
    ("openpyxl.worksheet.table", "TableStyleInfo"),
    ("openpyxl.worksheet.table", "TableList"),
    ("openpyxl.worksheet.table", "TablePartList"),
    ("openpyxl.worksheet.table", "AutoFilter"),
    ("openpyxl.worksheet.table", "SortState"),
    ("openpyxl.worksheet.table", "Related"),
    ("openpyxl.worksheet.table", "XMLColumnProps"),
    ("openpyxl.worksheet.page", "PageMargins"),
    ("openpyxl.worksheet.page", "PrintOptions"),
    ("openpyxl.worksheet.page", "PrintPageSetup"),
    ("openpyxl.worksheet.header_footer", "HeaderFooter"),
    ("openpyxl.worksheet.header_footer", "HeaderFooterItem"),
    ("openpyxl.worksheet.filters", "AutoFilter"),
    ("openpyxl.worksheet.filters", "FilterColumn"),
    ("openpyxl.worksheet.filters", "CustomFilter"),
    ("openpyxl.worksheet.filters", "CustomFilters"),
    ("openpyxl.worksheet.filters", "DateGroupItem"),
    ("openpyxl.worksheet.filters", "DynamicFilter"),
    ("openpyxl.worksheet.filters", "IconFilter"),
    ("openpyxl.worksheet.filters", "ColorFilter"),
    ("openpyxl.worksheet.filters", "BlankFilter"),
    ("openpyxl.worksheet.filters", "Top10"),
    ("openpyxl.worksheet.filters", "SortCondition"),
    ("openpyxl.worksheet.filters", "SortState"),
    ("openpyxl.worksheet.filters", "Filters"),
    ("openpyxl.worksheet.datavalidation", "DataValidation"),
    ("openpyxl.worksheet.datavalidation", "DataValidationList"),
    ("openpyxl.worksheet.worksheet", "Worksheet"),
    ("openpyxl.worksheet.copier", "WorksheetCopy"),

    # ---- workbook --------------------------------------------------------
    ("openpyxl.workbook.workbook", "Workbook"),
    ("openpyxl.workbook.defined_name", "DefinedName"),
    ("openpyxl.workbook.defined_name", "DefinedNameList"),
    ("openpyxl.workbook.defined_name", "DefinedNameDict"),
    ("openpyxl.workbook.protection", "WorkbookProtection"),
    ("openpyxl.workbook.protection", "FileSharing"),
    ("openpyxl.workbook.properties", "CalcProperties"),
    ("openpyxl.workbook.properties", "WorkbookProperties"),
    ("openpyxl.workbook.views", "BookView"),
    ("openpyxl.workbook.child", "_WorkbookChild"),
    ("openpyxl.packaging.custom", "CustomPropertyList"),
    ("openpyxl.packaging.custom", "StringProperty"),
    ("openpyxl.packaging.custom", "IntProperty"),
    ("openpyxl.packaging.custom", "FloatProperty"),
    ("openpyxl.packaging.custom", "BoolProperty"),
    ("openpyxl.packaging.custom", "DateTimeProperty"),
    ("openpyxl.packaging.custom", "LinkProperty"),

    # ---- utils -----------------------------------------------------------
    ("openpyxl.utils.cell", "column_index_from_string"),
    ("openpyxl.utils.cell", "get_column_letter"),
    ("openpyxl.utils.cell", "range_boundaries"),
    ("openpyxl.utils.cell", "coordinate_to_tuple"),
    ("openpyxl.utils.cell", "absolute_coordinate"),
    ("openpyxl.utils.cell", "range_to_tuple"),
    ("openpyxl.utils.cell", "rows_from_range"),
    ("openpyxl.utils.cell", "cols_from_range"),
    ("openpyxl.utils.cell", "get_column_interval"),
    ("openpyxl.utils.cell", "quote_sheetname"),
    ("openpyxl.utils.cell", "CellCoordinatesException"),
    ("openpyxl.utils.cell", "COORD_RE"),
    ("openpyxl.utils.cell", "RANGE_EXPR"),
    ("openpyxl.utils.exceptions", "CellCoordinatesException"),
    ("openpyxl.utils.exceptions", "IllegalCharacterError"),
    ("openpyxl.utils.exceptions", "InvalidFileException"),
    ("openpyxl.utils.exceptions", "ReadOnlyWorkbookException"),
    ("openpyxl.utils.exceptions", "WorkbookAlreadySaved"),
    ("openpyxl.utils.indexed_list", "IndexedList"),
    ("openpyxl.utils.dataframe", "dataframe_to_rows"),
    ("openpyxl.utils.datetime", "from_excel"),
    ("openpyxl.utils.datetime", "CALENDAR_WINDOWS_1900"),
    ("openpyxl.utils.datetime", "CALENDAR_MAC_1904"),
    ("openpyxl.utils.units", "EMU_to_pixels"),
    ("openpyxl.utils.units", "pixels_to_EMU"),
    ("openpyxl.utils.units", "EMU_PER_PIXEL"),
    ("openpyxl.utils.escape", "escape"),
    ("openpyxl.utils.escape", "unescape"),
    ("openpyxl.utils.formulas", "FORMULAE"),

    # ---- formatting ------------------------------------------------------
    ("openpyxl.formatting.rule", "Rule"),
    ("openpyxl.formatting.rule", "CellIsRule"),
    ("openpyxl.formatting.rule", "FormulaRule"),
    ("openpyxl.formatting.rule", "ColorScaleRule"),
    ("openpyxl.formatting.rule", "DataBarRule"),
    ("openpyxl.formatting.rule", "IconSetRule"),
    ("openpyxl.formatting.rule", "ColorScale"),
    ("openpyxl.formatting.rule", "DataBar"),
    ("openpyxl.formatting.rule", "IconSet"),
    ("openpyxl.formatting.rule", "DifferentialStyle"),
    ("openpyxl.formatting.rule", "RuleType"),
    ("openpyxl.formatting.formatting", "ConditionalFormatting"),
    ("openpyxl.formatting.formatting", "ConditionalFormattingList"),

    # ---- chart -----------------------------------------------------------
    ("openpyxl.chart.bar_chart", "BarChart"),
    ("openpyxl.chart.bar_chart", "BarChart3D"),
    ("openpyxl.chart.line_chart", "LineChart"),
    ("openpyxl.chart.line_chart", "LineChart3D"),
    ("openpyxl.chart.pie_chart", "PieChart"),
    ("openpyxl.chart.pie_chart", "PieChart3D"),
    ("openpyxl.chart.pie_chart", "Pie3D"),
    ("openpyxl.chart.area_chart", "AreaChart"),
    ("openpyxl.chart.area_chart", "AreaChart3D"),
    ("openpyxl.chart.scatter_chart", "ScatterChart"),
    ("openpyxl.chart.bubble_chart", "BubbleChart"),
    ("openpyxl.chart.radar_chart", "RadarChart"),
    ("openpyxl.chart.surface_chart", "SurfaceChart"),
    ("openpyxl.chart.surface_chart", "SurfaceChart3D"),
    ("openpyxl.chart.stock_chart", "StockChart"),
    ("openpyxl.chart.doughnut_chart", "DoughnutChart"),
    ("openpyxl.chart.projected_pie_chart", "ProjectedPieChart"),
    ("openpyxl.chart.reference", "Reference"),
    ("openpyxl.chart.series", "Series"),
    ("openpyxl.chart.series", "SeriesLabel"),
    ("openpyxl.chart.series", "XYSeries"),
    ("openpyxl.chart.series", "SeriesFactory"),
    ("openpyxl.chart.label", "DataLabel"),
    ("openpyxl.chart.label", "DataLabelList"),
    ("openpyxl.chart.legend", "Legend"),
    ("openpyxl.chart.title", "Title"),
    ("openpyxl.chart.layout", "Layout"),
    ("openpyxl.chart.layout", "ManualLayout"),
    ("openpyxl.chart.marker", "Marker"),
    ("openpyxl.chart.marker", "DataPoint"),
    ("openpyxl.chart.trendline", "Trendline"),
    ("openpyxl.chart.error_bar", "ErrorBars"),
    ("openpyxl.chart.axis", "ChartLines"),
    ("openpyxl.chart.axis", "NumericAxis"),
    ("openpyxl.chart.axis", "TextAxis"),
    ("openpyxl.chart.data_source", "NumRef"),
    ("openpyxl.chart.data_source", "NumDataSource"),
    ("openpyxl.chart.data_source", "AxDataSource"),
    ("openpyxl.chart.data_source", "StrRef"),

    # ---- chartsheet ------------------------------------------------------
    ("openpyxl.chartsheet", "Chartsheet"),
    ("openpyxl.chartsheet.chartsheet", "Chartsheet"),
    ("openpyxl.chartsheet.chartsheet", "ChartsheetProperties"),
    ("openpyxl.chartsheet.chartsheet", "ChartsheetProtection"),
    ("openpyxl.chartsheet.properties", "ChartsheetProperties"),
    ("openpyxl.chartsheet.protection", "ChartsheetProtection"),

    # ---- pivot -----------------------------------------------------------
    ("openpyxl.pivot.table", "PivotTable"),
    ("openpyxl.pivot.table", "TableDefinition"),
    ("openpyxl.pivot.table", "RowField"),
    ("openpyxl.pivot.table", "ColumnField"),
    ("openpyxl.pivot.table", "DataField"),
    ("openpyxl.pivot.table", "PageField"),
    ("openpyxl.pivot.table", "PivotField"),
    ("openpyxl.pivot.table", "PivotItem"),
    ("openpyxl.pivot.table", "Location"),
    ("openpyxl.pivot.cache", "PivotCache"),
    ("openpyxl.pivot.cache", "CacheDefinition"),
    ("openpyxl.pivot.cache", "CacheField"),
    ("openpyxl.pivot.cache", "CacheValue"),
    ("openpyxl.pivot.cache", "SharedItems"),
    ("openpyxl.pivot.cache", "WorksheetSource"),
    ("openpyxl.pivot.fields", "RowField"),
    ("openpyxl.pivot.fields", "DataField"),

    # ---- drawing ---------------------------------------------------------
    ("openpyxl.drawing.image", "Image"),
    ("openpyxl.drawing.spreadsheet_drawing", "SpreadsheetDrawing"),
    ("openpyxl.drawing.spreadsheet_drawing", "AbsoluteAnchor"),
    ("openpyxl.drawing.spreadsheet_drawing", "OneCellAnchor"),
    ("openpyxl.drawing.spreadsheet_drawing", "TwoCellAnchor"),
    ("openpyxl.drawing.spreadsheet_drawing", "AnchorMarker"),

    # ---- comments --------------------------------------------------------
    ("openpyxl.comments", "Comment"),
    ("openpyxl.comments.comments", "Comment"),
    ("openpyxl.comments.comments", "CommentSheet"),
]


def _to_wolfxl(path: str) -> str:
    """``openpyxl.X`` → ``wolfxl.X`` per RFC-060's drop-in claim."""
    assert path.startswith("openpyxl"), path
    return "wolfxl" + path[len("openpyxl"):]


@pytest.mark.parametrize(
    "openpyxl_path,symbol",
    PATHS,
    ids=[f"{p}::{s}" for p, s in PATHS],
)
def test_wolfxl_provides_openpyxl_shaped_path(openpyxl_path: str, symbol: str) -> None:
    """A search-and-replace ``openpyxl`` → ``wolfxl`` must produce a
    working import for every entry in ``PATHS``.
    """
    wolfxl_path = _to_wolfxl(openpyxl_path)
    try:
        mod = importlib.import_module(wolfxl_path)
    except ImportError as exc:
        pytest.fail(
            f"Drop-in import broken: {wolfxl_path!r} cannot be imported "
            f"({exc!r}).  RFC-060 requires this module to exist."
        )
    assert hasattr(mod, symbol), (
        f"{wolfxl_path}.{symbol} missing — drop-in claim broken "
        f"(RFC-060 §11)."
    )


def test_path_count_matches_rfc() -> None:
    """RFC-060 promises ~70+ drop-in import paths; we expect at least 70."""
    assert len(PATHS) >= 70, (
        f"PATHS table has {len(PATHS)} entries; RFC-060 §1 promises ~70+. "
        f"Either extend the table or update the RFC."
    )
