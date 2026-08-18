//! Emit `xl/slicers/slicer{N}.xml` (RFC-061 §3.1).
//!
//! The slicer presentation file holds N `<slicer>` entries — one per
//! slicer placed on the owning sheet. Multiple slicers on one sheet
//! share a single presentation file.

use super::{esc_attr, push_attr, push_attr_if, xml_decl};
use crate::emit::slicer_cache::NS_X14;
use crate::model::slicer::Slicer;

/// Emit the slicer presentation XML for a sheet, given a list of
/// slicers on that sheet.
pub fn slicer_xml(slicers: &[Slicer]) -> Vec<u8> {
    let mut out = String::with_capacity(1024);
    xml_decl(&mut out);

    out.push_str("<slicers");
    push_attr(&mut out, "xmlns", NS_X14);
    push_attr(&mut out, "xmlns:r", crate::ns::RELATIONSHIPS);
    out.push('>');

    for s in slicers {
        emit_slicer(&mut out, s);
    }

    out.push_str("</slicers>");
    out.into_bytes()
}

fn emit_slicer(out: &mut String, s: &Slicer) {
    out.push_str("<slicer");
    push_attr(out, "name", &s.name);
    push_attr(out, "cache", &s.cache_name);
    if !s.caption.is_empty() {
        push_attr(out, "caption", &s.caption);
    }
    push_attr(out, "rowHeight", &s.row_height.to_string());
    push_attr(out, "columnCount", &s.column_count.to_string());
    push_attr(out, "showCaption", if s.show_caption { "1" } else { "0" });
    if let Some(style) = &s.style {
        push_attr(out, "style", style);
    }
    push_attr_if(out, !s.locked, "lockedPosition", "0");
    out.push_str("/>");
}

/// Emit the inner `<x14:slicerList>` fragment for a sheet's
/// `<extLst>` per RFC-061 §3.1. Wrap with `<ext>` at the splice
/// site.
pub fn sheet_slicer_list_inner_xml(rid: &str) -> Vec<u8> {
    let mut out = String::with_capacity(96);
    out.push_str("<x14:slicerList");
    out.push_str(" xmlns:x14=\"");
    out.push_str(NS_X14);
    out.push_str("\">");
    out.push_str("<x14:slicer");
    out.push_str(" r:id=\"");
    esc_attr(rid, &mut out);
    out.push_str("\"/>");
    out.push_str("</x14:slicerList>");
    out.into_bytes()
}

/// Emit the `<sl:slicer>` extension fragment that goes inside a
/// drawing's `<xdr:graphicFrame>` `<extLst>` (§3.1 — drawing-level
/// rels).
pub fn drawing_slicer_ext_xml(slicer_name: &str) -> Vec<u8> {
    let mut out = String::with_capacity(192);
    out.push_str("<sl:slicer");
    out.push_str(" xmlns:sl=\"http://schemas.microsoft.com/office/drawing/2010/slicer\"");
    out.push_str(" name=\"");
    esc_attr(slicer_name, &mut out);
    out.push_str("\"/>");
    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_slicer() -> Slicer {
        let mut s = Slicer::new("Slicer_region1", "Slicer_region", "H2");
        s.caption = "Filter by Region".into();
        s.style = Some("SlicerStyleLight1".into());
        s
    }

    #[test]
    fn emit_basic() {
        let s = dummy_slicer();
        let xml = slicer_xml(&[s]);
        let raw = std::str::from_utf8(&xml).unwrap();
        assert!(raw.starts_with("<?xml"));
        assert!(raw.contains("<slicers"));
        assert!(raw.contains("<slicer"));
        assert!(raw.contains("name=\"Slicer_region1\""));
        assert!(raw.contains("cache=\"Slicer_region\""));
        assert!(raw.contains("caption=\"Filter by Region\""));
        assert!(raw.contains("rowHeight=\"204\""));
        assert!(raw.contains("style=\"SlicerStyleLight1\""));
    }

    #[test]
    fn emit_unlocked() {
        let mut s = dummy_slicer();
        s.locked = false;
        let xml = slicer_xml(&[s]);
        let raw = std::str::from_utf8(&xml).unwrap();
        assert!(raw.contains("lockedPosition=\"0\""));
    }

    #[test]
    fn emit_multiple_slicers() {
        let s1 = Slicer::new("Slicer_a1", "Slicer_a", "H2");
        let s2 = Slicer::new("Slicer_b1", "Slicer_b", "K2");
        let xml = slicer_xml(&[s1, s2]);
        let raw = std::str::from_utf8(&xml).unwrap();
        assert_eq!(raw.matches("<slicer ").count(), 2);
    }

    #[test]
    fn determinism() {
        let s = dummy_slicer();
        let a = slicer_xml(&[s.clone()]);
        let b = slicer_xml(&[s]);
        assert_eq!(a, b);
    }

    #[test]
    fn slicer_list_inner_xml() {
        let xml = sheet_slicer_list_inner_xml("rId4");
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("<x14:slicerList"));
        assert!(s.contains("r:id=\"rId4\""));
    }

    #[test]
    fn drawing_slicer_ext_xml_has_namespace() {
        let xml = drawing_slicer_ext_xml("Slicer_region1");
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("xmlns:sl=\""));
        assert!(s.contains("name=\"Slicer_region1\""));
    }
}
