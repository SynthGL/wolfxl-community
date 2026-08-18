//! Typed model for ECMA-376 §18.3.2 `<autoFilter>` and §18.3.1.92 `<sortState>`.
//!
//! See `Plans/rfcs/056-autofilter-eval.md` §2.1 for the source-of-truth
//! API list and §10 for the dict-shape contract that bridges the
//! Python coordinator to this crate.

pub mod column;
pub mod filter;
pub mod sort;

pub use column::{AutoFilter, DateGroupItem, DateTimeGrouping, FilterColumn};
pub use filter::{
    BlankFilter, ColorFilter, CustomFilter, CustomFilterOp, CustomFilters, DynamicFilter,
    DynamicFilterType, FilterKind, IconFilter, NumberFilter, StringFilter, Top10,
};
pub use sort::{SortBy, SortCondition, SortState};
