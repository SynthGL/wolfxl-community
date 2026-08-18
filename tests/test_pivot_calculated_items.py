"""RFC-061 Sub-feature 3.3 — Calculated items (~25 tests)."""

from __future__ import annotations

import pytest

from wolfxl.chart.reference import Reference
from wolfxl.pivot import (
    CalculatedItem,
    PivotCache,
    PivotTable,
)


class _StubCell:
    def __init__(self, v):
        self.value = v


class _StubWorksheet:
    def __init__(self, title, data):
        self.title = title
        self._data = data

    def __getitem__(self, addr):
        return _StubCell(self._data.get(addr))


def _materialized_cache():
    data = {
        "A1": "region", "B1": "revenue",
        "A2": "east",   "B2": 100.0,
        "A3": "west",   "B3": 200.0,
        "A4": "east",   "B4": 150.0,
    }
    ws = _StubWorksheet("Sheet1", data)
    src = Reference(worksheet=ws, min_col=1, min_row=1, max_col=2, max_row=4)
    pc = PivotCache(source=src)
    pc._cache_id = 0
    pc._materialize(ws)
    return pc


def _pivot_table(cache):
    return PivotTable(
        cache=cache,
        location="F2",
        rows=["region"],
        data=[("revenue", "sum")],
    )


# ---------------------------------------------------------------------------
# CalculatedItem construction
# ---------------------------------------------------------------------------


def test_calc_item_requires_field_name():
    with pytest.raises(ValueError):
        CalculatedItem(field_name="", item_name="x", formula="a + b")


def test_calc_item_requires_item_name():
    with pytest.raises(ValueError):
        CalculatedItem(field_name="region", item_name="", formula="a + b")


def test_calc_item_requires_formula():
    with pytest.raises(ValueError):
        CalculatedItem(field_name="region", item_name="combo", formula="")


def test_calc_item_balanced_parens_required():
    with pytest.raises(ValueError):
        CalculatedItem(field_name="r", item_name="x", formula="(a + b")


def test_calc_item_to_rust_dict_strips_equals():
    ci = CalculatedItem(field_name="region", item_name="ew", formula="= east + west")
    d = ci.to_rust_dict()
    assert d["field_name"] == "region"
    assert d["item_name"] == "ew"
    assert not d["formula"].startswith("=")


def test_calc_item_to_rust_dict_no_equals():
    ci = CalculatedItem(field_name="r", item_name="x", formula="a + b")
    d = ci.to_rust_dict()
    assert d["formula"] == "a + b"


# ---------------------------------------------------------------------------
# PivotTable.add_calculated_item
# ---------------------------------------------------------------------------


def test_pt_add_calculated_item():
    pc = _materialized_cache()
    pt = _pivot_table(pc)
    ci = pt.add_calculated_item("region", "east_west", "= east + west")
    assert isinstance(ci, CalculatedItem)
    assert ci.field_name == "region"
    assert ci.item_name == "east_west"
    assert pt.calculated_items == [ci]


def test_pt_add_multiple_calc_items():
    pc = _materialized_cache()
    pt = _pivot_table(pc)
    pt.add_calculated_item("region", "a", "= east + west")
    pt.add_calculated_item("region", "b", "= east - west")
    assert len(pt.calculated_items) == 2


def test_pt_calc_items_in_to_rust_dict():
    pc = _materialized_cache()
    pt = _pivot_table(pc)
    pt.add_calculated_item("region", "ew", "= east + west")
    d = pt.to_rust_dict()
    assert "calculated_items" in d
    assert len(d["calculated_items"]) == 1
    assert d["calculated_items"][0]["item_name"] == "ew"


def test_pt_no_calc_items_emits_empty_list():
    pc = _materialized_cache()
    pt = _pivot_table(pc)
    d = pt.to_rust_dict()
    assert d["calculated_items"] == []


# ---------------------------------------------------------------------------
# PyO3 round-trip
# ---------------------------------------------------------------------------


def test_serialize_pivot_table_with_calc_items():
    from wolfxl._rust import serialize_pivot_table_dict

    pc = _materialized_cache()
    pt = _pivot_table(pc)
    pt.add_calculated_item("region", "ew", "east + west")
    cache_d = pc.to_rust_dict()
    table_d = pt.to_rust_dict()
    xml = serialize_pivot_table_dict(cache_d, table_d)
    s = xml.decode()
    assert "<calculatedItems" in s
    assert "<calculatedItem " in s
    assert 'name="ew"' in s
    assert 'formula="east + west"' in s


def test_serialize_pivot_table_calc_items_count():
    from wolfxl._rust import serialize_pivot_table_dict

    pc = _materialized_cache()
    pt = _pivot_table(pc)
    pt.add_calculated_item("region", "a", "east + west")
    pt.add_calculated_item("region", "b", "east - west")
    cache_d = pc.to_rust_dict()
    table_d = pt.to_rust_dict()
    xml = serialize_pivot_table_dict(cache_d, table_d)
    s = xml.decode()
    assert s.count("<calculatedItem ") == 2


def test_serialize_pivot_table_no_calc_items_no_block():
    from wolfxl._rust import serialize_pivot_table_dict

    pc = _materialized_cache()
    pt = _pivot_table(pc)
    cache_d = pc.to_rust_dict()
    table_d = pt.to_rust_dict()
    xml = serialize_pivot_table_dict(cache_d, table_d)
    s = xml.decode()
    assert "<calculatedItems" not in s


def test_serialize_pivot_table_calc_items_byte_stable():
    from wolfxl._rust import serialize_pivot_table_dict

    pc = _materialized_cache()
    pt = _pivot_table(pc)
    pt.add_calculated_item("region", "ew", "east + west")
    cache_d = pc.to_rust_dict()
    table_d = pt.to_rust_dict()
    a = serialize_pivot_table_dict(cache_d, table_d)
    b = serialize_pivot_table_dict(cache_d, table_d)
    assert a == b


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_calc_item_with_complex_formula():
    ci = CalculatedItem(
        field_name="region",
        item_name="weighted",
        formula="= east * 0.6 + west * 0.4",
    )
    assert ci.to_rust_dict()["item_name"] == "weighted"


def test_calc_item_formula_with_quotes():
    ci = CalculatedItem(
        field_name="r",
        item_name="x",
        formula='= IF(a > 0, "yes", "no")',
    )
    assert "yes" in ci.formula


def test_calc_item_unicode_in_name():
    ci = CalculatedItem(field_name="r", item_name="α", formula="a + b")
    assert ci.item_name == "α"


def test_calc_item_chained_to_rust_dict_order():
    pc = _materialized_cache()
    pt = _pivot_table(pc)
    pt.add_calculated_item("region", "a", "x + 1")
    pt.add_calculated_item("region", "b", "y * 2")
    pt.add_calculated_item("region", "c", "a - b")
    d = pt.to_rust_dict()
    names = [ci["item_name"] for ci in d["calculated_items"]]
    assert names == ["a", "b", "c"]


def test_calc_item_returns_for_chaining():
    pc = _materialized_cache()
    pt = _pivot_table(pc)
    ci = pt.add_calculated_item("region", "x", "= a + b")
    assert ci in pt.calculated_items


def test_calc_item_xml_escapes_special_chars():
    from wolfxl._rust import serialize_pivot_table_dict

    pc = _materialized_cache()
    pt = _pivot_table(pc)
    pt.add_calculated_item("region", "x", "a < b & c > d")
    cache_d = pc.to_rust_dict()
    table_d = pt.to_rust_dict()
    xml = serialize_pivot_table_dict(cache_d, table_d)
    s = xml.decode()
    assert "&lt;" in s
    assert "&amp;" in s
    assert "&gt;" in s


def test_calc_item_formula_unbalanced_paren_rejects():
    with pytest.raises(ValueError):
        CalculatedItem(field_name="r", item_name="x", formula="(a + b")


def test_calc_item_formula_unterminated_string_rejects():
    with pytest.raises(ValueError):
        CalculatedItem(field_name="r", item_name="x", formula='= "hi')


def test_calc_item_dict_roundtrip_preserves_field_name():
    ci = CalculatedItem(field_name="region", item_name="x", formula="= a + b")
    d = ci.to_rust_dict()
    assert d["field_name"] == "region"


def test_calc_item_with_arithmetic_only():
    ci = CalculatedItem(field_name="r", item_name="x", formula="= 100 + 200")
    assert ci.to_rust_dict()["formula"] == " 100 + 200"


def test_pt_calc_item_does_not_affect_data_fields():
    pc = _materialized_cache()
    pt = _pivot_table(pc)
    pt.add_calculated_item("region", "ew", "= east + west")
    d = pt.to_rust_dict()
    # Should still have the original data fields untouched.
    assert len(d["data_fields"]) == 1
