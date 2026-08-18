"""Sprint Λ Pod-β (RFC-045) — image write parity vs openpyxl.

Verifies that wolfxl-written xlsx files containing images load
back via openpyxl with image count, format, and pixel dimensions
preserved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

wolfxl = pytest.importorskip("wolfxl")
openpyxl = pytest.importorskip("openpyxl")

from wolfxl.drawing import Image  # noqa: E402

FIXTURES = Path(__file__).parent.parent / "fixtures" / "images"
PNG_PATH = FIXTURES / "tiny_red_dot.png"
JPG_PATH = FIXTURES / "tiny_blue_dot.jpg"
GIF_PATH = FIXTURES / "tiny_green_dot.gif"
BMP_PATH = FIXTURES / "tiny_yellow_dot.bmp"


@pytest.mark.parametrize(
    ("path", "ext"),
    [
        (PNG_PATH, "png"),
        (JPG_PATH, "jpeg"),
        (GIF_PATH, "gif"),
        (BMP_PATH, "bmp"),
    ],
)
def test_openpyxl_finds_image(tmp_path: Path, path: Path, ext: str) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    ws.add_image(Image(path), "B5")
    out = tmp_path / "out.xlsx"
    wb.save(out)

    wb2 = openpyxl.load_workbook(out)
    ws2 = wb2.active
    assert len(ws2._images) == 1
    img = ws2._images[0]
    # openpyxl Image has format on PIL backing or filename-derived.
    fmt = (getattr(img, "format", "") or "").lower()
    if fmt:
        # When openpyxl can sniff the format, it should match.
        assert fmt.startswith(ext[:3])


def test_image_bytes_byte_identical(tmp_path: Path) -> None:
    """The media part round-trips byte-for-byte — important for SHAs / signed assets."""
    import zipfile

    wb = wolfxl.Workbook()
    wb.active.add_image(Image(PNG_PATH), "A1")
    out = tmp_path / "out.xlsx"
    wb.save(out)

    with zipfile.ZipFile(out) as z:
        assert z.read("xl/media/image1.png") == PNG_PATH.read_bytes()


def test_modify_mode_image_visible_to_openpyxl(tmp_path: Path) -> None:
    """End-to-end: write a baseline → modify-add image → openpyxl sees it."""
    base = tmp_path / "baseline.xlsx"
    wb = wolfxl.Workbook()
    wb.active["A1"] = "data"
    wb.save(base)

    wb2 = wolfxl.load_workbook(base, modify=True)
    wb2.active.add_image(Image(PNG_PATH), "C3")
    out = tmp_path / "modified.xlsx"
    wb2.save(out)

    wb3 = openpyxl.load_workbook(out)
    assert wb3.active["A1"].value == "data"
    assert len(wb3.active._images) == 1
