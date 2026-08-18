//! End-to-end and direct tests for the `xl/styles.xml` cellXfs walker.
//!
//! **Why this file exists.** calamine-styles' `Style::get_number_format()`
//! is the fast path for number-format resolution, but it returns `None` on
//! workbook shapes the walker has to cover - notably openpyxl-generated
//! parts where the author-side style emission leaves calamine unable to
//! associate a `<c s="N">` reference back to a `<numFmt>`. Before the
//! walker, those cells got reported as `number_format = None` and
//! `classify_format` fell back to `General`, defeating `peek`'s whole
//! number-format-aware rendering pitch.
//!
//! The `tier1_01_cell_values.xlsx` fixture is an Excel-authored workbook
//! with custom `numFmt` entries (ids 164+165) wired through two cellXfs
//! entries and referenced via `s="3"` / `s="4"` in the worksheet XML.
//! Asserting that a date/datetime format is resolvable by *some* path
//! (calamine fast-path OR walker fallback) is the real bar: the walker
//! is a safety net, and on any given workbook one path may cover it.
//!
//! Direct unit tests on `parse_cellxfs` + `parse_num_fmts` + the
//! `WorkbookStyles` resolution chain are in `src/styles.rs` and
//! `src/worksheet_xml.rs`. This file holds the integration-shape tests.

use std::path::PathBuf;

use wolfxl_core::format::classify_format;
use wolfxl_core::{FormatCategory, Workbook};

fn fixture_path(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join(name)
}

#[test]
fn workbook_resolves_date_formats_on_styled_fixture() {
    let path = fixture_path("tier1_01_cell_values.xlsx");
    assert!(path.exists(), "fixture missing at {}", path.display());

    let mut wb = Workbook::open(&path).expect("open tier1_01_cell_values.xlsx");
    let first = wb.sheet_names()[0].clone();
    let sheet = wb.sheet(&first).expect("load first sheet");

    // Every non-empty format the combined calamine-fast-path + walker
    // fallback surfaced. The fixture has two custom numFmts (dates);
    // they must come through one path or the other.
    let formats: Vec<String> = sheet
        .rows()
        .iter()
        .flat_map(|row| row.iter())
        .filter_map(|c| c.number_format.clone())
        .collect();

    assert!(
        !formats.is_empty(),
        "no number formats resolved on a workbook that has custom numFmts - both calamine path and walker missed"
    );

    let categories: Vec<FormatCategory> = formats.iter().map(|f| classify_format(f)).collect();

    // The fixture has one Date cell (yyyy-mm-dd at numFmtId 164) and one
    // DateTime cell (yyyy-mm-dd hh:mm:ss at 165). Either may pop up in
    // the stream depending on which path resolves it - we just need at
    // least one date-shaped classification.
    let has_date_like = categories
        .iter()
        .any(|c| matches!(c, FormatCategory::Date | FormatCategory::DateTime));
    assert!(
        has_date_like,
        "expected a Date or DateTime classification, saw {formats:?}"
    );

    for fmt in &formats {
        let trimmed = fmt.trim();
        assert!(!trimmed.is_empty(), "resolved format was empty");
        assert!(
            !trimmed.eq_ignore_ascii_case("General"),
            "resolved format was no-op 'General'"
        );
    }
}

#[test]
fn workbook_aligns_sparse_style_range_to_value_range() {
    let path = fixture_path("formatted-values.xlsx");
    assert!(path.exists(), "fixture missing at {}", path.display());

    let mut wb = Workbook::open(&path).expect("open formatted-values.xlsx");
    let sheet = wb.sheet("Formats").expect("load Formats sheet");
    let first_data = &sheet.rows()[1];

    assert_eq!(
        first_data[0].number_format.as_deref(),
        None,
        "text column should not inherit the next column's currency format"
    );
    assert_eq!(first_data[1].number_format.as_deref(), Some("$#,##0.00"));
    assert_eq!(first_data[2].number_format.as_deref(), Some("0.0%"));
    assert_eq!(first_data[3].number_format.as_deref(), Some("yyyy-mm-dd"));
}

#[test]
fn walker_direct_resolution_from_synthetic_xml() {
    // Minimal OOXML that exercises the walker end-to-end without a real
    // zip: openpyxl-style numFmts (id 164+165), cellXfs that reference
    // them, and a worksheet part where `<c r="B12" s="3">` / `s="4"`
    // carry those styles. The walker APIs are public so we can drive
    // them directly; the integration through `Workbook::open` is
    // already covered above.
    use std::collections::HashMap;
    use wolfxl_core::styles::{parse_cellxfs, parse_num_fmts, resolve_num_fmt};

    let styles_xml = r#"<?xml version="1.0"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="2">
    <numFmt numFmtId="164" formatCode="yyyy\-mm\-dd"/>
    <numFmt numFmtId="165" formatCode="yyyy\-mm\-dd\ hh:mm:ss"/>
  </numFmts>
  <cellXfs count="5">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0"/>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="0"/>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="0"/>
  </cellXfs>
</styleSheet>"#;

    let xfs = parse_cellxfs(styles_xml);
    assert_eq!(xfs.len(), 5, "expected 5 cellXf entries, got {}", xfs.len());
    assert_eq!(xfs[3].num_fmt_id, 164);
    assert_eq!(xfs[4].num_fmt_id, 165);

    let num_fmts = parse_num_fmts(styles_xml).expect("parse numFmts");
    assert_eq!(
        num_fmts.get(&164).map(String::as_str),
        Some(r"yyyy\-mm\-dd")
    );
    assert_eq!(
        num_fmts.get(&165).map(String::as_str),
        Some(r"yyyy\-mm\-dd\ hh:mm:ss")
    );

    // End-to-end resolution: styleId 3 -> numFmtId 164 -> custom code.
    let code_3 = resolve_num_fmt(xfs[3].num_fmt_id, &num_fmts).expect("resolve 164");
    assert_eq!(code_3, r"yyyy\-mm\-dd");
    // Backslash escapes are a literal convention in Excel format codes;
    // classify_format ignores them and still sees 'y' / 'm' / 'd'.
    assert_eq!(classify_format(code_3), FormatCategory::Date);

    let code_4 = resolve_num_fmt(xfs[4].num_fmt_id, &num_fmts).expect("resolve 165");
    assert_eq!(code_4, r"yyyy\-mm\-dd\ hh:mm:ss");
    assert_eq!(classify_format(code_4), FormatCategory::DateTime);

    // styleId 0 resolves to numFmtId 0 ("General") - must return None
    // or equivalently classify as General downstream. resolve_num_fmt
    // itself returns the built-in "General" code; the walker layer
    // filters that above.
    let general = resolve_num_fmt(xfs[0].num_fmt_id, &num_fmts);
    match general {
        None => {}
        Some(code) => assert!(
            code.eq_ignore_ascii_case("General") || code.is_empty(),
            "styleId 0 should resolve to General or None, got {code:?}"
        ),
    }

    // Silence unused-import warning when `HashMap` is only used
    // transitively via num_fmts.
    let _: &HashMap<u32, String> = &num_fmts;
}
