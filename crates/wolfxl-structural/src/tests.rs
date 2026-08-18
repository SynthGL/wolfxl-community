//! Integration tests across `axis` + `shift_anchors` + `shift_cells` +
//! `shift_formulas` + `shift_workbook`.

use crate::axis::{Axis, ShiftPlan};
use crate::{shift_anchor, shift_formula, shift_sheet_cells, shift_sqref};

#[test]
fn end_to_end_insert_3_at_row_5() {
    let xml = r#"<sheetData><row r="5"><c r="A5"><f>SUM(A1:A4)</f><v>10</v></c></row><row r="10"><c r="B10"><v>2</v></c></row></sheetData>"#;
    let p = ShiftPlan::insert(Axis::Row, 5, 3);
    let out = String::from_utf8(shift_sheet_cells(xml.as_bytes(), &p)).unwrap();
    assert!(out.contains(r#"<row r="8">"#));
    assert!(out.contains(r#"<c r="A8">"#));
    assert!(out.contains(r#"<row r="13">"#));
    assert!(out.contains(r#"<c r="B13">"#));
    // Formula refs above the insert band stay; here SUM(A1:A4) is fine.
    assert!(out.contains("<f>SUM(A1:A4)</f>"));
}

#[test]
fn end_to_end_delete_3_at_row_5() {
    let xml = r#"<sheetData><row r="4"><c r="A4"><v>1</v></c></row><row r="5"><c r="A5"><v>x</v></c></row><row r="6"><c r="A6"><v>y</v></c></row><row r="8"><c r="A8"><v>2</v></c></row></sheetData>"#;
    let p = ShiftPlan::delete(Axis::Row, 5, 3);
    let out = String::from_utf8(shift_sheet_cells(xml.as_bytes(), &p)).unwrap();
    // Row 4 stays.
    assert!(out.contains(r#"<row r="4">"#));
    // Original band-row content is gone.
    assert!(!out.contains("<v>x</v>"));
    assert!(!out.contains("<v>y</v>"));
    // Row 8 → 5 with cell value 2.
    assert!(out.contains(r#"<row r="5"><c r="A5">"#));
    assert!(out.contains("<v>2</v>"));
}

#[test]
fn anchor_then_formula_consistent_for_same_plan() {
    let p = ShiftPlan::insert(Axis::Row, 5, 3);
    assert_eq!(shift_anchor("A5", &p), "A8");
    assert_eq!(shift_formula("=A5", &p), "=A8");
}

#[test]
fn sqref_and_formula_handle_multi_range_consistently() {
    let p = ShiftPlan::insert(Axis::Row, 5, 3);
    assert_eq!(shift_sqref("A1:B3 D5:D10", &p), "A1:B3 D8:D13");
    // Formula doesn't have multi-range syntax (formulas use unions
    // via `(A1:B3,D5:D10)` parentheses); each range translates the
    // same way.
    assert!(shift_formula("=SUM(D5:D10)", &p).contains("D8:D13"));
}
