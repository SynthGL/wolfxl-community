//! `wolfxl-autofilter` — OOXML `<autoFilter>` + `<sortState>` model,
//! XML emit, and filter-evaluation engine.
//!
//! Pure Rust, no PyO3. Used by both the patcher (modify mode, Phase
//! 2.5o) via thin PyO3 bindings in `src/wolfxl/autofilter.rs` and the
//! native writer (write mode) via direct integration in
//! `crates/wolfxl-writer/src/emit/sheet_xml.rs`.
//!
//! See `Plans/rfcs/056-autofilter-eval.md` for the authoritative
//! contract:
//!
//! * §2.1 — public API surface (11 filter classes).
//! * §3   — XML output shape.
//! * §4   — evaluation semantics.
//! * §10  — dict contract used by the PyO3 boundary.
//!
//! # Architecture
//!
//! ```text
//! Python coordinator (.to_rust_dict())
//!         │
//!         ▼
//!  PyDict shape (RFC-056 §10)
//!         │
//!  ──────[ PyO3 boundary in src/wolfxl/autofilter.rs ]──────
//!         │
//!         ▼  (DictValue tree)
//!  parse::parse_autofilter() ──▶ AutoFilter (typed model)
//!         │                            │
//!         ▼                            ▼
//!  emit::emit() ─▶ Vec<u8>      evaluate::evaluate() ─▶ EvaluationResult
//! ```
//!
//! Ordering: the patcher's Phase 2.5o sequences AFTER pivot Phase
//! 2.5m and BEFORE the per-cell Phase 3. RFC-056 §5.

pub mod emit;
pub mod evaluate;
pub mod model;
pub mod parse;

pub use evaluate::{evaluate, evaluate_autofilter, today_serial, Cell, EvaluationResult};
pub use model::{
    AutoFilter, BlankFilter, ColorFilter, CustomFilter, CustomFilterOp, CustomFilters,
    DateGroupItem, DateTimeGrouping, DynamicFilter, DynamicFilterType, FilterColumn, FilterKind,
    IconFilter, NumberFilter, SortBy, SortCondition, SortState, StringFilter, Top10,
};
pub use parse::{parse_autofilter, DictValue};
