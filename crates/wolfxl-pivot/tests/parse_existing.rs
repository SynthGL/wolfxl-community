//! G17 / RFC-070 §7.3 — integration tests for the pivot mutation
//! parser. These complement the inline unit tests in `src/mutate.rs`
//! by hitting representative XML shapes the patcher can actually meet
//! on disk: foreign-tool variants (LibreOffice, Excel), namespace
//! variations, the `extLst` round-trip guarantee, and the
//! malformed-XML rejection path.

use wolfxl_pivot::mutate::{
    column_count_of_range, parse_pivot_cache_source, parse_pivot_table_meta, rewrite_cache_source,
};

#[test]
fn parses_canonical_wolfxl_emit() {
    // Shape emitted by `crates/wolfxl-pivot::emit::cache.rs` — the
    // baseline modify-mode round-trip target.
    let xml = br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="rId1" refreshOnLoad="0" refreshedBy="wolfxl" createdVersion="6" refreshedVersion="6" minRefreshableVersion="3" recordCount="2"><cacheSource type="worksheet"><worksheetSource ref="A1:B3" sheet="Sheet"/></cacheSource><cacheFields count="2"><cacheField name="region" numFmtId="0"><sharedItems count="2"><s v="east"/><s v="west"/></sharedItems></cacheField><cacheField name="amount" numFmtId="0"><sharedItems containsString="0" containsNumber="1" minValue="10" maxValue="20"/></cacheField></cacheFields></pivotCacheDefinition>"#;
    let m = parse_pivot_cache_source(xml).expect("parses");
    assert_eq!(m.range, "A1:B3");
    assert_eq!(m.sheet, "Sheet");
    assert_eq!(m.field_count, 2);
}

#[test]
fn parses_libreoffice_style_emit_with_extlst() {
    // LibreOffice serialises pivots with an `<extLst>` block carrying
    // pivot-table-style extensions. Our parser must walk past it
    // cleanly and the rewriter must preserve those bytes verbatim.
    let xml = br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="rId1" refreshOnLoad="1" recordCount="3">
  <cacheSource type="worksheet"><worksheetSource ref="A1:C4" sheet="Data"/></cacheSource>
  <cacheFields count="3">
    <cacheField name="A"/>
    <cacheField name="B"/>
    <cacheField name="C"/>
  </cacheFields>
  <extLst>
    <ext uri="{725AE2AE-9491-48be-B2B4-4EB974FC3084}" xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"><x14:pivotCacheDefinition/></ext>
  </extLst>
</pivotCacheDefinition>"#;
    let m = parse_pivot_cache_source(xml).expect("parses");
    assert_eq!(m.range, "A1:C4");
    assert_eq!(m.field_count, 3);

    let out = rewrite_cache_source(xml, "A1:C10", Some("Data"), false).expect("rewrite");
    let s = std::str::from_utf8(&out).unwrap();
    assert!(s.contains(r#"ref="A1:C10""#));
    assert!(s.contains(r#"<x14:pivotCacheDefinition/>"#));
    assert!(s.contains("</extLst>"));
}

#[test]
fn pivot_table_meta_roundtrip() {
    let xml = br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" name="MyPivot" cacheId="3" indent="0" outline="1">
  <location ref="C5:E25" firstHeaderRow="1" firstDataRow="2" firstDataCol="1" rowPageCount="0" colPageCount="0"/>
  <pivotFields count="2">
    <pivotField axis="axisRow" showAll="0"/>
    <pivotField dataField="1" showAll="0"/>
  </pivotFields>
</pivotTableDefinition>"#;
    let m = parse_pivot_table_meta(xml).expect("parses");
    assert_eq!(m.name, "MyPivot");
    assert_eq!(m.location_ref, "C5:E25");
    assert_eq!(m.cache_id, 3);
}

#[test]
fn rewrite_preserves_byte_layout_of_unrelated_blocks() {
    // The rewriter must touch only the worksheetSource attributes;
    // every other byte (whitespace, attribute order, comments) must
    // round-trip identically.
    let xml = br#"<?xml version="1.0" encoding="UTF-8"?>
<!-- some comment -->
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" recordCount="2">
  <cacheSource type="worksheet">
    <worksheetSource ref="A1:B3" sheet="Sheet"/>
  </cacheSource>
  <cacheFields count="2"><cacheField name="x"/><cacheField name="y"/></cacheFields>
</pivotCacheDefinition>"#;
    let out = rewrite_cache_source(xml, "A1:B5", Some("Sheet"), false).expect("rewrite");
    let s = std::str::from_utf8(&out).unwrap();
    assert!(s.contains("<!-- some comment -->"));
    assert!(s.contains(r#"ref="A1:B5""#));
    // Whitespace between elements must survive.
    assert!(s.contains("\n  <cacheSource"));
    assert!(s.contains("\n    <worksheetSource"));
}

#[test]
fn rewrite_handles_missing_sheet_attr_by_appending() {
    // openpyxl-authored caches may omit `sheet=` when the cache and
    // owner sheet coincide. Rewriter appends one if a new sheet is
    // supplied.
    let xml = br#"<?xml version="1.0"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cacheSource type="worksheet"><worksheetSource ref="A1:B3"/></cacheSource><cacheFields count="2"/></pivotCacheDefinition>"#;
    let out = rewrite_cache_source(xml, "A1:B5", Some("Sheet1"), false).expect("rewrite");
    let s = std::str::from_utf8(&out).unwrap();
    assert!(s.contains(r#"ref="A1:B5""#));
    assert!(s.contains(r#"sheet="Sheet1""#));
}

#[test]
fn rewrite_with_force_refresh_flips_flag() {
    let xml = br#"<?xml version="1.0"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" refreshOnLoad="0" recordCount="2"><cacheSource type="worksheet"><worksheetSource ref="A1:B3" sheet="Sheet1"/></cacheSource><cacheFields count="2"/></pivotCacheDefinition>"#;
    let out = rewrite_cache_source(xml, "A1:C5", Some("Sheet1"), true).expect("rewrite");
    let s = std::str::from_utf8(&out).unwrap();
    assert!(s.contains(r#"refreshOnLoad="1""#));
    assert_eq!(s.matches("refreshOnLoad=").count(), 1);
}

#[test]
fn rejects_input_missing_worksheet_source() {
    let xml = br#"<?xml version="1.0"?>
<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cacheSource type="external"/><cacheFields count="0"/></pivotCacheDefinition>"#;
    assert!(parse_pivot_cache_source(xml).is_err());
}

#[test]
fn column_count_handles_dollar_signs_and_singletons() {
    assert_eq!(column_count_of_range("A1"), Some(1));
    assert_eq!(column_count_of_range("$A$1"), Some(1));
    assert_eq!(column_count_of_range("A1:Z1"), Some(26));
    assert_eq!(column_count_of_range("A1:AA1"), Some(27));
}
