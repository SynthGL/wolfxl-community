//! Thin re-export of the `<sheetFormatPr>` emitter from
//! [`crate::parse::page_breaks`].
//!
//! The native writer's `sheet_xml::emit` calls this at slot 4 per
//! ECMA-376 §18.3.1.99 when the worksheet carries a typed
//! `SheetFormatProperties` override; otherwise the legacy hardcoded
//! default emits.

pub use crate::parse::page_breaks::{emit_sheet_format_pr, SheetFormatProperties};
