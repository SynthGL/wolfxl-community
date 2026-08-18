""":class:`PivotTableHandle` — modify-mode proxy for an existing pivot table.

Returned from ``Worksheet.pivot_tables`` for a pivot table that was
parsed off disk. Carries the metadata required to round-trip source
and layout edits:

- ``name`` (read-only) — the ``<pivotTableDefinition name="...">``.
- ``location`` (read-only) — the ``<location ref="A1:E20">`` string.
- ``cache_id`` (read-only) — the workbook-scope cache id.
- ``source`` (read/write) — a :class:`Reference` over the underlying
  ``<cacheSource><worksheetSource>`` element. Setting this stamps a
  new ref + flips ``_dirty``; the actual XML rewrite happens at
  :meth:`Workbook.save` time via ``apply_pivot_source_edits_phase``.
- ``row_fields`` / ``column_fields`` / ``page_fields`` /
  ``data_fields`` plus ``set_filter`` / ``set_aggregation`` mutate
  the existing pivot table layout and mark the linked cache
  refresh-on-open when derived cache records may need recalculation.
"""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from typing import TYPE_CHECKING, Any

from wolfxl.chart.reference import Reference
from ._table import ColumnField, DataField, DataFunction, PageField, RowField

if TYPE_CHECKING:
    from wolfxl._workbook import Workbook
    from wolfxl._worksheet import Worksheet


class PivotTableHandle:
    """Modify-mode proxy for an existing pivot table.

    Constructed lazily by :attr:`Worksheet.pivot_tables`. Users do not
    instantiate this directly.
    """

    __slots__ = (
        "_workbook",
        "_owner_sheet",
        "_name",
        "_location",
        "_cache_id",
        "_cache_part_path",
        "_records_part_path",
        "_table_part_path",
        "_orig_source_range",
        "_orig_source_sheet",
        "_orig_field_count",
        "_field_names",
        "_dirty",
        "_new_source",
        "_layout_dirty",
        "_row_field_specs",
        "_col_field_specs",
        "_page_field_specs",
        "_data_field_specs",
    )

    def __init__(
        self,
        *,
        workbook: Workbook,
        owner_sheet: Worksheet,
        name: str,
        location: str,
        cache_id: int,
        cache_part_path: str,
        records_part_path: str,
        table_part_path: str,
        orig_source_range: str,
        orig_source_sheet: str,
        orig_field_count: int,
        field_names: list[str] | None = None,
    ) -> None:
        self._workbook = workbook
        self._owner_sheet = owner_sheet
        self._name = name
        self._location = location
        self._cache_id = cache_id
        self._cache_part_path = cache_part_path
        self._records_part_path = records_part_path
        self._table_part_path = table_part_path
        self._orig_source_range = orig_source_range
        self._orig_source_sheet = orig_source_sheet
        self._orig_field_count = orig_field_count
        self._field_names = list(field_names or [])
        self._dirty = False
        self._new_source: Reference | None = None
        self._layout_dirty = False
        self._row_field_specs: list[RowField] | None = None
        self._col_field_specs: list[ColumnField] | None = None
        self._page_field_specs: list[PageField] | None = None
        self._data_field_specs: list[DataField] | None = None

    # ------------------------------------------------------------------
    # Read-only props
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """``<pivotTableDefinition name="...">`` from the source XML."""
        return self._name

    @property
    def location(self) -> str:
        """``<location ref="A1:E20">`` from the source XML.

        Source-range mutation does NOT alter the pivot's drawn
        location; that is determined by the table part, which v1.0
        passes through unchanged.
        """
        return self._location

    @property
    def cache_id(self) -> int:
        """Workbook-scope ``cacheId`` linking the table to its cache."""
        return self._cache_id

    @property
    def row_fields(self) -> list[RowField]:
        return list(self._row_field_specs or [])

    @row_fields.setter
    def row_fields(self, values: list[str | RowField]) -> None:
        self._row_field_specs = [v if isinstance(v, RowField) else RowField(str(v)) for v in values]
        self._mark_layout_dirty()

    @property
    def column_fields(self) -> list[ColumnField]:
        return list(self._col_field_specs or [])

    @column_fields.setter
    def column_fields(self, values: list[str | ColumnField]) -> None:
        self._col_field_specs = [
            v if isinstance(v, ColumnField) else ColumnField(str(v)) for v in values
        ]
        self._mark_layout_dirty()

    @property
    def page_fields(self) -> list[PageField]:
        return list(self._page_field_specs or [])

    @page_fields.setter
    def page_fields(self, values: list[str | PageField]) -> None:
        self._page_field_specs = [v if isinstance(v, PageField) else PageField(str(v)) for v in values]
        self._mark_layout_dirty()

    @property
    def data_fields(self) -> list[DataField]:
        return list(self._data_field_specs or [])

    @data_fields.setter
    def data_fields(self, values: list[str | DataField]) -> None:
        self._data_field_specs = [v if isinstance(v, DataField) else DataField(str(v)) for v in values]
        self._mark_layout_dirty()

    def set_aggregation(self, field: str, function: str) -> None:
        if function not in DataFunction.ALL:
            raise ValueError(f"Unknown aggregation function {function!r}")
        existing = self._data_field_specs or [DataField(field, function=function)]
        updated: list[DataField] = []
        found = False
        for spec in existing:
            if spec.name == field:
                updated.append(DataField(field, function=function, display_name=None))
                found = True
            else:
                updated.append(spec)
        if not found:
            updated.append(DataField(field, function=function))
        self._data_field_specs = updated
        self._mark_layout_dirty()

    def set_filter(self, field: str, *, item_index: int = -1) -> None:
        existing = self._page_field_specs or []
        updated: list[PageField] = []
        found = False
        for spec in existing:
            if spec.name == field:
                updated.append(PageField(field, item_index=item_index, hier=spec.hier, cap=spec.cap))
                found = True
            else:
                updated.append(spec)
        if not found:
            updated.append(PageField(field, item_index=item_index))
        self._page_field_specs = updated
        self._mark_layout_dirty()

    # ------------------------------------------------------------------
    # source — the only mutator in v1.0
    # ------------------------------------------------------------------

    @property
    def source(self) -> Reference:
        """Current source range. Returns the *pending* range when the
        handle has been mutated this session; otherwise the original
        on-disk range as a synthetic :class:`Reference`.
        """
        if self._new_source is not None:
            return self._new_source
        return self._build_orig_reference()

    @source.setter
    def source(self, value: Reference) -> None:
        """Stamp a new source range. The actual XML rewrite happens at
        save time. Raises :class:`RuntimeError` when the workbook is
        not in modify mode (read-only or write-only contexts cannot
        round-trip pivot edits).
        """
        wb = self._workbook
        if getattr(wb, "_read_only", False):
            raise RuntimeError(
                "PivotTableHandle.source = ... requires modify mode; "
                "this workbook was opened with read_only=True"
            )
        if getattr(wb, "_rust_patcher", None) is None:
            raise RuntimeError(
                "PivotTableHandle.source = ... requires modify mode; "
                "open the workbook with load_workbook(..., modify=True)"
            )
        if not isinstance(value, Reference):
            raise TypeError(
                f"PivotTableHandle.source must be a Reference, got "
                f"{type(value).__name__}"
            )
        self._new_source = value
        self._dirty = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_orig_reference(self) -> Reference:
        """Build a :class:`Reference` mirroring the on-disk source."""
        from wolfxl.chart.reference import _DummyWorksheet

        ws_obj: Any = None
        if self._orig_source_sheet:
            ws_obj = self._workbook._sheets.get(  # noqa: SLF001
                self._orig_source_sheet
            )
        if ws_obj is None:
            ws_obj = self._owner_sheet
        if ws_obj is None:
            ws_obj = _DummyWorksheet(self._orig_source_sheet)
        rng = self._orig_source_range or "A1"
        bounds = _parse_a1_range(rng)
        if bounds is None:
            # Cannot round-trip an unparseable original; surface a
            # synthetic single-cell reference rather than crash.
            return Reference(ws_obj, min_col=1, min_row=1, max_col=1, max_row=1)
        min_col, min_row, max_col, max_row = bounds
        return Reference(
            ws_obj,
            min_col=min_col,
            min_row=min_row,
            max_col=max_col,
            max_row=max_row,
        )

    def _new_source_to_a1(self) -> str:
        """Render :attr:`_new_source` as an A1 range string for emit."""
        from wolfxl.chart.reference import _index_to_col

        ref = self._new_source
        assert ref is not None  # caller checked _dirty
        if ref.min_col == ref.max_col and ref.min_row == ref.max_row:
            return f"{_index_to_col(ref.min_col)}{ref.min_row}"
        return (
            f"{_index_to_col(ref.min_col)}{ref.min_row}:"
            f"{_index_to_col(ref.max_col)}{ref.max_row}"
        )

    def _new_source_sheet_name(self) -> str:
        """Resolve the new source's sheet name (for ``sheet=``)."""
        ref = self._new_source
        assert ref is not None
        ws_obj = ref.worksheet
        if ws_obj is None:
            return self._orig_source_sheet
        title = getattr(ws_obj, "title", None)
        return str(title) if title is not None else self._orig_source_sheet

    def _column_count(self) -> int:
        """Column span of :attr:`_new_source`."""
        ref = self._new_source
        assert ref is not None
        return int(ref.max_col) - int(ref.min_col) + 1

    def _mark_layout_dirty(self) -> None:
        if getattr(self._workbook, "_read_only", False):
            raise RuntimeError("PivotTableHandle layout mutation requires modify mode")
        if getattr(self._workbook, "_rust_patcher", None) is None:
            raise RuntimeError(
                "PivotTableHandle layout mutation requires load_workbook(..., modify=True)"
            )
        self._layout_dirty = True

    def _layout_payload(self) -> dict[str, Any]:
        return {
            "table_part_path": self._table_part_path,
            "cache_part_path": self._cache_part_path,
            "field_names": list(self._field_names),
            "rows": [spec.name for spec in self._row_field_specs or []],
            "cols": [spec.name for spec in self._col_field_specs or []],
            "pages": [
                {
                    "name": spec.name,
                    "item_index": spec.item_index,
                    "hier": spec.hier,
                    "cap": spec.cap,
                }
                for spec in self._page_field_specs or []
            ],
            "data": [
                {
                    "name": spec.name,
                    "function": spec.function,
                    "display_name": spec.resolved_display_name(),
                    "base_field": spec.base_field,
                    "base_item": spec.base_item,
                    "num_fmt_id": spec.num_fmt_id,
                }
                for spec in self._data_field_specs or []
            ],
        }

    def __repr__(self) -> str:
        sfx = " *dirty*" if self._dirty else ""
        return f"<PivotTableHandle name={self._name!r} location={self._location!r}{sfx}>"


def _parse_a1_range(rng: str) -> tuple[int, int, int, int] | None:
    """Parse an A1 range string into 1-based column/row bounds."""
    if not rng:
        return None
    parts = rng.split(":")
    if len(parts) == 1:
        c, r = _parse_a1_cell(parts[0])
        if c is None or r is None:
            return None
        return (c, r, c, r)
    if len(parts) == 2:
        c1, r1 = _parse_a1_cell(parts[0])
        c2, r2 = _parse_a1_cell(parts[1])
        if c1 is None or r1 is None or c2 is None or r2 is None:
            return None
        return (c1, r1, c2, r2)
    return None


def _parse_a1_cell(cell: str) -> tuple[int | None, int | None]:
    """Parse a single A1 cell (e.g. ``$B$5``) into ``(col, row)``."""
    s = cell.lstrip("$")
    col = 0
    i = 0
    while i < len(s) and s[i].isalpha():
        col = col * 26 + (ord(s[i].upper()) - ord("A") + 1)
        i += 1
    if col == 0:
        return (None, None)
    if i < len(s) and s[i] == "$":
        i += 1
    row_str = s[i:]
    if not row_str.isdigit():
        return (None, None)
    return (col, int(row_str))


__all__ = ["PivotTableHandle"]


def apply_pivot_layout_authoring_to_xlsx(path: str, workbook: Any) -> None:
    payloads: list[dict[str, Any]] = []
    for ws in workbook._sheets.values():  # noqa: SLF001
        handles = getattr(ws, "_pivot_handles_cache", None)
        if not handles:
            continue
        for handle in handles:
            if getattr(handle, "_layout_dirty", False):
                payloads.append(handle._layout_payload())  # noqa: SLF001
                handle._layout_dirty = False  # noqa: SLF001
    if not payloads:
        return

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as src:
        names = set(src.namelist())
        for payload in payloads:
            table_path = payload["table_part_path"]
            cache_path = payload["cache_part_path"]
            if table_path in names:
                table_bytes = replacements.get(table_path) or src.read(table_path)
                replacements[table_path] = _rewrite_pivot_table_xml(table_bytes, payload)
            if cache_path in names:
                cache_bytes = replacements.get(cache_path) or src.read(cache_path)
                replacements[cache_path] = _force_refresh_on_load(cache_bytes)

    fd, tmp_name = tempfile.mkstemp(prefix="wolfxl-pivot-layout-", suffix=".xlsx")
    os.close(fd)
    try:
        with zipfile.ZipFile(path, "r") as src, zipfile.ZipFile(
            tmp_name, "w", zipfile.ZIP_DEFLATED
        ) as dst:
            for info in src.infolist():
                data = replacements.get(info.filename)
                if data is None:
                    with src.open(info, "r") as handle:
                        data = handle.read()
                dst.writestr(info, data)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _rewrite_pivot_table_xml(xml: bytes, payload: dict[str, Any]) -> bytes:
    text = xml.decode("utf-8")
    field_names = payload["field_names"]
    rows = [_field_index(field_names, name) for name in payload["rows"]]
    cols = [_field_index(field_names, name) for name in payload["cols"]]
    pages = [
        {**page, "idx": _field_index(field_names, page["name"])}
        for page in payload["pages"]
    ]
    data = [
        {**data_field, "idx": _field_index(field_names, data_field["name"])}
        for data_field in payload["data"]
    ]

    text = _replace_block(text, "pivotFields", _pivot_fields_block(len(field_names), rows, cols, pages, data))
    text = _replace_block(text, "rowFields", _axis_fields_block("rowFields", rows))
    text = _replace_block(text, "colFields", _axis_fields_block("colFields", cols))
    text = _replace_block(text, "pageFields", _page_fields_block(pages))
    text = _replace_block(text, "dataFields", _data_fields_block(data))
    return text.encode("utf-8")


def _replace_block(text: str, tag: str, replacement: str) -> str:
    pattern = rf"<{tag}\b[^>]*>.*?</{tag}>"
    if re.search(pattern, text, flags=re.DOTALL):
        return re.sub(pattern, replacement, text, count=1, flags=re.DOTALL)
    self_closing_pattern = rf"<{tag}\b[^>]*/>"
    if re.search(self_closing_pattern, text):
        return re.sub(self_closing_pattern, replacement, text, count=1)
    if not replacement:
        return text
    if tag == "pivotFields" and "</location>" in text:
        return text.replace("</location>", f"</location>{replacement}", 1)
    if tag in {"rowFields", "colFields", "pageFields"}:
        anchor = "</pivotFields>"
        return text.replace(anchor, f"{anchor}{replacement}", 1)
    anchor = "<pivotTableStyleInfo"
    if anchor in text:
        return text.replace(anchor, f"{replacement}{anchor}", 1)
    return text.replace("</pivotTableDefinition>", f"{replacement}</pivotTableDefinition>", 1)


def _pivot_fields_block(
    count: int,
    rows: list[int],
    cols: list[int],
    pages: list[dict[str, Any]],
    data: list[dict[str, Any]],
) -> str:
    page_indices = {int(page["idx"]): int(page.get("item_index", -1)) for page in pages}
    data_indices = {int(item["idx"]) for item in data}
    parts = [f'<pivotFields count="{count}">']
    for idx in range(count):
        attrs = ['showAll="0"']
        if idx in rows:
            attrs.insert(0, 'axis="axisRow"')
        elif idx in cols:
            attrs.insert(0, 'axis="axisCol"')
        elif idx in page_indices:
            attrs.insert(0, 'axis="axisPage"')
        if idx in data_indices:
            attrs.insert(0, 'dataField="1"')
        item_index = page_indices.get(idx)
        if item_index is not None and item_index >= 0:
            parts.append(f'<pivotField {" ".join(attrs)}><items count="1"><item x="{item_index}"/></items></pivotField>')
        else:
            parts.append(f'<pivotField {" ".join(attrs)}/>')
    parts.append("</pivotFields>")
    return "".join(parts)


def _axis_fields_block(tag: str, indices: list[int]) -> str:
    if not indices:
        return ""
    inner = "".join(f'<field x="{idx}"/>' for idx in indices)
    return f'<{tag} count="{len(indices)}">{inner}</{tag}>'


def _page_fields_block(pages: list[dict[str, Any]]) -> str:
    if not pages:
        return ""
    inner = ""
    for page in pages:
        attrs = [f'fld="{page["idx"]}"', f'item="{int(page.get("item_index", -1))}"']
        if int(page.get("hier", -1)) != -1:
            attrs.append(f'hier="{int(page["hier"])}"')
        if page.get("cap"):
            attrs.append(f'name="{_xml_attr_escape(str(page["cap"]))}"')
        inner += f'<pageField {" ".join(attrs)}/>'
    return f'<pageFields count="{len(pages)}">{inner}</pageFields>'


def _data_fields_block(data_fields: list[dict[str, Any]]) -> str:
    if not data_fields:
        return ""
    inner = ""
    for field in data_fields:
        attrs = [
            f'name="{_xml_attr_escape(str(field["display_name"]))}"',
            f'fld="{field["idx"]}"',
            f'subtotal="{_xml_attr_escape(str(field["function"]))}"',
            f'baseField="{int(field.get("base_field", 0))}"',
            f'baseItem="{int(field.get("base_item", 0))}"',
        ]
        if field.get("num_fmt_id") is not None:
            attrs.append(f'numFmtId="{int(field["num_fmt_id"])}"')
        inner += f'<dataField {" ".join(attrs)}/>'
    return f'<dataFields count="{len(data_fields)}">{inner}</dataFields>'


def _force_refresh_on_load(xml: bytes) -> bytes:
    text = xml.decode("utf-8")
    match = re.search(r"<pivotCacheDefinition\b[^>]*>", text)
    if not match:
        return xml
    tag = match.group(0)
    if "refreshOnLoad=" in tag:
        new_tag = re.sub(r'refreshOnLoad="[^"]*"', 'refreshOnLoad="1"', tag, count=1)
    else:
        new_tag = tag[:-1] + ' refreshOnLoad="1">'
    return (text[: match.start()] + new_tag + text[match.end() :]).encode("utf-8")


def _field_index(field_names: list[str], name: str) -> int:
    try:
        return field_names.index(name)
    except ValueError as exc:
        raise ValueError(f"unknown pivot field {name!r}; known fields: {field_names}") from exc


def _xml_attr_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
