"""Openpyxl-compatible VBA package-shape normalization tests."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl._openpyxl_package_shape import normalize_openpyxl_package_shape


MACRO_FIXTURE = Path(__file__).parent / "fixtures" / "macro_basic.xlsm"

CONTENT_TYPES = """\
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="bin" ContentType="application/vnd.ms-office.activeX"/>
  <Default Extension="emf" ContentType="image/x-emf"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="vml" ContentType="application/vnd.openxmlformats-officedocument.vmlDrawing"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
  <Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>
  <Override PartName="/xl/comments1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"/>
  <Override PartName="/xl/activeX/activeX1.xml" ContentType="application/vnd.ms-office.activeX+xml"/>
  <Override PartName="/xl/ctrlProps/ctrlProp1.xml" ContentType="application/vnd.ms-excel.controlproperties+xml"/>
  <Override PartName="/xl/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""

WORKBOOK_RELS = """\
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId4" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/>
</Relationships>
"""

SHEET = """\
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetData><row r="1"><c r="A1"/></row></sheetData>
  <drawing r:id="rId1"/>
  <legacyDrawing r:id="rId2"/>
</worksheet>
"""

SHEET_WITH_SHARED_STRING = """\
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData>
  <drawing r:id="rId1"/>
  <legacyDrawing r:id="rId2"/>
</worksheet>
"""

SHEET_RELS = """\
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing" Target="../drawings/vmlDrawing1.vml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/control" Target="../activeX/activeX1.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/ctrlProp" Target="../ctrlProps/ctrlProp1.xml"/>
</Relationships>
"""

COMMENTS_RELS = """\
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="anysvml" Target="../drawings/vmlDrawing1.vml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"/>
  <Relationship Id="comments" Target="/xl/comments1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"/>
</Relationships>
"""

CONTROL_DRAWING = """\
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:twoCellAnchor><xdr:sp macro=""><xdr:nvSpPr/><xdr:spPr/></xdr:sp><xdr:clientData/></xdr:twoCellAnchor>
</xdr:wsDr>
"""

PICTURE_DRAWING = """\
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">
  <xdr:twoCellAnchor><xdr:pic/><xdr:clientData/></xdr:twoCellAnchor>
</xdr:wsDr>
"""

SHARED_STRINGS = """\
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <si><t>hello</t></si>
</sst>
"""


def _write_package(
    path: Path,
    *,
    sheet: str = SHEET,
    sheet_rels: str = SHEET_RELS,
    drawing: str = CONTROL_DRAWING,
    comments: bool = False,
) -> None:
    parts = {
        "[Content_Types].xml": CONTENT_TYPES,
        "_rels/.rels": "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'/>",
        "docProps/app.xml": "<Properties/>",
        "docProps/core.xml": "<cp:coreProperties xmlns:cp='x'/>",
        "customUI/customUI.xml": "<customUI/>",
        "xl/_rels/workbook.xml.rels": WORKBOOK_RELS,
        "xl/activeX/activeX1.xml": "<activeX/>",
        "xl/activeX/activeX1.bin": b"active",
        "xl/ctrlProps/ctrlProp1.xml": "<formControlPr/>",
        "xl/drawings/drawing1.xml": drawing,
        "xl/drawings/vmlDrawing1.vml": "<xml/>",
        "xl/media/image1.emf": b"image",
        "xl/sharedStrings.xml": SHARED_STRINGS,
        "xl/styles.xml": "<styleSheet/>",
        "xl/theme/theme1.xml": "<theme/>",
        "xl/vbaProject.bin": b"vba",
        "xl/workbook.xml": "<workbook/>",
        "xl/worksheets/_rels/sheet1.xml.rels": sheet_rels,
        "xl/worksheets/sheet1.xml": sheet,
    }
    if comments:
        parts["xl/comments1.xml"] = "<comments/>"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)


def _names(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as zf:
        return set(zf.namelist())


def _read(path: Path, member: str) -> str:
    with zipfile.ZipFile(path) as zf:
        return zf.read(member).decode("utf-8")


def _require_macro_fixture() -> Path:
    if not MACRO_FIXTURE.exists():
        pytest.skip(f"VBA fixture missing: {MACRO_FIXTURE}")
    return MACRO_FIXTURE


def _macro_package_shape(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        content_types = zf.read("[Content_Types].xml").decode("utf-8", "replace")
        workbook_rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8", "replace")
    macro_related_parts = sorted(
        name
        for name in names
        if (
            name == "xl/vbaProject.bin"
            or name.startswith("customUI/")
            or name.startswith("xl/activeX/")
            or name.startswith("xl/ctrlProps/")
        )
    )
    return {
        "macro_related_parts": macro_related_parts,
        "macro_enabled_workbook_content_type": "macroEnabled" in content_types,
        "vba_project_content_type": "application/vnd.ms-office.vbaProject" in content_types,
        "vba_project_relationship": "relationships/vbaProject" in workbook_rels,
    }


def _save_with_openpyxl(source: Path, out: Path, *, keep_vba: bool) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(source, keep_vba=keep_vba)
    try:
        wb.save(out)
    finally:
        vba_archive = getattr(wb, "vba_archive", None)
        close_vba_archive = getattr(vba_archive, "close", None)
        if close_vba_archive is not None:
            close_vba_archive()
        wb.close()


def _save_with_wolfxl(source: Path, out: Path, *, keep_vba: bool) -> None:
    wb = wolfxl.load_workbook(source, keep_vba=keep_vba)
    try:
        wb.save(out)
    finally:
        wb.close()


@pytest.mark.parametrize("keep_vba", [True, False])
def test_load_workbook_keep_vba_save_matches_openpyxl_macro_package_shape(
    tmp_path: Path,
    keep_vba: bool,
) -> None:
    fixture = _require_macro_fixture()
    suffix = ".xlsm" if keep_vba else ".xlsx"
    openpyxl_out = tmp_path / f"openpyxl-keep-vba-{keep_vba}{suffix}"
    wolfxl_out = tmp_path / f"wolfxl-keep-vba-{keep_vba}{suffix}"

    _save_with_openpyxl(fixture, openpyxl_out, keep_vba=keep_vba)
    _save_with_wolfxl(fixture, wolfxl_out, keep_vba=keep_vba)

    assert _macro_package_shape(wolfxl_out) == _macro_package_shape(openpyxl_out)


def test_keep_vba_prunes_unused_shared_strings_and_control_drawing(tmp_path: Path) -> None:
    path = tmp_path / "macro.xlsm"
    _write_package(path)

    normalize_openpyxl_package_shape(str(path), keep_vba=True)

    names = _names(path)
    assert "xl/sharedStrings.xml" not in names
    assert "xl/drawings/drawing1.xml" not in names
    assert "xl/drawings/vmlDrawing1.vml" in names
    assert "xl/vbaProject.bin" in names
    assert "xl/activeX/activeX1.xml" in names
    assert "<drawing" not in _read(path, "xl/worksheets/sheet1.xml")
    rels = _read(path, "xl/worksheets/_rels/sheet1.xml.rels")
    assert "relationships/drawing" not in rels
    assert "relationships/control" not in rels
    assert "relationships/vmlDrawing" in rels


def test_noop_keep_vba_save_normalizes_openpyxl_package_shape(tmp_path: Path) -> None:
    source = tmp_path / "source.xlsm"
    out = tmp_path / "out.xlsm"
    _write_package(source)

    wb = wolfxl.load_workbook(source, keep_vba=True)
    try:
        wb.save(out)
    finally:
        wb.close()

    names = _names(out)
    assert "xl/sharedStrings.xml" not in names
    assert "xl/drawings/drawing1.xml" not in names
    assert "xl/drawings/vmlDrawing1.vml" in names


def test_keep_vba_renames_saved_comments_root_part(tmp_path: Path) -> None:
    path = tmp_path / "comments.xlsm"
    _write_package(
        path,
        sheet=SHEET.replace('<drawing r:id="rId1"/>', ""),
        sheet_rels=COMMENTS_RELS,
        comments=True,
    )

    normalize_openpyxl_package_shape(str(path), keep_vba=True)

    names = _names(path)
    assert "xl/comments/comment1.xml" in names
    assert "xl/comments1.xml" not in names
    rels = _read(path, "xl/worksheets/_rels/sheet1.xml.rels")
    assert 'Target="/xl/comments/comment1.xml"' in rels
    content_types = _read(path, "[Content_Types].xml")
    assert "/xl/comments/comment1.xml" in content_types
    assert "/xl/comments1.xml" not in content_types


def test_shared_string_cells_are_inlined_before_shared_strings_prune(tmp_path: Path) -> None:
    path = tmp_path / "shared.xlsm"
    _write_package(path, sheet=SHEET_WITH_SHARED_STRING)

    normalize_openpyxl_package_shape(str(path), keep_vba=True)

    names = _names(path)
    assert "xl/sharedStrings.xml" not in names
    sheet = _read(path, "xl/worksheets/sheet1.xml")
    assert 't="inlineStr"' in sheet
    assert "<t>hello</t>" in sheet


def test_picture_drawings_are_retained(tmp_path: Path) -> None:
    path = tmp_path / "picture.xlsm"
    _write_package(path, drawing=PICTURE_DRAWING)

    normalize_openpyxl_package_shape(str(path), keep_vba=True)

    names = _names(path)
    assert "xl/drawings/drawing1.xml" in names
    rels = _read(path, "xl/worksheets/_rels/sheet1.xml.rels")
    assert "relationships/drawing" in rels


def test_keep_vba_false_drops_core_macro_parts(tmp_path: Path) -> None:
    path = tmp_path / "no-vba.xlsx"
    _write_package(path)

    normalize_openpyxl_package_shape(str(path), keep_vba=False)

    names = _names(path)
    assert "xl/vbaProject.bin" not in names
    assert "customUI/customUI.xml" not in names
    assert not any(name.startswith("xl/activeX/") for name in names)
    assert not any(name.startswith("xl/ctrlProps/") for name in names)
    assert "relationships/vbaProject" not in _read(path, "xl/_rels/workbook.xml.rels")
    assert "macroEnabled" not in _read(path, "[Content_Types].xml")
