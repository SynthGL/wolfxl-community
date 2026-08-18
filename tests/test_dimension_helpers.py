"""RFC-062 §2.2 — DimensionHolder / SheetFormatProperties / SheetDimension.

Sprint Π Pod Π-α. Construction, dict-like routing for DimensionHolder,
defaults and ``to_rust_dict()`` contract for the §10 dict shape.
"""

from __future__ import annotations

import pytest

from wolfxl import Workbook
from wolfxl.worksheet.dimensions import (
    ColumnDimension,
    Dimension,
    DimensionHolder,
    RowDimension,
    SheetDimension,
    SheetFormatProperties,
)


# ---------------------------------------------------------------------------
# DimensionHolder
# ---------------------------------------------------------------------------


class TestDimensionHolder:
    def test_construction_minimal(self):
        wb = Workbook()
        ws = wb.active
        dh = DimensionHolder(ws)
        assert dh.worksheet is ws
        assert dh.default_factory is None
        assert dh.max_outline == 0

    def test_construction_with_overrides(self):
        wb = Workbook()
        ws = wb.active
        dh = DimensionHolder(worksheet=ws, default_factory=int, max_outline=3)
        assert dh.default_factory is int
        assert dh.max_outline == 3

    def test_routes_getitem_to_row_dimensions(self):
        wb = Workbook()
        ws = wb.active
        dh = DimensionHolder(ws)
        # ``dh[1]`` and ``ws.row_dimensions[1]`` materialise the same
        # logical row dimension. Wolfxl's proxy returns a fresh
        # _RowDimension wrapper per access, so compare via type and
        # the row index they bind to (and a writable height
        # round-trip to confirm shared storage).
        a = dh[1]
        b = ws.row_dimensions[1]
        assert type(a) is type(b)
        a.height = 22.5
        assert ws.row_dimensions[1].height == 22.5

    def test_iter_routes_to_proxy(self):
        wb = Workbook()
        ws = wb.active
        dh = DimensionHolder(ws)
        # Does not raise.
        list(iter(dh))

    def test_len_routes_to_proxy(self):
        wb = Workbook()
        ws = wb.active
        dh = DimensionHolder(ws)
        # Does not raise.
        n = len(dh)
        assert isinstance(n, int)

    def test_dimension_holder_property(self):
        wb = Workbook()
        ws = wb.active
        dh = ws.dimension_holder
        assert isinstance(dh, DimensionHolder)
        assert dh.worksheet is ws

    def test_dimension_holder_property_returns_fresh_view(self):
        # Each access constructs a fresh view (no caching). Matches
        # openpyxl semantics where DimensionHolder is a view, not a
        # singleton.
        wb = Workbook()
        ws = wb.active
        dh1 = ws.dimension_holder
        dh2 = ws.dimension_holder
        assert dh1 is not dh2
        # But both bind to the same worksheet.
        assert dh1.worksheet is dh2.worksheet


# ---------------------------------------------------------------------------
# SheetFormatProperties
# ---------------------------------------------------------------------------


class TestSheetFormatPropertiesDefaults:
    def test_default_values(self):
        sf = SheetFormatProperties()
        assert sf.baseColWidth == 8
        assert sf.defaultColWidth is None
        assert sf.defaultRowHeight == 15.0
        assert sf.customHeight is None
        assert sf.zeroHeight is None
        assert sf.thickTop is None
        assert sf.thickBottom is None
        assert sf.outlineLevelRow == 0
        assert sf.outlineLevelCol == 0

    def test_is_default_on_construction(self):
        assert SheetFormatProperties().is_default()

    def test_is_default_false_after_mutation(self):
        sf = SheetFormatProperties()
        sf.defaultRowHeight = 20.0
        assert not sf.is_default()

    def test_is_default_false_when_outline_set(self):
        sf = SheetFormatProperties(outlineLevelRow=2)
        assert not sf.is_default()

    def test_is_default_false_when_thick_top(self):
        sf = SheetFormatProperties(thickTop=True)
        assert not sf.is_default()

    def test_construction_with_overrides(self):
        sf = SheetFormatProperties(
            baseColWidth=10,
            defaultColWidth=12.5,
            defaultRowHeight=18.0,
            zeroHeight=True,
        )
        assert sf.baseColWidth == 10
        assert sf.defaultColWidth == 12.5
        assert sf.defaultRowHeight == 18.0
        assert sf.zeroHeight is True


class TestSheetFormatPropertiesRustDict:
    def test_default_dict_shape(self):
        sf = SheetFormatProperties()
        d = sf.to_rust_dict()
        assert d == {
            "base_col_width": 8,
            "default_col_width": None,
            "default_row_height": 15.0,
            "custom_height": None,
            "zero_height": None,
            "thick_top": None,
            "thick_bottom": None,
            "outline_level_row": 0,
            "outline_level_col": 0,
        }

    def test_custom_dict(self):
        sf = SheetFormatProperties(
            defaultRowHeight=22.0,
            outlineLevelRow=2,
            outlineLevelCol=1,
        )
        d = sf.to_rust_dict()
        assert d["default_row_height"] == 22.0
        assert d["outline_level_row"] == 2
        assert d["outline_level_col"] == 1


class TestWorksheetSheetFormat:
    def test_lazy_access(self):
        wb = Workbook()
        ws = wb.active
        sf = ws.sheet_format
        assert isinstance(sf, SheetFormatProperties)
        assert sf.is_default()

    def test_same_instance_returned(self):
        wb = Workbook()
        ws = wb.active
        a = ws.sheet_format
        b = ws.sheet_format
        assert a is b

    def test_zero_overhead_when_untouched(self):
        wb = Workbook()
        ws = wb.active
        assert ws._sheet_format is None

    def test_replacement_assignment(self):
        wb = Workbook()
        ws = wb.active
        new_sf = SheetFormatProperties(defaultRowHeight=30.0)
        ws.sheet_format = new_sf
        assert ws.sheet_format is new_sf

    def test_to_rust_sheet_format_dict_returns_none_at_default(self):
        wb = Workbook()
        ws = wb.active
        # Untouched: returns None.
        assert ws.to_rust_sheet_format_dict() is None
        # Lazy init but unchanged: still None.
        _ = ws.sheet_format
        assert ws.to_rust_sheet_format_dict() is None

    def test_to_rust_sheet_format_dict_after_change(self):
        wb = Workbook()
        ws = wb.active
        ws.sheet_format.defaultRowHeight = 25.0
        d = ws.to_rust_sheet_format_dict()
        assert d is not None
        assert d["default_row_height"] == 25.0


# ---------------------------------------------------------------------------
# SheetDimension
# ---------------------------------------------------------------------------


class TestSheetDimension:
    def test_default_ref(self):
        sd = SheetDimension()
        assert sd.ref == "A1"

    def test_construction_with_ref(self):
        sd = SheetDimension(ref="A1:Z100")
        assert sd.ref == "A1:Z100"

    def test_to_rust_dict(self):
        sd = SheetDimension(ref="B2:E50")
        assert sd.to_rust_dict() == {"ref": "B2:E50"}


# ---------------------------------------------------------------------------
# Dimension abstract base — advisory only
# ---------------------------------------------------------------------------


class TestDimensionAbstract:
    def test_dimension_requires_openpyxl_constructor_fields(self):
        with pytest.raises(TypeError):
            Dimension()

        d = Dimension(index=1, hidden=True, outlineLevel=1, collapsed=False, worksheet=object())
        assert dict(d) == {"hidden": "1", "outlineLevel": "1"}

    def test_row_column_dimension_imports_succeed(self):
        # The shim re-exports the underscore-prefixed proxies.
        assert RowDimension is not None
        assert ColumnDimension is not None


# ---------------------------------------------------------------------------
# SheetFormatProperties save round-trip
# ---------------------------------------------------------------------------


class TestSheetFormatSaveRoundTrip:
    def test_save_with_custom_row_height(self, tmp_path):
        import zipfile

        p = tmp_path / "fmt.xlsx"
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "x"
        ws.sheet_format.defaultRowHeight = 20.0
        wb.save(str(p))
        with zipfile.ZipFile(p) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode()
        assert 'defaultRowHeight="20"' in xml

    def test_save_at_default_keeps_legacy_emit(self, tmp_path):
        import zipfile

        p = tmp_path / "default.xlsx"
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "x"
        # Don't mutate sheet_format — legacy emit path stays.
        wb.save(str(p))
        with zipfile.ZipFile(p) as z:
            xml = z.read("xl/worksheets/sheet1.xml").decode()
        # Legacy default still present.
        assert '<sheetFormatPr defaultRowHeight="15"/>' in xml
