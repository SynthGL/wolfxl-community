"""RFC-035 Sprint Θ Pod-C2 — ``wb.copy_options.deep_copy_images``.

Tests that:
- Default (alias) mode keeps cloned drawing rels pointing at the
  same ``xl/media/imageN.<ext>`` path as the source (no new image
  bytes added to the saved zip).
- With ``wb.copy_options.deep_copy_images = True``, cloned drawing
  rels point at a freshly numbered ``xl/media/imageM.<ext>``, the
  new image bytes are present in the saved zip, and the original
  remains intact.

The fixture is hand-assembled at the ZIP level so we don't need
Pillow (openpyxl's image API requires it).
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

from wolfxl import CopyOptions, load_workbook


pytestmark = pytest.mark.rfc035


@pytest.fixture(autouse=True)
def _force_test_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WOLFXL_TEST_EPOCH", "0")


# A non-empty placeholder; the planner only copies bytes verbatim.
_DUMMY_IMG = b"\x89PNG\r\n\x1a\nfake-image-bytes-for-tests"


# Hand-rolled minimal OOXML parts for a workbook with one sheet that
# references a drawing pointing at xl/media/image1.png.
_CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
  <Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>
</Types>"""

_RELS_ROOT = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WORKBOOK_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Template" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

_WORKBOOK_RELS = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>"""

_SHEET1_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:A2"/>
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>0</v></c></row>
    <row r="2"><c r="A2"><v>1</v></c></row>
  </sheetData>
  <drawing r:id="rId1"/>
</worksheet>"""

_SHEET1_RELS = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>
</Relationships>"""

_DRAWING1_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <xdr:oneCellAnchor>
    <xdr:from><xdr:col>2</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>2</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>
    <xdr:ext cx="100000" cy="100000"/>
    <xdr:pic>
      <xdr:nvPicPr><xdr:cNvPr id="1" name="img"/><xdr:cNvPicPr/></xdr:nvPicPr>
      <xdr:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>
      <xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="100000" cy="100000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>
    </xdr:pic>
    <xdr:clientData/>
  </xdr:oneCellAnchor>
</xdr:wsDr>"""

_DRAWING1_RELS = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>"""

_STYLES_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0"/></cellXfs>
</styleSheet>"""

_SHARED_STRINGS = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1"><si><t>header</t></si></sst>"""


def _make_image_fixture(path: Path) -> None:
    """Build a minimal workbook with one sheet and one PNG image part."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS_ROOT)
        z.writestr("xl/workbook.xml", _WORKBOOK_XML)
        z.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        z.writestr("xl/styles.xml", _STYLES_XML)
        z.writestr("xl/sharedStrings.xml", _SHARED_STRINGS)
        z.writestr("xl/worksheets/sheet1.xml", _SHEET1_XML)
        z.writestr("xl/worksheets/_rels/sheet1.xml.rels", _SHEET1_RELS)
        z.writestr("xl/drawings/drawing1.xml", _DRAWING1_XML)
        z.writestr("xl/drawings/_rels/drawing1.xml.rels", _DRAWING1_RELS)
        z.writestr("xl/media/image1.png", _DUMMY_IMG)


def _list_zip_entries(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as z:
        return z.namelist()


def _read_drawing_rels(path: Path, drawing_n: int) -> bytes:
    with zipfile.ZipFile(path, "r") as z:
        return z.read(f"xl/drawings/_rels/drawing{drawing_n}.xml.rels")


# ---------------------------------------------------------------------------
# A — Fixture validation: openpyxl really did embed an image.
# ---------------------------------------------------------------------------


def test_a_fixture_has_image_part(tmp_path: Path) -> None:
    src = tmp_path / "src.xlsx"
    _make_image_fixture(src)
    entries = _list_zip_entries(src)
    media = [e for e in entries if e.startswith("xl/media/image")]
    assert media, f"fixture missing image part; entries={entries}"


# ---------------------------------------------------------------------------
# B — Default (alias) behavior: no new image part, drawing rels unchanged.
# ---------------------------------------------------------------------------


def test_b_default_aliases_image(tmp_path: Path) -> None:
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    _make_image_fixture(src)

    wb = load_workbook(src, modify=True)
    # Default: copy_options.deep_copy_images is False.
    assert isinstance(wb.copy_options, CopyOptions)
    assert wb.copy_options.deep_copy_images is False
    src_ws = wb["Template"]
    wb.copy_worksheet(src_ws)
    wb.save(dst)

    entries = _list_zip_entries(dst)
    media_entries = [e for e in entries if e.startswith("xl/media/image")]
    # Default = alias mode → exactly the original media files; no new
    # imageM.<ext> appears.
    assert len(media_entries) == 1, (
        f"alias mode must not add image parts; got {media_entries}"
    )

    # Drawings: there should be TWO drawing parts now (one per sheet),
    # but both rels files reference the same `imageN.<ext>` target.
    drawing_n_re = re.compile(r"^xl/drawings/drawing(\d+)\.xml$")
    drawing_ns = sorted(
        int(m.group(1))
        for m in (drawing_n_re.match(e) for e in entries)
        if m is not None
    )
    assert len(drawing_ns) >= 2, f"expected >= 2 drawings; got {drawing_ns}"
    targets_seen: set[str] = set()
    for n in drawing_ns:
        rels = _read_drawing_rels(dst, n).decode()
        # Pull every Target= attribute value.
        for tgt in re.findall(r'Target="([^"]+)"', rels):
            if "image" in tgt:
                targets_seen.add(tgt)
    assert len(targets_seen) == 1, (
        f"alias mode: every drawing rels target should be the same; "
        f"got {targets_seen}"
    )


# ---------------------------------------------------------------------------
# C — Deep-clone mode: new image part, cloned rels point at it.
# ---------------------------------------------------------------------------


def test_c_deep_clone_creates_new_image_part(tmp_path: Path) -> None:
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    _make_image_fixture(src)

    wb = load_workbook(src, modify=True)
    wb.copy_options.deep_copy_images = True
    src_ws = wb["Template"]
    wb.copy_worksheet(src_ws)
    wb.save(dst)

    entries = _list_zip_entries(dst)
    media_entries = sorted(e for e in entries if e.startswith("xl/media/image"))
    # Exactly two media entries now: original + cloned.
    assert len(media_entries) == 2, (
        f"deep-clone mode must add a new image part; got {media_entries}"
    )

    # Each drawing rels file should point at a DIFFERENT image target.
    drawing_n_re = re.compile(r"^xl/drawings/drawing(\d+)\.xml$")
    drawing_ns = sorted(
        int(m.group(1))
        for m in (drawing_n_re.match(e) for e in entries)
        if m is not None
    )
    assert len(drawing_ns) >= 2, f"expected >= 2 drawings; got {drawing_ns}"
    targets_seen: list[str] = []
    for n in drawing_ns:
        rels = _read_drawing_rels(dst, n).decode()
        for tgt in re.findall(r'Target="([^"]+)"', rels):
            if "image" in tgt:
                targets_seen.append(tgt)
    assert len(set(targets_seen)) == 2, (
        f"deep-clone mode: each drawing rels should point at a "
        f"distinct image target; got {targets_seen}"
    )

    # All distinct targets should resolve back to entries that exist
    # in the saved zip.
    with zipfile.ZipFile(dst, "r") as z:
        names = set(z.namelist())
    for tgt in set(targets_seen):
        # Drawing rels targets are like `../media/imageN.<ext>`.
        resolved = tgt.replace("../", "xl/")
        assert resolved in names, (
            f"deep-clone target {tgt} ({resolved}) missing from "
            f"saved zip; have {sorted(n for n in names if 'image' in n)}"
        )


# ---------------------------------------------------------------------------
# D — Toggling deep_copy_images mid-session: per-call snapshot.
# ---------------------------------------------------------------------------


def test_d_per_copy_snapshot_of_flag(tmp_path: Path) -> None:
    """The flag is captured at copy_worksheet() call time, not save time."""
    src = tmp_path / "src.xlsx"
    dst = tmp_path / "dst.xlsx"
    _make_image_fixture(src)

    wb = load_workbook(src, modify=True)
    src_ws = wb["Template"]

    # First copy: default alias-mode.
    wb.copy_worksheet(src_ws)
    # Toggle for the second copy.
    wb.copy_options.deep_copy_images = True
    wb.copy_worksheet(src_ws)
    # Toggle back — must NOT retroactively flip the queued copies.
    wb.copy_options.deep_copy_images = False

    wb.save(dst)

    entries = _list_zip_entries(dst)
    media_entries = sorted(e for e in entries if e.startswith("xl/media/image"))
    # Original + ONE clone (the second copy in deep-clone mode).
    # The first copy aliased.
    assert len(media_entries) == 2, (
        f"per-call snapshot: expected 2 image parts (1 original + 1 "
        f"deep-cloned); got {media_entries}"
    )
