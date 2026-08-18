"""Focused openpyxl invalid-input exception parity.

These tests cover deterministic pure-Python public APIs where openpyxl rejects
invalid values at construction or append time. WolfXL should reject the same
invalid operation with the same broad exception type instead of accepting it or
failing later with an unrelated error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest


def _assert_matches_openpyxl_exception(
    openpyxl_call: Callable[[], Any],
    wolfxl_call: Callable[[], Any],
) -> None:
    try:
        openpyxl_call()
    except Exception as exc:  # noqa: BLE001 - the concrete type is the oracle
        expected_type = type(exc)
    else:  # pragma: no cover - protects against openpyxl drift
        pytest.fail("openpyxl accepted the invalid input")

    with pytest.raises(expected_type):
        wolfxl_call()


def test_rich_text_rejects_invalid_text_block_fields() -> None:
    op_rt = pytest.importorskip("openpyxl.cell.rich_text")

    from wolfxl.cell.rich_text import InlineFont, TextBlock

    _assert_matches_openpyxl_exception(
        lambda: op_rt.TextBlock("not-a-font", "hello"),
        lambda: TextBlock("not-a-font", "hello"),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_rt.TextBlock(op_rt.InlineFont(), 123),
        lambda: TextBlock(InlineFont(), 123),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_rt.InlineFont(sz="large"),
        lambda: InlineFont(sz="large"),  # type: ignore[arg-type]
    )


def test_relationship_models_reject_invalid_public_values() -> None:
    op_rel = pytest.importorskip("openpyxl.packaging.relationship")

    from wolfxl.packaging.relationship import Relationship, RelationshipList

    _assert_matches_openpyxl_exception(
        lambda: op_rel.Relationship(type="worksheet", Target=123),
        lambda: Relationship(type="worksheet", Target=123),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_rel.Relationship(type="worksheet", Id=123, Target="sheet1.xml"),
        lambda: Relationship(type="worksheet", Id=123, Target="sheet1.xml"),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_rel.Relationship(
            type="worksheet",
            Target="sheet1.xml",
            TargetMode=123,
        ),
        lambda: Relationship(
            type="worksheet",
            Target="sheet1.xml",
            TargetMode=123,  # type: ignore[arg-type]
        ),
    )
    _assert_matches_openpyxl_exception(
        lambda: op_rel.RelationshipList().append("not-a-relationship"),
        lambda: RelationshipList().append("not-a-relationship"),  # type: ignore[arg-type]
    )


def test_relationship_type_keyword_normalizes_like_openpyxl() -> None:
    op_rel = pytest.importorskip("openpyxl.packaging.relationship")

    from wolfxl.packaging.relationship import Relationship

    values = [
        "worksheet",
        "http://example.com/custom",
    ]
    for value in values:
        assert Relationship(type=value, Target="sheet1.xml").Type == op_rel.Relationship(
            type=value,
            Target="sheet1.xml",
        ).Type


def test_container_lists_reject_invalid_appends() -> None:
    op_author = pytest.importorskip("openpyxl.comments.author")
    op_container = pytest.importorskip("openpyxl.descriptors.container")

    from wolfxl.comments.author import AuthorList
    from wolfxl.descriptors.container import ElementList

    _assert_matches_openpyxl_exception(
        lambda: op_author.AuthorList().append(None),
        lambda: AuthorList().append(None),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_author.AuthorList().append(""),
        lambda: AuthorList().append(""),
    )
    _assert_matches_openpyxl_exception(
        lambda: op_container.ElementList().append(None),
        lambda: ElementList().append(None),
    )
    _assert_matches_openpyxl_exception(
        lambda: op_container.ElementList().append(""),
        lambda: ElementList().append(""),
    )


def test_style_lists_reject_invalid_items() -> None:
    op_differential = pytest.importorskip("openpyxl.styles.differential")
    op_named_styles = pytest.importorskip("openpyxl.styles.named_styles")

    from wolfxl.styles.differential import DifferentialStyleList
    from wolfxl.styles.named_styles import NamedStyleList

    _assert_matches_openpyxl_exception(
        lambda: op_named_styles.NamedStyleList().append(None),
        lambda: NamedStyleList().append(None),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_differential.DifferentialStyleList().append(None),
        lambda: DifferentialStyleList().append(None),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_differential.DifferentialStyleList().add(None),
        lambda: DifferentialStyleList().add(None),  # type: ignore[arg-type]
    )


def test_worksheet_collections_reject_invalid_operations() -> None:
    op_cell_range = pytest.importorskip("openpyxl.worksheet.cell_range")
    op_datavalidation = pytest.importorskip("openpyxl.worksheet.datavalidation")
    op_table = pytest.importorskip("openpyxl.worksheet.table")

    from wolfxl.worksheet.cell_range import MultiCellRange
    from wolfxl.worksheet.datavalidation import DataValidation
    from wolfxl.worksheet.table import TableList

    _assert_matches_openpyxl_exception(
        lambda: op_cell_range.MultiCellRange().add(None),
        lambda: MultiCellRange().add(None),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_cell_range.MultiCellRange().add(123),
        lambda: MultiCellRange().add(123),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_cell_range.MultiCellRange().remove(None),
        lambda: MultiCellRange().remove(None),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_datavalidation.DataValidation().add(None),
        lambda: DataValidation().add(None),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_table.TableList().add(None),
        lambda: TableList().add(None),
    )


def test_workbook_remove_rejects_invalid_sheet_like_openpyxl() -> None:
    op_workbook = pytest.importorskip("openpyxl")

    import wolfxl

    _assert_matches_openpyxl_exception(
        lambda: op_workbook.Workbook().remove(None),
        lambda: wolfxl.Workbook().remove(None),  # type: ignore[arg-type]
    )


def test_chart_models_reject_invalid_typed_children() -> None:
    op_axis = pytest.importorskip("openpyxl.chart.axis")
    op_legend = pytest.importorskip("openpyxl.chart.legend")
    op_marker = pytest.importorskip("openpyxl.chart.marker")

    from wolfxl.chart.axis import NumericAxis, Scaling
    from wolfxl.chart.legend import Legend, LegendEntry
    from wolfxl.chart.marker import DataPoint

    _assert_matches_openpyxl_exception(
        lambda: op_marker.DataPoint(idx=0, marker="not-a-marker"),
        lambda: DataPoint(idx=0, marker="not-a-marker"),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_marker.DataPoint(idx=0, explosion="large"),
        lambda: DataPoint(idx=0, explosion="large"),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_legend.LegendEntry(idx=0, txPr="not-rich-text"),
        lambda: LegendEntry(idx=0, txPr="not-rich-text"),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_legend.Legend(legendEntry=["not-an-entry"]),
        lambda: Legend(legendEntry=["not-an-entry"]),  # type: ignore[list-item]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_axis.Scaling(logBase="not-a-number"),
        lambda: Scaling(logBase="not-a-number"),  # type: ignore[arg-type]
    )
    _assert_matches_openpyxl_exception(
        lambda: op_axis.NumericAxis(axId=1, scaling="not-scaling"),
        lambda: NumericAxis(axId=1, scaling="not-scaling"),  # type: ignore[arg-type]
    )
