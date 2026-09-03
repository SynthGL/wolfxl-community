"""Shared OOXML package namespaces, feature part prefixes, and byte markers.

Internal to the OOXML fidelity audit. The public surface stays
``wolfxl.operations._ooxml_fidelity``.
"""

from __future__ import annotations

REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CT_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"
MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

FEATURE_PART_PREFIXES = {
    "calc_chain": ("xl/calcChain.xml",),
    "chart": ("xl/charts/",),
    "chart_sheet": ("xl/chartsheets/",),
    "chart_style": ("xl/charts/style", "xl/charts/colors"),
    "comment": ("xl/comments", "xl/threadedComments/", "xl/persons/"),
    "conditional_formatting": ("xl/worksheets/", "xl/styles.xml"),
    "connection": ("xl/connections.xml", "xl/queryTables/"),
    "custom_property": ("xl/customProperty",),
    "custom_xml": ("customXml/", "xl/customXml/"),
    "data_model": ("xl/model/",),
    "doc_metadata": ("docMetadata/",),
    "drawing": ("xl/drawings/",),
    "embedded_object": ("xl/embeddings/", "xl/ctrlProps/", "xl/activeX/"),
    "external_link": ("xl/externalLinks/",),
    "image_media": ("xl/media/",),
    "javascript_project": ("xl/jsaProject.bin",),
    "named_sheet_view": ("xl/namedSheetViews/",),
    "pivot": ("xl/pivotCache/", "xl/pivotTables/", "pivotCache/"),
    "printer_settings": ("xl/printerSettings/",),
    "python": ("xl/python.xml",),
    "sheet_metadata": ("xl/metadata.xml",),
    "slicer": ("xl/slicers/", "xl/slicerCaches/"),
    "table": ("xl/tables/",),
    "timeline": ("xl/timelines/", "xl/timelineCaches/"),
    "vba": ("xl/vbaProject.bin",),
}

CF_EXTENSION_NAMES = frozenset(
    {
        "conditionalFormatting",
        "conditionalFormattings",
        "cfRule",
        "colorScale",
        "dataBar",
        "iconSet",
        "pivotAreas",
    }
)

SLICER_EXTENSION_NAMES = frozenset({"slicerCaches", "slicerList"})
TIMELINE_EXTENSION_NAMES = frozenset({"timelineCacheRefs", "timelineRefs", "timelineList"})
CONDITIONAL_FORMATTING_MARKERS = (b"conditionalFormatting", b"cfRule", b"extLst")
DATA_VALIDATION_MARKERS = (b"dataValidation",)
EXTENSION_MARKERS = (b"<ext", b":ext", b"extLst")
FORMULA_MARKERS = (b"<f", b":f")
PAGE_SETUP_MARKERS = (b"pageMargins", b"pageSetup", b"printOptions", b"headerFooter")
MARKER_SENSITIVE_SEMANTIC_FEATURES = frozenset(
    {
        "conditional_formatting",
        "data_validations",
        "external_links",
        "worksheet_formulas",
    }
)
