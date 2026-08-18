//! XML emitters for pivot caches and tables.
//!
//! Determinism guarantees:
//! - Attribute order is fixed per element (callers see the same byte
//!   output for the same input model).
//! - Child element order matches OOXML schema (rejection-rate is 0 in
//!   Excel and LibreOffice).
//! - No timestamps, no random ids — `WOLFXL_TEST_EPOCH=0` golden
//!   files are byte-stable.

pub mod cache;
pub mod records;
pub mod table;
// RFC-061 sub-features.
pub mod slicer;
pub mod slicer_cache;

pub use cache::pivot_cache_definition_xml;
pub use records::pivot_cache_records_xml;
pub use slicer::{drawing_slicer_ext_xml, sheet_slicer_list_inner_xml, slicer_xml};
pub use slicer_cache::{slicer_cache_xml, workbook_slicer_caches_inner_xml};
pub use table::pivot_table_xml;

// ---------------------------------------------------------------------------
// XML helpers — minimal hand-rolled writer. We intentionally avoid
// quick-xml's `Writer` here so the byte-output is fully deterministic
// (quick-xml escapes & encodings can vary by version). Mirrors the
// approach in `wolfxl-rels::serialize`.
// ---------------------------------------------------------------------------

pub(crate) fn xml_decl(out: &mut String) {
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
}

/// Escape a string for an XML attribute value.
pub(crate) fn esc_attr(s: &str, out: &mut String) {
    for ch in s.chars() {
        match ch {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            _ => out.push(ch),
        }
    }
}

/// Escape a string for XML element text. Reserved for future emitters
/// (e.g. `<c:name>` in pivot-source chart blocks). Currently unused
/// in this crate's own emitters because the pivot model serializes
/// values via attributes, not text nodes.
#[allow(dead_code)]
pub(crate) fn esc_text(s: &str, out: &mut String) {
    for ch in s.chars() {
        match ch {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            _ => out.push(ch),
        }
    }
}

/// Format a `f64` for an XML attribute. Excel writes integers without
/// the `.0` suffix; we match. Other values use Rust's default
/// `Display`. Mirrors openpyxl's `safe_repr`.
pub(crate) fn fmt_num(n: f64) -> String {
    if n.is_finite() && n.fract() == 0.0 && n.abs() < 1e15 {
        // Whole number — emit without trailing `.0`.
        format!("{}", n as i64)
    } else {
        format!("{n}")
    }
}

/// Emit `attr="value"`.
pub(crate) fn push_attr(out: &mut String, name: &str, value: &str) {
    out.push(' ');
    out.push_str(name);
    out.push_str("=\"");
    esc_attr(value, out);
    out.push('"');
}

/// Emit `attr="value"` only when `cond`. Used for boolean OOXML attrs
/// where the default is "absent → use Excel default".
pub(crate) fn push_attr_if(out: &mut String, cond: bool, name: &str, value: &str) {
    if cond {
        push_attr(out, name, value);
    }
}
