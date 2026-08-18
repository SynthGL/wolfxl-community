//! Emit `xl/slicerCaches/slicerCache{N}.xml` (RFC-061 §3.1).
//!
//! Slicer caches use the x14 + xr10 namespaces. Format mirrors the
//! shape openpyxl 3.1.x produces.

use super::{esc_attr, push_attr, push_attr_if, xml_decl};
#[cfg(test)]
use crate::model::slicer_cache::SlicerSortOrder;
use crate::model::slicer_cache::{SlicerCache, SlicerItem};

/// Namespace URIs used by slicer caches.
pub const NS_MAIN: &str = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
pub const NS_X14: &str = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main";
pub const NS_XR10: &str = "http://schemas.microsoft.com/office/spreadsheetml/2016/revision10";
pub const NS_MC: &str = "http://schemas.openxmlformats.org/markup-compatibility/2006";

/// Emit a single slicer-cache part.
///
/// The `pivot_cache_name` is the workbook-scope alias for the source
/// pivot cache; this is typically of the form
/// `_xlnm._FilterDatabase` or the cache_id-derived name. v2.0 emits
/// the canonical `<x14:pivotTables>` block referencing the source
/// pivot caches by their workbook rel id.
pub fn slicer_cache_xml(sc: &SlicerCache) -> Vec<u8> {
    let mut out = String::with_capacity(1024);
    xml_decl(&mut out);

    out.push_str("<slicerCacheDefinition");
    push_attr(&mut out, "xmlns", NS_X14);
    push_attr(&mut out, "xmlns:r", crate::ns::RELATIONSHIPS);
    push_attr(&mut out, "name", &sc.name);
    push_attr(&mut out, "sourceName", &sc.name);
    out.push('>');

    // Pivot-source linkage.
    out.push_str("<pivotTables>");
    out.push_str("<pivotTable");
    // tabId/name pinned via the sheet that anchors the slicer; here
    // we point at the cache via rel-style `r:id="rId1"` recorded on
    // the slicer-cache part's rels file.
    push_attr(&mut out, "tabId", "1");
    push_attr(
        &mut out,
        "name",
        &format!("PivotTable{}", sc.source_pivot_cache_id + 1),
    );
    out.push_str("/>");
    out.push_str("</pivotTables>");

    // <data> wrapper.
    out.push_str("<data>");
    emit_olap_or_tabular(&mut out, sc);
    out.push_str("</data>");

    out.push_str("</slicerCacheDefinition>");
    out.into_bytes()
}

fn emit_olap_or_tabular(out: &mut String, sc: &SlicerCache) {
    // Pivot-derived slicers use <tabular> with `pivotCacheId` ptr.
    out.push_str("<tabular");
    push_attr(out, "pivotCacheId", &sc.source_pivot_cache_id.to_string());
    push_attr(out, "sortOrder", sc.sort_order.xml_value());
    push_attr_if(out, sc.custom_list_sort, "customListSort", "1");
    push_attr_if(out, sc.hide_items_with_no_data, "showHiddenItems", "0");
    push_attr_if(out, !sc.show_missing, "showMissing", "0");
    out.push('>');

    if !sc.items.is_empty() {
        out.push_str("<items");
        push_attr(out, "count", &sc.items.len().to_string());
        out.push('>');
        for (i, item) in sc.items.iter().enumerate() {
            emit_item(out, i as u32, item);
        }
        out.push_str("</items>");
    }

    out.push_str("</tabular>");
}

fn emit_item(out: &mut String, index: u32, item: &SlicerItem) {
    out.push_str("<i");
    push_attr(out, "x", &index.to_string());
    push_attr_if(out, item.no_data, "nd", "1");
    push_attr_if(out, item.hidden, "s", "0");
    if !item.name.is_empty() {
        // Item name overrides go via attribute `n=`. Excel uses this
        // for renamed slicer items.
        out.push_str(" n=\"");
        esc_attr(&item.name, out);
        out.push('"');
    }
    out.push_str("/>");
}

/// Emit the workbook-extension fragment that wraps a list of slicer
/// caches. Inserted into `xl/workbook.xml` `<extLst>` per RFC-061
/// §3.1.
///
/// Returns just the inner `<x14:slicerCaches>...</x14:slicerCaches>`
/// fragment (without the surrounding `<ext>` wrapper). The patcher's
/// splice helper wraps with `<ext uri="…" xmlns:x14="…">…</ext>`.
pub fn workbook_slicer_caches_inner_xml(rids: &[(String, String)]) -> Vec<u8> {
    // rids: (slicer_cache_name, rel_id)
    let mut out = String::with_capacity(rids.len() * 64 + 64);
    out.push_str("<x14:slicerCaches");
    out.push_str(" xmlns:x14=\"");
    out.push_str(NS_X14);
    out.push_str("\">");
    for (_name, rid) in rids {
        out.push_str("<x14:slicerCache");
        out.push_str(" r:id=\"");
        esc_attr(rid, &mut out);
        out.push_str("\"/>");
    }
    out.push_str("</x14:slicerCaches>");
    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_cache() -> SlicerCache {
        let mut sc = SlicerCache::new("Slicer_region", 0, 0);
        sc.items = vec![SlicerItem::new("North"), SlicerItem::new("South")];
        sc
    }

    #[test]
    fn emit_basic() {
        let sc = dummy_cache();
        let xml = slicer_cache_xml(&sc);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.starts_with("<?xml"));
        assert!(s.contains("<slicerCacheDefinition"));
        assert!(s.contains("name=\"Slicer_region\""));
        assert!(s.contains("sourceName=\"Slicer_region\""));
        assert!(s.contains("<tabular"));
        assert!(s.contains("pivotCacheId=\"0\""));
        assert!(s.contains("sortOrder=\"ascending\""));
        assert!(s.contains("<items count=\"2\">"));
        assert!(s.contains("North"));
        assert!(s.contains("South"));
    }

    #[test]
    fn emit_no_items_omits_items_block() {
        let mut sc = dummy_cache();
        sc.items.clear();
        let xml = slicer_cache_xml(&sc);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(!s.contains("<items"));
    }

    #[test]
    fn emit_hidden_item() {
        let mut sc = dummy_cache();
        sc.items[0].hidden = true;
        let xml = slicer_cache_xml(&sc);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("s=\"0\""));
    }

    #[test]
    fn emit_no_data_item() {
        let mut sc = dummy_cache();
        sc.items[1].no_data = true;
        let xml = slicer_cache_xml(&sc);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("nd=\"1\""));
    }

    #[test]
    fn emit_descending_sort() {
        let mut sc = dummy_cache();
        sc.sort_order = SlicerSortOrder::Descending;
        let xml = slicer_cache_xml(&sc);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("sortOrder=\"descending\""));
    }

    #[test]
    fn determinism() {
        let sc = dummy_cache();
        let a = slicer_cache_xml(&sc);
        let b = slicer_cache_xml(&sc);
        assert_eq!(a, b);
    }

    #[test]
    fn workbook_slicer_caches_xml_has_namespace() {
        let xml = workbook_slicer_caches_inner_xml(&[
            ("Slicer_region".into(), "rId7".into()),
            ("Slicer_quarter".into(), "rId8".into()),
        ]);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("xmlns:x14=\""));
        assert!(s.contains("<x14:slicerCache"));
        assert!(s.contains("r:id=\"rId7\""));
        assert!(s.contains("r:id=\"rId8\""));
    }
}
