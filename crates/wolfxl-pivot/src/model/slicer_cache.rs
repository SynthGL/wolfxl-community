//! `SlicerCache` — workbook-scoped slicer cache (RFC-061 §2.1, §10.1).
//!
//! Mirrors openpyxl's `openpyxl.pivot.cache.PivotCacheDefinition`'s
//! slicer-cache extension. One `SlicerCache` represents
//! `xl/slicerCaches/slicerCache{N}.xml`; references a `PivotCache`
//! by id and a single field by index.
//!
//! Slicer caches are PIVOT-DERIVED in v2.0: every slicer in this
//! release uses a pivot cache as its data source (not a tabular
//! range or external model — those are deferred to v2.1+).

/// One enumerated value inside a slicer cache. Mirrors RFC-061 §10.1
/// `items[*]`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SlicerItem {
    pub name: String,
    pub hidden: bool,
    pub no_data: bool,
}

impl SlicerItem {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            hidden: false,
            no_data: false,
        }
    }
}

/// Sort order for slicer items. RFC-061 §10.1 `sort_order`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SlicerSortOrder {
    Ascending,
    Descending,
    None,
}

impl SlicerSortOrder {
    pub fn xml_value(&self) -> &'static str {
        match self {
            SlicerSortOrder::Ascending => "ascending",
            SlicerSortOrder::Descending => "descending",
            SlicerSortOrder::None => "none",
        }
    }
}

/// A slicer cache. Workbook-scoped; can be referenced by 0..N slicer
/// presentations (a single cache → many sheet placements).
///
/// RFC-061 §10.1 contract.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SlicerCache {
    /// Unique workbook-scoped slicer-cache name (e.g.
    /// `"Slicer_region"`). Becomes the `<x14:slicerCacheDefinition
    /// name="…">` attribute, AND the rel-target alias the
    /// `<x14:slicerCaches>` workbook extension uses.
    pub name: String,
    /// 0-based id of the source pivot cache.
    pub source_pivot_cache_id: u32,
    /// 0-based field index inside the source pivot cache.
    pub source_field_index: u32,
    pub sort_order: SlicerSortOrder,
    pub custom_list_sort: bool,
    pub hide_items_with_no_data: bool,
    pub show_missing: bool,
    /// Enumerated items, mirroring the source cache field's
    /// `<sharedItems>` plus per-item hidden/no_data flags. May be
    /// empty when the slicer is a "live filter" — Excel computes
    /// items on open in that case.
    pub items: Vec<SlicerItem>,
}

impl SlicerCache {
    pub fn new(
        name: impl Into<String>,
        source_pivot_cache_id: u32,
        source_field_index: u32,
    ) -> Self {
        Self {
            name: name.into(),
            source_pivot_cache_id,
            source_field_index,
            sort_order: SlicerSortOrder::Ascending,
            custom_list_sort: false,
            hide_items_with_no_data: false,
            show_missing: true,
            items: Vec::new(),
        }
    }

    /// RFC-061 §10.1 validation. Returns first violation.
    pub fn validate(&self) -> Result<(), String> {
        if self.name.is_empty() {
            return Err("SlicerCache requires a non-empty name".into());
        }
        if !self.name.starts_with("Slicer_") && !self.name.starts_with("NativeTimeline_") {
            // Not strictly required by the spec, but openpyxl + Excel
            // canonicalize on `Slicer_<field>` and timelines on
            // `NativeTimeline_<field>`. We tolerate other names but
            // warn callers expect to be alerted; a hard-error is too
            // strict for v2.0 — return Ok.
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validate_empty_name_rejects() {
        let sc = SlicerCache::new("", 0, 0);
        assert!(sc.validate().is_err());
    }

    #[test]
    fn validate_happy_path() {
        let sc = SlicerCache::new("Slicer_region", 0, 0);
        assert!(sc.validate().is_ok());
    }

    #[test]
    fn slicer_item_defaults() {
        let item = SlicerItem::new("North");
        assert_eq!(item.name, "North");
        assert!(!item.hidden);
        assert!(!item.no_data);
    }

    #[test]
    fn sort_order_xml_values() {
        assert_eq!(SlicerSortOrder::Ascending.xml_value(), "ascending");
        assert_eq!(SlicerSortOrder::Descending.xml_value(), "descending");
        assert_eq!(SlicerSortOrder::None.xml_value(), "none");
    }
}
