//! Workbook map: one-page summary of every sheet (dimensions, headers,
//! classification, anchored tables) plus workbook-level named ranges.
//!
//! The map exists for agents that need to *orient* before fetching cell
//! ranges. Loading every sheet's full grid just to ask "which sheet has
//! the data I want?" is the cost the map prevents.
//!
//! Build via [`Workbook::map`](crate::Workbook::map). Render to JSON or
//! plain text in the consuming binary — `wolfxl-core` stays serde-free.

use crate::cell::CellValue;
use crate::sheet::Sheet;

/// Coarse classification of a sheet's apparent purpose, derived from its
/// value grid alone (no merged-cell or formula inspection).
///
/// Drives downstream prompt strategy: `Data` sheets justify a `peek`,
/// `Readme` sheets often want a single-column dump, `Summary` sheets
/// look formula-heavy with low fill density.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SheetClass {
    Empty,
    Readme,
    Summary,
    Data,
}

impl SheetClass {
    /// Lowercase tag suitable for serialization or grep-friendly text.
    pub fn as_str(&self) -> &'static str {
        match self {
            SheetClass::Empty => "empty",
            SheetClass::Readme => "readme",
            SheetClass::Summary => "summary",
            SheetClass::Data => "data",
        }
    }
}

#[derive(Debug, Clone)]
pub struct SheetMap {
    pub name: String,
    pub rows: usize,
    pub cols: usize,
    pub class: SheetClass,
    /// First-row contents, with empty cells preserved as `""` so column
    /// position is meaningful for downstream consumers.
    pub headers: Vec<String>,
    /// Workbook tables (calamine `table_names_in_sheet`) anchored on this
    /// sheet. Empty when the workbook defines no tables, which is the
    /// common case for hand-authored sheets.
    pub tables: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct WorkbookMap {
    pub path: String,
    pub sheets: Vec<SheetMap>,
    /// Workbook-level defined names as `(name, formula)` pairs, exactly
    /// as calamine surfaces them. The formula string is a sheet+range
    /// reference like `'P&L'!$A$1:$D$25` for typical named ranges.
    pub named_ranges: Vec<(String, String)>,
}

/// Classify a sheet by shape and density. Pure value-grid heuristic — does
/// not look at merged cells, formulas, or formatting.
///
/// Rules in priority order:
/// 1. Zero rows or cols → `Empty`.
/// 2. Exactly one column wide → `Readme` (notes-column convention).
/// 3. Small (≤20 rows × ≤10 cols) AND fill density <40% → `Summary`
///    (sparse formula sheets, dashboards, KPI panels).
/// 4. Otherwise → `Data` (default for anything dense or large).
pub fn classify_sheet(sheet: &Sheet) -> SheetClass {
    let (rows, cols) = sheet.dimensions();
    if rows == 0 || cols == 0 {
        return SheetClass::Empty;
    }
    if cols == 1 {
        return SheetClass::Readme;
    }
    let total = rows * cols;
    let non_empty: usize = sheet
        .rows()
        .iter()
        .map(|row| {
            row.iter()
                .filter(|c| !matches!(c.value, CellValue::Empty))
                .count()
        })
        .sum();
    let density = non_empty as f64 / total as f64;
    if rows <= 20 && cols <= 10 && density < 0.4 {
        return SheetClass::Summary;
    }
    SheetClass::Data
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cell::Cell;

    fn cell(s: &str) -> Cell {
        Cell {
            value: CellValue::String(s.to_string()),
            number_format: None,
        }
    }

    fn empty() -> Cell {
        Cell::empty()
    }

    #[test]
    fn empty_sheet_is_classified_empty() {
        let sheet = Sheet::from_rows_for_test("blank", vec![]);
        assert_eq!(classify_sheet(&sheet), SheetClass::Empty);
    }

    #[test]
    fn single_column_sheet_is_classified_readme() {
        // A notes column — multiple rows but one column wide.
        let rows = (0..15)
            .map(|i| vec![cell(&format!("note line {i}"))])
            .collect();
        let sheet = Sheet::from_rows_for_test("Notes", rows);
        assert_eq!(classify_sheet(&sheet), SheetClass::Readme);
    }

    #[test]
    fn small_sparse_sheet_is_classified_summary() {
        // 5×5 with only a title and one KPI populated → density 2/25 = 8%,
        // well under the 40% threshold; small enough on both axes.
        let mut rows = vec![vec![empty(); 5]; 5];
        rows[0][0] = cell("Q1 2026 Summary");
        rows[2][1] = cell("$1.2M");
        let sheet = Sheet::from_rows_for_test("Summary", rows);
        assert_eq!(classify_sheet(&sheet), SheetClass::Summary);
    }

    #[test]
    fn dense_rectangular_sheet_is_classified_data() {
        // 10×5 fully populated grid → density 100%, defaults to Data.
        let rows = (0..10)
            .map(|r| (0..5).map(|c| cell(&format!("r{r}c{c}"))).collect())
            .collect();
        let sheet = Sheet::from_rows_for_test("Ledger", rows);
        assert_eq!(classify_sheet(&sheet), SheetClass::Data);
    }

    #[test]
    fn large_sheet_skips_summary_branch_even_if_sparse() {
        // 50×15 mostly empty (only first cell filled) → density well under
        // 40% but dimensions exceed the small-sheet gate, so falls
        // through to Data. Without this rule, a giant mostly-empty data
        // grid would mis-classify as Summary.
        let mut rows = vec![vec![empty(); 15]; 50];
        rows[0][0] = cell("seed");
        let sheet = Sheet::from_rows_for_test("Big", rows);
        assert_eq!(classify_sheet(&sheet), SheetClass::Data);
    }
}
