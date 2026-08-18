from __future__ import annotations

import zipfile
from pathlib import Path

from wolfxl import load_workbook


def test_copy_worksheet_clones_form_control_properties(tmp_path: Path) -> None:
    src = Path("tests/fixtures/external_oracle/real-excel-control-props-basic.xlsx")
    dst = tmp_path / "copied-control-props.xlsx"

    wb = load_workbook(src, modify=True)
    wb.copy_worksheet(wb.worksheets[0], name="Copied Control Props")
    wb.save(dst)

    with zipfile.ZipFile(dst) as zf:
        names = set(zf.namelist())
        assert "xl/ctrlProps/ctrlProp1.xml" in names
        assert "xl/ctrlProps/ctrlProp2.xml" in names

        sheet2_rels = zf.read("xl/worksheets/_rels/sheet2.xml.rels").decode()
        assert "../ctrlProps/ctrlProp2.xml" in sheet2_rels
        assert "../ctrlProps/ctrlProp1.xml" not in sheet2_rels

        content_types = zf.read("[Content_Types].xml").decode()
        assert 'PartName="/xl/ctrlProps/ctrlProp2.xml"' in content_types

        sheet2 = zf.read("xl/worksheets/sheet2.xml").decode()
        drawing2 = zf.read("xl/drawings/drawing2.xml").decode()
        vml2 = zf.read("xl/drawings/vmlDrawing2.vml").decode()
        assert 'shapeId="2049"' in sheet2
        assert 'shapeId="1025"' not in sheet2
        assert 'id="2049"' in drawing2
        assert 'spid="_x0000_s2049"' in drawing2
        assert 'data="2"' in vml2
        assert 'id="_x0000_s2049"' in vml2
