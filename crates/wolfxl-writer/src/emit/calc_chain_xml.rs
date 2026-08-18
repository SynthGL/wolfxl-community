//! `xl/calcChain.xml` emitter.
//!
//! Walks the workbook's sheets in tab order and emits a `<c r="…" i="…"/>`
//! entry for every cell holding a `WriteCellValue::Formula`. The result is
//! a perf hint that lets Excel skip its first-open recompute pass; it
//! never affects correctness.
//!
//! Returns `None` when the workbook has zero formulas — the caller should
//! omit the `xl/calcChain.xml` part entirely (and leave the
//! `[Content_Types].xml` Override + workbook rel out as well).

use crate::model::cell::WriteCellValue;
use crate::model::workbook::Workbook;

/// Content type for `xl/calcChain.xml`.
pub const CT_CALC_CHAIN: &str =
    "application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml";

/// Relationship type for the workbook → calcChain edge.
pub const REL_CALC_CHAIN: &str =
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain";

/// True when at least one cell in any sheet holds a formula. Cheap
/// short-circuit used by the caller to decide whether to emit the
/// part + register the Override + add the workbook rel.
pub fn has_any_formula(wb: &Workbook) -> bool {
    for sheet in &wb.sheets {
        for row in sheet.rows.values() {
            for cell in row.cells.values() {
                if matches!(cell.value, WriteCellValue::Formula { .. }) {
                    return true;
                }
            }
        }
    }
    false
}

/// Emit `xl/calcChain.xml` bytes. Returns `None` when there are no
/// formulas (caller should omit the part).
pub fn emit(wb: &Workbook) -> Option<Vec<u8>> {
    let mut out = String::new();
    let mut wrote_any = false;

    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n");
    out.push_str("<calcChain xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">");
    for (sheet_idx, sheet) in wb.sheets.iter().enumerate() {
        let i = (sheet_idx as u32) + 1;
        // BTreeMap iteration is row-then-column ascending — matches
        // the natural calcChain order.
        for (&row, row_data) in sheet.rows.iter() {
            for (&col, cell) in row_data.cells.iter() {
                if let WriteCellValue::Formula { .. } = cell.value {
                    let cell_ref = crate::refs::format_a1(row, col);
                    out.push_str(&format!("<c r=\"{}\" i=\"{}\"/>", cell_ref, i));
                    wrote_any = true;
                }
            }
        }
    }
    out.push_str("</calcChain>");
    if !wrote_any {
        return None;
    }
    Some(out.into_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::cell::{FormulaResult, WriteCellValue};
    use crate::model::worksheet::Worksheet;

    #[test]
    fn no_formulas_returns_none() {
        let mut wb = Workbook::new();
        let mut s = Worksheet::new("S");
        s.write_cell(1, 1, WriteCellValue::Number(1.0), None);
        wb.add_sheet(s);
        assert!(emit(&wb).is_none());
        assert!(!has_any_formula(&wb));
    }

    #[test]
    fn one_formula_round_trips() {
        let mut wb = Workbook::new();
        let mut s = Worksheet::new("S");
        s.write_cell(
            1,
            2,
            WriteCellValue::Formula {
                expr: "1+1".into(),
                result: Some(FormulaResult::Number(2.0)),
            },
            None,
        );
        wb.add_sheet(s);
        assert!(has_any_formula(&wb));
        let bytes = emit(&wb).expect("non-empty");
        let s = String::from_utf8(bytes).unwrap();
        assert!(s.contains("<c r=\"B1\" i=\"1\"/>"), "{s}");
    }

    #[test]
    fn formulas_across_two_sheets_get_distinct_i() {
        let mut wb = Workbook::new();
        let mut s1 = Worksheet::new("S1");
        s1.write_cell(
            1,
            1,
            WriteCellValue::Formula {
                expr: "1".into(),
                result: None,
            },
            None,
        );
        let mut s2 = Worksheet::new("S2");
        s2.write_cell(
            5,
            3,
            WriteCellValue::Formula {
                expr: "S1!A1".into(),
                result: None,
            },
            None,
        );
        wb.add_sheet(s1);
        wb.add_sheet(s2);
        let bytes = emit(&wb).expect("non-empty");
        let s = String::from_utf8(bytes).unwrap();
        assert!(s.contains("<c r=\"A1\" i=\"1\"/>"), "{s}");
        assert!(s.contains("<c r=\"C5\" i=\"2\"/>"), "{s}");
    }

    #[test]
    fn cells_in_row_order_then_col_order() {
        let mut wb = Workbook::new();
        let mut s = Worksheet::new("S");
        // Add in non-monotonic order; emit must be sorted (BTreeMap
        // gives us this for free).
        s.write_cell(
            5,
            5,
            WriteCellValue::Formula {
                expr: "1".into(),
                result: None,
            },
            None,
        );
        s.write_cell(
            2,
            3,
            WriteCellValue::Formula {
                expr: "1".into(),
                result: None,
            },
            None,
        );
        s.write_cell(
            2,
            1,
            WriteCellValue::Formula {
                expr: "1".into(),
                result: None,
            },
            None,
        );
        wb.add_sheet(s);
        let bytes = emit(&wb).expect("non-empty");
        let s = String::from_utf8(bytes).unwrap();
        let i_a2 = s.find("<c r=\"A2\"").unwrap();
        let i_c2 = s.find("<c r=\"C2\"").unwrap();
        let i_e5 = s.find("<c r=\"E5\"").unwrap();
        assert!(
            i_a2 < i_c2 && i_c2 < i_e5,
            "got order: A2={i_a2}, C2={i_c2}, E5={i_e5}, full: {s}"
        );
    }
}
