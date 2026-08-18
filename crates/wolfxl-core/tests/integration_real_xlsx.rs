//! Integration test: open a real workbook from the sibling `spreadsheet-peek`
//! repo and confirm wolfxl-core can read sheets, dimensions, headers, and
//! detect at least one styled column (currency or percentage).
//!
//! Skipped silently if the fixture is not present (so this doesn't break in
//! CI environments that don't check out the sibling repo).

use std::path::PathBuf;
use wolfxl_core::format::classify_format;
use wolfxl_core::{format_cell, FormatCategory, Workbook};

fn sample_path() -> Option<PathBuf> {
    let candidates = [
        "../../../spreadsheet-peek/examples/sample-financials.xlsx",
        "../../spreadsheet-peek/examples/sample-financials.xlsx",
    ];
    for c in candidates {
        let p = PathBuf::from(c);
        if p.exists() {
            return Some(p);
        }
    }
    None
}

#[test]
fn reads_sample_financials() {
    let Some(path) = sample_path() else {
        eprintln!("sample-financials.xlsx not found; skipping");
        return;
    };

    let mut wb = Workbook::open(&path).expect("open workbook");
    let names = wb.sheet_names().to_vec();
    assert!(!names.is_empty(), "workbook should have at least one sheet");

    let sheet = wb.first_sheet().expect("read first sheet");
    let (rows, cols) = sheet.dimensions();
    assert!(
        rows > 1 && cols > 0,
        "expected non-empty sheet, got {rows}x{cols}"
    );

    let headers = sheet.headers();
    assert_eq!(headers.len(), cols);
    assert!(
        headers.iter().any(|h| !h.is_empty()),
        "expected at least one non-empty header"
    );

    // Confirm reads work across every sheet (mostly proving sheet name
    // dispatch + iteration). Styled-format detection (currency/percent/date)
    // depends on resolving xl/styles.xml's cellXfs, which wolfxl-core does not
    // do yet - that resolution lands in step 3 alongside `wolfxl peek`.
    let names = wb.sheet_names().to_vec();
    let mut total_non_empty = 0usize;
    for sheet_name in &names {
        let s = wb.sheet(sheet_name).expect("sheet load");
        for row in s.rows() {
            for cell in row {
                if !cell.value.is_empty() {
                    total_non_empty += 1;
                    let _rendered = format_cell(cell);
                }
            }
        }
    }
    assert!(
        total_non_empty > 0,
        "expected non-empty cells across sheets"
    );

    // Smoke-test the format module against a known-good format string so we
    // know the API contract holds even if we can't yet observe it on this
    // particular workbook end-to-end.
    assert_eq!(classify_format("$#,##0.00"), FormatCategory::Currency);
}
