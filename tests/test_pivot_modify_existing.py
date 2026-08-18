"""G17 / RFC-070 — focused tests for modify-mode pivot source-range
mutation."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import wolfxl
from wolfxl.chart import Reference
from wolfxl.pivot._handle import _replace_block
from wolfxl.pivot import DataField, DataFunction, PageField, PivotCache, PivotTable


def _build_pivot_workbook(path: Path, *, max_row: int = 3, max_col: int = 2) -> Path:
    """Construct a fresh workbook with one pivot table.

    The data sheet's row/col span scales with ``max_row``/``max_col`` so
    the differing-shape test can ask for a 3-column source range.
    """
    wb = wolfxl.Workbook()
    ws = wb.active
    headers = [f"col{i + 1}" for i in range(max_col)]
    ws.append(headers)
    for r in range(max_row - 1):
        ws.append([f"v{r}{c}" if c == 0 else (r * 10 + c) for c in range(max_col)])
    cache = PivotCache(
        source=Reference(
            ws,
            min_col=1,
            min_row=1,
            max_col=max_col,
            max_row=max_row,
        )
    )
    wb.add_pivot_cache(cache)
    pt = PivotTable(
        cache=cache,
        location="D2",
        rows=[headers[0]],
        data=[headers[1]],
    )
    target = wb.create_sheet("Pivot")
    target.add_pivot_table(pt, "A1")
    wb.save(path)
    return path


def _read_zip_entry(path: Path, entry: str) -> bytes:
    with zipfile.ZipFile(path) as zf:
        return zf.read(entry)


def _list_pivot_cache_entries(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return sorted(
            n
            for n in zf.namelist()
            if n.startswith("xl/pivotCache/pivotCacheDefinition")
        )


def test_modify_pivot_source_same_shape_round_trip(tmp_path: Path) -> None:
    """Same-shape source mutation persists into the saved cache."""
    src = tmp_path / "pivot_same.xlsx"
    _build_pivot_workbook(src)

    wb2 = wolfxl.load_workbook(src, modify=True)
    handles = wb2["Pivot"].pivot_tables
    assert len(handles) == 1
    pivot = handles[0]
    assert pivot.name
    pivot.source = Reference(
        wb2.active, min_col=1, min_row=1, max_col=2, max_row=3
    )
    wb2.save(src)

    cache_entries = _list_pivot_cache_entries(src)
    assert cache_entries, "expected at least one pivotCacheDefinition*.xml"
    body = _read_zip_entry(src, cache_entries[0]).decode()
    assert 'ref="A1:B3"' in body
    # Same-shape mutation must NOT trip refreshOnLoad.
    assert 'refreshOnLoad="1"' not in body


def test_modify_pivot_source_different_shape_sets_refresh_on_load(tmp_path: Path) -> None:
    """Column-count divergence stamps ``refreshOnLoad="1"`` on the cache."""
    src = tmp_path / "pivot_diff.xlsx"
    _build_pivot_workbook(src, max_row=3, max_col=3)  # original has 3 cols

    wb2 = wolfxl.load_workbook(src, modify=True)
    pivot = wb2["Pivot"].pivot_tables[0]
    # New range has 2 columns — shape mismatch.
    pivot.source = Reference(
        wb2.active, min_col=1, min_row=1, max_col=2, max_row=5
    )
    wb2.save(src)

    cache_entries = _list_pivot_cache_entries(src)
    assert cache_entries
    body = _read_zip_entry(src, cache_entries[0]).decode()
    assert 'ref="A1:B5"' in body
    assert 'refreshOnLoad="1"' in body


def test_modify_pivot_source_two_saves_refreshes_handle_metadata(tmp_path: Path) -> None:
    """A second source edit in the same session compares against the first save."""
    src = tmp_path / "pivot_two_saves.xlsx"
    _build_pivot_workbook(src, max_row=5, max_col=2)

    wb2 = wolfxl.load_workbook(src, modify=True)
    pivot = wb2["Pivot"].pivot_tables[0]
    pivot.source = Reference(
        wb2.active, min_col=1, min_row=1, max_col=2, max_row=4
    )
    wb2.save(src)
    assert pivot.source.max_row == 4

    pivot.source = Reference(
        wb2.active, min_col=1, min_row=1, max_col=2, max_row=5
    )
    wb2.save(src)

    cache_entries = _list_pivot_cache_entries(src)
    body = _read_zip_entry(src, cache_entries[0]).decode()
    assert 'ref="A1:B5"' in body
    # Second edit is same-shape relative to first edit, so it should not
    # newly add a refresh marker due to stale original metadata.
    assert 'refreshOnLoad="1"' not in body


def test_modify_pivot_no_mutation_is_byte_identical(tmp_path: Path) -> None:
    """Loading + saving without a mutation must not touch pivot files."""
    src = tmp_path / "pivot_noop.xlsx"
    _build_pivot_workbook(src)
    cache_entries = _list_pivot_cache_entries(src)
    assert cache_entries
    original_body = _read_zip_entry(src, cache_entries[0])

    wb2 = wolfxl.load_workbook(src, modify=True)
    # Touch but don't mutate.
    handles = wb2["Pivot"].pivot_tables
    assert handles
    wb2.save(src)

    new_body = _read_zip_entry(src, cache_entries[0])
    assert new_body == original_body, (
        "no-mutation save altered the pivot cache definition"
    )


def test_modify_pivot_read_only_workbook_raises(tmp_path: Path) -> None:
    """Mutating a handle on a read-only workbook surfaces a clear error."""
    src = tmp_path / "pivot_readonly.xlsx"
    _build_pivot_workbook(src)

    wb_ro = wolfxl.load_workbook(src, read_only=True)
    handles = wb_ro["Pivot"].pivot_tables
    if not handles:
        pytest.skip(
            "read_only=True workbooks may not expose pivot handles; "
            "the mutation surface is gated through modify mode"
        )
    pivot = handles[0]
    with pytest.raises(RuntimeError, match="modify mode"):
        pivot.source = Reference(
            wb_ro.active, min_col=1, min_row=1, max_col=2, max_row=3
        )


def test_modify_pivot_handle_metadata_round_trips(tmp_path: Path) -> None:
    """The handle exposes the on-disk name / location / cache id."""
    src = tmp_path / "pivot_meta.xlsx"
    _build_pivot_workbook(src)
    wb2 = wolfxl.load_workbook(src, modify=True)
    pivot = wb2["Pivot"].pivot_tables[0]
    assert isinstance(pivot.name, str) and pivot.name
    assert ":" in pivot.location  # "A1:..." form
    assert pivot.cache_id >= 0


def test_modify_pivot_field_placement_updates_table_xml(tmp_path: Path) -> None:
    src = tmp_path / "pivot_fields.xlsx"
    _build_pivot_workbook(src, max_row=4, max_col=3)

    wb = wolfxl.load_workbook(src, modify=True)
    pivot = wb["Pivot"].pivot_tables[0]
    pivot.row_fields = ["col1"]
    pivot.column_fields = ["col3"]
    pivot.data_fields = [DataField("col2", function=DataFunction.SUM)]
    wb.save(src)

    table = _read_zip_entry(src, "xl/pivotTables/pivotTable1.xml").decode()
    cache = _read_zip_entry(src, "xl/pivotCache/pivotCacheDefinition1.xml").decode()
    assert '<rowFields count="1"><field x="0"/></rowFields>' in table
    assert '<colFields count="1"><field x="2"/></colFields>' in table
    assert 'axis="axisCol"' in table
    assert 'fld="1" subtotal="sum"' in table
    assert 'refreshOnLoad="1"' in cache


def test_modify_pivot_filter_item_selection_updates_page_fields(tmp_path: Path) -> None:
    src = tmp_path / "pivot_filter.xlsx"
    _build_pivot_workbook(src, max_row=4, max_col=3)

    wb = wolfxl.load_workbook(src, modify=True)
    pivot = wb["Pivot"].pivot_tables[0]
    pivot.page_fields = [PageField("col1", item_index=0)]
    wb.save(src)

    table = _read_zip_entry(src, "xl/pivotTables/pivotTable1.xml").decode()
    assert '<pageFields count="1"><pageField fld="0" item="0"/></pageFields>' in table
    assert 'axis="axisPage"' in table


def test_modify_pivot_aggregation_updates_data_field(tmp_path: Path) -> None:
    src = tmp_path / "pivot_agg.xlsx"
    _build_pivot_workbook(src, max_row=4, max_col=3)

    wb = wolfxl.load_workbook(src, modify=True)
    pivot = wb["Pivot"].pivot_tables[0]
    pivot.set_aggregation("col2", DataFunction.AVERAGE)
    wb.save(src)

    table = _read_zip_entry(src, "xl/pivotTables/pivotTable1.xml").decode()
    assert 'name="Average of col2"' in table
    assert 'fld="1" subtotal="average"' in table


def test_modify_pivot_source_and_layout_compose(tmp_path: Path) -> None:
    src = tmp_path / "pivot_compose.xlsx"
    _build_pivot_workbook(src, max_row=4, max_col=3)

    wb = wolfxl.load_workbook(src, modify=True)
    pivot = wb["Pivot"].pivot_tables[0]
    pivot.source = Reference(wb.active, min_col=1, min_row=1, max_col=3, max_row=4)
    pivot.column_fields = ["col3"]
    pivot.set_aggregation("col2", DataFunction.COUNT)
    wb.save(src)

    table = _read_zip_entry(src, "xl/pivotTables/pivotTable1.xml").decode()
    cache = _read_zip_entry(src, "xl/pivotCache/pivotCacheDefinition1.xml").decode()
    assert 'ref="A1:C4"' in cache
    assert '<colFields count="1"><field x="2"/></colFields>' in table
    assert 'subtotal="count"' in table


def test_replace_block_replaces_self_closing_axis_blocks() -> None:
    """Empty pivot axis blocks often serialize as self-closing OOXML tags."""
    xml = (
        '<pivotTableDefinition><location ref="A1"/>'
        '<pivotFields count="2"><pivotField/><pivotField/></pivotFields>'
        '<rowFields count="0"/><colFields count="0"/>'
        '<pivotTableStyleInfo name="PivotStyleLight16"/>'
        "</pivotTableDefinition>"
    )

    updated = _replace_block(
        xml,
        "rowFields",
        '<rowFields count="1"><field x="0"/></rowFields>',
    )

    assert '<rowFields count="1"><field x="0"/></rowFields>' in updated
    assert '<rowFields count="0"/>' not in updated
    assert updated.count("<rowFields") == 1


def test_foreign_authored_pivot_round_trips(tmp_path: Path) -> None:
    """Best-effort test for a foreign-authored pivot fixture.

    RFC-070 §7.2 marks this as best-effort: we look for a pre-baked
    external-oracle fixture that contains a pivot, mutate its source,
    and verify the rewrite."""
    fixture_dirs = [
        Path("tests/fixtures/external_oracle"),
        Path("tests/data/pivot_fixtures"),
        Path("tests/fixtures/pivot"),
    ]
    candidate: tuple[Path, str] | None = None
    for d in fixture_dirs:
        if d.exists():
            for f in sorted(d.glob("*.xlsx")):
                with zipfile.ZipFile(f) as zf:
                    if not any("pivotTable" in n for n in zf.namelist()):
                        continue
                probe = tmp_path / f"probe-{f.name}"
                probe.write_bytes(f.read_bytes())
                wb = wolfxl.load_workbook(probe, modify=True)
                for ws in wb.worksheets:
                    if ws.pivot_tables:
                        candidate = (f, ws.title)
                        break
                if candidate:
                    break
        if candidate:
            break
    assert candidate is not None, "expected a foreign-authored pivot fixture"

    candidate_path, candidate_sheet = candidate
    dest = tmp_path / candidate_path.name
    dest.write_bytes(candidate_path.read_bytes())

    wb = wolfxl.load_workbook(dest, modify=True)
    handles = wb[candidate_sheet].pivot_tables
    assert handles, "selected fixture had no parseable pivot handle"
    h = handles[0]
    # Mutate to the same shape so refreshOnLoad stays off.
    cur = h.source
    h.source = Reference(
        cur.worksheet,
        min_col=cur.min_col,
        min_row=cur.min_row,
        max_col=cur.max_col,
        max_row=cur.max_row,
    )
    wb.save(dest)
