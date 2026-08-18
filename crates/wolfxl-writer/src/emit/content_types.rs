//! `[Content_Types].xml` emitter.
//!
//! This is the map of file-extension → MIME-type overrides that the
//! xlsx container needs. Every part inside the ZIP must be accounted
//! for here or Excel flags the file as corrupt.
//!
//! # Structure
//!
//! The file has two kinds of children under `<Types>`:
//!
//! - `<Default Extension="…" ContentType="…"/>` — matches every entry
//!   whose path ends in that extension (e.g. `rels`, `xml`, `vml`).
//! - `<Override PartName="/…" ContentType="…"/>` — matches a single
//!   specific part path.
//!
//! We emit defaults for the universal extensions (`rels`, `xml`, and
//! `vml` when any sheet has comments), then one `<Override>` per part
//! that needs a specific content type (workbook, styles, each sheet,
//! etc.). This matches what openpyxl and Excel itself produce.

use crate::model::workbook::Workbook;

// -- Content types -----------------------------------------------------------
const CT_WORKBOOK: &str =
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml";
const CT_STYLES: &str = "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml";
const CT_SHARED_STRINGS: &str =
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml";
const CT_WORKSHEET: &str =
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml";
const CT_COMMENTS: &str =
    "application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml";
const CT_THREADED_COMMENTS: &str = "application/vnd.ms-excel.threadedcomments+xml";
const CT_PERSON_LIST: &str = "application/vnd.ms-excel.person+xml";
const CT_TABLE: &str = "application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml";
const CT_VML: &str = "application/vnd.openxmlformats-officedocument.vmlDrawing";
const CT_DRAWING: &str = "application/vnd.openxmlformats-officedocument.drawing+xml";
const CT_CHART: &str = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml";
const CT_CORE_PROPS: &str = "application/vnd.openxmlformats-package.core-properties+xml";
const CT_APP_PROPS: &str = "application/vnd.openxmlformats-officedocument.extended-properties+xml";
const CT_RELATIONSHIPS: &str = "application/vnd.openxmlformats-package.relationships+xml";
const CT_XML_DEFAULT: &str = "application/xml";

/// Emit `[Content_Types].xml` as UTF-8 bytes.
pub fn emit(wb: &Workbook) -> Vec<u8> {
    let mut out = String::with_capacity(1024);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str("<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">");

    // Defaults — apply to every entry whose path ends with the given extension.
    out.push_str(&format!(
        "<Default Extension=\"rels\" ContentType=\"{CT_RELATIONSHIPS}\"/>"
    ));
    out.push_str(&format!(
        "<Default Extension=\"xml\" ContentType=\"{CT_XML_DEFAULT}\"/>"
    ));

    let any_comments = wb.sheets.iter().any(|s| !s.comments.is_empty());
    if any_comments {
        out.push_str(&format!(
            "<Default Extension=\"vml\" ContentType=\"{CT_VML}\"/>"
        ));
    }

    // Default Extension entries for any image extensions used across
    // the workbook. Excel only requires one per distinct extension.
    // We emit them in stable
    // (sheet-order, intra-sheet image-order, dedup) order so two
    // saves of the same workbook produce identical bytes.
    let mut seen_exts: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    for sheet in &wb.sheets {
        for img in &sheet.images {
            seen_exts.insert(img.ext.to_ascii_lowercase());
        }
    }
    for ext in &seen_exts {
        let ct = crate::emit::drawings::content_type_for_ext(ext);
        out.push_str(&format!(
            "<Default Extension=\"{ext}\" ContentType=\"{ct}\"/>"
        ));
    }

    // Workbook-level overrides.
    out.push_str(&format!(
        "<Override PartName=\"/xl/workbook.xml\" ContentType=\"{CT_WORKBOOK}\"/>"
    ));

    // Per-sheet overrides (1-based ordering, insertion order).
    for (idx, _sheet) in wb.sheets.iter().enumerate() {
        let n = idx + 1;
        out.push_str(&format!(
            "<Override PartName=\"/xl/worksheets/sheet{n}.xml\" ContentType=\"{CT_WORKSHEET}\"/>"
        ));
    }

    out.push_str(&format!(
        "<Override PartName=\"/xl/styles.xml\" ContentType=\"{CT_STYLES}\"/>"
    ));
    out.push_str(&format!(
        "<Override PartName=\"/xl/sharedStrings.xml\" ContentType=\"{CT_SHARED_STRINGS}\"/>"
    ));

    // Per-sheet comments.xml overrides (N = sheet index + 1 when that
    // sheet has comments — numbering tracks the sheet, not a running
    // comments counter).
    for (idx, sheet) in wb.sheets.iter().enumerate() {
        if !sheet.comments.is_empty() {
            let n = idx + 1;
            out.push_str(&format!(
                "<Override PartName=\"/xl/comments/comments{n}.xml\" \
                 ContentType=\"{CT_COMMENTS}\"/>"
            ));
        }
    }

    // Per-sheet threadedCommentsN.xml overrides (RFC-068 / G08). Numbering
    // matches the sheet index for parity with `commentsN.xml`.
    for (idx, sheet) in wb.sheets.iter().enumerate() {
        if !sheet.threaded_comments.is_empty() {
            let n = idx + 1;
            out.push_str(&format!(
                "<Override PartName=\"/xl/threadedComments/threadedComments{n}.xml\" \
                 ContentType=\"{CT_THREADED_COMMENTS}\"/>"
            ));
        }
    }

    // Workbook-scoped personList.xml override (singular filename — there is
    // exactly one personList per workbook, regardless of how many sheets
    // carry threaded comments).
    if !wb.persons.is_empty() {
        out.push_str(&format!(
            "<Override PartName=\"/xl/persons/personList.xml\" \
             ContentType=\"{CT_PERSON_LIST}\"/>"
        ));
    }

    // Per-table overrides — tables are numbered globally (1..N) across
    // all sheets, matching openpyxl.
    let mut table_counter: usize = 0;
    for sheet in &wb.sheets {
        for _table in &sheet.tables {
            table_counter += 1;
            out.push_str(&format!(
                "<Override PartName=\"/xl/tables/table{table_counter}.xml\" \
                 ContentType=\"{CT_TABLE}\"/>"
            ));
        }
    }

    // Per-drawing overrides. Drawings are numbered globally (1..N) across
    // all sheets, one drawing per sheet that has at least one image OR chart.
    let mut drawing_counter: usize = 0;
    for sheet in &wb.sheets {
        if !sheet.images.is_empty() || !sheet.charts.is_empty() {
            drawing_counter += 1;
            out.push_str(&format!(
                "<Override PartName=\"/xl/drawings/drawing{drawing_counter}.xml\" \
                 ContentType=\"{CT_DRAWING}\"/>"
            ));
        }
    }

    // Per-chart overrides. Charts are numbered globally (1..N) across all
    // sheets in sheet+intra-sheet order. Each chart becomes one
    // xl/charts/chartN.xml part.
    let mut chart_counter: usize = 0;
    for sheet in &wb.sheets {
        for _chart in &sheet.charts {
            chart_counter += 1;
            out.push_str(&format!(
                "<Override PartName=\"/xl/charts/chart{chart_counter}.xml\" \
                 ContentType=\"{CT_CHART}\"/>"
            ));
        }
    }

    // calcChain.xml override, only when the workbook has at least one formula
    // (matches the emit-side gate in `emit_xlsx`).
    if crate::emit::calc_chain_xml::has_any_formula(wb) {
        out.push_str(&format!(
            "<Override PartName=\"/xl/calcChain.xml\" ContentType=\"{}\"/>",
            crate::emit::calc_chain_xml::CT_CALC_CHAIN
        ));
    }

    out.push_str(&format!(
        "<Override PartName=\"/docProps/core.xml\" ContentType=\"{CT_CORE_PROPS}\"/>"
    ));
    out.push_str(&format!(
        "<Override PartName=\"/docProps/app.xml\" ContentType=\"{CT_APP_PROPS}\"/>"
    ));

    out.push_str("</Types>");
    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::comment::Comment;
    use crate::model::table::{Table, TableColumn};
    use crate::model::worksheet::Worksheet;
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn wb_with_sheets(n: usize) -> Workbook {
        let mut wb = Workbook::new();
        for i in 1..=n {
            wb.add_sheet(Worksheet::new(format!("Sheet{i}")));
        }
        wb
    }

    #[test]
    fn well_formed_xml_for_simple_workbook() {
        let wb = wb_with_sheets(2);
        let bytes = emit(&wb);
        let text = std::str::from_utf8(&bytes).expect("utf8");
        let mut reader = Reader::from_str(text);
        let mut buf = Vec::new();
        let mut events = 0;
        loop {
            match reader.read_event_into(&mut buf) {
                Ok(Event::Eof) => break,
                Ok(_) => events += 1,
                Err(e) => panic!("parse error: {e}"),
            }
            buf.clear();
        }
        assert!(events > 0, "expected some XML events");
    }

    #[test]
    fn override_per_sheet() {
        let wb = wb_with_sheets(3);
        let bytes = emit(&wb);
        let text = std::str::from_utf8(&bytes).expect("utf8");
        assert!(text.contains("/xl/worksheets/sheet1.xml"));
        assert!(text.contains("/xl/worksheets/sheet2.xml"));
        assert!(text.contains("/xl/worksheets/sheet3.xml"));
        assert!(!text.contains("/xl/worksheets/sheet4.xml"));
    }

    #[test]
    fn required_top_level_overrides_present() {
        let wb = wb_with_sheets(1);
        let text = String::from_utf8(emit(&wb)).unwrap();
        for must in [
            "/xl/workbook.xml",
            "/xl/styles.xml",
            "/xl/sharedStrings.xml",
            "/docProps/core.xml",
            "/docProps/app.xml",
            "Extension=\"rels\"",
            "Extension=\"xml\"",
        ] {
            assert!(text.contains(must), "missing expected piece: {must}");
        }
    }

    #[test]
    fn vml_default_appears_only_when_comments_exist() {
        let wb = wb_with_sheets(1);
        let text = String::from_utf8(emit(&wb)).unwrap();
        assert!(!text.contains("Extension=\"vml\""));

        let mut wb = wb_with_sheets(1);
        wb.sheets[0].comments.insert(
            "A1".to_string(),
            Comment {
                text: "hi".to_string(),
                author_id: 0,
                width_pt: None,
                height_pt: None,
                visible: false,
            },
        );
        let text = String::from_utf8(emit(&wb)).unwrap();
        assert!(text.contains("Extension=\"vml\""));
        assert!(text.contains("/xl/comments/comments1.xml"));
    }

    #[test]
    fn comments_override_only_for_sheets_with_comments() {
        let mut wb = wb_with_sheets(3);
        // Only sheet 2 (index 1) has a comment.
        wb.sheets[1].comments.insert(
            "B2".to_string(),
            Comment {
                text: "note".to_string(),
                author_id: 0,
                width_pt: None,
                height_pt: None,
                visible: false,
            },
        );
        let text = String::from_utf8(emit(&wb)).unwrap();
        assert!(text.contains("/xl/comments/comments2.xml"));
        assert!(!text.contains("/xl/comments/comments1.xml"));
        assert!(!text.contains("/xl/comments/comments3.xml"));
    }

    #[test]
    fn tables_override_numbered_globally() {
        let mut wb = wb_with_sheets(2);
        let table = Table {
            name: "t".into(),
            display_name: None,
            range: "A1:B2".into(),
            columns: vec![
                TableColumn {
                    name: "a".into(),
                    totals_function: None,
                    totals_label: None,
                },
                TableColumn {
                    name: "b".into(),
                    totals_function: None,
                    totals_label: None,
                },
            ],
            header_row: true,
            totals_row: false,
            style: None,
            autofilter: false,
        };
        wb.sheets[0].tables.push(table.clone());
        wb.sheets[1].tables.push(table.clone());
        wb.sheets[1].tables.push(table);
        let text = String::from_utf8(emit(&wb)).unwrap();
        assert!(text.contains("/xl/tables/table1.xml"));
        assert!(text.contains("/xl/tables/table2.xml"));
        assert!(text.contains("/xl/tables/table3.xml"));
        assert!(!text.contains("/xl/tables/table4.xml"));
    }
}
