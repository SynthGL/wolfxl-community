//! Typed sheet setup slot emitters for `sheet_xml`.

use crate::model::worksheet::Worksheet;

fn push_utf8(out: &mut String, bytes: &[u8]) {
    out.push_str(std::str::from_utf8(bytes).unwrap_or(""));
}

pub(crate) fn emit_sheet_views(out: &mut String, sheet: &Worksheet, sheet_idx: u32) {
    if let Some(view_spec) = sheet.views.as_ref() {
        let bytes = crate::parse::sheet_setup::emit_sheet_views(view_spec);
        if !bytes.is_empty() {
            push_utf8(out, &bytes);
            return;
        }
    }
    super::sheet_views::emit(out, sheet, sheet_idx);
}

pub(crate) fn emit_sheet_format(out: &mut String, sheet: &Worksheet) {
    if let Some(spec) = sheet.sheet_format.as_ref() {
        let bytes = crate::parse::page_breaks::emit_sheet_format_pr(spec);
        if !bytes.is_empty() {
            push_utf8(out, &bytes);
            return;
        }
    }
    out.push_str("<sheetFormatPr defaultRowHeight=\"15\"/>");
}

pub(crate) fn emit_sheet_protection(out: &mut String, sheet: &Worksheet) {
    if let Some(spec) = sheet.protection.as_ref() {
        let bytes = crate::parse::sheet_setup::emit_sheet_protection(spec);
        if !bytes.is_empty() {
            push_utf8(out, &bytes);
        }
    }
}

pub(crate) fn emit_page_margins(out: &mut String, sheet: &Worksheet) {
    if let Some(spec) = sheet.page_margins.as_ref() {
        let bytes = crate::parse::sheet_setup::emit_page_margins(spec);
        push_utf8(out, &bytes);
    } else {
        out.push_str("<pageMargins left=\"0.7\" right=\"0.7\" top=\"0.75\" bottom=\"0.75\" header=\"0.3\" footer=\"0.3\"/>");
    }
}

pub(crate) fn emit_print_options(out: &mut String, sheet: &Worksheet) {
    if let Some(spec) = sheet.print_options.as_ref() {
        let bytes = crate::parse::sheet_setup::emit_print_options(spec);
        out.push_str(std::str::from_utf8(&bytes).unwrap_or(""));
    }
}

pub(crate) fn emit_page_setup(out: &mut String, sheet: &Worksheet) {
    if let Some(spec) = sheet.page_setup.as_ref() {
        let bytes = crate::parse::sheet_setup::emit_page_setup(spec);
        if !bytes.is_empty() {
            push_utf8(out, &bytes);
        }
    }
}

pub(crate) fn emit_header_footer(out: &mut String, sheet: &Worksheet) {
    if let Some(spec) = sheet.header_footer.as_ref() {
        let bytes = crate::parse::sheet_setup::emit_header_footer(spec);
        if !bytes.is_empty() {
            push_utf8(out, &bytes);
        }
    }
}
