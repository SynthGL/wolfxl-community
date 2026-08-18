//! Integration coverage for `wolfxl_reader::external_links` (RFC-071 / G18).
//!
//! The unit tests inside the module exercise the happy paths and the
//! malformed-XML rejection. These integration tests pin down a few extra
//! shapes that the Python load path actually relies on:
//!
//! * Multiple `<sheetData>` blocks under `<sheetDataSet>`.
//! * `cell` without an `r` attribute is silently skipped (not a panic).
//! * The "no rels file" case the Python loader uses to detect a part with
//!   no externalLinkPath rel — surfaces as `target == None`.
//! * `xml:space="preserve"` on `<v>` carries whitespace verbatim.

use wolfxl_reader::external_links::{parse_part, parse_rels};
use wolfxl_rels::TargetMode;

#[test]
fn part_with_multiple_sheet_data_blocks() {
    let xml = br#"<externalLink xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <externalBook r:id="rId1">
    <sheetNames>
      <sheetName val="One"/>
      <sheetName val="Two"/>
    </sheetNames>
    <sheetDataSet>
      <sheetData sheetId="0"><row r="1"><cell r="A1"><v>1</v></cell></row></sheetData>
      <sheetData sheetId="1"><row r="1"><cell r="B2"><v>two</v></cell></row></sheetData>
    </sheetDataSet>
  </externalBook>
</externalLink>"#;
    let p = parse_part(xml).unwrap();
    assert_eq!(p.sheet_names, vec!["One", "Two"]);
    assert_eq!(p.cached_data.len(), 2);
    assert_eq!(p.cached_data[0].0, "0");
    assert_eq!(p.cached_data[0].1[0].r#ref, "A1");
    assert_eq!(p.cached_data[0].1[0].value, "1");
    assert_eq!(p.cached_data[1].0, "1");
    assert_eq!(p.cached_data[1].1[0].r#ref, "B2");
    assert_eq!(p.cached_data[1].1[0].value, "two");
}

#[test]
fn part_drops_cells_without_ref() {
    // A `<cell>` without `r="..."` is malformed-but-real; we drop it
    // rather than panicking. The next legal cell still appears.
    let xml = br#"<externalLink xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <externalBook r:id="rId1">
    <sheetNames><sheetName val="S"/></sheetNames>
    <sheetDataSet>
      <sheetData sheetId="0">
        <row r="1">
          <cell><v>orphan</v></cell>
          <cell r="A1"><v>kept</v></cell>
        </row>
      </sheetData>
    </sheetDataSet>
  </externalBook>
</externalLink>"#;
    let p = parse_part(xml).unwrap();
    assert_eq!(p.cached_data.len(), 1);
    let cells = &p.cached_data[0].1;
    assert_eq!(cells.len(), 1);
    assert_eq!(cells[0].r#ref, "A1");
    assert_eq!(cells[0].value, "kept");
}

#[test]
fn part_preserves_whitespace_in_v() {
    let xml = br#"<externalLink xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><externalBook r:id="rId1"><sheetNames/><sheetDataSet><sheetData sheetId="0"><row r="1"><cell r="A1"><v xml:space="preserve">  spaced  </v></cell></row></sheetData></sheetDataSet></externalBook></externalLink>"#;
    let p = parse_part(xml).unwrap();
    assert_eq!(p.cached_data[0].1[0].value, "  spaced  ");
}

#[test]
fn rels_external_link_path_with_relative_target() {
    // Excel emits relative paths for sibling files; Open packaging
    // does NOT URL-decode the target so we keep it verbatim.
    let xml =
        br#"<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId42"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath"
    Target="../some%20folder/data.xlsx" TargetMode="External"/>
</Relationships>"#;
    let r = parse_rels(xml).unwrap();
    assert_eq!(r.target.as_deref(), Some("../some%20folder/data.xlsx"));
    assert_eq!(r.target_mode, Some(TargetMode::External));
    assert_eq!(r.rid.as_deref(), Some("rId42"));
}

#[test]
fn rels_accepts_excel_xl_path_missing_external_link_path() {
    // Current Microsoft Excel can emit this relationship type when the linked
    // workbook path is unavailable at save time. It still carries the workbook
    // target and should surface as a normal external file link to callers.
    let xml =
        br#"<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.microsoft.com/office/2006/relationships/xlExternalLinkPath/xlPathMissing"
    Target="wolfxl_excel_link_source.xlsx" TargetMode="External"/>
</Relationships>"#;
    let r = parse_rels(xml).unwrap();
    assert_eq!(r.target.as_deref(), Some("wolfxl_excel_link_source.xlsx"));
    assert_eq!(r.target_mode, Some(TargetMode::External));
    assert_eq!(r.rid.as_deref(), Some("rId1"));
}

#[test]
fn rels_only_first_external_link_path_wins() {
    let xml =
        br#"<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath"
    Target="first.xlsx" TargetMode="External"/>
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath"
    Target="second.xlsx" TargetMode="External"/>
</Relationships>"#;
    let r = parse_rels(xml).unwrap();
    assert_eq!(r.target.as_deref(), Some("first.xlsx"));
    assert_eq!(r.rid.as_deref(), Some("rId1"));
}

#[test]
fn rels_ignores_non_external_link_path_rels() {
    let xml =
        br#"<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
    Target="https://example.com" TargetMode="External"/>
</Relationships>"#;
    let r = parse_rels(xml).unwrap();
    assert!(r.target.is_none());
    assert!(r.rid.is_none());
}
