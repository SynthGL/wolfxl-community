//! Worksheet data — rows, cells, merges, freeze, and all sheet-scope features.

use std::collections::BTreeMap;

use super::cell::{WriteCell, WriteCellValue};
use super::chart::Chart;
use super::comment::Comment;
use super::conditional::ConditionalFormat;
use super::image::SheetImage;
use super::table::Table;
use super::threaded_comment::ThreadedComment;
use super::validation::DataValidation;
use crate::refs;

/// A single worksheet within a workbook.
///
/// `BTreeMap` row/cell keys are deliberate: OOXML requires rows inside
/// `<sheetData>` to be sorted ascending by `r`, and cells inside each
/// `<row>` to be sorted ascending by column letter. Using `BTreeMap`
/// means the emitter iterates them in the right order without an
/// explicit pre-sort pass.
///
/// **Streaming mode** ([`Worksheet::streaming`] = `Some`) skips the
/// `BTreeMap` entirely. Rows are encoded straight into a per-sheet
/// temp file as they arrive; `<sheetData>` is then spliced from that
/// file at save time. Streaming and eager are mutually exclusive on a
/// per-sheet basis — `Workbook(write_only=True)` makes every sheet
/// streaming. `Worksheet` is intentionally not `Clone` because the
/// open temp-file handle inside [`StreamingSheet`] cannot be safely
/// duplicated; in practice nothing in the writer crate clones
/// worksheets (each pyclass call mutates in place).
#[derive(Debug)]
pub struct Worksheet {
    /// Sheet display name. Maximum 31 chars; `/\?*[]:` must be stripped
    /// before reaching here. See [`crate::refs::sanitize_sheet_name`].
    pub name: String,

    /// Sparse row storage, keyed by 1-based row index.
    pub rows: BTreeMap<u32, Row>,

    /// Ranges of cells merged into one visual cell.
    pub merges: Vec<Merge>,

    /// The freeze or split pane configuration, if any.
    pub freeze: Option<FreezePane>,
    pub split: Option<SplitPane>,

    /// Column metadata: widths, hidden flags, style defaults.
    /// Keyed by 1-based column index.
    pub columns: BTreeMap<u32, Column>,

    /// Cell-scope hyperlinks. Keyed by A1 reference (e.g. `"A1"`).
    pub hyperlinks: BTreeMap<String, Hyperlink>,

    /// Cell comments. Keyed by A1 reference. Author insertion order
    /// is preserved by the `IndexMap` inside the workbook-level emitter.
    pub comments: BTreeMap<String, Comment>,

    /// Threaded comments (RFC-068 / G08). Flat OOXML-shaped list — replies
    /// are siblings of their parent linked via [`ThreadedComment::parent_id`].
    /// Order is the on-disk emit order: top-level first, then replies in
    /// chronological order. Empty by default.
    pub threaded_comments: Vec<ThreadedComment>,

    /// Conditional formatting blocks. Order is preserved (Excel honors
    /// first-matching priority).
    pub conditional_formats: Vec<ConditionalFormat>,

    /// Data validation rules. Order is preserved.
    pub validations: Vec<DataValidation>,

    /// Tables (`<table>` OOXML, not HTML tables) — named structured ranges.
    pub tables: Vec<Table>,

    /// Print area, stored as a range reference string (e.g. `"A1:D20"`).
    /// Written both into `<definedNames>` at workbook scope and into the
    /// sheet's `<pageSetup>`-adjacent blocks.
    pub print_area: Option<String>,

    /// Whether the sheet tab is visible, hidden, or very-hidden.
    pub visibility: SheetVisibility,

    /// Images attached to this sheet via `ws.add_image(img, anchor)`.
    /// Drained at emit time into
    /// `xl/drawings/drawingN.xml` + `xl/media/imageN.<ext>`.
    pub images: Vec<SheetImage>,

    /// Charts attached to this sheet. Each chart becomes one
    /// `xl/charts/chartN.xml` part referenced from the sheet's drawing
    /// via `<xdr:graphicFrame>`. A sheet can mix images and charts in a
    /// single drawing.
    pub charts: Vec<Chart>,

    /// Pre-emitted `<autoFilter>` block bytes. The native writer does not
    /// run filter evaluation (no existing-cell read-back path); it just
    /// splices the XML at slot 11 of the worksheet element. Modify mode
    /// runs evaluation in the patcher instead.
    ///
    /// `None` (default) → no `<autoFilter>` block emitted. The
    /// caller (workbook-level coordinator) sets this from the
    /// Python `ws.auto_filter.to_rust_dict()` and Rust
    /// `wolfxl_autofilter::emit::emit`.
    pub auto_filter_xml: Option<Vec<u8>>,

    /// Optional `<sheetView>` override. When set, the native writer's
    /// `<sheetViews>` slot uses the typed spec instead of the legacy
    /// hardcoded freeze-pane path. `None` keeps the default sheet view plus
    /// `Worksheet.freeze` / `Worksheet.split` pane mapping.
    pub views: Option<crate::parse::sheet_setup::SheetViewSpec>,

    /// `<sheetProtection>` slot 8.
    pub protection: Option<crate::parse::sheet_setup::SheetProtectionSpec>,

    /// `<pageMargins>` slot 21. Overrides the default margins.
    pub page_margins: Option<crate::parse::sheet_setup::PageMarginsSpec>,

    /// `<printOptions>` slot 20.
    pub print_options: Option<crate::parse::sheet_setup::PrintOptionsSpec>,

    /// `<pageSetup>` slot 22.
    pub page_setup: Option<crate::parse::sheet_setup::PageSetupSpec>,

    /// `<headerFooter>` slot 23.
    pub header_footer: Option<crate::parse::sheet_setup::HeaderFooterSpec>,

    /// `<rowBreaks>` slot 24. `None` means no row-breaks element is emitted.
    pub row_breaks: Option<crate::parse::page_breaks::PageBreakList>,

    /// `<colBreaks>` slot 25. `None` means no col-breaks element is emitted.
    pub col_breaks: Option<crate::parse::page_breaks::PageBreakList>,

    /// `<sheetFormatPr>` slot 4. `None` means the writer keeps the legacy
    /// `<sheetFormatPr defaultRowHeight="15"/>` emit path.
    pub sheet_format: Option<crate::parse::page_breaks::SheetFormatProperties>,

    /// Streaming write_only state (G20 / RFC-073). `None` for normal
    /// eager-mode sheets — the entire `BTreeMap<u32, Row>` workflow
    /// applies. `Some(...)` flips this sheet into bounded-memory
    /// append-only mode: each call to `append_streaming_row` writes
    /// straight to the per-sheet temp file, and
    /// [`crate::emit::sheet_xml::emit`] splices that file into the
    /// `<sheetData>` slot at save time.
    pub streaming: Option<crate::streaming::StreamingSheet>,
}

impl Worksheet {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            rows: BTreeMap::new(),
            merges: Vec::new(),
            freeze: None,
            split: None,
            columns: BTreeMap::new(),
            hyperlinks: BTreeMap::new(),
            comments: BTreeMap::new(),
            threaded_comments: Vec::new(),
            conditional_formats: Vec::new(),
            validations: Vec::new(),
            tables: Vec::new(),
            print_area: None,
            visibility: SheetVisibility::Visible,
            images: Vec::new(),
            charts: Vec::new(),
            auto_filter_xml: None,
            views: None,
            protection: None,
            page_margins: None,
            print_options: None,
            page_setup: None,
            header_footer: None,
            row_breaks: None,
            col_breaks: None,
            sheet_format: None,
            streaming: None,
        }
    }

    /// Set a cell by 1-based row/column. Any row in between is left untouched.
    pub fn set_cell(&mut self, row: u32, col: u32, cell: WriteCell) {
        self.rows.entry(row).or_default().cells.insert(col, cell);
    }

    pub fn set_row_height(&mut self, row: u32, height: f64) {
        self.rows.entry(row).or_default().custom_height = Some(height);
    }

    pub fn set_column(&mut self, col: u32, column: Column) {
        self.columns.insert(col, column);
    }

    pub fn merge(&mut self, range: Merge) {
        self.merges.push(range);
    }

    /// Add a merge by A1 range string (e.g. `"A1:B2"`).
    ///
    /// Returns `Err` when the range fails A1 parsing — the pyclass surfaces
    /// this to Python as `ValueError`.
    pub fn merge_cells(&mut self, range: &str) -> Result<(), String> {
        let ((r1, c1), (r2, c2)) =
            refs::parse_range(range).ok_or_else(|| format!("invalid A1 range: {range:?}"))?;
        self.merges.push(Merge {
            top_row: r1,
            left_col: c1,
            bottom_row: r2,
            right_col: c2,
        });
        Ok(())
    }

    /// Remove a pending merge by A1 range string.
    pub fn unmerge_cells(&mut self, range: &str) -> Result<(), String> {
        let ((r1, c1), (r2, c2)) =
            refs::parse_range(range).ok_or_else(|| format!("invalid A1 range: {range:?}"))?;
        self.merges.retain(|merge| {
            !(merge.top_row == r1
                && merge.left_col == c1
                && merge.bottom_row == r2
                && merge.right_col == c2)
        });
        Ok(())
    }

    /// Set or replace the freeze-pane configuration.
    ///
    /// `freeze_row` and `freeze_col` are 1-based; `0` means no freeze on that
    /// axis. `top_left` is the cell scrolled into the bottom-right pane;
    /// `None` lets the emitter default it.
    pub fn set_freeze(&mut self, freeze_row: u32, freeze_col: u32, top_left: Option<(u32, u32)>) {
        self.freeze = Some(FreezePane {
            freeze_row,
            freeze_col,
            top_left,
        });
        self.split = None;
    }

    /// Set or replace the split-pane configuration. Mutually exclusive with
    /// [`Worksheet::set_freeze`] — calling one clears the other.
    pub fn set_split(&mut self, x_split: f64, y_split: f64, top_left: Option<(u32, u32)>) {
        self.split = Some(SplitPane {
            x_split,
            y_split,
            top_left,
        });
        self.freeze = None;
    }

    /// Set a column's width (in Excel "max-digit-width" units). Other column
    /// metadata (hidden, style_id, outline_level) is preserved if already set.
    pub fn set_column_width(&mut self, col: u32, width: f64) {
        self.columns.entry(col).or_default().width = Some(width);
    }

    /// Set a cell by raw value + optional style id. Convenience wrapper over
    /// [`Worksheet::set_cell`] that the pyclass uses on every Python-side
    /// `write_cell_value` call without having to construct `WriteCell`.
    pub fn write_cell(&mut self, row: u32, col: u32, value: WriteCellValue, style_id: Option<u32>) {
        let cell = WriteCell { value, style_id };
        self.set_cell(row, col, cell);
    }

    /// Rename this sheet, validating the name per Excel rules.
    ///
    /// Errors when the name is empty, longer than 31 chars, contains any of
    /// `/\?*[]:`, or has leading/trailing `'`. Unlike
    /// [`refs::sanitize_sheet_name`] (which silently strips bad chars), this
    /// is the API path Python users hit — they want to know they passed a
    /// bad name, not have it quietly mutated.
    pub fn rename(&mut self, new_name: String) -> Result<(), String> {
        validate_sheet_name(&new_name)?;
        self.name = new_name;
        Ok(())
    }
}

/// Validate an Excel sheet name. Used by [`Worksheet::rename`] and the
/// pyclass's `add_sheet` path. Returns `Err` with a human-readable message.
pub fn validate_sheet_name(name: &str) -> Result<(), String> {
    if name.is_empty() {
        return Err("sheet name must not be empty".to_string());
    }
    if name.chars().count() > 31 {
        return Err(format!(
            "sheet name {name:?} exceeds Excel's 31-char limit ({})",
            name.chars().count()
        ));
    }
    for bad in ['/', '\\', '?', '*', '[', ']', ':'] {
        if name.contains(bad) {
            return Err(format!(
                "sheet name {name:?} contains forbidden character {bad:?}"
            ));
        }
    }
    if name.starts_with('\'') || name.ends_with('\'') {
        return Err(format!(
            "sheet name {name:?} must not start or end with an apostrophe"
        ));
    }
    Ok(())
}

/// One row's metadata and its cells.
#[derive(Debug, Clone, Default)]
pub struct Row {
    /// If set, the row is emitted with `ht="…" customHeight="1"`.
    pub custom_height: Option<f64>,

    /// If set, the row is hidden (`hidden="1"`).
    pub hidden: bool,

    /// Optional style_id for whole-row default style.
    pub style_id: Option<u32>,

    /// Sparse cell storage, keyed by 1-based column index.
    pub cells: BTreeMap<u32, WriteCell>,
}

/// One column's metadata. Excel stores column widths per-range, but the
/// most common API shape is per-column, so we normalize to that and let
/// the emitter coalesce adjacent identical ranges if desired.
#[derive(Debug, Clone, Default)]
pub struct Column {
    /// Column width in "max-digit-width" units (Excel's oddball measure).
    /// Pass-through whatever the Python caller provides.
    pub width: Option<f64>,
    pub hidden: bool,
    pub style_id: Option<u32>,
    /// Outline-grouping level (used by Data → Group).
    pub outline_level: u8,
}

/// A rectangular range of cells merged into one visual cell.
///
/// `top_row` and `bottom_row` are 1-based; `left_col` and `right_col` are
/// 1-based. For a single cell, all four values are equal — but OOXML
/// allows that and Excel treats it as a no-op.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Merge {
    pub top_row: u32,
    pub left_col: u32,
    pub bottom_row: u32,
    pub right_col: u32,
}

/// Freeze-pane configuration: rows above `freeze_row` and columns left
/// of `freeze_col` stay fixed while the user scrolls.
///
/// Pure split panes (resizable dividers, no freeze) use [`SplitPane`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FreezePane {
    /// 1-based row; 0/1 means no horizontal freeze.
    pub freeze_row: u32,
    /// 1-based column; 0/1 means no vertical freeze.
    pub freeze_col: u32,
    /// The top-left cell shown in the bottom-right pane.
    /// If `None`, defaults to `(freeze_row, freeze_col)`.
    pub top_left: Option<(u32, u32)>,
