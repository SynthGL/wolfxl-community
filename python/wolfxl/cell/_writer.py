"""Compatibility port of ``openpyxl.cell._writer``.

This module exists so vendored openpyxl tests can call ``write_cell`` with
the same xmlfile-based API the upstream writer uses. wolfxl's production
writer path is Rust-backed and does not consume these functions — they're
only reachable via the openpyxl compatibility surface.

The implementation tracks openpyxl 3.1.5's ``_writer.py``: ``_set_attributes``
encodes the ``<c>`` element's attributes (coordinate, style, data type, date
conversion); ``etree_write_cell`` builds the element tree and writes it
through the supplied ``xf`` context's ``write`` method. The lxml variant
maps to the same etree path because we don't take the lxml-streaming fast
path for compatibility-only callers.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from wolfxl.cell.cell import ArrayFormula, DataTableFormula
from wolfxl.cell.rich_text import CellRichText
from wolfxl.compat.strings import safe_string
from wolfxl.utils.datetime import to_excel, to_ISO8601
from wolfxl.xml.constants import XML_NS
from wolfxl.xml.functions import Element, SubElement, whitespace

LXML = False


def _set_attributes(cell: Any, styled: Any = None) -> tuple[Any, dict[str, str]]:
    """Compute the ``<c>`` element's attributes and the materialized value.

    Mirrors openpyxl's helper, which is what every parametrized
    ``test_writer.py`` case expects. Date conversion respects the
    workbook's ``iso_dates`` and ``epoch`` settings.
    """
    attrs: dict[str, str] = {"r": cell.coordinate}
    if styled:
        attrs["s"] = f"{cell.style_id}"

    if cell.data_type == "s":
        attrs["t"] = "inlineStr"
    elif cell.data_type != "f":
        attrs["t"] = cell.data_type

    value = cell._value

    if cell.data_type == "d":
        if hasattr(value, "tzinfo") and value.tzinfo is not None:
            raise TypeError(
                "Excel does not support timezones in datetimes. "
                "The tzinfo in the datetime/time object must be set to None."
            )
        if cell.parent.parent.iso_dates and not isinstance(value, timedelta):
            value = to_ISO8601(value)
        else:
            attrs["t"] = "n"
            value = to_excel(value, cell.parent.parent.epoch)

    if cell.hyperlink:
        if not hasattr(cell.parent, "_hyperlinks"):
            cell.parent._hyperlinks = []  # noqa: SLF001
        cell.parent._hyperlinks.append(cell.hyperlink)  # noqa: SLF001

    return value, attrs


def etree_write_cell(xf: Any, worksheet: Any, cell: Any, styled: Any = None) -> None:  # noqa: ARG001
    value, attributes = _set_attributes(cell, styled)
    el = Element("c", attributes)
    if value is None or value == "":
        xf.write(el)
        return

    if cell.data_type == "f":
        attrib: dict[str, str] = {}
        if isinstance(value, ArrayFormula) or _is_array_formula_like(value):
            attrib = dict(value)
            value = value.text
        elif isinstance(value, DataTableFormula) or _is_data_table_formula_like(value):
            attrib = dict(value)
            value = None
        formula = SubElement(el, "f", attrib)
        if value is not None and attrib.get("t") != "dataTable":
            formula.text = (
                value[1:] if isinstance(value, str) and value.startswith("=") else value
            )
            value = None

    if cell.data_type == "s":
        if (
            isinstance(value, CellRichText) or _is_cell_rich_text_like(value)
        ) and hasattr(value, "to_tree"):
            el.append(value.to_tree())
        else:
            inline_string = Element("is")
            text = Element("t")
            text.text = value
            whitespace(text)
            inline_string.append(text)
            el.append(inline_string)
    else:
        cell_content = SubElement(el, "v")
        if value is not None:
            cell_content.text = safe_string(value)

    xf.write(el)


lxml_write_cell = etree_write_cell
write_cell = etree_write_cell


def _is_array_formula_like(value: Any) -> bool:
    return (
        getattr(value, "t", None) == "array"
        and hasattr(value, "ref")
        and hasattr(value, "text")
    )


def _is_data_table_formula_like(value: Any) -> bool:
    return getattr(value, "t", None) == "dataTable" and hasattr(value, "ref")


def _is_cell_rich_text_like(value: Any) -> bool:
    return type(value).__name__ == "CellRichText"


def to_excel_passthrough(value: Any) -> Any:  # pragma: no cover - retained shim
    """Kept for any external caller that imported the prior stub."""
    return value


__all__ = [
    "ArrayFormula",
    "CellRichText",
    "DataTableFormula",
    "Element",
    "LXML",
    "SubElement",
    "XML_NS",
    "etree_write_cell",
    "lxml_write_cell",
    "safe_string",
    "timedelta",
    "to_ISO8601",
    "to_excel",
    "whitespace",
    "write_cell",
]
