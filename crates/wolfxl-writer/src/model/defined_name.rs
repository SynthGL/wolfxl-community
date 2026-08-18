//! Defined names (named ranges) scoped to the workbook or a specific sheet.

/// A single defined name. Workbook-scope names live on
/// [`crate::model::workbook::Workbook::defined_names`]; sheet-scope names
/// are also stored there with `scope_sheet_index` set to the owning sheet.
///
/// Phase 2 (G22): the optional fields after `hidden` cover the rest of
/// the ECMA-376 §18.2.5 `definedName` attribute surface that openpyxl
/// exposes. Each maps 1:1 to an XML attribute on `<definedName>`.
/// `None` means the attribute is omitted on emit (XML default).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct DefinedName {
    /// The name Excel shows in the Name Manager. Rules: starts with a
    /// letter or `_`, no spaces, ≤ 255 chars, not a cell reference.
    pub name: String,

    /// The formula / range reference the name resolves to. Sheet names
    /// inside the formula are quoted on emission if they contain spaces.
    pub formula: String,

    /// `None` for workbook-scope, `Some(idx)` for a specific sheet.
    pub scope_sheet_index: Option<usize>,

    /// If set, the name is a print area or title — Excel uses magic
    /// well-known names like `_xlnm.Print_Area` and `_xlnm.Print_Titles`.
    /// Callers pass the user-facing name; the emitter adds the `_xlnm.`
    /// prefix where appropriate.
    pub builtin: Option<BuiltinName>,

    /// Whether the name is hidden from the Name Manager (but still usable
    /// in formulas). Used by some apps for bookkeeping ranges.
    pub hidden: bool,

    /// `comment` attribute — free-text comment shown in the Name Manager.
    pub comment: Option<String>,

    /// `customMenu` attribute — string Excel shows in a custom menu slot.
    pub custom_menu: Option<String>,

    /// `description` attribute — free-text description.
    pub description: Option<String>,

    /// `help` attribute — help text.
    pub help: Option<String>,

    /// `statusBar` attribute — status-bar prompt.
    pub status_bar: Option<String>,

    /// `shortcutKey` attribute — single-character keyboard shortcut.
    pub shortcut_key: Option<String>,

    /// `function` attribute — when `Some(true)`, the name is a function.
    pub function: Option<bool>,

    /// `functionGroupId` attribute — function group identifier.
    pub function_group_id: Option<u32>,

    /// `vbProcedure` attribute — when `Some(true)`, the name is a VB procedure.
    pub vb_procedure: Option<bool>,

    /// `xlm` attribute — when `Some(true)`, the name is an Excel 4.0 macro.
    pub xlm: Option<bool>,

    /// `publishToServer` attribute.
    pub publish_to_server: Option<bool>,

    /// `workbookParameter` attribute — when `Some(true)`, the name is a
    /// workbook parameter.
    pub workbook_parameter: Option<bool>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BuiltinName {
    PrintArea,
    PrintTitles,
    /// Referenced by Excel as `_xlnm._FilterDatabase`.
    FilterDatabase,
}
