"""Drawing reader compatibility."""

from __future__ import annotations

from io import BytesIO
from warnings import warn

from wolfxl.drawing.image import Image, PILImage
from wolfxl.chart.chartspace import ChartSpace
from wolfxl.chart.reader import read_chart
from wolfxl.drawing.spreadsheet_drawing import SpreadsheetDrawing
from wolfxl.packaging.relationship import (
    RelationshipList,
    get_dependents,
    get_rel,
    get_rels_path,
)
from wolfxl.xml.constants import IMAGE_NS
from wolfxl.xml.functions import fromstring


def find_images(archive, path):  # noqa: ANN001
    src = archive.read(path)
    tree = fromstring(src)
    try:
        drawing = SpreadsheetDrawing.from_tree(tree)
    except TypeError:
        warn(
            "DrawingML support is incomplete and limited to charts and images only. "
            "Shapes and drawings will be lost."
        )
        return [], []

    rels_path = get_rels_path(path)
    deps = RelationshipList()
    if rels_path in archive.namelist():
        deps = get_dependents(archive, rels_path)

    charts = []
    for rel in drawing._chart_rels:
        try:
            dep = deps.get(rel.id)
            chart_xml = archive.read(dep.target)
            chart_space = ChartSpace.from_tree(fromstring(chart_xml))
            chart = read_chart(chart_space)
        except (KeyError, TypeError, AttributeError) as exc:
            warn(f"Unable to read chart {rel.id} from {path} {exc}")
            continue
        chart.anchor = rel.anchor
        charts.append(chart)

    images = []
    for rel in drawing._blip_rels:
        dep = deps.get(rel.embed)
        if dep.Type != IMAGE_NS:
            continue
        try:
            image = Image(BytesIO(archive.read(dep.target)))
        except (OSError, ValueError):
            warn(f"The image {dep.target} will be removed because it cannot be read")
            continue
        if image.format.upper() == "WMF":
            warn(f"{image.format} image format is not supported so the image is being dropped")
            continue
        image.anchor = rel.anchor
        images.append(image)
    return charts, images


__all__ = [
    "BytesIO",
    "ChartSpace",
    "IMAGE_NS",
    "Image",
    "PILImage",
    "SpreadsheetDrawing",
    "find_images",
    "fromstring",
    "get_dependents",
    "get_rel",
    "get_rels_path",
    "read_chart",
    "warn",
]
