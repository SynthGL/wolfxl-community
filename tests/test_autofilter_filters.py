"""Sprint Ο Pod 1B (RFC-056) — AutoFilter class construction + dict
round-trip tests.

These tests exercise only the Python dataclass / dict-shape layer
(no Rust patcher save). The XML emit + filter-evaluation pinning
lives in the Rust crate's own tests.
"""
from __future__ import annotations

import pytest

from wolfxl.worksheet.filters import (
    AutoFilter,
    BlankFilter,
    ColorFilter,
    CustomFilter,
    CustomFilters,
    DateGroupItem,
    DynamicFilter,
    FilterColumn,
    IconFilter,
    NumberFilter,
    SortCondition,
    SortState,
    StringFilter,
    Top10,
)


class TestFilterClassConstruction:
    """Each of the 11 filter classes can be constructed and the
    dataclass field defaults are sane."""

    def test_blank(self) -> None:
        b = BlankFilter()
        assert b == BlankFilter()

    def test_color_default(self) -> None:
        c = ColorFilter()
        assert c.dxf_id is None
        assert c.cell_color is None

    def test_color_font(self) -> None:
        c = ColorFilter(dxf_id=5, cell_color=False)
        assert c.dxf_id == 5
        assert c.cell_color is False

    def test_custom_filter(self) -> None:
        c = CustomFilter(operator="greaterThan", val="100")
        assert c.operator == "greaterThan"
        assert c.val == "100"

    def test_custom_filters_or(self) -> None:
        c = CustomFilters(
            customFilter=[
                CustomFilter(operator="greaterThan", val="5"),
                CustomFilter(operator="lessThan", val="100"),
            ],
        )
        assert c.and_ is None
        assert len(c.customFilter) == 2
        # Alias property
        assert c.filters is c.customFilter

    def test_custom_filters_and(self) -> None:
        c = CustomFilters(
            customFilter=[CustomFilter(operator="equal", val="x")], and_=True
        )
        assert c.and_ is True

    def test_date_group_item(self) -> None:
        d = DateGroupItem(year=2024, month=3, date_time_grouping="month")
        assert d.year == 2024
        assert d.month == 3
        assert d.day is None
        assert d.date_time_grouping == "month"

    def test_dynamic_filter_today(self) -> None:
        d = DynamicFilter(type="today")
        assert d.type == "today"
        assert d.val is None

    def test_dynamic_filter_above_average(self) -> None:
        d = DynamicFilter(type="aboveAverage", val=42.0)
        assert d.val == 42.0

    def test_dynamic_filter_quarter(self) -> None:
        d = DynamicFilter(type="Q3")
        assert d.type == "Q3"

    def test_dynamic_filter_month(self) -> None:
        d = DynamicFilter(type="M11")
        assert d.type == "M11"

    def test_icon_filter(self) -> None:
        i = IconFilter(icon_set="5Quarters", icon_id=2)
        assert i.icon_set == "5Quarters"
        assert i.icon_id == 2

    def test_number_filter(self) -> None:
        n = NumberFilter(filters=[1.0, 2.5, 3.0])
        assert n.filters == [1.0, 2.5, 3.0]
        assert n.blank is False

    def test_number_filter_with_blank(self) -> None:
        n = NumberFilter(filters=[1.0], blank=True)
        assert n.blank is True

    def test_string_filter(self) -> None:
        s = StringFilter(values=["red", "blue"])
        assert s.values == ["red", "blue"]

    def test_top10_default(self) -> None:
        t = Top10(val=10.0)
        assert t.top is None
        assert t.percent is None
        assert t.val == 10.0
        assert t.filter_val is None

    def test_top10_bottom_percent(self) -> None:
        t = Top10(top=False, percent=True, val=25.0)
        assert t.top is False
        assert t.percent is True


class TestFilterColumn:
    def test_default(self) -> None:
        fc = FilterColumn(col_id=0)
        assert fc.col_id == 0
        assert fc.show_button is True
        assert fc.hidden_button is False
        assert fc.filter is None

    def test_with_number_filter(self) -> None:
        fc = FilterColumn(col_id=2, filter=NumberFilter(filters=[100, 200]))
        assert isinstance(fc.filter, NumberFilter)
        assert fc.filter.filters == [100, 200]


class TestSortCondition:
    def test_default(self) -> None:
        sc = SortCondition(ref="A2:A100")
        assert sc.descending is None
        assert sc.sort_by is None

    def test_descending(self) -> None:
        sc = SortCondition(ref="B2:B50", descending=True, sort_by="cellColor")
        assert sc.descending is True
        assert sc.sort_by == "cellColor"


class TestSortState:
    def test_empty(self) -> None:
        s = SortState()
        assert s.sort_conditions == []

    def test_with_condition(self) -> None:
        s = SortState(
            sort_conditions=[SortCondition(ref="A2:A100", descending=True)],
            ref="A2:A100",
        )
        assert len(s.sort_conditions) == 1
        assert s.sort_conditions[0].descending is True


class TestAutoFilterDataclass:
    def test_default(self) -> None:
        af = AutoFilter()
        assert af.ref is None
        assert af.filter_columns == []
        assert af.sort_state is None

    def test_add_filter_column(self) -> None:
        af = AutoFilter(ref="A1:D100")
        af.add_filter_column(0, NumberFilter(filters=[1, 2, 3]))
        fc = af.filter_columns[0]
        assert fc.col_id == 0
        assert af.filter_columns == [fc]

    def test_add_sort_condition(self) -> None:
        af = AutoFilter(ref="A1:D100")
        af.add_sort_condition("A2:A100", descending=True)
        sc = af.sort_state.sort_conditions[0]
        assert af.sort_state is not None
        assert af.sort_state.sort_conditions[0] is sc

    def test_add_multiple_sort_conditions(self) -> None:
        af = AutoFilter()
        af.add_sort_condition("A2:A100", descending=True)
        af.add_sort_condition("B2:B100", descending=False)
        assert af.sort_state is not None
        assert len(af.sort_state.sort_conditions) == 2


class TestToRustDictRoundTrip:
    """The §10 dict shape carries each filter kind through unmolested."""

    def test_empty(self) -> None:
        af = AutoFilter()
        d = af.to_rust_dict()
        assert d == {"ref": None, "filter_columns": [], "sort_state": None}

    def test_ref_only(self) -> None:
        af = AutoFilter(ref="A1:D10")
        d = af.to_rust_dict()
        assert d["ref"] == "A1:D10"

    def test_blank_filter(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, BlankFilter())
        d = af.to_rust_dict()
        assert d["filter_columns"][0]["filter"] == {"kind": "blank"}

    def test_number_filter_dict_shape(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, NumberFilter(filters=[1.0, 2.0], blank=True))
        d = af.to_rust_dict()
        f = d["filter_columns"][0]["filter"]
        assert f["kind"] == "number"
        assert f["filters"] == [1.0, 2.0]
        assert f["blank"] is True

    def test_string_filter_dict_shape(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, StringFilter(values=["a", "b"]))
        d = af.to_rust_dict()
        f = d["filter_columns"][0]["filter"]
        assert f["kind"] == "string"
        assert f["values"] == ["a", "b"]

    def test_custom_filters_dict_shape(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(
            0,
            CustomFilters(
                customFilter=[
                    CustomFilter(operator="greaterThan", val="10"),
                    CustomFilter(operator="lessThan", val="100"),
                ],
                and_=True,
            ),
        )
        d = af.to_rust_dict()
        f = d["filter_columns"][0]["filter"]
        assert f["kind"] == "custom"
        assert f["and_"] is True
        assert len(f["filters"]) == 2
        assert f["filters"][0]["operator"] == "greaterThan"

    def test_dynamic_filter_dict_shape(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, DynamicFilter(type="aboveAverage", val=42.0))
        d = af.to_rust_dict()
        f = d["filter_columns"][0]["filter"]
        assert f["kind"] == "dynamic"
        assert f["type"] == "aboveAverage"
        assert f["val"] == 42.0

    def test_top10_dict_shape(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, Top10(top=False, percent=True, val=25.0))
        d = af.to_rust_dict()
        f = d["filter_columns"][0]["filter"]
        assert f["kind"] == "top10"
        assert f["top"] is False
        assert f["percent"] is True
        assert f["val"] == 25.0

    def test_color_filter_dict_shape(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, ColorFilter(dxf_id=3, cell_color=False))
        d = af.to_rust_dict()
        f = d["filter_columns"][0]["filter"]
        assert f["kind"] == "color"
        assert f["dxf_id"] == 3
        assert f["cell_color"] is False

    def test_icon_filter_dict_shape(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, IconFilter(icon_set="3Arrows", icon_id=1))
        d = af.to_rust_dict()
        f = d["filter_columns"][0]["filter"]
        assert f["kind"] == "icon"
        assert f["icon_set"] == "3Arrows"
        assert f["icon_id"] == 1

    def test_sort_state_dict_shape(self) -> None:
        af = AutoFilter()
        af.add_sort_condition("A2:A100", descending=True)
        d = af.to_rust_dict()
        s = d["sort_state"]
        assert s["sort_conditions"][0]["descending"] is True
        assert s["sort_conditions"][0]["ref"] == "A2:A100"

    def test_date_group_item_dict_shape(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(
            0,
            None,
            date_group_items=[
                DateGroupItem(
                    year=2024, month=3, day=15, date_time_grouping="day"
                )
            ],
        )
        d = af.to_rust_dict()
        dgis = d["filter_columns"][0]["date_group_items"]
        assert len(dgis) == 1
        assert dgis[0]["year"] == 2024
        assert dgis[0]["date_time_grouping"] == "day"

    def test_show_button_default_true(self) -> None:
        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, NumberFilter(filters=[1]))
        d = af.to_rust_dict()
        assert d["filter_columns"][0]["show_button"] is True


class TestSerializeAutofilterDict:
    """Round-trip Python dict → Rust XML emit via the PyO3 binding."""

    def test_serialize_empty_returns_empty_bytes(self) -> None:
        from wolfxl import _rust

        b = _rust.serialize_autofilter_dict(AutoFilter().to_rust_dict())
        # Empty model returns no bytes (caller skips the splice).
        assert b == b""

    def test_serialize_ref_only(self) -> None:
        from wolfxl import _rust

        b = _rust.serialize_autofilter_dict(AutoFilter(ref="A1:D100").to_rust_dict())
        assert b == b'<autoFilter ref="A1:D100"/>'

    def test_serialize_number_filter(self) -> None:
        from wolfxl import _rust

        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, NumberFilter(filters=[100, 200]))
        b = _rust.serialize_autofilter_dict(af.to_rust_dict())
        s = b.decode()
        assert '<autoFilter ref="A1:A10">' in s
        assert '<filter val="100"/>' in s
        assert '<filter val="200"/>' in s
        assert s.endswith("</autoFilter>")

    def test_serialize_top10(self) -> None:
        from wolfxl import _rust

        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, Top10(val=5.0))
        b = _rust.serialize_autofilter_dict(af.to_rust_dict())
        assert b'<top10 val="5"/>' in b

    def test_serialize_string_filter_escapes_xml(self) -> None:
        from wolfxl import _rust

        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(0, StringFilter(values=["<tag>", "&amp"]))
        b = _rust.serialize_autofilter_dict(af.to_rust_dict()).decode()
        assert "&lt;tag&gt;" in b
        assert "&amp;amp" in b

    def test_serialize_custom_filters_with_and(self) -> None:
        from wolfxl import _rust

        af = AutoFilter(ref="A1:A10")
        af.add_filter_column(
            0,
            CustomFilters(
                customFilter=[CustomFilter(operator="greaterThan", val="10")],
                and_=True,
            ),
        )
        b = _rust.serialize_autofilter_dict(af.to_rust_dict()).decode()
        assert 'and="1"' in b
        assert 'operator="greaterThan"' in b

    def test_serialize_sort_state(self) -> None:
        from wolfxl import _rust

        af = AutoFilter()
        af.ref = "A1:D100"
        af.add_sort_condition("A2:A100", descending=True)
        b = _rust.serialize_autofilter_dict(af.to_rust_dict()).decode()
        assert "<sortState" in b
        assert '<sortCondition ref="A2:A100" descending="1"/>' in b


def test_set_autofilter_native_wraps_writer_errors() -> None:
    from wolfxl._worksheet_flush import _set_autofilter_native

    class FailingWriter:
        def set_autofilter_native(self, _sheet, _payload):
            raise ValueError("bad filter")

    af = AutoFilter(ref="A1:A10")
    with pytest.raises(RuntimeError, match="failed to write autofilter for sheet 'Sheet'") as exc:
        _set_autofilter_native(FailingWriter(), "Sheet", af)

    assert isinstance(exc.value.__cause__, ValueError)


class TestWorksheetAutoFilterIntegration:
    """`ws.auto_filter` proxy exposes the same surface."""

    def test_proxy_default(self) -> None:
        from wolfxl import Workbook

        wb = Workbook()
        ws = wb.active
        assert ws.auto_filter.ref is None
        assert ws.auto_filter.filter_columns == []
        assert ws.auto_filter.sort_state is None

    def test_proxy_set_ref(self) -> None:
        from wolfxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.auto_filter.ref = "A1:D100"
        assert ws.auto_filter.ref == "A1:D100"

    def test_proxy_add_filter_column(self) -> None:
        from wolfxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.auto_filter.ref = "A1:D100"
        ws.auto_filter.add_filter_column(0, NumberFilter(filters=[100, 200, 300]))
        fc = ws.auto_filter.filter_columns[0]
        assert fc.col_id == 0
        assert isinstance(fc.filter, NumberFilter)
        assert ws.auto_filter.filter_columns == [fc]

    def test_proxy_add_sort_condition(self) -> None:
        from wolfxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.auto_filter.add_sort_condition("A2:A100", descending=True)
        assert ws.auto_filter.sort_state is not None
        assert len(ws.auto_filter.sort_state.sort_conditions) == 1

    def test_proxy_to_rust_dict(self) -> None:
        from wolfxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.auto_filter.ref = "A1:D10"
        ws.auto_filter.add_filter_column(0, StringFilter(values=["red"]))
        d = ws.auto_filter.to_rust_dict()
        assert d["ref"] == "A1:D10"
        assert d["filter_columns"][0]["filter"]["kind"] == "string"
