//! Sprint Ο Pod 3.5 (RFC-061 §3.1) — patcher Phase 2.5p slicer drain.
//!
//! This module is **Phase 2.5p**, sequenced AFTER pivots (Phase 2.5m,
//! optionally after sheet-setup 2.5n once that lands) and BEFORE
//! autofilter (Phase 2.5o) per RFC-061 §3.1.
//!
//! Each queued slicer carries:
//!   * The §10.1 cache dict (one cache per slicer in v2.0 — slicer
//!     caches do not share between slicers in this release).
//!   * The §10.2 slicer-presentation dict.
//!   * The owner sheet title.
//!
//! Drainage steps per queued slicer:
//!   1. Allocate a slicer-cache part id (`xl/slicerCaches/slicerCache{N}.xml`)
//!      and a slicer-presentation part id (`xl/slicers/slicer{M}.xml`).
//!      v2.0 emits one slicer per presentation file (no merging).
//!   2. Render the cache part via `serialize_slicer_cache_dict`-equivalent
//!      (we re-use `wolfxl_pivot::emit::slicer_cache_xml`) and the
//!      slicer part via `wolfxl_pivot::emit::slicer_xml`.
//!   3. Build per-cache rels file pointing at the source pivot cache.
//!   4. Add a workbook-rel of type `SLICER_CACHE` for each cache.
//!   5. Splice an `<extLst>` block into `xl/workbook.xml` carrying
//!      `<x14:slicerCaches>` per RFC-061 §3.1.
//!   6. Add a sheet-rel of type `SLICER` per slicer-presentation.
//!   7. Splice an `<extLst>` `<x14:slicerList>` into the owner sheet.
//!   8. Add content-type Overrides for both parts.
//!
//! All XML emit is delegated to `wolfxl_pivot::emit::*` so this
//! module is a pure orchestrator.

use crate::wolfxl::pivot::{parse_slicer_cache_dict, parse_slicer_dict};

use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

use wolfxl_pivot::emit::{
    sheet_slicer_list_inner_xml, slicer_cache_xml, slicer_xml, workbook_slicer_caches_inner_xml,
};
use wolfxl_pivot::model::slicer::Slicer;
use wolfxl_pivot::model::slicer_cache::SlicerCache;

// ---------------------------------------------------------------------------
// Queue payload — held on `XlsxPatcher`.
// ---------------------------------------------------------------------------

/// One slicer queued for emit at Phase 2.5p.
///
/// Holds typed model values (parsed from §10 dicts at queue time)
/// rather than raw `PyObject`s so the queue is `Send + Sync` clean
/// and observable in unit tests.
#[derive(Debug, Clone)]
pub struct QueuedSlicer {
    /// Owner sheet title.
    pub sheet: String,
    /// Typed §10.1 slicer-cache model.
    pub cache: SlicerCache,
    /// Typed §10.2 slicer-presentation model.
    pub slicer: Slicer,
}

// ---------------------------------------------------------------------------
// Workbook.xml `<extLst>` splice — inserts/extends the
// `<x14:slicerCaches>` extension.
// ---------------------------------------------------------------------------

/// One workbook-rel pair for the `<x14:slicerCaches>` block:
/// `(slicer_cache_name, rel_id)`.
#[derive(Debug, Clone)]
pub struct WorkbookSlicerCacheRef {
    pub name: String,
    pub rid: String,
}

/// One workbook-rel pair for the `<x15:timelineCacheRefs>` block.
#[derive(Debug, Clone)]
pub struct WorkbookTimelineCacheRef {
    pub name: String,
    pub rid: String,
}

/// Splice the `<x14:slicerCaches>` extension into `xl/workbook.xml`.
///
/// Logic mirrors `pivot::splice_pivot_caches`: tolerant placement with
/// a preference for an existing `<extLst>`; if absent, append a fresh
/// `<extLst>` immediately before `</workbook>`.
///
/// Empty input is a no-op.
pub fn splice_workbook_slicer_caches(
    workbook_xml: &[u8],
    entries: &[WorkbookSlicerCacheRef],
) -> Result<Vec<u8>, String> {
    if entries.is_empty() {
        return Ok(workbook_xml.to_vec());
    }
    let pairs: Vec<(String, String)> = entries
        .iter()
        .map(|e| (e.name.clone(), e.rid.clone()))
        .collect();
    let inner = workbook_slicer_caches_inner_xml(&pairs);
    let inner_str =
        std::str::from_utf8(&inner).map_err(|e| format!("slicer_caches inner not utf8: {e}"))?;
    let entry_fragment = slicer_cache_entry_fragment(inner_str);

    let s = std::str::from_utf8(workbook_xml).map_err(|e| format!("workbook.xml not utf8: {e}"))?;

    if let Some(close_pos) = s.find("</x15:slicerCaches>") {
        let mut out = String::with_capacity(s.len() + entry_fragment.len());
        out.push_str(&s[..close_pos]);
        out.push_str(&entry_fragment);
        out.push_str(&s[close_pos..]);
        return Ok(out.into_bytes());
    }
    if let Some(close_pos) = s.find("</x14:slicerCaches>") {
        let mut out = String::with_capacity(s.len() + entry_fragment.len());
        out.push_str(&s[..close_pos]);
        out.push_str(&entry_fragment);
        out.push_str(&s[close_pos..]);
        return Ok(out.into_bytes());
    }

    // Build the wrapped <ext> fragment — the <ext> wrapper carries
    // the URI and x14 namespace declaration so splicing into either
    // an existing <extLst> or a fresh one is identical.
    let ext_fragment = format!(
        r#"<ext uri="{uri}" xmlns:x14="{ns}">{inner}</ext>"#,
        uri = wolfxl_pivot::ext_uri::WORKBOOK_SLICER_CACHES,
        ns = wolfxl_pivot::emit::slicer_cache::NS_X14,
        inner = inner_str,
    );

    // Case A: existing <extLst>...</extLst>: insert just before </extLst>.
    if let Some(close_pos) = s.find("</extLst>") {
        let mut out = String::with_capacity(s.len() + ext_fragment.len());
        out.push_str(&s[..close_pos]);
        out.push_str(&ext_fragment);
        out.push_str(&s[close_pos..]);
        return Ok(out.into_bytes());
    }
    // Case B: existing self-closing <extLst/>.
    if let Some(empty_pos) = s.find("<extLst/>") {
        let mut out = String::with_capacity(s.len() + ext_fragment.len() + 32);
        out.push_str(&s[..empty_pos]);
        out.push_str("<extLst>");
        out.push_str(&ext_fragment);
        out.push_str("</extLst>");
        out.push_str(&s[empty_pos + "<extLst/>".len()..]);
        return Ok(out.into_bytes());
    }
    // Case C: no <extLst>. Insert just before </workbook>.
    if let Some(close_wb) = s.rfind("</workbook>") {
        let block = format!("<extLst>{ext_fragment}</extLst>");
        let mut out = String::with_capacity(s.len() + block.len());
        out.push_str(&s[..close_wb]);
        out.push_str(&block);
        out.push_str(&s[close_wb..]);
        return Ok(out.into_bytes());
    }
    Err("workbook.xml has no </workbook> closing tag".into())
}

fn slicer_cache_entry_fragment(inner_str: &str) -> String {
    let Some(open_end) = inner_str.find('>') else {
        return inner_str.to_string();
    };
    let Some(close_start) = inner_str.rfind("</") else {
        return inner_str.to_string();
    };
    inner_str[open_end + 1..close_start].to_string()
}

/// Splice the `<x15:timelineCacheRefs>` extension into `xl/workbook.xml`.
pub fn splice_workbook_timeline_caches(
    workbook_xml: &[u8],
    entries: &[WorkbookTimelineCacheRef],
) -> Result<Vec<u8>, String> {
    if entries.is_empty() {
        return Ok(workbook_xml.to_vec());
    }
    let entry_fragment: String = entries
        .iter()
        .map(|e| format!(r#"<x15:timelineCacheRef r:id="{}"/>"#, e.rid))
        .collect();
    let s = std::str::from_utf8(workbook_xml).map_err(|e| format!("workbook.xml not utf8: {e}"))?;

    if let Some(close_pos) = s.find("</x15:timelineCacheRefs>") {
        let mut out = String::with_capacity(s.len() + entry_fragment.len());
        out.push_str(&s[..close_pos]);
        out.push_str(&entry_fragment);
        out.push_str(&s[close_pos..]);
        return Ok(out.into_bytes());
    }

    let ext_fragment = format!(
        r#"<ext uri="{{7E03D99C-DC04-49d9-9315-930204A7B6E9}}" xmlns:x15="http://schemas.microsoft.com/office/spreadsheetml/2010/11/main"><x15:timelineCacheRefs>{entry_fragment}</x15:timelineCacheRefs></ext>"#
    );
    if let Some(close_pos) = s.find("</extLst>") {
        let mut out = String::with_capacity(s.len() + ext_fragment.len());
        out.push_str(&s[..close_pos]);
        out.push_str(&ext_fragment);
        out.push_str(&s[close_pos..]);
        return Ok(out.into_bytes());
    }
    if let Some(empty_pos) = s.find("<extLst/>") {
        let mut out = String::with_capacity(s.len() + ext_fragment.len() + 32);
        out.push_str(&s[..empty_pos]);
        out.push_str("<extLst>");
        out.push_str(&ext_fragment);
        out.push_str("</extLst>");
        out.push_str(&s[empty_pos + "<extLst/>".len()..]);
        return Ok(out.into_bytes());
    }
    if let Some(close_pos) = s.rfind("</workbook>") {
        let mut out = String::with_capacity(s.len() + ext_fragment.len() + 18);
        out.push_str(&s[..close_pos]);
        out.push_str("<extLst>");
        out.push_str(&ext_fragment);
        out.push_str("</extLst>");
        out.push_str(&s[close_pos..]);
        return Ok(out.into_bytes());
    }
    Err("workbook.xml has no </workbook> closing tag".into())
}

/// Splice a sheet's `<extLst>` to add the `<x14:slicerList>` extension
/// pointing at one slicer-presentation rel id.
///
/// Mirrors `splice_workbook_slicer_caches` for placement.
pub fn splice_sheet_slicer_list(sheet_xml: &[u8], slicer_rid: &str) -> Result<Vec<u8>, String> {
    let inner = sheet_slicer_list_inner_xml(slicer_rid);
    let inner_str =
        std::str::from_utf8(&inner).map_err(|e| format!("slicer_list inner not utf8: {e}"))?;

    let s = std::str::from_utf8(sheet_xml).map_err(|e| format!("sheet xml not utf8: {e}"))?;

    let ext_fragment = format!(
        r#"<ext uri="{uri}" xmlns:x14="{ns}" xmlns:r="{rels}">{inner}</ext>"#,
        uri = wolfxl_pivot::ext_uri::SHEET_SLICER_LIST,
        ns = wolfxl_pivot::emit::slicer_cache::NS_X14,
        rels = wolfxl_pivot::ns::RELATIONSHIPS,
        inner = inner_str,
    );

    if let Some(close_pos) = s.find("</extLst>") {
        let mut out = String::with_capacity(s.len() + ext_fragment.len());
        out.push_str(&s[..close_pos]);
        out.push_str(&ext_fragment);
        out.push_str(&s[close_pos..]);
        return Ok(out.into_bytes());
    }
    if let Some(empty_pos) = s.find("<extLst/>") {
        let mut out = String::with_capacity(s.len() + ext_fragment.len() + 32);
        out.push_str(&s[..empty_pos]);
        out.push_str("<extLst>");
        out.push_str(&ext_fragment);
        out.push_str("</extLst>");
        out.push_str(&s[empty_pos + "<extLst/>".len()..]);
        return Ok(out.into_bytes());
    }
    // Insert right before </worksheet>.
    if let Some(close_ws) = s.rfind("</worksheet>") {
        let block = format!("<extLst>{ext_fragment}</extLst>");
        let mut out = String::with_capacity(s.len() + block.len());
        out.push_str(&s[..close_ws]);
        out.push_str(&block);
        out.push_str(&s[close_ws..]);
        return Ok(out.into_bytes());
    }
    Err("sheet xml has no </worksheet> closing tag".into())
}

// ---------------------------------------------------------------------------
// Per-patcher slicer part-id allocator.
// ---------------------------------------------------------------------------

/// Per-patcher slicer-cache + slicer-presentation part counters.
#[derive(Debug, Clone, Default)]
pub struct SlicerPartCounters {
    pub next_cache: u32,
    pub next_slicer: u32,
}

impl SlicerPartCounters {
    pub fn new() -> Self {
        Self {
            next_cache: 1,
            next_slicer: 1,
        }
    }

    pub fn alloc_cache(&mut self) -> u32 {
        let n = self.next_cache;
        self.next_cache += 1;
        n
    }

    pub fn alloc_slicer(&mut self) -> u32 {
        let n = self.next_slicer;
        self.next_slicer += 1;
        n
    }

    /// Bump counters by observing existing part paths from the source
    /// ZIP.
    pub fn observe(&mut self, path: &str) {
        if let Some(rest) = path.strip_prefix("xl/slicerCaches/slicerCache") {
            if let Some(num_str) = rest.strip_suffix(".xml") {
                if let Ok(n) = num_str.parse::<u32>() {
                    if n + 1 > self.next_cache {
                        self.next_cache = n + 1;
                    }
                }
            }
        } else if let Some(rest) = path.strip_prefix("xl/slicers/slicer") {
            if let Some(num_str) = rest.strip_suffix(".xml") {
                if let Ok(n) = num_str.parse::<u32>() {
                    if n + 1 > self.next_slicer {
                        self.next_slicer = n + 1;
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// PyO3-side parser helper used by `XlsxPatcher::queue_slicer_add`.
// ---------------------------------------------------------------------------

/// Parse the `(cache_dict, slicer_dict, sheet)` triple into a typed
/// `QueuedSlicer`. Used by `XlsxPatcher::queue_slicer_add`.
pub fn parse_queued_slicer(
    sheet: &str,
    cache_dict: &Bound<'_, PyDict>,
    slicer_dict: &Bound<'_, PyDict>,
) -> PyResult<QueuedSlicer> {
    let cache = parse_slicer_cache_dict(cache_dict)?;
    let slicer = parse_slicer_dict(slicer_dict)?;
    Ok(QueuedSlicer {
        sheet: sheet.to_string(),
        cache,
        slicer,
    })
}

// ---------------------------------------------------------------------------
// Drain helper — pure / PyO3-free. Returns the parts to splice; the
// caller (in `mod.rs`) wires them into `file_adds` / `rels_patches` /
// `file_patches`.
// ---------------------------------------------------------------------------

/// One drained slicer's outputs.
#[derive(Debug, Clone)]
pub struct SlicerDrainOutput {
    pub sheet_title: String,
    pub cache_part_path: String,
    pub cache_rels_part_path: String,
    pub cache_xml: Vec<u8>,
    pub slicer_part_path: String,
    pub slicer_xml: Vec<u8>,
    pub cache_id: u32,
    pub slicer_id: u32,
    pub cache_name: String,
    /// Source pivot cache part id this slicer cache references.
    pub source_pivot_cache_id: u32,
}

/// Drain a single `QueuedSlicer` into emit byproducts. Pure helper.
pub fn drain_one(queued: &QueuedSlicer, counters: &mut SlicerPartCounters) -> SlicerDrainOutput {
    let cache_id = counters.alloc_cache();
    let slicer_id = counters.alloc_slicer();
    let cache_part_path = format!("xl/slicerCaches/slicerCache{cache_id}.xml");
    let cache_rels_part_path = format!("xl/slicerCaches/_rels/slicerCache{cache_id}.xml.rels");
    let slicer_part_path = format!("xl/slicers/slicer{slicer_id}.xml");
    let cache_xml = slicer_cache_xml(&queued.cache);
    let slicer_xml_bytes = slicer_xml(std::slice::from_ref(&queued.slicer));
    SlicerDrainOutput {
        sheet_title: queued.sheet.clone(),
        cache_part_path,
        cache_rels_part_path,
        cache_xml,
        slicer_part_path,
        slicer_xml: slicer_xml_bytes,
        cache_id,
        slicer_id,
        cache_name: queued.cache.name.clone(),
        source_pivot_cache_id: queued.cache.source_pivot_cache_id,
    }
}

// ---------------------------------------------------------------------------
// Tests (pure helpers — splice + counter logic).
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use wolfxl_pivot::model::slicer::Slicer as SlicerModel;
    use wolfxl_pivot::model::slicer_cache::{SlicerCache as SlicerCacheModel, SlicerItem};

    fn dummy_queued() -> QueuedSlicer {
        let mut cache = SlicerCacheModel::new("Slicer_region", 0, 0);
        cache.items = vec![SlicerItem::new("North"), SlicerItem::new("South")];
        let slicer = SlicerModel::new("Slicer_region1", "Slicer_region", "H2");
        QueuedSlicer {
            sheet: "Sheet1".into(),
            cache,
            slicer,
        }
    }

    #[test]
    fn splice_workbook_inserts_extlst_when_absent() {
        let xml = br#"<workbook><sheets/></workbook>"#;
        let entries = vec![WorkbookSlicerCacheRef {
            name: "Slicer_region".into(),
            rid: "rId7".into(),
        }];
        let out = splice_workbook_slicer_caches(xml, &entries).unwrap();
        let s = std::str::from_utf8(&out).unwrap();
        assert!(s.contains("<extLst>"), "output missing <extLst>: {s}");
        assert!(
            s.contains("<x14:slicerCaches"),
            "output missing x14:slicerCaches: {s}"
        );
        assert!(s.contains("r:id=\"rId7\""));
    }

    #[test]
    fn splice_workbook_extends_existing_extlst() {
        let xml = br#"<workbook><sheets/><extLst><ext uri="X"/></extLst></workbook>"#;
        let entries = vec![WorkbookSlicerCacheRef {
            name: "Slicer_region".into(),
            rid: "rId7".into(),
        }];
        let out = splice_workbook_slicer_caches(xml, &entries).unwrap();
        let s = std::str::from_utf8(&out).unwrap();
        // Original ext preserved.
        assert!(s.contains(r#"<ext uri="X"/>"#));
        // New x14:slicerCaches inside the same extLst.
        assert_eq!(s.matches("<extLst>").count(), 1);
        assert!(s.contains("<x14:slicerCaches"));
    }

    #[test]
    fn splice_workbook_extends_existing_slicer_cache_block() {
        let xml = br#"<workbook><extLst><ext uri="x"><x15:slicerCaches><x14:slicerCache r:id="rId2"/></x15:slicerCaches></ext></extLst></workbook>"#;
        let entries = vec![WorkbookSlicerCacheRef {
            name: "Slicer_region".into(),
            rid: "rId7".into(),
        }];
        let out = splice_workbook_slicer_caches(xml, &entries).unwrap();
        let s = std::str::from_utf8(&out).unwrap();
        assert_eq!(s.matches("slicerCaches").count(), 2, "{s}");
        assert!(s.contains(r#"<x14:slicerCache r:id="rId2"/><x14:slicerCache r:id="rId7"/>"#));
    }

    #[test]
    fn splice_workbook_extends_existing_timeline_cache_block() {
        let xml = br#"<workbook><extLst><ext uri="x"><x15:timelineCacheRefs><x15:timelineCacheRef r:id="rId5"/></x15:timelineCacheRefs></ext></extLst></workbook>"#;
        let entries = vec![WorkbookTimelineCacheRef {
            name: "NativeTimeline_DATE1".into(),
            rid: "rId7".into(),
        }];
        let out = splice_workbook_timeline_caches(xml, &entries).unwrap();
        let s = std::str::from_utf8(&out).unwrap();
        assert_eq!(s.matches("timelineCacheRefs").count(), 2, "{s}");
        assert!(
            s.contains(r#"<x15:timelineCacheRef r:id="rId5"/><x15:timelineCacheRef r:id="rId7"/>"#)
        );
    }

    #[test]
    fn splice_workbook_empty_is_noop() {
        let xml = br#"<workbook><sheets/></workbook>"#;
        let out = splice_workbook_slicer_caches(xml, &[]).unwrap();
        assert_eq!(out, xml.to_vec());
    }

    #[test]
    fn splice_sheet_inserts_slicer_list_before_close() {
        let xml = br#"<worksheet><sheetData/></worksheet>"#;
        let out = splice_sheet_slicer_list(xml, "rId4").unwrap();
        let s = std::str::from_utf8(&out).unwrap();
        assert!(s.contains("<extLst>"));
        assert!(s.contains("<x14:slicerList"));
        assert!(s.contains("r:id=\"rId4\""));
    }

    #[test]
    fn splice_sheet_extends_existing_extlst() {
        let xml = br#"<worksheet><sheetData/><extLst><ext uri="X"/></extLst></worksheet>"#;
        let out = splice_sheet_slicer_list(xml, "rId4").unwrap();
        let s = std::str::from_utf8(&out).unwrap();
        assert!(s.contains(r#"<ext uri="X"/>"#));
        assert_eq!(s.matches("<extLst>").count(), 1);
    }

    #[test]
    fn part_counters_observe_existing() {
        let mut c = SlicerPartCounters::new();
        c.observe("xl/slicerCaches/slicerCache3.xml");
        c.observe("xl/slicers/slicer5.xml");
        assert_eq!(c.alloc_cache(), 4);
        assert_eq!(c.alloc_slicer(), 6);
    }

    #[test]
    fn drain_one_returns_consistent_paths() {
        let q = dummy_queued();
        let mut c = SlicerPartCounters::new();
        let out = drain_one(&q, &mut c);
        assert_eq!(out.cache_part_path, "xl/slicerCaches/slicerCache1.xml");
        assert_eq!(
            out.cache_rels_part_path,
            "xl/slicerCaches/_rels/slicerCache1.xml.rels"
        );
        assert_eq!(out.slicer_part_path, "xl/slicers/slicer1.xml");
        assert!(!out.cache_xml.is_empty());
        assert!(!out.slicer_xml.is_empty());
        assert_eq!(out.cache_name, "Slicer_region");
        assert_eq!(out.sheet_title, "Sheet1");
    }

    #[test]
    fn drain_two_increments_ids() {
        let q1 = dummy_queued();
        let mut q2 = dummy_queued();
        q2.cache.name = "Slicer_quarter".into();
        q2.slicer.cache_name = "Slicer_quarter".into();
        q2.slicer.name = "Slicer_quarter1".into();
        let mut c = SlicerPartCounters::new();
        let o1 = drain_one(&q1, &mut c);
        let o2 = drain_one(&q2, &mut c);
        assert_eq!(o1.cache_id, 1);
        assert_eq!(o2.cache_id, 2);
        assert_eq!(o1.slicer_id, 1);
        assert_eq!(o2.slicer_id, 2);
    }
}

// Re-export `HashMap` to keep the suppressed-warning surface visible
// even when no caller uses it directly.
#[allow(dead_code)]
pub(crate) type _UnusedMap = HashMap<String, String>;
