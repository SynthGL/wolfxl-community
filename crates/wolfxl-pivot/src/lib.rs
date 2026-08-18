//! `wolfxl-pivot` — OOXML pivot-cache + pivot-table model and emit.
//!
//! Pure Rust, no PyO3. Used by both the patcher (modify mode) via PyO3
//! bindings in `src/wolfxl/` and the native writer (write mode) via
//! `crates/wolfxl-writer/src/emit/pivot_*.rs`.
//!
//! See `Plans/rfcs/047-pivot-caches.md` (§10) and
//! `Plans/rfcs/048-pivot-tables.md` (§10) for the authoritative
//! contracts. The model types in this crate are the Rust mirror of
//! those §10 dicts; the Python coordinator's `to_rust_dict()` and
//! the Rust `parse::*` functions in `src/wolfxl/` are the boundary.
//!
//! # Sprint Ν scaffold notes
//!
//! Sprint Ν is in progress. This crate's API surface is fixed by the
//! §10 contracts; the emit implementations are minimal-viable and
//! will be hardened by the parallel pods. The integration points
//! (model types, function signatures, deterministic output) are
//! production-grade.

pub mod emit;
pub mod model;
pub mod mutate;
pub mod parse;
pub mod structural;

pub use model::cache::{
    CacheField, CacheValue, DataType, PivotCache, SharedItems, WorksheetSource,
};
pub use model::records::{CacheRecord, RecordCell};
pub use model::slicer::Slicer;
pub use model::slicer_cache::{SlicerCache, SlicerItem, SlicerSortOrder};
pub use model::table::{
    AxisItem, AxisItemType, AxisType, DataField, DataFunction, Location, PageField, PivotField,
    PivotItem, PivotItemType, PivotSource, PivotTable, PivotTableStyleInfo,
};

/// Crate version string used for `created_version`, `refreshed_version`
/// attributes when the caller does not provide a value. Pinned to `6`
/// (Excel 2010+) per RFC-047 §10.1 default. Matches openpyxl's default.
pub const DEFAULT_CACHE_VERSION: u8 = 6;

/// Default `min_refreshable_version`. `3` = Excel 2007+ refresh
/// compatibility. RFC-047 §10.1 default.
pub const DEFAULT_MIN_REFRESHABLE_VERSION: u8 = 3;

/// Namespace URIs.
pub mod ns {
    pub const SPREADSHEETML: &str = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
    pub const RELATIONSHIPS: &str =
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
}

/// Content-type URIs for the three pivot parts.
pub mod ct {
    pub const PIVOT_CACHE_DEFINITION: &str =
        "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml";
    pub const PIVOT_CACHE_RECORDS: &str =
        "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheRecords+xml";
    pub const PIVOT_TABLE: &str =
        "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml";
    /// RFC-061 — slicer cache part content-type.
    pub const SLICER_CACHE: &str = "application/vnd.ms-excel.slicerCache+xml";
    /// RFC-061 — slicer presentation part content-type.
    pub const SLICER: &str = "application/vnd.ms-excel.slicer+xml";
}

/// Relationship-type URIs that the workbook / cache / sheet rels graphs
/// emit. The workbook-level `PIVOT_CACHE_DEF` and sheet-level
/// `PIVOT_TABLE` are also re-exported from `wolfxl-rels::rt::*` for
/// callers already on that namespace; we re-state them here for the
/// pivot-internal `PIVOT_CACHE_RECORDS` rel which is unique to this
/// crate.
pub mod rt {
    pub const PIVOT_CACHE_RECORDS: &str =
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheRecords";
    /// RFC-061 — slicer cache → pivot cache rel type.
    pub const SLICER_CACHE: &str =
        "http://schemas.microsoft.com/office/2007/relationships/slicerCache";
    /// RFC-061 — sheet → slicer presentation rel type.
    pub const SLICER: &str = "http://schemas.microsoft.com/office/2007/relationships/slicer";
}

/// `<extLst>` extension URIs (RFC-061 §3.1).
pub mod ext_uri {
    /// Workbook-level `<x14:slicerCaches>` extension URI.
    pub const WORKBOOK_SLICER_CACHES: &str = "{A8765BA9-456A-4DAB-B4F3-ACF838C121DE}";
    /// Sheet-level `<x14:slicerList>` extension URI.
    pub const SHEET_SLICER_LIST: &str = "{3A4CF648-6AED-40f4-86FF-DC5316D8AED3}";
}
