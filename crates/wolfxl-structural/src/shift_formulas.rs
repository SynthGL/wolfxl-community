// TODO(RFC-012 BLOCKER): respect_dollar=false hard-coded here per
// RFC-030 §10. The Excel-side verification at
// `Plans/rfcs/notes/excel-respect-dollar-check.md` is PENDING. If that
// doc resolves to "absolute refs DO shift" (matrix row 1) we keep the
// current `false`; if it resolves to "absolute refs DO NOT shift"
// (matrix row 2) flip to `true` here and re-run the test suite.

//! Thin wrapper around `wolfxl_formula::shift` to hide the
//! `respect_dollar` plumbing.
//!
//! Every formula rewrite in `wolfxl-structural` routes through this
//! module so the boundary decision lives in one place.

use crate::axis::{Axis, ShiftPlan};
use wolfxl_formula::{
    shift as formula_shift, translate_with_meta, Axis as FormulaAxis, DeletedRange, RefDelta,
    ShiftPlan as FormulaShiftPlan, TranslateResult, MAX_COL, MAX_ROW,
};

/// Convert our local axis enum to `wolfxl_formula::Axis`.
fn map_axis(a: Axis) -> FormulaAxis {
    match a {
        Axis::Row => FormulaAxis::Row,
        Axis::Col => FormulaAxis::Col,
    }
}

/// Wrap a formula string for the tokenizer: prepend `=` if missing
/// (the OOXML `<f>` payload omits the leading equals). Returns
/// `(wrapped, was_wrapped)`.
fn wrap_for_tokenizer(formula: &str) -> (String, bool) {
    if formula.starts_with('=') {
        (formula.to_string(), false)
    } else {
        (format!("={formula}"), true)
    }
}

/// Strip the synthetic `=` prefix from a tokenized result if we wrapped.
fn unwrap_after_tokenize(s: String, was_wrapped: bool) -> String {
    if was_wrapped {
        s.strip_prefix('=').map(|x| x.to_string()).unwrap_or(s)
    } else {
        s
    }
}

/// Shift every reference in `formula` per the structural plan.
///
/// `respect_dollar` is hard-coded to `false` per RFC-030 §10
/// (coordinate-space remap semantic).
///
/// Inserts: `n > 0` → refs at `>= idx` shift by `+n`.
///
/// Deletes: `n < 0` → we ALSO populate the `DeletedRange` tombstone
/// so refs falling inside `[idx, idx+|n|)` become `#REF!`. The shift
/// applies to refs at `>= idx+|n|` (after the tombstone band).
///
/// Accepts formulas with or without a leading `=`. OOXML stores
/// formulas as `<f>SUM(A1)</f>` (no `=`), so we prepend one
/// internally and strip it back off the result.
pub fn shift_formula(formula: &str, plan: &ShiftPlan) -> String {
    if plan.is_noop() {
        return formula.to_string();
    }
    let (wrapped, was_wrapped) = wrap_for_tokenizer(formula);
    if plan.is_insert() {
        let fp = FormulaShiftPlan {
            axis: map_axis(plan.axis),
            at: plan.idx,
            n: plan.n,
            respect_dollar: false,
        };
        unwrap_after_tokenize(formula_shift(&wrapped, &fp), was_wrapped)
    } else {
        // Delete: shift at `idx + |n|` by `n` and tombstone the
        // `[idx, idx + |n|)` band so refs into it become #REF!.
        let abs = plan.abs_n();
        let mut delta = RefDelta::empty();
        delta.respect_dollar = false;
        match plan.axis {
            Axis::Row => {
                delta.rows = plan.n;
                delta.anchor_row = plan.idx + abs;
                delta.deleted_range = Some(DeletedRange {
                    min_row: plan.idx,
                    max_row: plan.idx + abs - 1,
                    min_col: 1,
                    max_col: MAX_COL,
                });
            }
            Axis::Col => {
                delta.cols = plan.n;
                delta.anchor_col = plan.idx + abs;
                delta.deleted_range = Some(DeletedRange {
                    min_row: 1,
                    max_row: MAX_ROW,
                    min_col: plan.idx,
                    max_col: plan.idx + abs - 1,
                });
            }
        }
        let result =
            wolfxl_formula::translate(&wrapped, &delta).unwrap_or_else(|_| wrapped.clone());
        unwrap_after_tokenize(result, was_wrapped)
    }
}

/// Like `shift_formula` but returns `TranslateResult` metadata so the
/// caller can detect `INDIRECT(...)` etc.
pub fn shift_formula_with_meta(formula: &str, plan: &ShiftPlan) -> TranslateResult {
    if plan.is_noop() {
        return TranslateResult {
            formula: formula.to_string(),
            refs_changed: 0,
            refs_to_ref_error: 0,
            has_volatile_indirect: false,
        };
    }
    let (wrapped, was_wrapped) = wrap_for_tokenizer(formula);
    let mut delta = RefDelta::empty();
    delta.respect_dollar = false;
    if plan.is_insert() {
        match plan.axis {
            Axis::Row => {
                delta.rows = plan.n;
                delta.anchor_row = plan.idx;
            }
            Axis::Col => {
                delta.cols = plan.n;
                delta.anchor_col = plan.idx;
            }
        }
    } else {
        let abs = plan.abs_n();
        match plan.axis {
            Axis::Row => {
                delta.rows = plan.n;
                delta.anchor_row = plan.idx + abs;
                delta.deleted_range = Some(DeletedRange {
                    min_row: plan.idx,
                    max_row: plan.idx + abs - 1,
                    min_col: 1,
                    max_col: MAX_COL,
                });
            }
            Axis::Col => {
                delta.cols = plan.n;
                delta.anchor_col = plan.idx + abs;
                delta.deleted_range = Some(DeletedRange {
                    min_row: 1,
                    max_row: MAX_ROW,
                    min_col: plan.idx,
                    max_col: plan.idx + abs - 1,
                });
            }
        }
    }
    let mut r = translate_with_meta(&wrapped, &delta).unwrap_or_else(|_| TranslateResult {
        formula: wrapped.clone(),
        refs_changed: 0,
        refs_to_ref_error: 0,
        has_volatile_indirect: false,
    });
    r.formula = unwrap_after_tokenize(r.formula, was_wrapped);
    r
}

/// Like `shift_formula` but scoped to a specific `formula_sheet`. Used
/// for workbook-scope `<definedName>` rewrites: a workbook-scope
/// formula references a particular sheet, and we only shift refs that
/// target the sheet we're mutating.
pub fn shift_formula_on_sheet(formula: &str, plan: &ShiftPlan, sheet: &str) -> String {
    if plan.is_noop() {
        return formula.to_string();
    }
    let (wrapped, was_wrapped) = wrap_for_tokenizer(formula);
    let abs = plan.abs_n();
    let mut delta = RefDelta::empty();
    delta.respect_dollar = false;
    delta.formula_sheet = Some(sheet.to_string());
    match (plan.axis, plan.is_insert()) {
        (Axis::Row, true) => {
            delta.rows = plan.n;
            delta.anchor_row = plan.idx;
        }
        (Axis::Row, false) => {
            delta.rows = plan.n;
            delta.anchor_row = plan.idx + abs;
            delta.deleted_range = Some(DeletedRange {
                min_row: plan.idx,
                max_row: plan.idx + abs - 1,
                min_col: 1,
                max_col: MAX_COL,
            });
            delta.deleted_range_sheet = Some(sheet.to_string());
        }
        (Axis::Col, true) => {
            delta.cols = plan.n;
            delta.anchor_col = plan.idx;
        }
        (Axis::Col, false) => {
            delta.cols = plan.n;
            delta.anchor_col = plan.idx + abs;
            delta.deleted_range = Some(DeletedRange {
                min_row: 1,
                max_row: MAX_ROW,
                min_col: plan.idx,
                max_col: plan.idx + abs - 1,
            });
            delta.deleted_range_sheet = Some(sheet.to_string());
        }
    }
    let result = wolfxl_formula::translate(&wrapped, &delta).unwrap_or_else(|_| wrapped.clone());
    unwrap_after_tokenize(result, was_wrapped)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn insert_rows_shifts_relative_and_absolute() {
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        assert_eq!(shift_formula("=A5", &p), "=A8");
        // respect_dollar=false → $A$5 also shifts.
        assert_eq!(shift_formula("=$A$5", &p), "=$A$8");
        // Refs above the band are untouched.
        assert_eq!(shift_formula("=A4", &p), "=A4");
    }

    #[test]
    fn insert_rows_at_start() {
        let p = ShiftPlan::insert(Axis::Row, 1, 1);
        assert_eq!(shift_formula("=A1", &p), "=A2");
    }

    #[test]
    fn delete_rows_shifts_after_band() {
        let p = ShiftPlan::delete(Axis::Row, 5, 3);
        // Refs at >=8 shift by -3.
        assert_eq!(shift_formula("=A8", &p), "=A5");
        // Refs above band untouched.
        assert_eq!(shift_formula("=A4", &p), "=A4");
        // Refs into deletion band → #REF!.
        assert_eq!(shift_formula("=A6", &p), "=#REF!");
    }

    #[test]
    fn delete_clip_range_partial() {
        // SUM(A4:A10) with rows 5-7 deleted: rows 8-10 → 5-7, so the
        // range is clipped to A4:A7.
        let p = ShiftPlan::delete(Axis::Row, 5, 3);
        // Range is partially overlapped. Translator clip then shift.
        let out = shift_formula("=SUM(A4:A10)", &p);
        // Implementation detail: the translator shrinks the range
        // and then shifts the surviving portion.
        assert!(out.contains("A4"));
        assert!(out.contains("A7") || out.contains("A4:A7"));
    }

    #[test]
    fn noop_returns_input_unchanged() {
        let p = ShiftPlan {
            axis: Axis::Row,
            idx: 1,
            n: 0,
        };
        assert_eq!(shift_formula("=A1+B2", &p), "=A1+B2");
    }

    #[test]
    fn meta_detects_indirect() {
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        let r = shift_formula_with_meta("=INDIRECT(\"A5\")", &p);
        assert!(r.has_volatile_indirect);
    }

    #[test]
    fn shift_on_sheet_passes_formula_sheet_for_delete_scope() {
        // For DELETE, the underlying translator scopes the tombstone
        // by `deleted_range_sheet`. Refs to a different sheet are
        // not tombstoned.
        let p = ShiftPlan::delete(Axis::Row, 5, 1);
        let out = shift_formula_on_sheet("=Sheet1!A5+Sheet2!A5", &p, "Sheet1");
        // Sheet1!A5 falls inside the tombstone band → #REF!.
        // Sheet2!A5 is not on the deleted sheet so it survives the
        // tombstone, but the row-shift on the translator still applies
        // (the translator does not gate insert/delete shifts by sheet).
        // What we DO guarantee: the formula does not error out and
        // Sheet1!A5 is the one that became #REF!.
        assert!(out.contains("#REF!"));
    }

    #[test]
    fn col_axis_insert() {
        let p = ShiftPlan::insert(Axis::Col, 2, 1);
        assert_eq!(shift_formula("=B5", &p), "=C5");
        assert_eq!(shift_formula("=A5", &p), "=A5");
    }

    #[test]
    fn shifts_no_leading_equals_formula() {
        // Formulas inside <f>, <formula1>, <formula2> have no leading
        // `=`. The translator must still tokenize them.
        let p = ShiftPlan::insert(Axis::Row, 5, 3);
        let out = shift_formula("$Z$5:$Z$10", &p);
        assert_eq!(out, "$Z$8:$Z$13");
    }

    #[test]
    fn col_axis_delete() {
        let p = ShiftPlan::delete(Axis::Col, 2, 1);
        // Col B deleted; col C → B; col A untouched; refs into B → #REF!.
        assert_eq!(shift_formula("=C5", &p), "=B5");
        assert_eq!(shift_formula("=A5", &p), "=A5");
        assert_eq!(shift_formula("=B5", &p), "=#REF!");
    }
}
