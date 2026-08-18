"""Sprint Λ Pod-β (RFC-045) — write-mode image tests.

Verifies that ``Worksheet.add_image(Image(...))`` in write mode
produces a structurally-valid xlsx with:

* ``xl/drawings/drawingN.xml`` (oneCellAnchor / twoCellAnchor)
* ``xl/drawings/_rels/drawingN.xml.rels`` (image rel)
* ``xl/media/imageM.<ext>`` (byte-identical to source)
* ``xl/worksheets/sheetN.xml`` carries ``<drawing r:id="..."/>``
* ``xl/worksheets/_rels/sheetN.xml.rels`` carries the drawing rel
* ``[Content_Types].xml`` carries ``Default Extension=...`` +
  ``Override PartName=...``

All four supported image formats (PNG, JPEG, GIF, BMP) round-trip.
openpyxl can read the result back and finds the image.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.drawing import Image

FIXTURES = Path(__file__).parent / "fixtures" / "images"

PNG_PATH = FIXTURES / "tiny_red_dot.png"
JPG_PATH = FIXTURES / "tiny_blue_dot.jpg"
GIF_PATH = FIXTURES / "tiny_green_dot.gif"
BMP_PATH = FIXTURES / "tiny_yellow_dot.bmp"


# ---------------------------------------------------------------------------
# Image() constructor
# ---------------------------------------------------------------------------


def test_image_from_path_png() -> None:
    img = Image(PNG_PATH)
    assert img.format == "png"
    assert img.width > 0
    assert img.height > 0
    assert img.path == str(PNG_PATH)


def test_image_from_path_jpeg() -> None:
    img = Image(JPG_PATH)
    assert img.format == "jpeg"


def test_image_from_path_gif() -> None:
    img = Image(GIF_PATH)
    assert img.format == "gif"


def test_image_from_path_bmp() -> None:
    img = Image(BMP_PATH)
    assert img.format == "bmp"


def test_image_from_bytesio() -> None:
    data = PNG_PATH.read_bytes()
    img = Image(io.BytesIO(data))
    assert img.format == "png"
    assert img.path is None


def test_image_from_bytes() -> None:
    data = PNG_PATH.read_bytes()
    img = Image(data)
    assert img.format == "png"


def test_image_unknown_format_rejected() -> None:
    with pytest.raises(ValueError, match="(?i)image format"):
        Image(b"not an image")


# ---------------------------------------------------------------------------
# Write-mode round-trip
# ---------------------------------------------------------------------------


def _save(wb: wolfxl.Workbook, tmp_path: Path) -> Path:
    out = tmp_path / "out.xlsx"
    wb.save(out)
    return out


def test_write_mode_png_round_trip(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "anchor"
    ws.add_image(Image(PNG_PATH), "B5")
    out = _save(wb, tmp_path)

    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert "xl/drawings/drawing1.xml" in names
        assert "xl/drawings/_rels/drawing1.xml.rels" in names
        assert "xl/media/image1.png" in names

        # Media bytes are byte-identical to the source file.
        assert z.read("xl/media/image1.png") == PNG_PATH.read_bytes()

        # Sheet XML carries <drawing r:id="..."/>
        s1 = z.read("xl/worksheets/sheet1.xml").decode()
        assert "<drawing r:id=" in s1

        # Sheet rels has a drawing rel
        rels = z.read("xl/worksheets/_rels/sheet1.xml.rels").decode()
        assert "/relationships/drawing" in rels
        assert "../drawings/drawing1.xml" in rels

        # Drawing rels has an image rel
        d_rels = z.read("xl/drawings/_rels/drawing1.xml.rels").decode()
        assert "/relationships/image" in d_rels
        assert "../media/image1.png" in d_rels

        # Content types: Default Extension="png" + Override
        ct = z.read("[Content_Types].xml").decode()
        assert 'Extension="png"' in ct
        assert 'ContentType="image/png"' in ct
        assert "/xl/drawings/drawing1.xml" in ct


@pytest.mark.parametrize(
    ("path", "ext", "ct"),
    [
        (PNG_PATH, "png", "image/png"),
        (JPG_PATH, "jpeg", "image/jpeg"),
        (GIF_PATH, "gif", "image/gif"),
        (BMP_PATH, "bmp", "image/bmp"),
    ],
)
def test_write_mode_all_formats(
    tmp_path: Path, path: Path, ext: str, ct: str
) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws.add_image(Image(path), "C3")
    out = _save(wb, tmp_path)

    with zipfile.ZipFile(out) as z:
        media = f"xl/media/image1.{ext}"
        assert media in z.namelist()
        assert z.read(media) == path.read_bytes()

        ct_xml = z.read("[Content_Types].xml").decode()
        assert f'Extension="{ext}"' in ct_xml
        assert f'ContentType="{ct}"' in ct_xml


def test_openpyxl_reads_back(tmp_path: Path) -> None:
    """openpyxl can load the wolfxl-written file and find the image."""
    openpyxl = pytest.importorskip("openpyxl")

    wb = wolfxl.Workbook()
    ws = wb.active
    ws["A1"] = "hello"
    ws.add_image(Image(PNG_PATH), "B5")
    out = _save(wb, tmp_path)

    wb2 = openpyxl.load_workbook(out)
    ws2 = wb2.active
    assert ws2["A1"].value == "hello"
    assert len(ws2._images) == 1


def test_multiple_images_one_sheet(tmp_path: Path) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws.add_image(Image(PNG_PATH), "B2")
    ws.add_image(Image(JPG_PATH), "D4")
    ws.add_image(Image(GIF_PATH), "F6")
    out = _save(wb, tmp_path)

    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        # A single drawing part holds all three images.
        assert "xl/drawings/drawing1.xml" in names
        # Three media parts, globally numbered.
        assert "xl/media/image1.png" in names
        assert "xl/media/image2.jpeg" in names
        assert "xl/media/image3.gif" in names

        d_rels = z.read("xl/drawings/_rels/drawing1.xml.rels").decode()
        assert d_rels.count("/relationships/image") == 3
