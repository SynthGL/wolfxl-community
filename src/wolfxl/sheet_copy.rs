//! `sheet_copy` — entry point for the `Workbook.copy_worksheet` planner
//! (RFC-035).
//!
//! Lives at `src/wolfxl/sheet_copy.rs` per RFC-035 §7.2's API location
//! requirement, but the actual planner logic lives in the PyO3-free
//! `wolfxl_structural::sheet_copy` module so that its unit tests can run
//! via `cargo test -p wolfxl-structural` without touching the cdylib's
//! known macOS-arm64 link issue (see CLAUDE.md / Sprint Ε notes).
//!
//! Phase 2.7 of `XlsxPatcher::do_save` will consume `plan_sheet_copy`
//! to drain `queued_sheet_copies`. Pod-β owns that wiring; this slice
//! ships the planner only.
//!
//! See `Plans/rfcs/035-copy-worksheet.md` §4.2 for the contract and
//! §7.1 / §7.2 for the slicing.

#[allow(unused_imports)]
pub use wolfxl_structural::sheet_copy::{
    plan_sheet_copy, DefinedNameClone, SheetCopyError, SheetCopyInputs, SheetCopyMutations,
};
