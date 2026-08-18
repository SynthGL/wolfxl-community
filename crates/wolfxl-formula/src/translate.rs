//! Public translation operations: row/col shift, sheet rename, range
//! move, and the lower-level [`translate`] / [`translate_with_meta`]
//! entry points used by the patcher.
//!
//! See [`crate`] doc for an overview.
//!
//! # respect_dollar (open question, BLOCKER)
//!
//! Whether absolute (`$`) row/col parts shift on insert/delete row is
//! still pending Excel-side verification (see
//! `Plans/rfcs/notes/excel-respect-dollar-check.md`). Until verified,
//! the [`ShiftPlan::respect_dollar`] field is required (no default).
//! Likewise [`RefDelta::respect_dollar`] has no default for shift
//! operations.

use std::collections::HashMap;

use crate::reference::{
    col_letter, parse_ref, render_cell, sheet_name_needs_quoting, A1Cell, A1Col, A1Row, RefKind,
    SheetPrefix,
};
use crate::tokenizer::{render, tokenize, Token, TokenKind, TokenSubKind, TokenizeError};
use crate::{MAX_COL, MAX_ROW};

/// Which axis to shift on.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Axis {
    /// Shift rows.
    Row,
    /// Shift columns.
    Col,
}

/// Plan for a row- or col-insert/delete shift across one sheet's coordinate
/// space.
///
/// `n` is the signed delta — positive for insert, negative for delete.
/// Rows / cols at index `>= at` are affected. To delete rows, callers
/// pass a negative `n` AND set the deleted range via the lower-level
/// [`RefDelta::deleted_range`] API (use [`translate_with_meta`] directly).
#[derive(Debug, Clone)]
pub struct ShiftPlan {
    /// Row or col axis.
    pub axis: Axis,
    /// 1-based index where shifting begins (rows/cols `>= at` shift).
    pub at: u32,
    /// Signed shift count.
    pub n: i32,
    /// If true, `$`-absolute row/col parts are NOT shifted (paste-style
    /// semantics). If false, all references shift regardless of `$`
    /// (coordinate-remap semantics — what Excel does on insert_rows).
    ///
    /// **No default**. See module doc — pending Excel verification.
    pub respect_dollar: bool,
}

/// Inclusive 1-based rectangular range used for tombstone / move ops.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Range {
    /// Top-left row (inclusive).
    pub min_row: u32,
    /// Bottom-right row (inclusive).
    pub max_row: u32,
    /// Top-left col (inclusive).
    pub min_col: u32,
    /// Bottom-right col (inclusive).
    pub max_col: u32,
}

impl Range {
    fn contains(&self, row: u32, col: u32) -> bool {
        row >= self.min_row && row <= self.max_row && col >= self.min_col && col <= self.max_col
    }
}

/// Tombstone — references whose coordinates fall inside this range
/// become `#REF!` after translation. Used by `delete_rows` / `delete_cols`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DeletedRange {
    /// Inclusive 1-based row min.
    pub min_row: u32,
    /// Inclusive 1-based row max.
    pub max_row: u32,
    /// Inclusive 1-based col min.
    pub min_col: u32,
    /// Inclusive 1-based col max.
    pub max_col: u32,
}

impl DeletedRange {
    fn contains(&self, row: u32, col: u32) -> bool {
        row >= self.min_row && row <= self.max_row && col >= self.min_col && col <= self.max_col
    }

    fn whole_rows(&self) -> bool {
        self.min_col == 1 && self.max_col >= MAX_COL
    }

    fn whole_cols(&self) -> bool {
        self.min_row == 1 && self.max_row >= MAX_ROW
    }
}

/// Low-level translator inputs.
///
/// Most callers should prefer the high-level [`shift`], [`rename_sheet`],
/// or [`move_range`] helpers.
#[derive(Debug, Clone)]
pub struct RefDelta {
    /// Row offset (signed). Applied to refs whose row >= `anchor_row`.
    pub rows: i32,
    /// Column offset (signed). Applied to refs whose col >= `anchor_col`.
    pub cols: i32,
    /// Row anchor: shift only applies if ref.row >= anchor_row. 0 means
    /// no row anchor (don't shift rows at all).
    pub anchor_row: u32,
    /// Col anchor: shift only applies if ref.col >= anchor_col. 0 means
    /// no col anchor.
    pub anchor_col: u32,
    /// Sheet renames applied AFTER coordinate shift.
    pub sheet_renames: HashMap<String, String>,
    /// Tombstone range — refs *into* this range become `#REF!`.
    pub deleted_range: Option<DeletedRange>,
    /// Sheet name the formula belongs to. Used to scope unqualified refs
    /// against `deleted_range_sheet`.
    pub formula_sheet: Option<String>,
    /// Sheet name `deleted_range` applies to. None = "applies regardless
    /// of sheet" (only used in tests).
    pub deleted_range_sheet: Option<String>,
    /// If true, `$`-marked row/col parts are NOT shifted (paste-style).
    /// If false, all refs shift regardless of `$` (coordinate-remap).
    pub respect_dollar: bool,
    /// Optional move-range: refs that point inside `move_src` (on
    /// `formula_sheet`) get re-anchored by `move_dst - move_src`.
    /// Independent of `rows`/`cols` (which model insert/delete).
    pub move_src: Option<Range>,
    /// Move-range destination top-left (1-based).
    pub move_dst_row: u32,
    /// Move-range destination top-left col (1-based).
    pub move_dst_col: u32,
}

impl RefDelta {
    /// New `RefDelta` with all fields zero / empty. `respect_dollar`
    /// defaults to `false` (coordinate-remap) which is the value used by
    /// [`shift`] / [`rename_sheet`]. `move_range` overrides this to
    /// `true` (paste-style).
    pub fn empty() -> Self {
        Self {
            rows: 0,
            cols: 0,
            anchor_row: 0,
            anchor_col: 0,
            sheet_renames: HashMap::new(),
            deleted_range: None,
            formula_sheet: None,
            deleted_range_sheet: None,
            respect_dollar: false,
            move_src: None,
            move_dst_row: 0,
            move_dst_col: 0,
        }
    }
}

/// Result of a single translation, with metadata.
#[derive(Debug, Clone)]
pub struct TranslateResult {
    /// Translated formula text.
    pub formula: String,
    /// Number of references actually rewritten (value changed).
    pub refs_changed: u32,
    /// Number of references that became `#REF!` due to delete or
    /// out-of-bounds shift.
    pub refs_to_ref_error: u32,
    /// True if INDIRECT / OFFSET / ADDRESS / INDEX / CHOOSE / HYPERLINK
    /// appears in the formula. The translator does NOT modify their
    /// text-arg contents; the caller may want to surface a warning.
    pub has_volatile_indirect: bool,
}

/// Tokenize, translate every Range-subtype operand per `delta`, and
/// re-emit. Returns the new formula string. The leading `=` is preserved
/// if present in input.
///
/// Errors propagate from [`tokenize`].
pub fn translate(formula: &str, delta: &RefDelta) -> Result<String, TokenizeError> {
    Ok(translate_with_meta(formula, delta)?.formula)
}

/// Like [`translate`] but returns metadata.
pub fn translate_with_meta(
    formula: &str,
    delta: &RefDelta,
) -> Result<TranslateResult, TokenizeError> {
    let tokens = tokenize(formula)?;
    let mut refs_changed = 0;
    let mut refs_to_ref_error = 0;
    let has_volatile_indirect = detect_volatile(&tokens);

    let mut new_tokens: Vec<Token> = Vec::with_capacity(tokens.len());
    for t in tokens.into_iter() {
        if t.kind == TokenKind::Operand && t.subkind == TokenSubKind::Range {
            let parsed = parse_ref(&t.value);
            let (new_kind, changed, to_ref_err) = translate_ref_kind(parsed, delta);
            let new_value = new_kind.render();
            if new_value != t.value {
                refs_changed += if changed { 1 } else { 0 };
                if to_ref_err {
                    refs_to_ref_error += 1;
                }
                new_tokens.push(Token {
                    value: new_value,
                    kind: TokenKind::Operand,
                    subkind: match &new_kind {
                        RefKind::Error(_) => TokenSubKind::Error,
                        _ => TokenSubKind::Range,
                    },
                });
            } else {
                new_tokens.push(t);
            }
        } else {
            new_tokens.push(t);
        }
    }

    Ok(TranslateResult {
        formula: render(&new_tokens),
        refs_changed,
        refs_to_ref_error,
        has_volatile_indirect,
    })
}

fn detect_volatile(tokens: &[Token]) -> bool {
    let names = [
        "INDIRECT(",
        "OFFSET(",
        "ADDRESS(",
        "INDEX(",
        "CHOOSE(",
        "HYPERLINK(",
    ];
    tokens.iter().any(|t| {
        t.kind == TokenKind::Func
            && t.subkind == TokenSubKind::Open
            && names.iter().any(|n| t.value.eq_ignore_ascii_case(n))
    })
}

/// Returns (new RefKind, changed?, became #REF!?).
fn translate_ref_kind(rk: RefKind, delta: &RefDelta) -> (RefKind, bool, bool) {
    match rk {
        RefKind::Cell { sheet, cell } => {
            let (sheet, cell, became_ref, _changed) = translate_cell(sheet, cell, delta);
            if became_ref {
                return (RefKind::Error("#REF!".into()), true, true);
            }
            (RefKind::Cell { sheet, cell }, true, false)
        }
        RefKind::Range { sheet, lhs, rhs } => translate_range_kind(sheet, lhs, rhs, delta),
        RefKind::RowRange { sheet, lhs, rhs } => translate_row_range(sheet, lhs, rhs, delta),
        RefKind::ColRange { sheet, lhs, rhs } => translate_col_range(sheet, lhs, rhs, delta),
        RefKind::Table(_) | RefKind::ExternalBook { .. } | RefKind::Name(_) | RefKind::Error(_) => {
            (rk, false, false)
        }
    }
}

fn translate_cell(
    sheet: Option<SheetPrefix>,
    cell: A1Cell,
    delta: &RefDelta,
) -> (Option<SheetPrefix>, A1Cell, bool, bool) {
    let sheet = sheet.map(|s| {
        if let Some(new_name) = delta.sheet_renames.get(&s.name) {
            renamed_sheet_prefix(new_name)
        } else {
            s
        }
    });

    let eff_sheet = sheet
        .as_ref()
        .map(|s| s.name.as_str())
        .or(delta.formula_sheet.as_deref());

    if let Some(d) = &delta.deleted_range {
        let matches = match (&delta.deleted_range_sheet, eff_sheet) {
            (Some(want), Some(got)) => want == got,
            (Some(_), None) => false,
            (None, _) => true,
        };
        if matches && d.contains(cell.row, cell.col) {
            return (sheet, cell, true, true);
        }
    }

    let mut row = cell.row;
    let mut col = cell.col;
    if let Some(src) = &delta.move_src {
        let in_src_sheet = match (&delta.formula_sheet, eff_sheet) {
            (Some(fs), Some(es)) => fs == es,
            _ => true,
        };
        if in_src_sheet && src.contains(row, col) {
            let dr = delta.move_dst_row as i64 - src.min_row as i64;
            let dc = delta.move_dst_col as i64 - src.min_col as i64;
            let nr = row as i64 + dr;
            let nc = col as i64 + dc;
            if nr < 1 || nc < 1 || nr > MAX_ROW as i64 || nc > MAX_COL as i64 {
                return (sheet, cell, true, true);
            }
            row = nr as u32;
            col = nc as u32;
        }
    }

    let shift_row = delta.rows != 0
        && delta.anchor_row > 0
        && row >= delta.anchor_row
        && !(delta.respect_dollar && cell.row_abs);
    let shift_col = delta.cols != 0
        && delta.anchor_col > 0
        && col >= delta.anchor_col
        && !(delta.respect_dollar && cell.col_abs);

    if shift_row {
        let nr = row as i64 + delta.rows as i64;
        if nr < 1 || nr > MAX_ROW as i64 {
            return (sheet, cell, true, true);
        }
        row = nr as u32;
    }
    if shift_col {
        let nc = col as i64 + delta.cols as i64;
        if nc < 1 || nc > MAX_COL as i64 {
            return (sheet, cell, true, true);
        }
        col = nc as u32;
    }

    let new_cell = A1Cell {
        row,
        col,
        col_abs: cell.col_abs,
        row_abs: cell.row_abs,
    };
    let changed = new_cell != cell;
    (sheet, new_cell, false, changed)
}

fn translate_range_kind(
    sheet: Option<SheetPrefix>,
    lhs: A1Cell,
    rhs: A1Cell,
    delta: &RefDelta,
) -> (RefKind, bool, bool) {
    let full_sheet = is_full_sheet_range(&lhs, &rhs);
    if full_sheet
        && ((delta.rows != 0 && delta.anchor_row > 0)
            || (delta.cols != 0 && delta.anchor_col > 0)
            || delta.deleted_range.is_some())
    {
        let (sheet, sheet_changed) = translate_sheet_prefix(sheet, delta);
        return (RefKind::Range { sheet, lhs, rhs }, sheet_changed, false);
    }

    if let Some(d) = &delta.deleted_range {
        let eff_sheet = sheet
            .as_ref()
            .map(|s| s.name.as_str())
            .or(delta.formula_sheet.as_deref());
        let scope_match = match (&delta.deleted_range_sheet, eff_sheet) {
            (Some(want), Some(got)) => want == got,
            (Some(_), None) => false,
            (None, _) => true,
        };
        if scope_match {
            if let Some((nlhs, nrhs)) = clip_range(&lhs, &rhs, d) {
                let (s_a, c_a, err_a, _) =
                    translate_cell_skip_tombstone(sheet.clone(), nlhs, delta);
                let (_, c_b, err_b, _) = translate_cell_skip_tombstone(None, nrhs, delta);
                if err_a || err_b {
                    return (RefKind::Error("#REF!".into()), true, true);
                }
                return (
                    RefKind::Range {
                        sheet: s_a,
                        lhs: c_a,
                        rhs: c_b,
                    },
                    true,
                    false,
                );
            } else {
                return (RefKind::Error("#REF!".into()), true, true);
            }
        }
    }

    let (s_a, c_a, err_a, _) = translate_cell(sheet, lhs, delta);
    if err_a {
        return (RefKind::Error("#REF!".into()), true, true);
    }
    let (_, c_b, err_b, _) = translate_cell(None, rhs, delta);
    if err_b {
        return (RefKind::Error("#REF!".into()), true, true);
    }
    (
        RefKind::Range {
            sheet: s_a,
            lhs: c_a,
            rhs: c_b,
        },
        true,
        false,
    )
}

fn translate_cell_skip_tombstone(
    sheet: Option<SheetPrefix>,
    cell: A1Cell,
    delta: &RefDelta,
) -> (Option<SheetPrefix>, A1Cell, bool, bool) {
    let sheet = sheet.map(|s| {
        if let Some(new_name) = delta.sheet_renames.get(&s.name) {
            renamed_sheet_prefix(new_name)
        } else {
            s
        }
    });

    let mut row = cell.row;
    let mut col = cell.col;

    if let Some(src) = &delta.move_src {
        if src.contains(row, col) {
            let dr = delta.move_dst_row as i64 - src.min_row as i64;
            let dc = delta.move_dst_col as i64 - src.min_col as i64;
            let nr = row as i64 + dr;
            let nc = col as i64 + dc;
            if nr < 1 || nc < 1 || nr > MAX_ROW as i64 || nc > MAX_COL as i64 {
                return (sheet, cell, true, true);
            }
            row = nr as u32;
            col = nc as u32;
        }
    }

    let shift_row = delta.rows != 0
        && delta.anchor_row > 0
        && row >= delta.anchor_row
        && !(delta.respect_dollar && cell.row_abs);
    let shift_col = delta.cols != 0
        && delta.anchor_col > 0
        && col >= delta.anchor_col
        && !(delta.respect_dollar && cell.col_abs);

    if shift_row {
        let nr = row as i64 + delta.rows as i64;
        if nr < 1 || nr > MAX_ROW as i64 {
            return (sheet, cell, true, true);
        }
        row = nr as u32;
    }
    if shift_col {
        let nc = col as i64 + delta.cols as i64;
        if nc < 1 || nc > MAX_COL as i64 {
            return (sheet, cell, true, true);
        }
        col = nc as u32;
    }

    let new_cell = A1Cell {
        row,
        col,
        col_abs: cell.col_abs,
        row_abs: cell.row_abs,
    };
    let changed = new_cell != cell;
    (sheet, new_cell, false, changed)
}

fn clip_range(lhs: &A1Cell, rhs: &A1Cell, d: &DeletedRange) -> Option<(A1Cell, A1Cell)> {
    let r_min = lhs.row.min(rhs.row);
    let r_max = lhs.row.max(rhs.row);
    let c_min = lhs.col.min(rhs.col);
    let c_max = lhs.col.max(rhs.col);

    let row_delete = d.whole_rows();
    let col_delete = d.whole_cols();

    if row_delete {
        if d.max_row < r_min || d.min_row > r_max {
            return Some((lhs.clone(), rhs.clone()));
        }
        if d.min_row <= r_min && d.max_row >= r_max {
            return None;
        }
        let new_r_min = if d.min_row <= r_min {
            d.max_row + 1
        } else {
            r_min
        };
        let new_r_max = if d.max_row >= r_max {
            d.min_row - 1
        } else {
            r_max
        };
        if new_r_min > new_r_max {
            return None;
        }
        let (new_lhs_row, new_rhs_row) = if lhs.row <= rhs.row {
            (new_r_min, new_r_max)
        } else {
            (new_r_max, new_r_min)
        };
        return Some((
            A1Cell {
                row: new_lhs_row,
                col: lhs.col,
                col_abs: lhs.col_abs,
                row_abs: lhs.row_abs,
            },
            A1Cell {
                row: new_rhs_row,
                col: rhs.col,
                col_abs: rhs.col_abs,
                row_abs: rhs.row_abs,
            },
        ));
    }

    if col_delete {
        if d.max_col < c_min || d.min_col > c_max {
            return Some((lhs.clone(), rhs.clone()));
        }
        if d.min_col <= c_min && d.max_col >= c_max {
            return None;
        }
        let new_c_min = if d.min_col <= c_min {
            d.max_col + 1
        } else {
            c_min
        };
        let new_c_max = if d.max_col >= c_max {
            d.min_col - 1
        } else {
            c_max
        };
        if new_c_min > new_c_max {
            return None;
        }
        let (new_lhs_col, new_rhs_col) = if lhs.col <= rhs.col {
            (new_c_min, new_c_max)
        } else {
            (new_c_max, new_c_min)
        };
        return Some((
            A1Cell {
                row: lhs.row,
                col: new_lhs_col,
                col_abs: lhs.col_abs,
                row_abs: lhs.row_abs,
            },
            A1Cell {
                row: rhs.row,
                col: new_rhs_col,
                col_abs: rhs.col_abs,
                row_abs: rhs.row_abs,
            },
        ));
    }

    if d.min_row <= r_min && d.max_row >= r_max && d.min_col <= c_min && d.max_col >= c_max {
        None
    } else {
        Some((lhs.clone(), rhs.clone()))
    }
}

fn translate_row_range(
    sheet: Option<SheetPrefix>,
    lhs: A1Row,
    rhs: A1Row,
    delta: &RefDelta,
) -> (RefKind, bool, bool) {
    let (sheet, sheet_changed) = translate_sheet_prefix(sheet, delta);

    if is_full_row_range(&lhs, &rhs)
        && (delta.rows != 0 && delta.anchor_row > 0 || row_delete_applies(delta))
    {
        return (RefKind::RowRange { sheet, lhs, rhs }, sheet_changed, false);
    }

    if let Some(d) = &delta.deleted_range {
        if d.whole_rows() {
            let r_min = lhs.row.min(rhs.row);
            let r_max = lhs.row.max(rhs.row);
            if d.min_row <= r_min && d.max_row >= r_max {
                return (RefKind::Error("#REF!".into()), true, true);
            }
        }
    }
    let new_l = shift_row(&lhs, delta);
    let new_r = shift_row(&rhs, delta);
    match (new_l, new_r) {
        (Some(l), Some(r)) => (
            RefKind::RowRange {
                sheet,
                lhs: l,
                rhs: r,
            },
            true,
            false,
        ),
        _ => (RefKind::Error("#REF!".into()), true, true),
    }
}

fn shift_row(r: &A1Row, delta: &RefDelta) -> Option<A1Row> {
    if delta.rows == 0 || delta.anchor_row == 0 || r.row < delta.anchor_row {
        return Some(r.clone());
    }
    if delta.respect_dollar && r.abs {
        return Some(r.clone());
    }
    let nr = r.row as i64 + delta.rows as i64;
    if nr < 1 || nr > MAX_ROW as i64 {
        return None;
    }
    Some(A1Row {
        row: nr as u32,
        abs: r.abs,
    })
}

fn translate_col_range(
    sheet: Option<SheetPrefix>,
    lhs: A1Col,
    rhs: A1Col,
    delta: &RefDelta,
) -> (RefKind, bool, bool) {
    let (sheet, sheet_changed) = translate_sheet_prefix(sheet, delta);

    if is_full_col_range(&lhs, &rhs)
        && (delta.cols != 0 && delta.anchor_col > 0 || col_delete_applies(delta))
    {
        return (RefKind::ColRange { sheet, lhs, rhs }, sheet_changed, false);
    }

    if let Some(d) = &delta.deleted_range {
        if d.whole_cols() {
            let c_min = lhs.col.min(rhs.col);
            let c_max = lhs.col.max(rhs.col);
            if d.min_col <= c_min && d.max_col >= c_max {
                return (RefKind::Error("#REF!".into()), true, true);
            }
        }
    }
    let new_l = shift_col(&lhs, delta);
    let new_r = shift_col(&rhs, delta);
    match (new_l, new_r) {
        (Some(l), Some(r)) => (
            RefKind::ColRange {
                sheet,
                lhs: l,
                rhs: r,
            },
            true,
            false,
        ),
        _ => (RefKind::Error("#REF!".into()), true, true),
    }
}

fn shift_col(c: &A1Col, delta: &RefDelta) -> Option<A1Col> {
    if delta.cols == 0 || delta.anchor_col == 0 || c.col < delta.anchor_col {
        return Some(c.clone());
    }
    if delta.respect_dollar && c.abs {
        return Some(c.clone());
    }
    let nc = c.col as i64 + delta.cols as i64;
    if nc < 1 || nc > MAX_COL as i64 {
        return None;
    }
    Some(A1Col {
        col: nc as u32,
        abs: c.abs,
    })
}

fn translate_sheet_prefix(
    sheet: Option<SheetPrefix>,
    delta: &RefDelta,
) -> (Option<SheetPrefix>, bool) {
    match sheet {
        Some(s) => {
            if let Some(new_name) = delta.sheet_renames.get(&s.name) {
                (Some(renamed_sheet_prefix(new_name)), true)
            } else {
                (Some(s), false)
            }
        }
        None => (None, false),
    }
}

fn renamed_sheet_prefix(new_name: &str) -> SheetPrefix {
    SheetPrefix {
        name: new_name.to_string(),
        quoted: sheet_name_needs_quoting(new_name),
    }
}

fn is_full_sheet_range(lhs: &A1Cell, rhs: &A1Cell) -> bool {
    lhs.row.min(rhs.row) == 1
        && lhs.row.max(rhs.row) == MAX_ROW
        && lhs.col.min(rhs.col) == 1
        && lhs.col.max(rhs.col) == MAX_COL
}

fn is_full_row_range(lhs: &A1Row, rhs: &A1Row) -> bool {
    lhs.row.min(rhs.row) == 1 && lhs.row.max(rhs.row) == MAX_ROW
}

fn is_full_col_range(lhs: &A1Col, rhs: &A1Col) -> bool {
    lhs.col.min(rhs.col) == 1 && lhs.col.max(rhs.col) == MAX_COL
}

fn row_delete_applies(delta: &RefDelta) -> bool {
    delta
        .deleted_range
        .as_ref()
        .map(|d| d.whole_rows())
        .unwrap_or(false)
}

fn col_delete_applies(delta: &RefDelta) -> bool {
    delta
        .deleted_range
        .as_ref()
        .map(|d| d.whole_cols())
        .unwrap_or(false)
}

#[allow(dead_code)]
fn _touch_unused() {
    let _ = render_cell;
    let _ = col_letter;
}

// ----------------- High-level helpers -------------------------------

/// Shift every reference per the plan and return the new formula string.
///
/// On parse error, returns the formula unchanged. (Callers that need to
/// detect bad formulas should use [`translate_with_meta`] directly.)
pub fn shift(formula: &str, plan: &ShiftPlan) -> String {
    let mut delta = RefDelta::empty();
    delta.respect_dollar = plan.respect_dollar;
    match plan.axis {
        Axis::Row => {
            delta.rows = plan.n;
            delta.anchor_row = plan.at;
        }
        Axis::Col => {
            delta.cols = plan.n;
            delta.anchor_col = plan.at;
        }
    }
    translate(formula, &delta).unwrap_or_else(|_| formula.to_string())
}

/// Rewrite every 3-D reference whose sheet name matches `old` to use
/// `new`. Returns the new formula text. Pass-through on parse error.
pub fn rename_sheet(formula: &str, old: &str, new: &str) -> String {
    let mut delta = RefDelta::empty();
    delta.sheet_renames.insert(old.to_string(), new.to_string());
    translate(formula, &delta).unwrap_or_else(|_| formula.to_string())
}

/// Move references from `src` to `dst`. Refs that point INTO `src`
/// re-anchor by `dst.min_row - src.min_row`, `dst.min_col - src.min_col`.
/// Refs outside `src` are not touched (paste-style: `respect_dollar=true`
/// is implied — `$` markers do NOT cause shift, but they're not relevant
/// here since move only re-anchors refs that fall inside `src`).
pub fn move_range(formula: &str, src: &Range, dst: &Range, respect_dollar: bool) -> String {
    let mut delta = RefDelta::empty();
    delta.respect_dollar = respect_dollar;
    delta.move_src = Some(*src);
    delta.move_dst_row = dst.min_row;
    delta.move_dst_col = dst.min_col;
    translate(formula, &delta).unwrap_or_else(|_| formula.to_string())
}
