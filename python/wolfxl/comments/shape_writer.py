"""Comment VML shape writer compatibility."""

from __future__ import annotations

from wolfxl.utils.cell import coordinate_to_tuple
from wolfxl.xml.functions import Element, SubElement, tostring

excelns = "urn:schemas-microsoft-com:office:excel"
officens = "urn:schemas-microsoft-com:office:office"
vmlns = "urn:schemas-microsoft-com:vml"


class ShapeWriter:
    def __init__(self, comments: object | None = None) -> None:
        self.comments = comments

    def add_comment_shapetype(self, root: object) -> None:
        shape_layout = SubElement(
            root,
            f"{{{officens}}}shapelayout",
            {f"{{{vmlns}}}ext": "edit"},
        )
        SubElement(
            shape_layout,
            f"{{{officens}}}idmap",
            {f"{{{vmlns}}}ext": "edit", "data": "1"},
        )
        shape_type = SubElement(
            root,
            f"{{{vmlns}}}shapetype",
            {
                "id": "_x0000_t202",
                "coordsize": "21600,21600",
                f"{{{officens}}}spt": "202",
                "path": "m,l,21600r21600,l21600,xe",
            },
        )
        SubElement(shape_type, f"{{{vmlns}}}stroke", {"joinstyle": "miter"})
        SubElement(
            shape_type,
            f"{{{vmlns}}}path",
            {
                "gradientshapeok": "t",
                f"{{{officens}}}connecttype": "rect",
            },
        )

    def add_comment_shape(
        self,
        root: object,
        idx: int,
        coord: str,
        height: int | None,
        width: int | None,
    ) -> None:
        row, col = coordinate_to_tuple(coord)
        shape = _shape_factory(row - 1, col - 1, height or 79, width or 144)
        shape.set("id", f"_x0000_s{idx:04d}")
        root.append(shape)

    def write(self, root: object | None = None) -> bytes:
        node = root if hasattr(root, "findall") else Element("xml")

        comments = node.findall(f"{{{vmlns}}}shape[@type='#_x0000_t202']")
        for comment in comments:
            node.remove(comment)

        shape_type = node.find(f"{{{vmlns}}}shapetype[@id='_x0000_t202']")
        if shape_type is None:
            self.add_comment_shapetype(node)

        for idx, (coord, comment) in enumerate(self.comments or (), 1026):
            self.add_comment_shape(
                node,
                idx,
                coord,
                getattr(comment, "height", None),
                getattr(comment, "width", None),
            )

        return tostring(node)


def _shape_factory(row: int, column: int, height: int, width: int) -> object:
    style = (
        "position:absolute; "
        "margin-left:59.25pt;"
        "margin-top:1.5pt;"
        f"width:{width}px;"
        f"height:{height}px;"
        "z-index:1;"
        "visibility:hidden"
    )
    shape = Element(
        f"{{{vmlns}}}shape",
        {
            "type": "#_x0000_t202",
            "style": style,
            "fillcolor": "#ffffe1",
            f"{{{officens}}}insetmode": "auto",
        },
    )

    SubElement(shape, f"{{{vmlns}}}fill", {"color2": "#ffffe1"})
    SubElement(shape, f"{{{vmlns}}}shadow", {"color": "black", "obscured": "t"})
    SubElement(shape, f"{{{vmlns}}}path", {f"{{{officens}}}connecttype": "none"})
    textbox = SubElement(
        shape,
        f"{{{vmlns}}}textbox",
        {"style": "mso-direction-alt:auto"},
    )
    SubElement(textbox, "div", {"style": "text-align:left"})
    client_data = SubElement(
        shape,
        f"{{{excelns}}}ClientData",
        {"ObjectType": "Note"},
    )
    SubElement(client_data, f"{{{excelns}}}MoveWithCells")
    SubElement(client_data, f"{{{excelns}}}SizeWithCells")
    SubElement(client_data, f"{{{excelns}}}AutoFill").text = "False"
    SubElement(client_data, f"{{{excelns}}}Row").text = str(row)
    SubElement(client_data, f"{{{excelns}}}Column").text = str(column)
    return shape


__all__ = [
    "Element",
    "ShapeWriter",
    "SubElement",
    "_shape_factory",
    "coordinate_to_tuple",
    "excelns",
    "officens",
    "tostring",
    "vmlns",
]
