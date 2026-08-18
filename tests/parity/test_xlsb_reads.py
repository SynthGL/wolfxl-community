"""Native ``.xlsb`` read parity against committed sidecar goldens."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import wolfxl

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "xlsb"
EXCELGEN_DIR = FIXTURES_DIR / "excelgen"


def _all_fixtures() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.xlsb"))


_FIXTURES = _all_fixtures()


pytestmark = pytest.mark.skipif(
    not _FIXTURES,
    reason="No .xlsb fixtures present (Sprint Κ Pod-γ)",
)


def _coerce(v: object) -> object:
    """Normalize workbook values for JSON-sidecar equality."""
    if hasattr(v, "isoformat"):
        return v.isoformat()  # type: ignore[no-any-return]
    return v


def _trim_trailing_empty(rows: list[list[object]]) -> list[list[object]]:
    while rows and all(value is None for value in rows[-1]):
        rows.pop()
    return rows


def _sheet_values(ws: object) -> list[list[object]]:
    rows = [
        [_coerce(cell.value) for cell in row]
        for row in ws.iter_rows()  # type: ignore[attr-defined]
    ]
    return _trim_trailing_empty(rows)


def _cell_style_signature(cell: object) -> dict[str, object]:
    font = cell.font  # type: ignore[attr-defined]
    return {
        "style_id": cell.style_id,  # type: ignore[attr-defined]
        "number_format": cell.number_format,  # type: ignore[attr-defined]
        "font": {
            "name": font.name,
            "size": font.size,
            "bold": bool(font.bold),
            "italic": bool(font.italic),
        },
    }


def _excelgen_sample_root() -> Path | None:
    """Return the optional upstream ExcelGen sample root for paired oracles."""
    raw = os.environ.get("WOLFXL_EXCELGEN_SAMPLES")
    if not raw:
        return None
    root = Path(raw)
    return root if root.exists() else None


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.name)
def test_xlsb_values_match_committed_goldens(fixture: Path) -> None:
    """Native xlsb reads match committed dependency-free value sidecars."""
    wb = wolfxl.load_workbook(str(fixture), data_only=True)
    expected = json.loads(fixture.with_suffix(".golden.json").read_text())
    actual = {sheet_name: _sheet_values(wb[sheet_name]) for sheet_name in wb.sheetnames}
    assert actual == expected


def test_xlsb_styles_match_committed_goldens() -> None:
    """Native xlsb style reads match the committed style sidecar."""
    fixture = FIXTURES_DIR / "dates.xlsb"
    expected = json.loads(fixture.with_suffix(".styles.golden.json").read_text())
    wb = wolfxl.load_workbook(str(fixture), data_only=True)
    actual = {
        sheet_name: {
            coord: _cell_style_signature(wb[sheet_name][coord])
            for coord in cells
        }
        for sheet_name, cells in expected.items()
    }
    assert actual == expected


def test_xlsb_modify_raises() -> None:
    fixture = _FIXTURES[0]
    with pytest.raises(NotImplementedError, match="transcribe"):
        wolfxl.load_workbook(str(fixture), modify=True)


def test_xlsb_read_only_raises() -> None:
    fixture = _FIXTURES[0]
    with pytest.raises(NotImplementedError, match="xlsx-only"):
        wolfxl.load_workbook(str(fixture), read_only=True)


def test_xlsb_password_raises() -> None:
    fixture = _FIXTURES[0]
    with pytest.raises(NotImplementedError, match="xlsx-only"):
        wolfxl.load_workbook(str(fixture), password="anything")


def test_xlsb_cell_styles_are_readable() -> None:
    """Native xlsb exposes read-side style accessors."""
    fixture = _FIXTURES[0]
    wb = wolfxl.load_workbook(str(fixture))
    ws = wb.active
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                assert cell.font is not None
                assert cell.fill is not None
                assert cell.border is not None
                assert cell.alignment is not None
                _ = cell.number_format
                return
    pytest.fail("no non-empty cells in fixture")


def test_xlsb_defined_names_are_readable() -> None:
    """Native xlsb exposes the defined-names reader surface."""
    fixture = _FIXTURES[0]
    wb = wolfxl.load_workbook(str(fixture))
    assert isinstance(wb.defined_names, dict)


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.name)
def test_xlsb_public_metadata_surfaces_do_not_raise(fixture: Path) -> None:
    """Native xlsb exposes the same lazy worksheet metadata APIs as xlsx."""
    wb = wolfxl.load_workbook(str(fixture))
    for ws in wb.worksheets:
        assert isinstance(list(ws.merged_cells.ranges), list)
        assert isinstance(ws.sheet_visibility(), dict)
        assert isinstance(ws.cached_formula_values(), dict)
        assert isinstance(ws.tables, dict)
        assert isinstance(list(ws.data_validations), list)
        assert isinstance(list(ws.conditional_formatting), list)
        assert ws.print_options is not None
        assert ws.page_margins is not None
        assert ws.page_setup is not None
        assert ws.row_breaks is not None
        assert ws.col_breaks is not None
        assert isinstance(ws._images, list)
        assert isinstance(ws._charts, list)
        assert ws.row_dimensions[1].height is None or isinstance(
            ws.row_dimensions[1].height, float
        )
        assert ws.column_dimensions["A"].width is None or isinstance(
            ws.column_dimensions["A"].width, float
        )
        assert ws["A1"].rich_text is None


def test_xlsb_from_bytes() -> None:
    fixture = _FIXTURES[0]
    data = fixture.read_bytes()
    wb_bytes = wolfxl.load_workbook(data)
    wb_path = wolfxl.load_workbook(str(fixture))
    assert wb_bytes.sheetnames == wb_path.sheetnames


def test_xlsb_classify_format() -> None:
    """``wolfxl.classify_file_format`` reports 'xlsb' for this fixture
    both as a path and as bytes.

    Note: ``wolfxl.classify_format`` (without ``_file_``) is a separate,
    long-standing SynthGL number-format archetype classifier. The
    Sprint Κ file-format detector lives at
    ``wolfxl.classify_file_format`` (re-exported from
    ``wolfxl._rust.classify_file_format``).
    """
    fixture = _FIXTURES[0]
    fmt_path = wolfxl.classify_file_format(str(fixture))
    assert fmt_path == "xlsb", f"path -> {fmt_path!r}"
    fmt_bytes = wolfxl.classify_file_format(fixture.read_bytes())
    assert fmt_bytes == "xlsb", f"bytes -> {fmt_bytes!r}"


@pytest.mark.parametrize(
    "sample_name",
    ["test-formula", "test-image-1", "test-links"],
)
def test_xlsb_excelgen_formulas_match_xlsx_twin(sample_name: str) -> None:
    """Optionally compare formula text against ExcelGen's paired xlsx files."""
    root = _excelgen_sample_root()
    if root is None:
        pytest.skip("set WOLFXL_EXCELGEN_SAMPLES=/path/to/ExcelGen/samples")

    openpyxl = pytest.importorskip("openpyxl")
    xlsx_path = root / f"{sample_name}.xlsx"
    xlsb_path = root / f"{sample_name}.xlsb"
    if not xlsx_path.exists() or not xlsb_path.exists():
        pytest.skip(f"missing ExcelGen paired sample {sample_name}")

    expected_wb = openpyxl.load_workbook(xlsx_path, data_only=False)
    actual_wb = wolfxl.load_workbook(xlsb_path, data_only=False)
    for sheet_name in expected_wb.sheetnames:
        expected_ws = expected_wb[sheet_name]
        actual_ws = actual_wb[sheet_name]
        for row in expected_ws.iter_rows():
            for expected_cell in row:
                expected_value = expected_cell.value
                if isinstance(expected_value, str) and expected_value.startswith("="):
                    assert actual_ws[expected_cell.coordinate].value == expected_value


def test_xlsb_excelgen_data_validations_and_tables() -> None:
    """ExcelGen's xlsb sample exposes table and validation metadata."""
    wb = wolfxl.load_workbook(EXCELGEN_DIR / "data-validations-and-tables.xlsb")

    assert wb.sheetnames == ["sheet1", "sheet2", "sheet3"]

    sheet1_validations = list(wb["sheet1"].data_validations)
    assert [
        (validation.type, validation.operator, str(validation.sqref))
        for validation in sheet1_validations
    ] == [
        ("list", None, "B1"),
        ("whole", "between", "B2"),
        ("date", "between", "B3"),
    ]

    sheet2 = wb["sheet2"]
    assert list(sheet2.tables) == ["Table1"]
    table = sheet2.tables["Table1"]
    assert table.ref == "A1:E15"
    assert table.tableStyleInfo.name == "TableStyleLight1"
    assert [column.name for column in table.tableColumns[:5]] == [
        "EMPNO",
        "ENAME",
        "JOB",
        "SAL",
        "COMM",
    ]
    assert {
        (validation.type, validation.operator, str(validation.sqref))
        for validation in sheet2.data_validations
    } == {
        ("list", None, "C2:C15"),
        ("decimal", "lessThanOrEqual", "E2:E15"),
    }

    sheet3 = wb["sheet3"]
    assert list(sheet3.tables) == ["JobList"]
    assert sheet3.tables["JobList"].ref == "A1:A5"
    assert [column.name for column in sheet3.tables["JobList"].tableColumns] == ["JOB"]


def test_xlsb_excelgen_conditional_formatting_matrix() -> None:
    """ExcelGen's xlsb CF workbook covers the main rule container shapes."""
    wb = wolfxl.load_workbook(EXCELGEN_DIR / "conditional-formatting.xlsb")

    assert wb.sheetnames == ["Misc.", "Chessboard", "Colorscale", "Employees"]

    misc_entries = list(wb["Misc."].conditional_formatting)
    assert len(misc_entries) == 9
    rule_types = {rule.type for entry in misc_entries for rule in entry.rules}
    assert {
        "cellIs",
        "colorScale",
        "dataBar",
        "expression",
        "iconSet",
        "top10",
    } <= rule_types

    chessboard_entries = list(wb["Chessboard"].conditional_formatting)
    assert len(chessboard_entries) == 1
    assert str(chessboard_entries[0].sqref) == "B2:I9"
    assert chessboard_entries[0].rules[0].type == "expression"

    assert len(list(wb["Colorscale"].conditional_formatting)) == 606
    assert len(list(wb["Employees"].conditional_formatting)) == 2


def test_xlsb_excelgen_merged_ranges() -> None:
    """ExcelGen's xlsb merged-cell sample round-trips all ranges."""
    wb = wolfxl.load_workbook(EXCELGEN_DIR / "merged-cells.xlsb")
    ws = wb["sheet1"]

    assert {str(cell_range) for cell_range in ws.merged_cells.ranges} == {
        "A1:D1",
        "A2:B3",
        "C2:D3",
        "A4:B5",
        "C4:D5",
    }


def test_xlsb_excelgen_style_showcase_tables() -> None:
    """ExcelGen's style showcase gives us dense table/merge metadata coverage."""
    wb = wolfxl.load_workbook(EXCELGEN_DIR / "style-showcase.xlsb")

    tables_sheet = wb["Tables"]
    assert len(tables_sheet.tables) == 60
    first_table = tables_sheet.tables["Table1"]
    assert first_table.ref == "B4:B7"
    assert first_table.tableStyleInfo.name == "TableStyleLight1"
    assert [column.name for column in first_table.tableColumns] == ["C1"]

    alignments = {
        str(cell_range) for cell_range in wb["Alignments"].merged_cells.ranges
    }
    assert {
        "B1:B2",
        "C1:C2",
        "D1:D2",
        "E1:E2",
        "F1:F2",
        "G1:G2",
        "H1:H2",
    } <= alignments

    orientation = {str(cell_range) for cell_range in wb["Orientation"].merged_cells.ranges}
    assert "B2:B16" in orientation


def test_xlsb_excelgen_image_drawing() -> None:
    """Drawing-backed images in xlsb hydrate through the worksheet image API."""
    wb = wolfxl.load_workbook(EXCELGEN_DIR / "image-drawing.xlsb")
    ws = wb["sheet1"]

    assert len(ws._images) == 1
    image = ws._images[0]
    assert image.format == "png"
    assert image.width == 400
    assert image.height == 200
    assert image.anchor._from.col == 1
    assert image.anchor._from.row == 3
    assert image.anchor.ext is None


def test_xlsb_excelgen_shared_formulas_and_names() -> None:
    """Shared xlsb formulas hydrate with relative refs and defined names."""
    wb = wolfxl.load_workbook(EXCELGEN_DIR / "formulas-and-names.xlsb")
    ws = wb["sheet1"]

    expected_formulas = {
        "B2": "=2*A2+1",
        "B3": "=2*A3+1",
        "B6": "=2*A6+1",
        "C2": "=TEST1",
        "C6": "=TEST1",
        "C7": '="Total="&SUM(C$2:C6)',
    }
    for coordinate, formula in expected_formulas.items():
        assert ws[coordinate].value == formula

    cached_values = ws.cached_formula_values()
    assert cached_values["B2"] == "#N/A"
    assert cached_values["C6"] == "#N/A"
    assert cached_values["C7"] == "#N/A"

    records = {
        record["coordinate"]: record
        for record in ws.cell_records(include_cached_formula_value=True)
        if record["coordinate"] in expected_formulas
    }
    assert set(records) == set(expected_formulas)
    assert records["B2"]["formula"] == "=2*A2+1"
    assert records["B2"]["cached_value"] == "#N/A"
    assert records["C7"]["formula"] == '="Total="&SUM(C$2:C6)'
    assert records["C7"]["data_type"] == "formula"


def test_xlsb_excelgen_hyperlink_formulas() -> None:
    """ExcelGen's link workbook covers HYPERLINK formulas and shared refs."""
    wb = wolfxl.load_workbook(EXCELGEN_DIR / "links-and-hyperlink-formulas.xlsb")
    ws = wb["sheet1"]

    expected_formulas = {
        "B2": '=HYPERLINK("scheme://test/"&C2,"TEST1")',
        "C2": "=$A2+1",
        "B3": '=HYPERLINK("scheme://test/"&C3,"TEST2")',
        "C3": "=$A3+1",
        "B101": '=HYPERLINK("scheme://test/"&C101,"TEST100")',
        "C101": "=$A101+1",
        "C102": '=HYPERLINK("#A1","Back to top")',
    }
    for coordinate, formula in expected_formulas.items():
        assert ws[coordinate].value == formula

    cached_values = ws.cached_formula_values()
    assert cached_values["B2"] == "#N/A"
    assert cached_values["C2"] == "#N/A"
    assert cached_values["C102"] == "#N/A"


def test_xlsb_excelgen_lookup_formulas_and_table() -> None:
    """ExcelGen's selector workbook covers lookup formulas and table metadata."""
    wb = wolfxl.load_workbook(EXCELGEN_DIR / "lookup-formulas-and-table.xlsb")

    selector = wb["selector"]
    assert selector["C2"].value == "FR"
    assert selector["B3"].value == '=VLOOKUP($C$2,INDIRECT("FlagList"),4,FALSE)'
    assert selector["B16"].value == '=VLOOKUP($C$2,INDIRECT("FlagList"),3,FALSE)'
    assert {str(cell_range) for cell_range in selector.merged_cells.ranges} == {
        "B3:C15",
        "B16:C16",
    }
    assert selector.cached_formula_values()["B3"] == "#N/A"
    assert selector.cached_formula_values()["B16"] == "#N/A"

    data = wb["data"]
    assert list(data.tables) == ["FlagList"]
    table = data.tables["FlagList"]
    assert table.ref == "A1:D230"
    assert [column.name for column in table.tableColumns] == [
        "ISO2_CODE",
        "UN_CODE",
        "LABEL_EN",
        "IMAGE_PNG",
    ]


def test_xlsb_chart_drawing() -> None:
    """Drawing-backed charts in xlsb hydrate through the worksheet chart API."""
    wb = wolfxl.load_workbook(FIXTURES_DIR / "multisheet.xlsb")
    ws = wb["Chart"]

    assert len(ws._charts) == 1
    chart = ws._charts[0]
    assert type(chart).__name__ == "BarChart"
    assert len(chart.series) == 2
    assert chart.anchor == "E15"
