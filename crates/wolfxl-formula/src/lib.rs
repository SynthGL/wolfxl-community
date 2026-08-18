//! `wolfxl-formula` — A1-syntax Excel formula tokenizer and reference
//! translator.
//!
//! This crate is consumed by both the wolfxl patcher (modify-mode) and
//! the native writer. Per the workspace invariant from `CLAUDE.md`,
//! it has **no PyO3 dependency** — pure Rust only.
//!
//! See `Plans/rfcs/012-formula-xlator.md` for the authoritative spec.
//!
//! # Modules
//!
//! - [`tokenizer`] — Direct port of openpyxl's Bachtal-style tokenizer.
//!   Splits a formula string into a flat sequence of [`Token`] objects
//!   while preserving every byte of source content (whitespace, operators,
//!   string literals). The tokenizer is what lets the translator avoid
//!   the regex pitfalls described in RFC-012 §3.
//! - [`reference`] — Parses [`tokenizer::Token`] values whose
//!   subkind is [`TokenSubKind::Range`] into structured [`reference::RefKind`]
//!   variants (cell, range, whole-row, whole-col, structured-table, name).
//! - [`translate`] — The public translation operations that mutate a
//!   formula string in-place: row/col shift, sheet rename, range move,
//!   range-clip on delete.
//!
//! # Public surface (entry points)
//!
//! ```ignore
//! use wolfxl_formula::{shift, rename_sheet, move_range, ShiftPlan, Axis, Range};
//!
//! // Insert 3 rows starting at row 5: every row >= 5 in every reference
//! // shifts down by 3 (both relative and absolute, modulo respect_dollar).
//! let f = "=SUM($A$5:B10)+Sheet2!C7";
//! let out = shift(f, &ShiftPlan { axis: Axis::Row, at: 5, n: 3, respect_dollar: false });
//! assert_eq!(out, "=SUM($A$8:B13)+Sheet2!C10");
//!
//! // Rename a sheet that's referenced from elsewhere.
//! let out = rename_sheet("=Forecast!B5", "Forecast", "Forecast_v2");
//! assert_eq!(out, "=Forecast_v2!B5");
//! ```
//!
//! # Open question (BLOCKER)
//!
//! See `Plans/rfcs/notes/excel-respect-dollar-check.md`. The default value
//! of `respect_dollar` for row/col-shift operations has not yet been
//! verified in Excel. Until that 5-minute check is done:
//!
//! - [`ShiftPlan::respect_dollar`] is a **required field with no default**.
//!   Callers must explicitly pass it.
//! - The `RefDelta` low-level API (used internally by [`translate::translate_with_meta`])
//!   exposes the same flag without a default.
//!
//! Once the verification doc is updated, RFC-012 §5.5 will be patched
//! and a `Default` impl can be added here.

#![deny(rust_2018_idioms)]

pub mod reference;
pub mod tokenizer;
pub mod translate;

#[cfg(test)]
mod tests;

// Re-exports for ergonomic top-level access.

pub use tokenizer::{tokenize, Token, TokenKind, TokenSubKind, TokenizeError};

pub use reference::{
    parse_cell, parse_range_part, A1Cell, A1Col, A1RangeEndpoint, A1Row, RefKind, TableRef,
};

pub use translate::{
    move_range, rename_sheet, shift, translate, translate_with_meta, Axis, DeletedRange, Range,
    RefDelta, ShiftPlan, TranslateResult,
};

/// Maximum row index supported by Excel 2007+ (1-based, inclusive).
pub const MAX_ROW: u32 = 1_048_576;

/// Maximum column index supported by Excel 2007+ (1-based, inclusive).
pub const MAX_COL: u32 = 16_384;
