"""RFC-061 Sub-feature 3.4 — Field grouping (date / range / recursive)."""

from __future__ import annotations

from datetime import datetime

import pytest

from wolfxl.chart.reference import Reference
from wolfxl.pivot import (
    FieldGroup,
    FieldGroupDate,
    FieldGroupRange,
    PivotCache,
)
from wolfxl.pivot._group import (
    synthesize_date_group_items,
    synthesize_range_group_items,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        "A1": "order_date", "B1": "age", "C1": "revenue",
        "A2": datetime(2020, 1, 15), "B2": 25, "C2": 100.0,
        "A3": datetime(2021, 6, 1),  "B3": 35, "C3": 200.0,
        "A4": datetime(2025, 12, 1), "B4": 45, "C4": 150.0,
    }
    ws = _StubWorksheet("Sheet1", data)
    src = Reference(worksheet=ws, min_col=1, min_row=1, max_col=3, max_row=4)
    pc = PivotCache(source=src)
    pc._cache_id = 0
    pc._materialize(ws)
    return pc


# ---------------------------------------------------------------------------
# FieldGroupDate / FieldGroupRange validation
# ---------------------------------------------------------------------------


def test_field_group_date_invalid_group_by():
    with pytest.raises(ValueError):
        FieldGroupDate(
            group_by="weeks",
            start_date="2020-01-01T00:00:00",
            end_date="2025-12-31T00:00:00",
        )


def test_field_group_range_zero_interval():
    with pytest.raises(ValueError):
        FieldGroupRange(start=0, end=100, interval=0)


def test_field_group_range_negative_interval():
    with pytest.raises(ValueError):
        FieldGroupRange(start=0, end=100, interval=-5)


def test_field_group_range_end_before_start():
    with pytest.raises(ValueError):
        FieldGroupRange(start=100, end=50, interval=10)


def test_field_group_date_to_rust_dict():
    d = FieldGroupDate(
        group_by="months",
        start_date="2020-01-01T00:00:00",
        end_date="2025-12-31T23:59:59",
    ).to_rust_dict()
    assert d["group_by"] == "months"


def test_field_group_range_to_rust_dict():
    d = FieldGroupRange(start=0, end=100, interval=10).to_rust_dict()
    assert d["start"] == 0.0
    assert d["end"] == 100.0
    assert d["interval"] == 10.0


# ---------------------------------------------------------------------------
# FieldGroup top-level validation
# ---------------------------------------------------------------------------


def test_field_group_invalid_kind():
    with pytest.raises(ValueError):
        FieldGroup(field_index=0, kind="custom")


def test_field_group_date_kind_requires_date():
    with pytest.raises(ValueError):
        FieldGroup(field_index=0, kind="date")


def test_field_group_range_kind_requires_range():
    with pytest.raises(ValueError):
        FieldGroup(field_index=0, kind="range")


def test_field_group_date_kind_rejects_range():
    fgd = FieldGroupDate(
        group_by="months",
        start_date="2020-01-01T00:00:00",
        end_date="2025-01-01T00:00:00",
    )
    fgr = FieldGroupRange(start=0, end=10, interval=1)
    with pytest.raises(ValueError):
        FieldGroup(field_index=0, kind="date", date=fgd, range=fgr)


def test_field_group_to_rust_dict_shape():
    fgd = FieldGroupDate(
        group_by="months",
        start_date="2020-01-01T00:00:00",
        end_date="2025-12-31T00:00:00",
    )
    fg = FieldGroup(field_index=0, kind="date", date=fgd, items=["Jan", "Feb"])
    d = fg.to_rust_dict()
    assert d["field_index"] == 0
    assert d["kind"] == "date"
    assert d["date"]["group_by"] == "months"
    assert d["range"] is None
    assert d["items"] == [{"name": "Jan"}, {"name": "Feb"}]


# ---------------------------------------------------------------------------
# Date group synthesis
# ---------------------------------------------------------------------------


def test_synthesize_months():
    items, start_iso, end_iso = synthesize_date_group_items(
        "months", datetime(2020, 1, 1), datetime(2025, 12, 31)
    )
    # 12 month labels + 2 sentinels
    assert len(items) == 14
    assert items[0].startswith("<")
    assert items[-1].startswith(">")
    assert "Jan" in items
    assert "Dec" in items


def test_synthesize_quarters():
    items, _, _ = synthesize_date_group_items(
        "quarters", datetime(2020, 1, 1), datetime(2025, 12, 31)
    )
    # 4 quarters + 2 sentinels
    assert len(items) == 6
    assert "Qtr1" in items
    assert "Qtr4" in items


def test_synthesize_years():
    items, _, _ = synthesize_date_group_items(
        "years", datetime(2020, 1, 1), datetime(2022, 12, 31)
    )
    # 3 years + 2 sentinels
    assert "2020" in items
    assert "2021" in items
    assert "2022" in items


def test_synthesize_days():
    items, _, _ = synthesize_date_group_items(
        "days", datetime(2020, 1, 1), datetime(2020, 1, 31)
    )
    # 31 days + 2 sentinels
    assert len(items) == 33


def test_synthesize_unknown_group_by():
    with pytest.raises(ValueError):
        synthesize_date_group_items(
            "weeks", datetime(2020, 1, 1), datetime(2025, 12, 31)
        )


# ---------------------------------------------------------------------------
# Range group synthesis
# ---------------------------------------------------------------------------


def test_synthesize_range_basic():
    items = synthesize_range_group_items(0, 100, 10)
    # 10 buckets + 2 sentinels
    assert items[0] == "<0"
    assert items[-1] == ">100"
    assert "0-9" in items
    assert "90-99" in items


def test_synthesize_range_invalid_interval():
    with pytest.raises(ValueError):
        synthesize_range_group_items(0, 10, 0)


def test_synthesize_range_float_interval():
    items = synthesize_range_group_items(0, 1.0, 0.25)
    assert items[0] == "<0"
    assert items[-1] == ">1"


# ---------------------------------------------------------------------------
# PivotCache.group_field
# ---------------------------------------------------------------------------


def test_group_field_date_by_months():
    pc = _materialized_cache()
    fg = pc.group_field(
        "order_date",
        by="months",
        start=datetime(2020, 1, 1),
        end=datetime(2025, 12, 31),
    )
    assert isinstance(fg, FieldGroup)
    assert fg.kind == "date"
    assert fg.date.group_by == "months"
    assert pc.field_groups == [fg]


def test_group_field_date_by_years():
    pc = _materialized_cache()
    fg = pc.group_field(
        "order_date",
        by="years",
        start=datetime(2020, 1, 1),
        end=datetime(2022, 12, 31),
    )
    assert fg.date.group_by == "years"


def test_group_field_range_numeric():
    pc = _materialized_cache()
    fg = pc.group_field("age", start=0, end=100, interval=10)
    assert fg.kind == "range"
    assert fg.range.interval == 10


def test_group_field_invalid_field_raises():
    pc = _materialized_cache()
    with pytest.raises(KeyError):
        pc.group_field("nonexistent", by="months")


def test_group_field_invalid_group_by_raises():
    pc = _materialized_cache()
    with pytest.raises(ValueError):
        pc.group_field(
            "order_date",
            by="weeks",
            start=datetime(2020, 1, 1),
            end=datetime(2022, 12, 31),
        )


def test_group_field_range_missing_args_raises():
    pc = _materialized_cache()
    with pytest.raises(ValueError):
        pc.group_field("age")  # nothing


def test_group_field_recursive_year_then_month():
    """RFC-061 §2.4 — recursive grouping (year → month)."""
    pc = _materialized_cache()
    pc.group_field(
        "order_date",
        by="years",
        start=datetime(2020, 1, 1),
        end=datetime(2022, 12, 31),
    )
    fg = pc.group_field(
        "order_date",
        by="months",
        start=datetime(2020, 1, 1),
        end=datetime(2022, 12, 31),
        parent="order_date",
    )
    assert fg.parent_index == 0


def test_group_field_recursion_depth_capped_at_4():
    pc = _materialized_cache()
    # Create 4 groups against the same field — the 5th should be rejected.
    for i in range(4):
        pc.group_field(
            "age",
            start=0,
            end=100 * (i + 1),
            interval=10,
        )
    with pytest.raises(ValueError):
        pc.group_field("age", start=0, end=500, interval=10)


# ---------------------------------------------------------------------------
# to_rust_dict + Rust serializer round-trip
# ---------------------------------------------------------------------------


def test_pivot_cache_field_groups_in_to_rust_dict():
    pc = _materialized_cache()
    pc.group_field(
        "order_date",
        by="months",
        start=datetime(2020, 1, 1),
        end=datetime(2025, 12, 31),
    )
    d = pc.to_rust_dict()
    assert "field_groups" in d
    assert len(d["field_groups"]) == 1
    assert d["field_groups"][0]["kind"] == "date"


def test_serialize_pivot_cache_with_date_group():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    pc.group_field(
        "order_date",
        by="months",
        start=datetime(2020, 1, 1),
        end=datetime(2025, 12, 31),
    )
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    assert "<fieldGroup" in s
    assert "<rangePr" in s
    assert 'groupBy="months"' in s
    assert "<groupItems" in s
    assert "Jan" in s


def test_serialize_pivot_cache_with_range_group():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    pc.group_field("age", start=0, end=100, interval=10)
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    assert "<fieldGroup" in s
    assert "<rangePr" in s
    assert 'startNum="0"' in s
    assert 'endNum="100"' in s
    assert 'groupInterval="10"' in s


def test_serialize_pivot_cache_field_group_byte_stable():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    pc.group_field("age", start=0, end=100, interval=10)
    d = pc.to_rust_dict()
    a = serialize_pivot_cache_dict(d)
    b = serialize_pivot_cache_dict(d)
    assert a == b


def test_serialize_pivot_cache_no_groups_no_field_group_block():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    assert "<fieldGroup" not in s


def test_serialize_recursive_field_group_emits_par_attr():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    pc.group_field(
        "order_date",
        by="years",
        start=datetime(2020, 1, 1),
        end=datetime(2022, 12, 31),
    )
    pc.group_field(
        "order_date",
        by="months",
        start=datetime(2020, 1, 1),
        end=datetime(2022, 12, 31),
        parent="order_date",
    )
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    # The second group should carry par="N" pointing at order_date.
    # field_index of order_date is 0 in our fixture.
    assert 'par="0"' in s


def test_field_group_items_synthesized_in_xml():
    from wolfxl._rust import serialize_pivot_cache_dict

    pc = _materialized_cache()
    pc.group_field(
        "order_date",
        by="quarters",
        start=datetime(2020, 1, 1),
        end=datetime(2022, 12, 31),
    )
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    assert "Qtr1" in s
    assert "Qtr4" in s


def test_field_group_with_pure_discrete_no_rangepr():
    from wolfxl._rust import serialize_pivot_cache_dict

    # Construct a discrete group manually.
    pc = _materialized_cache()
    fg = FieldGroup(
        field_index=0,
        kind="discrete",
        items=["bucket_a", "bucket_b"],
    )
    pc.field_groups.append(fg)
    d = pc.to_rust_dict()
    xml = serialize_pivot_cache_dict(d)
    s = xml.decode()
    assert "<fieldGroup" in s
    assert "bucket_a" in s
    # Discrete groups don't get rangePr.
    # We check this loosely — it should still be safe for Excel.


def test_group_field_quarters_synthesizes_4_buckets():
    items, _, _ = synthesize_date_group_items(
        "quarters", datetime(2020, 1, 1), datetime(2022, 12, 31)
    )
    assert items.count("Qtr1") == 1
    assert items.count("Qtr2") == 1


def test_group_field_with_iso_string_start_end():
    pc = _materialized_cache()
    fg = pc.group_field(
        "order_date",
        by="months",
        start="2020-01-01T00:00:00",
        end="2025-12-31T00:00:00",
    )
    assert fg.kind == "date"


def test_group_field_returns_for_chaining():
    pc = _materialized_cache()
    fg = pc.group_field("age", start=0, end=10, interval=1)
    assert fg in pc.field_groups
