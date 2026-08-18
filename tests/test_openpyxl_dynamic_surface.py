"""Dynamic public-surface ratchet against openpyxl objects.

This is intentionally not a behavioral oracle. It catches newly exposed
openpyxl public attributes that WolfXL has not consciously mirrored, so API
drift becomes a reviewed diff instead of a quiet compatibility surprise.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
import warnings

import pytest

import wolfxl

openpyxl = pytest.importorskip("openpyxl")


@dataclass(frozen=True)
class SurfaceCase:
    label: str
    factory: Callable[[], tuple[object, object]]
    ignored: frozenset[str] = frozenset()


def _png_1x1() -> bytes:
    return bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
        "0000000D49444154789C6360000002000154A24F5D0000000049454E44AE426082"
    )


SERIALISABLE_XML_NOISE = frozenset(
    {
        "extLst",
        "from_tree",
        "id",
        "idx_base",
        "mime_type",
        "namespace",
        "path",
        "plot_area",
        "rel_type",
        "tagname",
        "to_tree",
    }
)

TABLE_XML_NOISE = SERIALISABLE_XML_NOISE | frozenset(
    {
        "autoFilter",
        "column_names",
        "connectionId",
        "dataCellStyle",
        "dataDxfId",
        "headerRowBorderDxfId",
        "headerRowCellStyle",
        "headerRowDxfId",
        "insertRow",
        "insertRowShift",
        "published",
        "sortState",
        "tableBorderDxfId",
        "totalsRowBorderDxfId",
        "totalsRowCellStyle",
        "totalsRowDxfId",
    }
)

EXTERNAL_LINK_NOISE = SERIALISABLE_XML_NOISE | frozenset({"externalBook"})


CASES: list[SurfaceCase] = [
    SurfaceCase("Workbook", lambda: (openpyxl.Workbook(), wolfxl.Workbook())),
    SurfaceCase(
        "Worksheet",
        lambda: (openpyxl.Workbook().active, wolfxl.Workbook().active),
    ),
    SurfaceCase(
        "Cell",
        lambda: (openpyxl.Workbook().active["A1"], wolfxl.Workbook().active["A1"]),
    ),
    SurfaceCase(
        "Font",
        lambda: (__import__("openpyxl.styles").styles.Font(), wolfxl.styles.Font()),
    ),
    SurfaceCase(
        "Fill",
        lambda: (
            __import__("openpyxl.styles.fills", fromlist=["Fill"]).Fill(),
            wolfxl.styles.Fill(),
        ),
        ignored=SERIALISABLE_XML_NOISE,
    ),
    SurfaceCase(
        "PatternFill",
        lambda: (
            __import__("openpyxl.styles").styles.PatternFill(),
            wolfxl.styles.PatternFill(),
        ),
    ),
    SurfaceCase(
        "GradientFill",
        lambda: (
            __import__("openpyxl.styles").styles.GradientFill(),
            wolfxl.styles.GradientFill(),
        ),
        ignored=frozenset({"from_tree", "idx_base", "namespace", "to_tree"}),
    ),
    SurfaceCase(
        "Border",
        lambda: (__import__("openpyxl.styles").styles.Border(), wolfxl.styles.Border()),
    ),
    SurfaceCase(
        "Alignment",
        lambda: (
            __import__("openpyxl.styles").styles.Alignment(),
            wolfxl.styles.Alignment(),
        ),
    ),
    SurfaceCase(
        "Protection",
        lambda: (
            __import__("openpyxl.styles").styles.Protection(),
            wolfxl.styles.Protection(),
        ),
    ),
    SurfaceCase(
        "NamedStyle",
        lambda: (
            __import__("openpyxl.styles").styles.NamedStyle(name="Ratchet"),
            wolfxl.styles.NamedStyle(name="Ratchet"),
        ),
    ),
    SurfaceCase(
        "DefinedName",
        lambda: (
            __import__(
                "openpyxl.workbook.defined_name", fromlist=["DefinedName"]
            ).DefinedName(name="Ratchet", attr_text="Sheet!$A$1"),
            wolfxl.workbook.defined_name.DefinedName(
                name="Ratchet", attr_text="Sheet!$A$1"
            ),
        ),
    ),
    SurfaceCase(
        "ExternalLink",
        lambda: (
            __import__(
                "openpyxl.workbook.external_link.external",
                fromlist=["ExternalLink"],
            ).ExternalLink(),
            __import__("wolfxl._external_links", fromlist=["ExternalLink"]).ExternalLink(
                file_link=__import__(
                    "wolfxl._external_links", fromlist=["ExternalFileLink"]
                ).ExternalFileLink("book.xlsx"),
                rid="rId1",
                target="book.xlsx",
            ),
        ),
        ignored=EXTERNAL_LINK_NOISE,
    ),
    SurfaceCase(
        "BarChart",
        lambda: (
            __import__("openpyxl.chart", fromlist=["BarChart"]).BarChart(),
            __import__("wolfxl.chart", fromlist=["BarChart"]).BarChart(),
        ),
        ignored=SERIALISABLE_XML_NOISE,
    ),
    SurfaceCase(
        "Image",
        lambda: (
            pytest.importorskip("PIL") and __import__(
                "openpyxl.drawing.image", fromlist=["Image"]
            ).Image(BytesIO(_png_1x1())),
            __import__("wolfxl.drawing.image", fromlist=["Image"]).Image(_png_1x1()),
        ),
    ),
    SurfaceCase(
        "Comment",
        lambda: (
            __import__("openpyxl.comments", fromlist=["Comment"]).Comment(
                "note", "wolfxl"
            ),
            wolfxl.comments.Comment("note", "wolfxl"),
        ),
    ),
    SurfaceCase(
        "Table",
        lambda: (
            __import__("openpyxl.worksheet.table", fromlist=["Table"]).Table(
                displayName="RatchetTable", ref="A1:B2"
            ),
            wolfxl.worksheet.table.Table(name="RatchetTable", ref="A1:B2"),
        ),
        ignored=TABLE_XML_NOISE,
    ),
    SurfaceCase(
        "DataValidation",
        lambda: (
            __import__(
                "openpyxl.worksheet.datavalidation", fromlist=["DataValidation"]
            ).DataValidation(type="whole"),
            wolfxl.worksheet.datavalidation.DataValidation(type="whole"),
        ),
    ),
    SurfaceCase(
        "ConditionalFormatting",
        lambda: (
            __import__(
                "openpyxl.formatting.formatting", fromlist=["ConditionalFormatting"]
            ).ConditionalFormatting(sqref="A1:A2"),
            wolfxl.formatting.ConditionalFormatting("A1:A2"),
        ),
        ignored=SERIALISABLE_XML_NOISE,
    ),
    SurfaceCase(
        "ConditionalFormattingList",
        lambda: (
            __import__(
                "openpyxl.formatting.formatting",
                fromlist=["ConditionalFormattingList"],
            ).ConditionalFormattingList(),
            wolfxl.formatting.ConditionalFormattingList(),
        ),
    ),
    SurfaceCase(
        "AutoFilter",
        lambda: (
            __import__("openpyxl.worksheet.filters", fromlist=["AutoFilter"]).AutoFilter(
                ref="A1:B2"
            ),
            wolfxl.worksheet.filters.AutoFilter(ref="A1:B2"),
        ),
    ),
    SurfaceCase(
        "PageSetup",
        lambda: (
            __import__(
                "openpyxl.worksheet.page", fromlist=["PrintPageSetup"]
            ).PrintPageSetup(),
            wolfxl.worksheet.page_setup.PageSetup(),
        ),
        ignored=SERIALISABLE_XML_NOISE,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.label)
def test_objects_expose_openpyxl_public_surface(case: SurfaceCase) -> None:
    """Tracked openpyxl objects should not gain unreviewed public attr gaps."""
    openpyxl_obj, wolfxl_obj = case.factory()
    missing_callables: list[str] = []
    missing_values: list[str] = []
    type_mismatches: list[tuple[str, str]] = []

    for name in dir(openpyxl_obj):
        if name.startswith("_") or name in case.ignored:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                openpyxl_value = getattr(openpyxl_obj, name)
            except Exception:  # noqa: BLE001 - descriptors can require workbook state
                continue

        if not hasattr(wolfxl_obj, name):
            if callable(openpyxl_value):
                missing_callables.append(name)
            else:
                missing_values.append(name)
            continue

        wolfxl_value = getattr(wolfxl_obj, name)
        if callable(openpyxl_value) and not callable(wolfxl_value):
            type_mismatches.append((name, "openpyxl callable, wolfxl value"))
        elif not callable(openpyxl_value) and callable(wolfxl_value):
            type_mismatches.append((name, "openpyxl value, wolfxl callable"))

    assert missing_callables == [], f"{case.label} missing callables: {missing_callables}"
    assert missing_values == [], f"{case.label} missing values: {missing_values}"
    assert type_mismatches == [], f"{case.label} type mismatches: {type_mismatches}"
