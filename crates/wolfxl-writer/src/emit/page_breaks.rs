//! Page-break slot emitters.

pub use crate::parse::page_breaks::{emit_col_breaks, emit_row_breaks, BreakSpec, PageBreakList};

use crate::model::worksheet::Worksheet;

fn push_utf8(out: &mut String, bytes: &[u8]) {
    out.push_str(std::str::from_utf8(bytes).unwrap_or(""));
}

pub(crate) fn emit(out: &mut String, sheet: &Worksheet) {
    if let Some(spec) = sheet.row_breaks.as_ref() {
        let bytes = emit_row_breaks(spec);
        if !bytes.is_empty() {
            push_utf8(out, &bytes);
        }
    }

    if let Some(spec) = sheet.col_breaks.as_ref() {
        let bytes = emit_col_breaks(spec);
        if !bytes.is_empty() {
            push_utf8(out, &bytes);
        }
    }
}
