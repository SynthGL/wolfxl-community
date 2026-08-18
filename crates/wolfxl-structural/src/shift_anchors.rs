//! Rewrite `ref` / `sqref` attribute strings.
//!
//! `ref` is a single A1 cell or range (`B5`, `A1:E10`). `sqref` is a
//! space-separated list of refs (`A1:B5 C7 D9:E10`). Multi-range
//! `sqref` is what data-validation and conditional-formatting use.
//!
//! Tombstoned single-cell `ref` becomes `#REF!`. Tombstoned range
//! `ref` clips to the surviving portion (matching openpyxl's DV/CF
//! clip behaviour); a fully-tombstoned range collapses to `#REF!`
//! (and for `sqref` is dropped).

use crate::axis::{Axis, ShiftPlan};
use wolfxl_formula::reference::{col_letter, col_letters_to_num};
use wolfxl_formula::{MAX_COL, MAX_ROW};

/// Shift a single `ref` attribute (cell or range, no sheet prefix,
/// no spaces). Returns `"#REF!"` if the ref was fully tombstoned.
pub fn shift_anchor(s: &str, plan: &ShiftPlan) -> String {
    if plan.is_noop() {
        return s.to_string();
    }
    let trimmed = s.trim();
    if trimmed.is_empty() {
        return s.to_string();
    }
    if let Some((lhs, rhs)) = split_range(trimmed) {
        match shift_range_endpoints(lhs, rhs, plan) {
            Some((nl, nr)) => format!("{nl}:{nr}"),
            None => "#REF!".to_string(),
        }
    } else {
        match shift_cell_str(trimmed, plan) {
            Some(c) => c,
            None => "#REF!".to_string(),
        }
    }
}

/// Shift a multi-range `sqref` attribute. Tombstoned ranges are
/// dropped; if everything tombstones, returns the empty string (the
/// caller should typically drop the entire `<dataValidation>` /
/// `<conditionalFormatting>` element when this happens, but we leave
/// that decision to the orchestrator).
pub fn shift_sqref(s: &str, plan: &ShiftPlan) -> String {
    if plan.is_noop() {
        return s.to_string();
    }
    let mut out: Vec<String> = Vec::new();
    for piece in s.split_whitespace() {
        if let Some((lhs, rhs)) = split_range(piece) {
            if let Some((nl, nr)) = shift_range_endpoints(lhs, rhs, plan) {
                out.push(format!("{nl}:{nr}"));
            }
            // Else: fully tombstoned, drop.
        } else if let Some(c) = shift_cell_str(piece, plan) {
            out.push(c);
        }
        // Else: tombstoned single cell, drop.
    }
    out.join(" ")
}

/// Returns `(lhs, rhs)` if `s` is a range like `"A1:B5"`. Single-cell
/// returns None.
fn split_range(s: &str) -> Option<(&str, &str)> {
    let bytes = s.as_bytes();
    for (i, &b) in bytes.iter().enumerate() {
        if b == b':' {
            return Some((&s[..i], &s[i + 1..]));
        }
    }
    None
}

#[derive(Debug, Clone, Copy)]
struct CellParts {
    col: u32,
    col_abs: bool,
    row: u32,
    row_abs: bool,
    /// True if the source had no row digits (column-only, like `A`).
    col_only: bool,
    /// True if the source had no col letters (row-only, like `5`).
    row_only: bool,
}

fn parse_cell_parts(s: &str) -> Option<CellParts> {
    let bytes = s.as_bytes();
    if bytes.is_empty() {
        return None;
    }
    let mut i = 0;
    let col_abs = if bytes[i] == b'$' {
        i += 1;
        true
    } else {
        false
    };
    let col_start = i;
    while i < bytes.len() && bytes[i].is_ascii_alphabetic() {
        i += 1;
    }
    let col_str = &s[col_start..i];
    let row_abs = if i < bytes.len() && bytes[i] == b'$' {
        i += 1;
        true
    } else {
        false
    };
    let row_start = i;
    while i < bytes.len() && bytes[i].is_ascii_digit() {
        i += 1;
    }
    if i != bytes.len() {
        return None;
    }
    let col_only = !col_str.is_empty() && row_start == bytes.len();
    let row_only = col_str.is_empty() && row_start < bytes.len();
    let col: u32 = if col_str.is_empty() {
        0
    } else {
        col_letters_to_num(col_str)?
    };
    let row: u32 = if row_start == bytes.len() {
        0
    } else {
        s[row_start..].parse().ok()?
    };
    if !col_only && col == 0 && !row_only {
        return None;
    }
    if col_only && col == 0 {
        return None;
    }
    if !col_only && row == 0 {
        return None;
    }
    if col > MAX_COL || row > MAX_ROW {
        return None;
    }
    Some(CellParts {
        col,
        col_abs,
        row,
        row_abs,
        col_only,
        row_only,
    })
}

fn render_cell_parts(c: &CellParts) -> String {
    let mut out = String::with_capacity(8);
    if c.col_abs {
        out.push('$');
    }
    if !c.row_only {
        out.push_str(&col_letter(c.col));
    }
    if c.row_abs {
        out.push('$');
    }
    if !c.col_only {
        out.push_str(&c.row.to_string());
    }
    out
}

/// Shift one A1 cell string. Returns None if tombstoned.
fn shift_cell_str(s: &str, plan: &ShiftPlan) -> Option<String> {
    let mut p = parse_cell_parts(s)?;
    let abs = plan.abs_n();
    match plan.axis {
        Axis::Row => {
            if p.col_only {
                return Some(s.to_string());
            }
            if plan.is_insert() {
                if p.row >= plan.idx {
                    let nr = p.row as i64 + plan.n as i64;
                    if nr < 1 || nr > MAX_ROW as i64 {
                        return None;
                    }
                    p.row = nr as u32;
                }
            } else {
                // delete
                if p.row >= plan.idx && p.row < plan.idx + abs {
                    return None; // tombstone
                }
                if p.row >= plan.idx + abs {
                    let nr = p.row as i64 + plan.n as i64;
                    if nr < 1 || nr > MAX_ROW as i64 {
                        return None;
                    }
                    p.row = nr as u32;
                }
            }
        }
        Axis::Col => {
            if p.row_only {
                return Some(s.to_string());
            }
            if plan.is_insert() {
                if p.col >= plan.idx {
                    let nc = p.col as i64 + plan.n as i64;
                    if nc < 1 || nc > MAX_COL as i64 {
                        return None;
                    }
                    p.col = nc as u32;
                }
            } else {
                if p.col >= plan.idx && p.col < plan.idx + abs {
                    return None;
                }
                if p.col >= plan.idx + abs {
                    let nc = p.col as i64 + plan.n as i64;
                    if nc < 1 || nc > MAX_COL as i64 {
                        return None;
                    }
                    p.col = nc as u32;
                }
            }
        }
    }
    Some(render_cell_parts(&p))
}

/// Shift the two endpoints of a range, clipping if the range
/// partially overlaps the deletion band (matching openpyxl DV/CF
/// clip).
fn shift_range_endpoints(lhs: &str, rhs: &str, plan: &ShiftPlan) -> Option<(String, String)> {
    let mut a = parse_cell_parts(lhs)?;
    let mut b = parse_cell_parts(rhs)?;
    let abs = plan.abs_n();

    if plan.is_insert() {
        // Same as cell-shift on each endpoint.
        match plan.axis {
            Axis::Row => {
                if !a.col_only && a.row >= plan.idx {
                    let nr = a.row as i64 + plan.n as i64;
                    if nr > MAX_ROW as i64 {
                        return None;
                    }
                    a.row = nr as u32;
                }
                if !b.col_only && b.row >= plan.idx {
                    let nr = b.row as i64 + plan.n as i64;
                    if nr > MAX_ROW as i64 {
                        return None;
                    }
                    b.row = nr as u32;
                }
            }
            Axis::Col => {
                if !a.row_only && a.col >= plan.idx {
                    let nc = a.col as i64 + plan.n as i64;
                    if nc > MAX_COL as i64 {
                        return None;
                    }
                    a.col = nc as u32;
                }
                if !b.row_only && b.col >= plan.idx {
                    let nc = b.col as i64 + plan.n as i64;
                    if nc > MAX_COL as i64 {
                        return None;
                    }
                    b.col = nc as u32;
                }
            }
        }
        return Some((render_cell_parts(&a), render_cell_parts(&b)));
    }

    // Delete: clip + shift.
    match plan.axis {
        Axis::Row => {
            if a.col_only && b.col_only {
                // Whole-col range — row component absent on both ends, no change.
                return Some((render_cell_parts(&a), render_cell_parts(&b)));
            }
            // Treat absent rows on either end as the natural extreme.
            let r_min_src = if a.row == 0 { 1 } else { a.row.min(b.row) };
            let r_max_src = {
                let ar = if a.row == 0 { MAX_ROW } else { a.row };
                let br = if b.row == 0 { MAX_ROW } else { b.row };
                ar.max(br)
            };
            let band_lo = plan.idx;
            let band_hi = plan.idx + abs - 1;
            if band_hi < r_min_src || band_lo > r_max_src {
                // Band entirely outside range. If band is below
                // (band_hi < r_min_src) shift both endpoints by -|n|.
                // If band entirely above range (band_lo > r_max_src)
                // we don't shift.
                if band_hi < r_min_src {
                    if !a.col_only {
                        a.row = (a.row as i64 + plan.n as i64) as u32;
                    }
                    if !b.col_only {
                        b.row = (b.row as i64 + plan.n as i64) as u32;
                    }
                }
                return Some((render_cell_parts(&a), render_cell_parts(&b)));
            }
            if band_lo <= r_min_src && band_hi >= r_max_src {
                // Range fully tombstoned.
                return None;
            }
            // Partial overlap: clip surviving portion.
            let new_r_min = if band_lo <= r_min_src {
                band_hi + 1
            } else {
                r_min_src
            };
            let new_r_max = if band_hi >= r_max_src {
                band_lo - 1
            } else {
                r_max_src
            };
            // Shift surviving portion: rows >= idx+|n| shift by n.
            let shift_pair = |row: u32| -> u32 {
                if row >= plan.idx + abs {
                    (row as i64 + plan.n as i64) as u32
                } else {
                    row
                }
            };
            let pre_a = if a.row == 0 { new_r_min } else { a.row };
            let pre_b = if b.row == 0 { new_r_max } else { b.row };
            // For each endpoint pick: if its source value falls in
            // band, snap to the surviving boundary; else keep as-is.
            let snap = |row: u32, is_lo_endpoint: bool| -> u32 {
                if row >= band_lo && row <= band_hi {
                    if is_lo_endpoint {
                        new_r_min
                    } else {
                        new_r_max
                    }
                } else {
                    row
                }
            };
            // Determine which endpoint maps to lo vs hi.
            let (lo_is_a, _) = if pre_a <= pre_b {
                (true, ())
            } else {
                (false, ())
            };
            let new_a_row = if lo_is_a {
                snap(pre_a, true)
            } else {
                snap(pre_a, false)
            };
            let new_b_row = if lo_is_a {
                snap(pre_b, false)
            } else {
                snap(pre_b, true)
            };
            let new_a_row = shift_pair(new_a_row);
            let new_b_row = shift_pair(new_b_row);
            if !a.col_only {
                a.row = new_a_row;
            }
            if !b.col_only {
                b.row = new_b_row;
            }
            Some((render_cell_parts(&a), render_cell_parts(&b)))
        }
        Axis::Col => {
            if a.row_only && b.row_only {
                return Some((render_cell_parts(&a), render_cell_parts(&b)));
            }
            let c_min_src = if a.col == 0 { 1 } else { a.col.min(b.col) };
            let c_max_src = {
                let ac = if a.col == 0 { MAX_COL } else { a.col };
                let bc = if b.col == 0 { MAX_COL } else { b.col };
                ac.max(bc)
            };
            let band_lo = plan.idx;
            let band_hi = plan.idx + abs - 1;
            if band_hi < c_min_src || band_lo > c_max_src {
                if band_hi < c_min_src {
                    if !a.row_only {
                        a.col = (a.col as i64 + plan.n as i64) as u32;
                    }
                    if !b.row_only {
                        b.col = (b.col as i64 + plan.n as i64) as u32;
                    }
                }
                return Some((render_cell_parts(&a), render_cell_parts(&b)));
            }
            if band_lo <= c_min_src && band_hi >= c_max_src {
                return None;
            }
            let new_c_min = if band_lo <= c_min_src {
                band_hi + 1
            } else {
                c_min_src
            };
            let new_c_max = if band_hi >= c_max_src {
                band_lo - 1
            } else {
                c_max_src
            };
            let shift_pair = |col: u32| -> u32 {
                if col >= plan.idx + abs {
                    (col as i64 + plan.n as i64) as u32
                } else {
                    col
                }
            };
            let pre_a = if a.col == 0 { new_c_min } else { a.col };
            let pre_b = if b.col == 0 { new_c_max } else { b.col };
            let snap = |col: u32, is_lo_endpoint: bool| -> u32 {
                if col >= band_lo && col <= band_hi {
                    if is_lo_endpoint {
                        new_c_min
                    } else {
                        new_c_max
                    }
                } else {
                    col
                }
            };
            let (lo_is_a, _) = if pre_a <= pre_b {
                (true, ())
            } else {
                (false, ())
            };
            let new_a_col = if lo_is_a {
                snap(pre_a, true)
            } else {
                snap(pre_a, false)
            };
            let new_b_col = if lo_is_a {
                snap(pre_b, false)
            } else {
                snap(pre_b, true)
            };
            let new_a_col = shift_pair(new_a_col);
            let new_b_col = shift_pair(new_b_col);
            if !a.row_only {
                a.col = new_a_col;
            }
            if !b.row_only {
                b.col = new_b_col;
            }
            Some((render_cell_parts(&a), render_cell_parts(&b)))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn insert_single_cell() {
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        assert_eq!(shift_anchor("A5", &p), "A8");
        assert_eq!(shift_anchor("A4", &p), "A4");
    }

    #[test]
    fn insert_range() {
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        assert_eq!(shift_anchor("A1:E10", &p), "A1:E13");
    }

    #[test]
    fn insert_dollar_anchor_shifts() {
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        assert_eq!(shift_anchor("$A$5", &p), "$A$8");
    }

    #[test]
    fn delete_tombstones_single_cell() {
        let p = ShiftPlan::delete(Axis::Row, 5, 3);
        assert_eq!(shift_anchor("A6", &p), "#REF!");
    }

    #[test]
    fn delete_clips_range() {
        // Rows 5-7 deleted from A4:A10 → surviving rows 4 and 8-10
        // → after shift A4 + A5:A7. The clip rule snaps the upper
        // endpoint to the surviving boundary (row 4), and the lower
        // endpoint shifts from row 10 by -3 to row 7.
        let p = ShiftPlan::delete(Axis::Row, 5, 3);
        let out = shift_anchor("A4:A10", &p);
        assert_eq!(out, "A4:A7");
    }

    #[test]
    fn delete_drops_fully_tombstoned() {
        let p = ShiftPlan::delete(Axis::Row, 5, 3);
        assert_eq!(shift_anchor("A5:A7", &p), "#REF!");
    }

    #[test]
    fn delete_below_band_shifts_only() {
        let p = ShiftPlan::delete(Axis::Row, 5, 3);
        assert_eq!(shift_anchor("A8:A12", &p), "A5:A9");
    }

    #[test]
    fn delete_above_band_unchanged() {
        let p = ShiftPlan::delete(Axis::Row, 5, 3);
        assert_eq!(shift_anchor("A1:A3", &p), "A1:A3");
    }

    #[test]
    fn sqref_drops_tombstoned_pieces() {
        let p = ShiftPlan::delete(Axis::Row, 5, 3);
        let out = shift_sqref("A6 B7 C10", &p);
        // A6 + B7 are inside band → drop. C10 → C7.
        assert_eq!(out, "C7");
    }

    #[test]
    fn sqref_multi_range() {
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        let out = shift_sqref("A1:B3 D5:D10", &p);
        assert_eq!(out, "A1:B3 D8:D13");
    }

    #[test]
    fn col_shift_anchor() {
        let p = ShiftPlan::insert(Axis::Col, 2, 1);
        assert_eq!(shift_anchor("B5", &p), "C5");
        assert_eq!(shift_anchor("A5", &p), "A5");
    }

    #[test]
    fn col_only_anchor_unchanged_on_row_shift() {
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        // Whole-column reference like in some <ref> contexts — pass
        // through unchanged on a row shift.
        assert_eq!(shift_anchor("A:A", &p), "A:A");
    }

    #[test]
    fn row_only_anchor_unchanged_on_col_shift() {
        let p = ShiftPlan::insert(Axis::Col, 2, 1);
        assert_eq!(shift_anchor("5:5", &p), "5:5");
    }

    #[test]
    fn empty_string_passthrough() {
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        assert_eq!(shift_anchor("", &p), "");
        assert_eq!(shift_sqref("", &p), "");
    }

    #[test]
    fn noop_unchanged() {
        let p = ShiftPlan {
            axis: Axis::Row,
            idx: 1,
            n: 0,
        };
        assert_eq!(shift_anchor("A1:E10", &p), "A1:E10");
    }

    #[test]
    fn shift_overflow_tombstones() {
        let p = ShiftPlan::insert(Axis::Row, 1, MAX_ROW);
        // We expect the cell to overflow → #REF!.
        assert_eq!(shift_anchor("A2", &p), "#REF!");
    }
}
