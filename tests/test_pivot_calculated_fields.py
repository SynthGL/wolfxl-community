"""RFC-061 Sub-feature 3.2 — Calculated fields (~30 tests)."""

from __future__ import annotations

import pytest

from wolfxl.chart.reference import Reference
from wolfxl.pivot import CalculatedField, PivotCache


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
        "A1": "region", "B1": "revenue", "C1": "cost",
        "A2": "North",  "B2": 100.0,     "C2": 60.0,
        "A3": "South",  "B3": 200.0,     "C3": 90.0,
    }
    ws = _StubWorksheet("Sheet1", data)
    src = Reference(worksheet=ws, min_col=1, min_row=1, max_col=3, max_row=3)
    pc = PivotCache(source=src)
    pc._cache_id = 0
    pc._materialize(ws)
    return pc


# ---------------------------------------------------------------------------
# CalculatedField construction validation
# ---------------------------------------------------------------------------


def test_calculated_field_requires_name():
    with pytest.raises(ValueError):
        CalculatedField(name="", formula="= a + b")


def test_calculated_field_requires_formula():
    with pytest.raises(ValueError):
        CalculatedField(name="profit", formula="")


def test_calculated_field_invalid_data_type():
    with pytest.raises(ValueError):
        CalculatedField(name="x", formula="= a + b", data_type="float")


def test_calculated_field_default_data_type_is_number():
    cf = CalculatedField(name="profit", formula="= revenue - cost")
    assert cf.data_type == "number"


def test_calculated_field_supports_string_type():
    cf = CalculatedField(name="x", formula='= "hello"', data_type="string")
    assert cf.data_type == "string"


def test_calculated_field_supports_boolean_type():
    cf = CalculatedField(name="x", formula="= a > b", data_type="boolean")
    assert cf.data_type == "boolean"


def test_calculated_field_supports_date_type():
    cf = CalculatedField(name="x", formula="= today()", data_type="date")
    assert cf.data_type == "date"


# ---------------------------------------------------------------------------
# Formula structural validation
# ---------------------------------------------------------------------------


def test_formula_unbalanced_paren_raises():
    with pytest.raises(ValueError):
        CalculatedField(name="x", formula="= (a + b")


def test_formula_unbalanced_close_paren_raises():
    with pytest.raises(ValueError):
        CalculatedField(name="x", formula="= a + b)")


def test_formula_unterminated_string_raises():
    with pytest.raises(ValueError):
        CalculatedField(name="x", formula='= "hello')


def test_formula_balanced_parens_accepted():
    cf = CalculatedField(name="x", formula="= sum((a + b) * c)")
    assert cf.formula == "= sum((a + b) * c)"


def test_formula_string_literal_accepted():
    cf = CalculatedField(name="x", formula='= "hello world"')
    assert cf.formula == '= "hello world"'


def test_formula_leading_equals_optional():
    cf = CalculatedField(name="x", formula="a + b")
    # Stored as-is, but to_rust_dict strips leading '='.
    assert cf.to_rust_dict()["formula"] == "a + b"


def test_formula_leading_equals_stripped_in_dict():
    cf = CalculatedField(name="x", formula="= a + b")
    assert cf.to_rust_dict()["formula"] == " a + b"


# ---------------------------------------------------------------------------
# to_rust_dict shape
# ---------------------------------------------------------------------------


def test_calculated_field_to_rust_dict_shape():
    cf = CalculatedField(name="profit", formula="= revenue - cost")
    d = cf.to_rust_dict()
    assert d["name"] == "profit"
    assert "formula" in d
    assert d["data_type"] == "number"


# ---------------------------------------------------------------------------
# PivotCache.add_calculated_field()
# ---------------------------------------------------------------------------


def test_pivot_cache_add_calculated_field():
    pc = _materialized_cache()
    cf = pc.add_calculated_field("profit", "= revenue - cost")
    assert isinstance(cf, CalculatedField)
    assert cf.name == "profit"
    assert pc.calculated_fields == [cf]


def test_pivot_cache_add_multiple_calculated_fields():
    pc = _materialized_cache()
    pc.add_calculated_field("profit", "= revenue - cost")
    pc.add_calculated_field("margin", "= profit / revenue")
    assert len(pc.calculated_fields) == 2


def test_pivot_cache_calculated_fields_in_to_rust_dict():
    pc = _materialized_cache()
    pc.add_calculated_field("profit", "= revenue - cost")
    d = pc.to_rust_dict()
    assert "calculated_fields" in d
    assert len(d["calculated_fields"]) == 1
    assert d["calculated_fields"][0]["name"] == "profit"


def test_pivot_cache_with_no_calc_fields_emits_empty_list():
    pc = _materialized_cache()
    d = pc.to_rust_dict()
    assert d["calculated_fields"] == []


# ---------------------------------------------------------------------------
# PyO3 round-trip via serialize_pivot_cache_dict
# ---------------------------------------------------------------------------


def test_serialize_pivot_cache_with_calc_field():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    pc.add_calculated_field("profit", "revenue - cost")
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    assert "<calculatedItems" in s
    assert 'count="1"' in s
    assert "<calculatedItem" in s
    assert 'formula="revenue - cost"' in s


def test_serialize_pivot_cache_calc_field_fld_index():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    # 3 cache fields → calc field at fld=3
    pc.add_calculated_field("profit", "revenue - cost")
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    assert 'fld="3"' in s


def test_serialize_pivot_cache_no_calc_field_no_block():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    assert "<calculatedItems" not in s


def test_serialize_pivot_cache_multiple_calc_fields():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    pc.add_calculated_field("profit", "revenue - cost")
    pc.add_calculated_field("margin", "profit / revenue")
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    # Count standalone `<calculatedItem ` (note trailing space) — the
    # `<calculatedItems>` wrapper would otherwise be counted.
    assert s.count("<calculatedItem ") == 2


def test_serialize_pivot_cache_calc_field_byte_stable():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    pc.add_calculated_field("profit", "revenue - cost")
    d = pc.to_rust_dict()
    a = serialize_pivot_cache_dict(d)
    b = serialize_pivot_cache_dict(d)
    assert a == b


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_serialize_pivot_cache_rejects_non_finite_shared_item_bounds(bad):
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    d = pc.to_rust_dict()
    d["fields"][1]["shared_items"]["min_value"] = bad
    with pytest.raises(ValueError, match="non-finite floats"):
        serialize_pivot_cache_dict(d)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_serialize_pivot_records_rejects_non_finite_numeric_values(bad):
    from wolfxl._rust import serialize_pivot_records_dict

    pc = _materialized_cache()
    cache_d = pc.to_rust_dict()
    records_d = pc.to_rust_records_dict()
    records_d["records"][0][1] = {"kind": "number", "value": bad}
    with pytest.raises(ValueError, match="non-finite floats"):
        serialize_pivot_records_dict(cache_d, records_d)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_calc_field_with_complex_formula():
    cf = CalculatedField(name="x", formula="= IF(a > 0, b * 0.1, 0)")
    assert cf.name == "x"


def test_calc_field_formula_with_spaces():
    cf = CalculatedField(name="x", formula="=    a    +    b   ")
    assert cf.formula == "=    a    +    b   "


def test_calc_field_formula_with_quotes():
    cf = CalculatedField(name="x", formula='= IF(a > 0, "yes", "no")')
    assert "yes" in cf.formula


def test_calc_field_unicode_in_name():
    cf = CalculatedField(name="πrofit", formula="= a + b")
    assert cf.name == "πrofit"


def test_pivot_cache_calc_field_chained_to_rust_dict():
    pc = _materialized_cache()
    pc.add_calculated_field("a", "x + 1")
    pc.add_calculated_field("b", "y * 2")
    pc.add_calculated_field("c", "a - b")
    d = pc.to_rust_dict()
    names = [c["name"] for c in d["calculated_fields"]]
    assert names == ["a", "b", "c"]


def test_pivot_cache_calc_field_keeps_data_type():
    pc = _materialized_cache()
    pc.add_calculated_field("flag", "= a > b", data_type="boolean")
    d = pc.to_rust_dict()
    assert d["calculated_fields"][0]["data_type"] == "boolean"


def test_pivot_cache_calc_field_returns_field_for_chaining():
    pc = _materialized_cache()
    cf = pc.add_calculated_field("profit", "= a - b")
    assert cf in pc.calculated_fields


def test_serialize_pivot_cache_calc_field_escapes_xml():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    pc.add_calculated_field("x", "a < b & c")
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    assert "&amp;" in s
    assert "&lt;" in s


def test_calc_field_dict_preserves_formula_after_strip():
    cf = CalculatedField(name="x", formula="= a + b")
    d = cf.to_rust_dict()
    # leading '=' stripped
    assert not d["formula"].startswith("=")


def test_calc_field_no_strip_when_no_equals():
    cf = CalculatedField(name="x", formula="a+b")
    assert cf.to_rust_dict()["formula"] == "a+b"
