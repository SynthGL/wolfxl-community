"""Shared string reader compatibility."""

from __future__ import annotations

from wolfxl.cell.rich_text import CellRichText
from wolfxl.cell.text import Text
from wolfxl.xml.constants import SHEET_MAIN_NS
from wolfxl.xml.functions import iterparse


def read_string_table(xml_source):  # noqa: ANN001
    strings = []
    string_tag = f"{{{SHEET_MAIN_NS}}}si"

    for _, node in iterparse(xml_source):
        if node.tag == string_tag:
            text = Text.from_tree(node).content
            strings.append(text.replace("x005F_", ""))
            node.clear()

    return strings


def read_rich_text(xml_source):  # noqa: ANN001
    strings = []
    string_tag = f"{{{SHEET_MAIN_NS}}}si"

    for _, node in iterparse(xml_source):
        if node.tag == string_tag:
            text = CellRichText.from_tree(node)
            if len(text) == 0:
                text = ""
            elif len(text) == 1 and isinstance(text[0], str):
                text = text[0]
            strings.append(text)
            node.clear()

    return strings


__all__ = [
    "CellRichText",
    "SHEET_MAIN_NS",
    "Text",
    "iterparse",
    "read_rich_text",
    "read_string_table",
]
