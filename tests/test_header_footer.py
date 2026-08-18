"""RFC-055 §2.3 — HeaderFooter tests (Sprint Ο Pod 1A).

Includes the OOXML format-code grammar coverage (`&L`/`&C`/`&R`/`&P`/
`&N`/`&D`/`&T`/`&F`/`&A`/`&Z`/`&K{RRGGBB}`/`&"font,style"`/`&NN`/`&B`/
`&I`/`&U`/`&S`/`&X`/`&Y`/`&&`).
"""

from __future__ import annotations

import pytest

from wolfxl import Workbook
from wolfxl.worksheet.header_footer import (
    HeaderFooter,
    HeaderFooterItem,
    validate_header_footer_format,
)


class TestFormatCodeGrammar:
    def test_simple_text_validates(self):
        assert validate_header_footer_format("Hello")
        assert validate_header_footer_format("")
        assert validate_header_footer_format(None)  # type: ignore[arg-type]

    def test_alignment_codes(self):
        assert validate_header_footer_format("&LLeft")
        assert validate_header_footer_format("&CCenter")
        assert validate_header_footer_format("&RRight")

    def test_page_count_codes(self):
        assert validate_header_footer_format("Page &P of &N")
        assert validate_header_footer_format("&P&N")

    def test_date_time_codes(self):
        assert validate_header_footer_format("&D &T")
        assert validate_header_footer_format("&D")

    def test_file_path_sheet_codes(self):
        assert validate_header_footer_format("&F &Z &A")

    def test_double_ampersand_literal(self):
        assert validate_header_footer_format("&&")
        assert validate_header_footer_format("Tom && Jerry")

    def test_bare_ampersand_at_end_invalid(self):
        assert not validate_header_footer_format("hello&")

    def test_color_hex_short_form(self):
        assert validate_header_footer_format("&Kff0000Red")
        assert validate_header_footer_format("&K00FF00")

    def test_color_hex_brace_form(self):
        assert validate_header_footer_format("&K{FF0000}Red")

    def test_color_hex_invalid_chars_rejected(self):
        # 'X' is not a hex digit — the validator should reject.
        assert not validate_header_footer_format("&KZZZZZZ")

    def test_font_select(self):
        assert validate_header_footer_format('&"Arial,Bold"text')
        assert validate_header_footer_format('&"Times New Roman,Regular"')

    def test_font_size(self):
        assert validate_header_footer_format("&18Hello")
        assert validate_header_footer_format("&8small")

    def test_style_codes(self):
        assert validate_header_footer_format("&BBold&B")
        assert validate_header_footer_format("&IItalic&I")
        assert validate_header_footer_format("&UUnder&U")
        assert validate_header_footer_format("&SStrike&S")
        assert validate_header_footer_format("&XSuper&X")
        assert validate_header_footer_format("&YSub&Y")

    def test_unclosed_font_quote_invalid(self):
        assert not validate_header_footer_format('&"Arial')


class TestHeaderFooterItem:
    def test_default_is_empty(self):
        hfi = HeaderFooterItem()
        assert hfi.is_empty()
        assert hfi.left.text is None
        assert hfi.center.text is None
        assert hfi.right.text is None
        assert hfi.left == None  # noqa: E711 - compare-with-None hits is_empty()

    def test_text_composes_segments(self):
        hfi = HeaderFooterItem(left="L", center="C", right="R")
        # The text accessor concatenates the alignment switches.
        assert hfi.text == "&LL&CC&RR"

    def test_invalid_format_code_raises(self):
        with pytest.raises(ValueError, match="invalid format code"):
            HeaderFooterItem(center="bare&")

    def test_to_rust_dict_returns_none_when_empty(self):
        assert HeaderFooterItem().to_rust_dict() is None


class TestHeaderFooter:
    def test_default_is_default(self):
        hf = HeaderFooter()
        assert hf.is_default()

    def test_set_odd_header_left(self):
        hf = HeaderFooter()
        hf.odd_header.left = "Title"
        assert not hf.is_default()
        assert hf.odd_header.left == "Title"

    def test_camelcase_aliases(self):
        hf = HeaderFooter()
        hf.odd_header.center = "X"
        # openpyxl-shaped alias.
        assert hf.oddHeader is hf.odd_header
        assert hf.evenHeader is hf.even_header
        assert hf.firstFooter is hf.first_footer

    def test_to_rust_dict_emits_none_for_empty_segments(self):
        hf = HeaderFooter()
        hf.odd_header.left = "X"
        d = hf.to_rust_dict()
        assert d["odd_header"] == {"left": "X", "center": None, "right": None}
        assert d["odd_footer"] is None
        assert d["even_header"] is None
        assert d["different_odd_even"] is False
        assert d["scale_with_doc"] is True


class TestWorksheetHeaderFooterAccessor:
    def test_lazy_access(self):
        wb = Workbook()
        ws = wb.active
        hf = ws.header_footer
        assert isinstance(hf, HeaderFooter)

    def test_set_segments_persist(self):
        wb = Workbook()
        ws = wb.active
        ws.header_footer.odd_header.center = "Confidential"
        ws.header_footer.odd_footer.right = "Page &P of &N"
        assert ws.header_footer.odd_header.center == "Confidential"
        assert ws.header_footer.odd_footer.right == "Page &P of &N"
