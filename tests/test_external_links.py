"""Focused tests for the workbook-level external-link collection (G18).

Covers RFC-071 §6.2:

* empty case (a freshly-saved workbook has no external-link parts)
* forward-ref formula (the compat-oracle probe scenario)
* real fixture round-trip (a hand-built xlsx with one external link)
* alias check (``wb.external_links is wb._external_links``)
* modify-mode preservation (the patcher round-trips the bytes)
* ``keep_links=False`` hides links in read mode and drops external-link
  OOXML parts in modify mode
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl import ExternalLink

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "external_links_basic.xlsx"
REAL_EXCEL_FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "external_oracle"
    / "real-excel-external-link-basic.xlsx"
)


def _build_external_link_fixture() -> bytes:
    """Hand-build a minimal xlsx with one external link.

    The result has:

    * one worksheet (``Sheet``) with a single forward-reference formula
      cell ``A1`` that points at ``'[ext.xlsx]Sheet1'!$A$1``;
    * one ``xl/externalLinks/externalLink1.xml`` part referencing
      ``Sheet1`` in an external workbook;
    * a sibling ``xl/externalLinks/_rels/externalLink1.xml.rels`` whose
      sole rel is an ``externalLinkPath`` to ``ext.xlsx``;
    * the workbook-rels graph wired up with ``rId1=externalLink``;
    * ``[Content_Types].xml`` declares the externalLink override.

    Built once at import time and cached on disk so we keep the fixture
    folder source-controlled (real files in ``tests/fixtures/``). When
    the file already exists we trust its bytes.
    """
    parts: dict[str, bytes] = {}

    parts["[Content_Types].xml"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        b'<Default Extension="xml" ContentType="application/xml"/>'
        b'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        b'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        b'<Override PartName="/xl/externalLinks/externalLink1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.externalLink+xml"/>'
        b'<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        b"</Types>"
    )

    parts["_rels/.rels"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        b'Target="xl/workbook.xml"/>'
        b"</Relationships>"
    )

    parts["xl/workbook.xml"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        b' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        b'<sheets><sheet name="Sheet" sheetId="1" r:id="rId1"/></sheets>'
        b'<externalReferences><externalReference r:id="rId2"/></externalReferences>'
        b"</workbook>"
    )

    parts["xl/_rels/workbook.xml.rels"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        b'Target="worksheets/sheet1.xml"/>'
        b'<Relationship Id="rId2" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLink" '
        b'Target="externalLinks/externalLink1.xml"/>'
        b'<Relationship Id="rId3" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        b'Target="styles.xml"/>'
        b"</Relationships>"
    )

    parts["xl/worksheets/sheet1.xml"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        b'<sheetData><row r="1"><c r="A1"><f>=\'[ext.xlsx]Sheet1\'!$A$1</f><v>99</v></c></row></sheetData>'
        b"</worksheet>"
    )

    parts["xl/externalLinks/externalLink1.xml"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        b' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        b'<externalBook r:id="rId1">'
        b"<sheetNames><sheetName val=\"Sheet1\"/></sheetNames>"
        b'<sheetDataSet><sheetData sheetId="0">'
        b'<row r="1"><cell r="A1"><v>99</v></cell></row>'
        b"</sheetData></sheetDataSet>"
        b"</externalBook></externalLink>"
    )

    parts["xl/externalLinks/_rels/externalLink1.xml.rels"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath" '
        b'Target="ext.xlsx" TargetMode="External"/>'
        b"</Relationships>"
    )

    parts["xl/styles.xml"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        b"<fonts count=\"1\"><font><sz val=\"11\"/><name val=\"Calibri\"/></font></fonts>"
        b"<fills count=\"1\"><fill><patternFill patternType=\"none\"/></fill></fills>"
        b"<borders count=\"1\"><border/></borders>"
        b"<cellStyleXfs count=\"1\"><xf/></cellStyleXfs>"
        b"<cellXfs count=\"1\"><xf/></cellXfs>"
        b"</styleSheet>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _build_two_external_links_fixture(path: Path) -> Path:
    """Clone the one-link fixture and add a second external link part."""
    src = _build_external_link_fixture()
    parts: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(src), "r") as zf:
        for name in zf.namelist():
            parts[name] = zf.read(name)

    parts["xl/externalLinks/externalLink2.xml"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        b' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        b'<externalBook r:id="rId1"><sheetNames><sheetName val="Sheet2"/></sheetNames>'
        b"</externalBook></externalLink>"
    )
    parts["xl/externalLinks/_rels/externalLink2.xml.rels"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath" '
        b'Target="ext2.xlsx" TargetMode="External"/>'
        b"</Relationships>"
    )
    parts["xl/workbook.xml"] = parts["xl/workbook.xml"].replace(
        b'<externalReferences><externalReference r:id="rId2"/></externalReferences>',
        b'<externalReferences><externalReference r:id="rId2"/><externalReference r:id="rId4"/></externalReferences>',
    )
    parts["xl/_rels/workbook.xml.rels"] = parts["xl/_rels/workbook.xml.rels"].replace(
        b"</Relationships>",
        b'<Relationship Id="rId4" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLink" '
        b'Target="externalLinks/externalLink2.xml"/></Relationships>',
    )
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
        b"</Types>",
        b'<Override PartName="/xl/externalLinks/externalLink2.xml" '
        b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.externalLink+xml"/>'
        b"</Types>",
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)
    return path


@pytest.fixture(scope="module")
def fixture_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Yield the on-disk fixture, copied to a tmp path for hermetic mods.

    The canonical bytes live at ``tests/fixtures/external_links_basic.xlsx``
    so the layout is grep-able and inspectable. We copy them into a
    per-test tmpdir so modify-mode round-trip tests (which write back
    to the same path) don't churn the source-controlled fixture.

    If the disk fixture is missing (e.g. someone deleted it), we
    re-synthesise from :func:`_build_external_link_fixture` so the
    suite still runs green.
    """
    p = tmp_path_factory.mktemp("g18") / "external_links_basic.xlsx"
    if FIXTURE_PATH.is_file():
        p.write_bytes(FIXTURE_PATH.read_bytes())
    else:  # pragma: no cover - safety net for fresh checkouts
        p.write_bytes(_build_external_link_fixture())
    return p


# --------------------------------------------------------------------------
# RFC-071 §6.2 cases
# --------------------------------------------------------------------------


def test_empty_case_write_mode_workbook() -> None:
    """A freshly-created Workbook() exposes an empty list."""
    wb = wolfxl.Workbook()
    assert wb._external_links == []
    assert wb.external_links == []


def test_forward_ref_formula_round_trip(tmp_path: Path) -> None:
    """The compat-oracle probe scenario verbatim.

    Saving a workbook whose only contact with external workbooks is a
    forward-reference formula in a cell shouldn't synthesise any
    ``xl/externalLinks/`` parts (we don't author them in v1.0). Reload
    yields an empty list.
    """
    wb = wolfxl.Workbook()
    wb.active["A1"] = "='[ext.xlsx]Sheet1'!$A$1"
    out = tmp_path / "ext.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out, "r") as zf:
        names = set(zf.namelist())
    assert not any(n.startswith("xl/externalLinks/") for n in names)

    wb2 = wolfxl.load_workbook(out)
    assert wb2._external_links == []


def test_real_fixture_exposes_link(fixture_path: Path) -> None:
    """The hand-built fixture exposes one ExternalLink with the right shape."""
    wb = wolfxl.load_workbook(fixture_path)
    links = wb._external_links
    assert len(links) == 1
    link = links[0]
    assert link.target == "ext.xlsx"
    assert link.sheet_names == ["Sheet1"]
    assert link.file_link.target == "ext.xlsx"
    assert link.file_link.target_mode == "External"
    assert link.rid == "rId2"  # the externalLink rel id in the workbook rels


def test_keep_links_false_hides_links_in_read_mode(fixture_path: Path) -> None:
    wb = wolfxl.load_workbook(fixture_path, keep_links=False)
    assert wb._external_links == []
    assert wb.external_links == []


def test_bytes_backed_external_links_are_loaded(fixture_path: Path) -> None:
    data = fixture_path.read_bytes()
    for source in (data, io.BytesIO(data)):
        wb = wolfxl.load_workbook(source)
        assert len(wb._external_links) == 1
        assert wb._external_links[0].target == "ext.xlsx"


def test_real_excel_xl_path_missing_external_link_target_loads() -> None:
    wb = wolfxl.load_workbook(REAL_EXCEL_FIXTURE_PATH)

    assert len(wb._external_links) == 1
    link = wb._external_links[0]
    assert link.target == "wolfxl_excel_link_source.xlsx"
    assert link.file_link is not None
    assert link.file_link.target == "wolfxl_excel_link_source.xlsx"
    assert link.file_link.target_mode == "External"
    assert link.sheet_names == ["Sheet1"]


def test_modify_mode_preserves_external_link_bytes(
    fixture_path: Path, tmp_path: Path
) -> None:
    """``modify=True`` save preserves ``xl/externalLinks/`` parts byte-for-byte."""
    wb = wolfxl.load_workbook(fixture_path, modify=True)
    out = tmp_path / "round_trip.xlsx"
    wb.save(out)

    # Fixture bytes for the two parts we care about.
    with zipfile.ZipFile(fixture_path, "r") as src_zf:
        src_part = src_zf.read("xl/externalLinks/externalLink1.xml")
        src_rels = src_zf.read("xl/externalLinks/_rels/externalLink1.xml.rels")
    with zipfile.ZipFile(out, "r") as dst_zf:
        dst_part = dst_zf.read("xl/externalLinks/externalLink1.xml")
        dst_rels = dst_zf.read("xl/externalLinks/_rels/externalLink1.xml.rels")

    assert dst_part == src_part
    assert dst_rels == src_rels

    # And the reload still surfaces the same link.
    wb2 = wolfxl.load_workbook(out)
    assert len(wb2._external_links) == 1
    assert wb2._external_links[0].target == "ext.xlsx"


def test_modify_mode_keep_links_false_drops_external_link_parts(
    fixture_path: Path, tmp_path: Path
) -> None:
    wb = wolfxl.load_workbook(fixture_path, modify=True, keep_links=False)
    assert wb._external_links == []
    out = tmp_path / "dropped_links.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out, "r") as zf:
        names = set(zf.namelist())
        assert not any(name.startswith("xl/externalLinks/") for name in names)
        workbook_xml = zf.read("xl/workbook.xml").decode()
        workbook_rels = zf.read("xl/_rels/workbook.xml.rels").decode()
        content_types = zf.read("[Content_Types].xml").decode()

    assert "externalReferences" not in workbook_xml
    assert "/relationships/externalLink" not in workbook_rels
    assert "externalLink+xml" not in content_types


def test_modify_mode_keep_links_false_drops_multiple_external_links(
    tmp_path: Path,
) -> None:
    fixture = _build_two_external_links_fixture(tmp_path / "two_external_links.xlsx")
    wb = wolfxl.load_workbook(fixture, modify=True, keep_links=False)
    out = tmp_path / "dropped_two_links.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out, "r") as zf:
        names = set(zf.namelist())
        workbook_xml = zf.read("xl/workbook.xml").decode()
        workbook_rels = zf.read("xl/_rels/workbook.xml.rels").decode()
        content_types = zf.read("[Content_Types].xml").decode()

    assert not any(name.startswith("xl/externalLinks/") for name in names)
    assert "externalReferences" not in workbook_xml
    assert "/relationships/externalLink" not in workbook_rels
    assert "externalLink+xml" not in content_types


def test_keep_links_false_composes_with_sheet_create_rels(tmp_path: Path) -> None:
    fixture = _build_two_external_links_fixture(tmp_path / "source_with_links.xlsx")
    wb = wolfxl.load_workbook(fixture, modify=True, keep_links=False)
    added = wb.create_sheet("Added")
    added["A1"] = "kept"
    out = tmp_path / "links_dropped_sheet_added.xlsx"
    wb.save(out)
    wb.close()

    with zipfile.ZipFile(out, "r") as zf:
        names = set(zf.namelist())
        workbook_xml = zf.read("xl/workbook.xml").decode("utf-8")
        workbook_rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        content_types = zf.read("[Content_Types].xml").decode("utf-8")

    assert not any(name.startswith("xl/externalLinks/") for name in names)
    assert "externalReferences" not in workbook_xml
    assert "/relationships/externalLink" not in workbook_rels
    assert "externalLink+xml" not in content_types
    assert 'name="Added"' in workbook_xml
    assert "worksheets/sheet2.xml" in workbook_rels
    assert "xl/worksheets/sheet2.xml" in names

    reloaded = wolfxl.load_workbook(out, read_only=True)
    assert reloaded["Added"]["A1"].value == "kept"
    assert reloaded._external_links == []


def test_external_links_alias_is_same_list(fixture_path: Path) -> None:
    """``wb.external_links`` and ``wb._external_links`` return the same list.

    The properties compute lazily; identity holds because both wrap the
    cached instance the first call materialised on the workbook.
    """
    wb = wolfxl.load_workbook(fixture_path)
    assert wb.external_links is wb._external_links


def test_write_mode_append_external_link_authors_parts(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    wb.active["A1"] = "='[linked.xlsx]Sheet1'!$A$1"
    wb._external_links.append(ExternalLink(target="linked.xlsx", sheet_names=["Sheet1"]))
    out = tmp_path / "authored.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out, "r") as zf:
        names = set(zf.namelist())
        wb_xml = zf.read("xl/workbook.xml").decode("utf-8")
        wb_rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        link_xml = zf.read("xl/externalLinks/externalLink1.xml").decode("utf-8")
        link_rels = zf.read("xl/externalLinks/_rels/externalLink1.xml.rels").decode("utf-8")
        ct_xml = zf.read("[Content_Types].xml").decode("utf-8")

    assert "xl/externalLinks/externalLink1.xml" in names
    assert "<externalReferences>" in wb_xml
    assert "relationships/externalLink" in wb_rels
    assert "linked.xlsx" in link_rels
    assert 'sheetName val="Sheet1"' in link_xml
    assert "/xl/externalLinks/externalLink1.xml" in ct_xml

    wb2 = wolfxl.load_workbook(out)
    assert len(wb2._external_links) == 1
    assert wb2._external_links[0].target == "linked.xlsx"


def test_modify_mode_append_external_link_preserves_existing_and_adds_new(
    fixture_path: Path, tmp_path: Path
) -> None:
    src = tmp_path / "src.xlsx"
    src.write_bytes(fixture_path.read_bytes())
    wb = wolfxl.load_workbook(src, modify=True)
    wb._external_links.append(ExternalLink(target="other.xlsx", sheet_names=["Other"]))
    out = tmp_path / "out.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out, "r") as zf:
        names = set(zf.namelist())
        assert "xl/externalLinks/externalLink1.xml" in names
        assert "xl/externalLinks/externalLink2.xml" in names
        assert "ext.xlsx" in zf.read(
            "xl/externalLinks/_rels/externalLink1.xml.rels"
        ).decode("utf-8")
        assert "other.xlsx" in zf.read(
            "xl/externalLinks/_rels/externalLink2.xml.rels"
        ).decode("utf-8")

    wb2 = wolfxl.load_workbook(out)
    assert [link.target for link in wb2._external_links] == ["ext.xlsx", "other.xlsx"]


def test_remove_external_link_prunes_parts_and_workbook_wiring(
    fixture_path: Path, tmp_path: Path
) -> None:
    wb = wolfxl.load_workbook(fixture_path, modify=True)
    wb._external_links.clear()
    out = tmp_path / "removed.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out, "r") as zf:
        names = set(zf.namelist())
        wb_xml = zf.read("xl/workbook.xml").decode("utf-8")
        wb_rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        ct_xml = zf.read("[Content_Types].xml").decode("utf-8")

    assert not any(name.startswith("xl/externalLinks/") for name in names)
    assert "<externalReferences>" not in wb_xml
    assert "relationships/externalLink" not in wb_rels
    assert "/xl/externalLinks/" not in ct_xml


def test_keep_links_false_modify_save_strips_external_links(
    fixture_path: Path, tmp_path: Path
) -> None:
    wb = wolfxl.load_workbook(fixture_path, modify=True, keep_links=False)
    out = tmp_path / "keep_links_false.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out, "r") as zf:
        names = set(zf.namelist())
        wb_xml = zf.read("xl/workbook.xml").decode("utf-8")
        wb_rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        ct_xml = zf.read("[Content_Types].xml").decode("utf-8")

    assert not any(name.startswith("xl/externalLinks/") for name in names)
    assert "<externalReferences>" not in wb_xml
    assert "relationships/externalLink" not in wb_rels
    assert "/xl/externalLinks/" not in ct_xml


def test_update_external_link_target_rewrites_link_rels(
    fixture_path: Path, tmp_path: Path
) -> None:
    wb = wolfxl.load_workbook(fixture_path, modify=True)
    wb._external_links[0].update_target("renamed.xlsx")
    out = tmp_path / "retargeted.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out, "r") as zf:
        rels = zf.read("xl/externalLinks/_rels/externalLink1.xml.rels").decode("utf-8")
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")

    assert "renamed.xlsx" in rels
    assert "ext.xlsx" not in rels
    assert "[renamed.xlsx]Sheet1" in sheet
    assert "[ext.xlsx]Sheet1" not in sheet
    wb2 = wolfxl.load_workbook(out)
    assert wb2._external_links[0].target == "renamed.xlsx"


def test_update_external_link_targets_rewrite_formulas_without_cascading(
    tmp_path: Path,
) -> None:
    fixture = _build_two_external_links_fixture(tmp_path / "two_external_links.xlsx")
    wb = wolfxl.load_workbook(fixture, modify=True)
    wb._external_links[0].update_target("ext2.xlsx")
    wb._external_links[1].update_target("final.xlsx")
    out = tmp_path / "retargeted_without_cascade.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out, "r") as zf:
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")

    assert "[ext2.xlsx]Sheet1" in sheet
    assert "[final.xlsx]Sheet1" not in sheet
