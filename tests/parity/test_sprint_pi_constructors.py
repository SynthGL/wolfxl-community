"""Sprint Π constructor ratchet for formerly stubbed openpyxl paths."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

import pytest


def _construct_dimension_holder(cls: type[Any]) -> Any:
    from wolfxl import Workbook

    return cls(Workbook().active)


def _construct_merge_cell(cls: type[Any]) -> Any:
    return cls("A1:B2")


def _construct_no_args(cls: type[Any]) -> Any:
    return cls()


def _construct_worksheet_copy(cls: type[Any]) -> Any:
    from wolfxl import Workbook

    wb = Workbook()
    source = wb.active
    target = wb.create_sheet("Copied")
    return cls(source, target)


# Only include pods that have landed on feat/native-writer. Later Sprint Π pods
# should append their symbols here as they replace the remaining stubs.
SPRINT_PI_LANDED_CONSTRUCTORS: tuple[
    tuple[str, str, Callable[[type[Any]], Any]],
    ...,
] = (
    # RFC-066 / Π-epsilon: re-route to existing real page_setup classes.
    ("wolfxl.worksheet.page", "PageMargins", _construct_no_args),
    ("wolfxl.worksheet.page", "PrintOptions", _construct_no_args),
    ("wolfxl.worksheet.page", "PrintPageSetup", _construct_no_args),
    # RFC-062 / Π-alpha: page breaks + dimensions.
    ("wolfxl.worksheet.pagebreak", "Break", _construct_no_args),
    ("wolfxl.worksheet.pagebreak", "ColBreak", _construct_no_args),
    ("wolfxl.worksheet.pagebreak", "RowBreak", _construct_no_args),
    ("wolfxl.worksheet.dimensions", "DimensionHolder", _construct_dimension_holder),
    ("wolfxl.worksheet.dimensions", "SheetFormatProperties", _construct_no_args),
    ("wolfxl.worksheet.dimensions", "SheetDimension", _construct_no_args),
    # RFC-063 / Π-beta: merge, table-list, and copier support types.
    ("wolfxl.worksheet.merge", "MergeCell", _construct_merge_cell),
    ("wolfxl.worksheet.merge", "MergeCells", _construct_no_args),
    ("wolfxl.worksheet.copier", "WorksheetCopy", _construct_worksheet_copy),
    ("wolfxl.worksheet.table", "TableList", _construct_no_args),
    ("wolfxl.worksheet.table", "TablePartList", _construct_no_args),
    ("wolfxl.worksheet.table", "Related", _construct_no_args),
    ("wolfxl.worksheet.table", "XMLColumnProps", _construct_no_args),
    # RFC-065 / Π-delta: workbook calculation + workbook properties.
    ("wolfxl.workbook.properties", "CalcProperties", _construct_no_args),
    ("wolfxl.workbook.properties", "WorkbookProperties", _construct_no_args),
    ("wolfxl.workbook.child", "_WorkbookChild", _construct_no_args),
    ("wolfxl.comments.comments", "CommentSheet", _construct_no_args),
    ("wolfxl.drawing.spreadsheet_drawing", "SpreadsheetDrawing", _construct_no_args),
    # RFC-064 / Π-gamma: style support types.
    ("wolfxl.styles", "NamedStyle", _construct_no_args),
    ("wolfxl.styles", "Protection", _construct_no_args),
    ("wolfxl.styles", "GradientFill", _construct_no_args),
    ("wolfxl.styles.fills", "Fill", _construct_no_args),
    ("wolfxl.styles.differential", "DifferentialStyle", _construct_no_args),
)


@pytest.mark.parametrize(
    ("module_path", "symbol_name", "factory"),
    SPRINT_PI_LANDED_CONSTRUCTORS,
)
def test_landed_sprint_pi_constructors_are_not_stubs(
    module_path: str,
    symbol_name: str,
    factory: Callable[[type[Any]], Any],
) -> None:
    module = importlib.import_module(module_path)
    cls = getattr(module, symbol_name)

    try:
        instance = factory(cls)
    except NotImplementedError as exc:  # pragma: no cover - regression path
        pytest.fail(f"{module_path}.{symbol_name} still raises NotImplementedError: {exc}")

    assert instance is not None


def test_mergecells_unbound_container_is_set_like() -> None:
    from wolfxl.worksheet.merge import MergeCell, MergeCells

    merges = MergeCells(mergeCell=["A1:B2", MergeCell("C3:D4"), "A1:B2"])

    assert merges.count == 2
    assert "A1:B2" in merges
    assert [cell.ref for cell in merges] == ["A1:B2", "C3:D4"]

    merges.remove("A1:B2")

    assert merges.count == 1
    assert [cell.coord for cell in merges.mergeCell] == ["C3:D4"]


def test_mergecells_bound_container_updates_worksheet_ranges() -> None:
    from wolfxl.worksheet.merge import MergeCells

    from wolfxl import Workbook

    ws = Workbook().active
    merges = MergeCells(ws)

    merges.append("B2:C3")

    assert "B2:C3" in ws._merged_ranges  # noqa: SLF001
    assert [cell.ref for cell in merges] == ["B2:C3"]


def test_table_list_unbound_and_table_part_helpers() -> None:
    from wolfxl.worksheet.table import Related, Table, TableList, TablePartList, XMLColumnProps

    tables = TableList()
    table = Table(name="Sales", ref="A1:B2")

    tables.add(table)

    assert len(tables) == 1
    assert "Sales" in tables
    assert tables["Sales"] is table
    assert tables.items() == [("Sales", "A1:B2")]

    parts = TablePartList(tablePart=[Related("rId1")])
    parts.append(Related("rId2"))

    assert parts.count == 2
    assert [part.id for part in parts] == ["rId1", "rId2"]
    assert XMLColumnProps(mapId=7, xpath="/root/item").mapId == 7


def test_table_list_bound_container_queues_tables_on_worksheet() -> None:
    from wolfxl.worksheet.table import Table, TableList

    from wolfxl import Workbook

    ws = Workbook().active
    table = Table(name="Sales", ref="A1:B2")

    tables = TableList(ws)
    tables.add(table)

    assert tables["Sales"] is table
    assert ws.tables["Sales"] is table
    assert table in ws._pending_tables  # noqa: SLF001


def test_worksheetcopy_copies_into_existing_target_worksheet() -> None:
    from wolfxl.worksheet.copier import WorksheetCopy

    from wolfxl import Workbook

    wb = Workbook()
    source = wb.active
    source["A1"] = "copied"
    source.merge_cells("B2:C3")
    target = wb.create_sheet("Copied")

    copied = WorksheetCopy(source, target).copy_worksheet()

    assert copied is None
    assert target["A1"].value == "copied"
    assert "B2:C3" in target._merged_ranges  # noqa: SLF001


def test_workbook_property_dataclasses_export_rust_contract() -> None:
    from wolfxl.workbook.properties import CalcProperties, WorkbookProperties

    calc = CalcProperties(calcId=191029, calcMode="manual", forceFullCalc=True)
    props = WorkbookProperties(date1904=True, codeName="ThisWorkbook")

    assert calc.to_rust_dict()["calc_id"] == 191029
    assert calc.to_rust_dict()["calc_mode"] == "manual"
    assert calc.to_rust_dict()["force_full_calc"] is True
    assert props.to_rust_dict()["date1904"] is True
    assert props.to_rust_dict()["code_name"] == "ThisWorkbook"


def test_named_style_registry_and_style_helpers() -> None:
    from wolfxl.styles import GradientFill, NamedStyle, Protection
    from wolfxl.styles._named_style import _NamedStyleList
    from wolfxl.styles.differential import DifferentialStyle
    from wolfxl.styles.fills import Fill

    from wolfxl import PatternFill

    registry = _NamedStyleList()
    custom = NamedStyle(
        name="Metric",
        fill=PatternFill(fill_type="solid", fgColor="FF00AA00"),
        protection=Protection(hidden=True),
    )
    registry.append(custom)

    assert "Normal" in registry
    assert registry["Metric"] is custom
    assert registry.user_styles() == [custom]
    assert custom.to_rust_dict()["fill"]["patternType"] == "solid"
    assert custom.to_rust_dict()["protection"] == {"locked": True, "hidden": True}
    assert GradientFill(stop=["FF0000"]).to_rust_dict()["stop"] == ["FF0000"]
    assert Fill().to_rust_dict() == {"tagname": None}
    assert DifferentialStyle(fill=GradientFill()).to_rust_dict()["fill"]["type"] == "linear"


def test_remaining_internal_containers_construct_and_mutate() -> None:
    from wolfxl.comments import Comment
    from wolfxl.comments.comments import CommentSheet
    from wolfxl.drawing.spreadsheet_drawing import OneCellAnchor, SpreadsheetDrawing
    from wolfxl.workbook.child import _WorkbookChild

    child = _WorkbookChild(title="Sheet 1")
    comments = CommentSheet()
    drawing = SpreadsheetDrawing(oneCellAnchor=[OneCellAnchor()])

    comments.append(Comment("hello", author="wolfxl"))

    assert child.title == "Sheet 1"
    assert child.encoding == "utf-8"
    assert comments.authors == ["wolfxl"]
    assert len(drawing.oneCellAnchor) == 1
