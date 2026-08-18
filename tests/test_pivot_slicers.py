"""RFC-061 Sub-feature 3.1 — Slicers (~40 tests).

Validates the public API of ``wolfxl.pivot.{Slicer, SlicerCache,
SlicerItem}`` and the ``to_rust_dict()`` shape per RFC-061 §10.1
and §10.2.

The Rust serialiser tests live in ``crates/wolfxl-pivot/src/emit/``.
"""

from __future__ import annotations

import pytest

from wolfxl.chart.reference import Reference
from wolfxl.pivot import PivotCache, Slicer, SlicerCache, SlicerItem


# ---------------------------------------------------------------------------
# Stub worksheet
# ---------------------------------------------------------------------------


class _StubCell:
    def __init__(self, value):
        self.value = value


class _StubWorksheet:
    def __init__(self, title, data):
        self.title = title
        self._data = data

    def __getitem__(self, addr):
        return _StubCell(self._data.get(addr))


def _build_worksheet():
    data = {
        "A1": "region", "B1": "quarter", "C1": "revenue",
        "A2": "North",  "B2": "Q1",       "C2": 100.0,
        "A3": "South",  "B3": "Q1",       "C3": 200.0,
        "A4": "North",  "B4": "Q2",       "C4": 150.0,
        "A5": "South",  "B5": "Q2",       "C5": 250.0,
    }
    return _StubWorksheet("Sheet1", data)


def _materialized_cache():
    ws = _build_worksheet()
    src = Reference(worksheet=ws, min_col=1, min_row=1, max_col=3, max_row=5)
    pc = PivotCache(source=src)
    pc._cache_id = 0
    pc._materialize(ws)
    return pc


# ---------------------------------------------------------------------------
# SlicerItem
# ---------------------------------------------------------------------------


def test_slicer_item_defaults():
    it = SlicerItem(name="North")
    assert it.name == "North"
    assert it.hidden is False
    assert it.no_data is False


def test_slicer_item_to_rust_dict():
    it = SlicerItem(name="North", hidden=True, no_data=False)
    d = it.to_rust_dict()
    assert d == {"name": "North", "hidden": True, "no_data": False}


def test_slicer_item_no_data():
    it = SlicerItem(name="X", no_data=True)
    assert it.to_rust_dict()["no_data"] is True


# ---------------------------------------------------------------------------
# SlicerCache
# ---------------------------------------------------------------------------


def test_slicer_cache_requires_pivot_cache():
    with pytest.raises(TypeError):
        SlicerCache(name="Slicer_x", source_pivot_cache="not a cache", field="x")


def test_slicer_cache_requires_non_empty_name():
    pc = _materialized_cache()
    with pytest.raises(ValueError):
        SlicerCache(name="", source_pivot_cache=pc, field="region")


def test_slicer_cache_invalid_sort_order():
    pc = _materialized_cache()
    with pytest.raises(ValueError):
        SlicerCache(
            name="Slicer_region",
            source_pivot_cache=pc,
            field="region",
            sort_order="reverse",
        )


def test_slicer_cache_defaults():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    assert sc.name == "Slicer_region"
    assert sc.field == "region"
    assert sc.sort_order == "ascending"
    assert sc.custom_list_sort is False
    assert sc.hide_items_with_no_data is False
    assert sc.show_missing is True
    assert sc.items == []


def test_slicer_cache_unregistered_raises_on_id():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    with pytest.raises(RuntimeError):
        _ = sc.slicer_cache_id


def test_slicer_cache_field_index_resolution():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    assert sc.source_field_index == 0
    sc2 = SlicerCache(
        name="Slicer_quarter", source_pivot_cache=pc, field="quarter"
    )
    assert sc2.source_field_index == 1


def test_slicer_cache_unknown_field_raises():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_xyz", source_pivot_cache=pc, field="xyz"
    )
    with pytest.raises(KeyError):
        _ = sc.source_field_index


def test_slicer_cache_add_item():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    sc.add_item("North")
    sc.add_item("South", hidden=True)
    sc.add_item("East", no_data=True)
    assert len(sc.items) == 3
    assert sc.items[1].hidden is True
    assert sc.items[2].no_data is True


def test_slicer_cache_populate_items_from_cache():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    sc.populate_items_from_cache()
    names = [it.name for it in sc.items]
    assert "North" in names
    assert "South" in names


def test_slicer_cache_to_rust_dict_pre_register_raises():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    with pytest.raises(RuntimeError):
        sc.to_rust_dict()


def test_slicer_cache_to_rust_dict_shape():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    sc._slicer_cache_id = 0  # register manually
    sc.add_item("North")
    sc.add_item("South")
    d = sc.to_rust_dict()
    assert d["name"] == "Slicer_region"
    assert d["source_pivot_cache_id"] == 0
    assert d["source_field_index"] == 0
    assert d["sort_order"] == "ascending"
    assert d["custom_list_sort"] is False
    assert d["show_missing"] is True
    assert isinstance(d["items"], list)
    assert len(d["items"]) == 2
    assert d["items"][0]["name"] == "North"


def test_slicer_cache_descending_sort_in_dict():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region",
        source_pivot_cache=pc,
        field="region",
        sort_order="descending",
    )
    sc._slicer_cache_id = 0
    assert sc.to_rust_dict()["sort_order"] == "descending"


def test_slicer_cache_hide_no_data_in_dict():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region",
        source_pivot_cache=pc,
        field="region",
        hide_items_with_no_data=True,
    )
    sc._slicer_cache_id = 0
    assert sc.to_rust_dict()["hide_items_with_no_data"] is True


# ---------------------------------------------------------------------------
# Slicer presentation
# ---------------------------------------------------------------------------


def _slicer_cache():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    sc._slicer_cache_id = 0
    return sc


def test_slicer_requires_cache():
    with pytest.raises(TypeError):
        Slicer(name="x", cache="not a cache")


def test_slicer_requires_non_empty_name():
    sc = _slicer_cache()
    with pytest.raises(ValueError):
        Slicer(name="", cache=sc)


def test_slicer_zero_columns_rejects():
    sc = _slicer_cache()
    with pytest.raises(ValueError):
        Slicer(name="x", cache=sc, column_count=0)


def test_slicer_zero_row_height_rejects():
    sc = _slicer_cache()
    with pytest.raises(ValueError):
        Slicer(name="x", cache=sc, row_height=0)


def test_slicer_defaults():
    sc = _slicer_cache()
    s = Slicer(name="Slicer_region1", cache=sc)
    assert s.row_height == 204
    assert s.column_count == 1
    assert s.show_caption is True
    assert s.style == "SlicerStyleLight1"
    assert s.locked is True
    assert s.anchor is None


def test_slicer_unanchored_dict_raises():
    sc = _slicer_cache()
    s = Slicer(name="Slicer_region1", cache=sc)
    with pytest.raises(RuntimeError):
        s.to_rust_dict()


def test_slicer_to_rust_dict_shape():
    sc = _slicer_cache()
    s = Slicer(
        name="Slicer_region1",
        cache=sc,
        caption="Filter by Region",
        row_height=300,
        column_count=2,
        show_caption=False,
        style="SlicerStyleDark1",
        locked=False,
    )
    s.anchor = "H2"
    d = s.to_rust_dict()
    assert d["name"] == "Slicer_region1"
    assert d["cache_name"] == "Slicer_region"
    assert d["caption"] == "Filter by Region"
    assert d["row_height"] == 300
    assert d["column_count"] == 2
    assert d["show_caption"] is False
    assert d["style"] == "SlicerStyleDark1"
    assert d["locked"] is False
    assert d["anchor"] == "H2"


def test_slicer_no_style_emits_none():
    sc = _slicer_cache()
    s = Slicer(name="x", cache=sc, style=None)
    s.anchor = "A1"
    assert s.to_rust_dict()["style"] is None


# ---------------------------------------------------------------------------
# Rust serializer round-trip via PyO3 (skipped if extension not built)
# ---------------------------------------------------------------------------


pytest.importorskip("wolfxl._rust")


def test_serialize_slicer_cache_dict_roundtrip():
    from wolfxl._rust import serialize_slicer_cache_dict

    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    sc._slicer_cache_id = 0
    sc.add_item("North")
    sc.add_item("South")
    xml = serialize_slicer_cache_dict(sc.to_rust_dict())
    assert isinstance(xml, bytes)
    s = xml.decode()
    assert s.startswith("<?xml")
    assert "<slicerCacheDefinition" in s
    assert 'name="Slicer_region"' in s
    assert 'sourceName="Slicer_region"' in s
    assert "<tabular" in s
    assert 'pivotCacheId="0"' in s
    assert "<items" in s
    assert "North" in s
    assert "South" in s


def test_serialize_slicer_cache_dict_descending_sort():
    from wolfxl._rust import serialize_slicer_cache_dict

    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region",
        source_pivot_cache=pc,
        field="region",
        sort_order="descending",
    )
    sc._slicer_cache_id = 0
    xml = serialize_slicer_cache_dict(sc.to_rust_dict())
    s = xml.decode()
    assert 'sortOrder="descending"' in s


def test_serialize_slicer_cache_dict_byte_stable():
    from wolfxl._rust import serialize_slicer_cache_dict

    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_region", source_pivot_cache=pc, field="region"
    )
    sc._slicer_cache_id = 0
    sc.add_item("North")
    a = serialize_slicer_cache_dict(sc.to_rust_dict())
    b = serialize_slicer_cache_dict(sc.to_rust_dict())
    assert a == b


def test_serialize_slicer_dict_single():
    from wolfxl._rust import serialize_slicer_dict

    sc = _slicer_cache()
    s = Slicer(
        name="Slicer_region1",
        cache=sc,
        caption="Filter by Region",
    )
    s.anchor = "H2"
    xml = serialize_slicer_dict([s.to_rust_dict()])
    raw = xml.decode()
    assert raw.startswith("<?xml")
    assert "<slicers" in raw
    assert "<slicer" in raw
    assert 'name="Slicer_region1"' in raw
    assert 'cache="Slicer_region"' in raw
    assert 'caption="Filter by Region"' in raw


def test_serialize_slicer_dict_multiple():
    from wolfxl._rust import serialize_slicer_dict

    sc = _slicer_cache()
    s1 = Slicer(name="Slicer_a1", cache=sc)
    s1.anchor = "H2"
    s2 = Slicer(name="Slicer_b1", cache=sc)
    s2.anchor = "K2"
    xml = serialize_slicer_dict([s1.to_rust_dict(), s2.to_rust_dict()])
    raw = xml.decode()
    assert raw.count("<slicer ") == 2


def test_serialize_slicer_dict_unlocked():
    from wolfxl._rust import serialize_slicer_dict

    sc = _slicer_cache()
    s = Slicer(name="x", cache=sc, locked=False)
    s.anchor = "A1"
    xml = serialize_slicer_dict([s.to_rust_dict()])
    raw = xml.decode()
    assert 'lockedPosition="0"' in raw


def test_serialize_slicer_dict_byte_stable():
    from wolfxl._rust import serialize_slicer_dict

    sc = _slicer_cache()
    s = Slicer(name="Slicer_x1", cache=sc)
    s.anchor = "A1"
    a = serialize_slicer_dict([s.to_rust_dict()])
    b = serialize_slicer_dict([s.to_rust_dict()])
    assert a == b


def test_slicer_to_rust_dict_lock_flag_on():
    sc = _slicer_cache()
    s = Slicer(name="x", cache=sc)
    s.anchor = "A1"
    assert s.to_rust_dict()["locked"] is True


def test_slicer_to_rust_dict_lock_flag_off():
    sc = _slicer_cache()
    s = Slicer(name="x", cache=sc, locked=False)
    s.anchor = "A1"
    assert s.to_rust_dict()["locked"] is False


def test_slicer_cache_show_missing_default_true():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_x", source_pivot_cache=pc, field="region"
    )
    assert sc.show_missing is True


def test_slicer_cache_show_missing_false():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_x",
        source_pivot_cache=pc,
        field="region",
        show_missing=False,
    )
    sc._slicer_cache_id = 0
    assert sc.to_rust_dict()["show_missing"] is False


def test_slicer_cache_custom_list_sort_in_dict():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_x",
        source_pivot_cache=pc,
        field="region",
        custom_list_sort=True,
    )
    sc._slicer_cache_id = 0
    assert sc.to_rust_dict()["custom_list_sort"] is True


def test_slicer_cache_items_to_rust_dict_round_trip():
    pc = _materialized_cache()
    sc = SlicerCache(
        name="Slicer_x", source_pivot_cache=pc, field="region"
    )
    sc._slicer_cache_id = 0
    sc.add_item("A", hidden=True)
    sc.add_item("B", no_data=True)
    items = sc.to_rust_dict()["items"]
    assert items[0] == {"name": "A", "hidden": True, "no_data": False}
    assert items[1] == {"name": "B", "hidden": False, "no_data": True}


def test_slicer_default_caption_empty():
    sc = _slicer_cache()
    s = Slicer(name="x", cache=sc)
    s.anchor = "A1"
    assert s.to_rust_dict()["caption"] == ""


def test_slicer_invalid_cache_type_raises():
    with pytest.raises(TypeError):
        Slicer(name="x", cache="not_a_cache")


def test_slicer_negative_column_count_rejects():
    sc = _slicer_cache()
    with pytest.raises(ValueError):
        Slicer(name="x", cache=sc, column_count=-1)


def test_slicer_emu_row_height_in_dict():
    sc = _slicer_cache()
    s = Slicer(name="x", cache=sc, row_height=512)
    s.anchor = "A1"
    assert s.to_rust_dict()["row_height"] == 512
