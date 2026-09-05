//! `.rels` emitter — root rels, workbook rels, and per-sheet rels.
//!
//! OOXML relationships are a layer of indirection between parts: every
//! `r:id="rId5"` attribute somewhere in the workbook is resolved through
//! a `.rels` file to the actual target part path.
//!
//! Three `.rels` files are emitted here:
//!
//! | File | Emitter | Purpose |
//! |------|---------|---------|
//! | `_rels/.rels` | [`emit_root`] | workbook + docProps/core + docProps/app |
//! | `xl/_rels/workbook.xml.rels` | [`emit_workbook`] | sheets + styles + SST |
//! | `xl/worksheets/_rels/sheet{N}.xml.rels` | [`emit_sheet`] | comments, vml, tables, external hyperlinks |
//!
//! The sheet-level rels file is only emitted when the sheet has at least
//! one of: comments, external hyperlinks, tables. Otherwise [`emit_sheet`]
//! returns an empty byte vector and the caller skips the file entirely.
//!
//! Relationship-type URIs and the `Relationship` model live in the shared
//! `wolfxl-rels` crate so the writer and the patcher stay in lock-step.

use super::sheet_rel_ids::SheetRelIdPlan;
use crate::model::workbook::Workbook;
use wolfxl_rels::{rt, RelId, RelsGraph, TargetMode};

/// `_rels/.rels` — top-level relationships (workbook, core props, app props).
pub fn emit_root(_wb: &Workbook) -> Vec<u8> {
    let mut g = RelsGraph::new();
    g.add_with_id(
        RelId("rId1".into()),
        rt::OFFICE_DOC,
        "xl/workbook.xml",
        TargetMode::Internal,
    );
    g.add_with_id(
        RelId("rId2".into()),
        rt::CORE_PROPS,
        "docProps/core.xml",
        TargetMode::Internal,
    );
    g.add_with_id(
        RelId("rId3".into()),
        rt::EXT_PROPS,
        "docProps/app.xml",
        TargetMode::Internal,
    );
    g.serialize()
}

/// `xl/_rels/workbook.xml.rels` — workbook → sheets, styles, shared strings,
/// (optional) calcChain.
pub fn emit_workbook(wb: &Workbook) -> Vec<u8> {
    emit_workbook_with_calc_chain(wb, crate::emit::calc_chain_xml::has_any_formula(wb))
}

pub(crate) fn emit_workbook_with_calc_chain(wb: &Workbook, has_calc_chain: bool) -> Vec<u8> {
    let mut g = RelsGraph::new();
    let n_sheets = wb.sheets.len();
    for idx in 0..n_sheets {
        let sheet_n = idx + 1;
        g.add_with_id(
            RelId(format!("rId{sheet_n}")),
            rt::WORKSHEET,
            &format!("worksheets/sheet{sheet_n}.xml"),
            TargetMode::Internal,
        );
    }
    let mut next_rid = n_sheets + 1;
    g.add_with_id(
        RelId(format!("rId{next_rid}")),
        rt::STYLES,
        "styles.xml",
        TargetMode::Internal,
    );
    next_rid += 1;
    g.add_with_id(
        RelId(format!("rId{next_rid}")),
        rt::SHARED_STRINGS,
        "sharedStrings.xml",
        TargetMode::Internal,
    );
    next_rid += 1;
    // calcChain rel, only when the workbook has at least one formula
    // (matches the gate in `emit_xlsx`).
    if has_calc_chain {
        g.add_with_id(
            RelId(format!("rId{next_rid}")),
            crate::emit::calc_chain_xml::REL_CALC_CHAIN,
            "calcChain.xml",
            TargetMode::Internal,
        );
        next_rid += 1;
    }
    // RFC-068 / G08: workbook-scoped personList rel, only when the workbook
    // has at least one threaded-comment person.
    if !wb.persons.is_empty() {
        g.add_with_id(
            RelId(format!("rId{next_rid}")),
            rt::PERSON_LIST,
            "persons/personList.xml",
            TargetMode::Internal,
        );
    }
    g.serialize()
}

/// `xl/worksheets/_rels/sheet{N}.xml.rels` — sheet → comments, drawings,
/// tables, external hyperlinks.
///
/// Returns an empty vec when the sheet has none of those things. The
/// caller is expected to detect `is_empty()` and skip the file.
///
/// # Relationship numbering
///
/// - If comments exist: `rId1` = comments, `rId2` = vmlDrawing.
/// - Tables occupy the next contiguous block of rIds.
/// - External hyperlinks (those that do not start with `#`) occupy the
///   tail of the rId range.
///
/// # Table numbering
///
/// Tables are numbered globally across the workbook (1..N) in sheet
/// insertion order. This matches openpyxl and [`super::content_types::emit`].
pub fn emit_sheet(wb: &Workbook, sheet_idx: usize) -> Vec<u8> {
    let Some(sheet) = wb.sheets.get(sheet_idx) else {
        return Vec::new();
    };

    let rel_ids = SheetRelIdPlan::new(sheet);
    let has_comments = !sheet.comments.is_empty();
    let external_hyperlinks: Vec<(&String, &crate::model::worksheet::Hyperlink)> = sheet
        .hyperlinks
        .iter()
        .filter(|(_, h)| !h.is_internal)
        .collect();
    let has_images = !sheet.images.is_empty();
    let has_charts = !sheet.charts.is_empty();
    // A sheet needs a drawing part if it has at least one image OR chart.
    let has_drawing = has_images || has_charts;

    if !rel_ids.has_relationships() {
        return Vec::new();
    }

    // Global table numbering: count how many tables exist in sheets before
    // this one, then assign 1-based ids starting from there + 1.
    let tables_before: usize = wb.sheets[..sheet_idx].iter().map(|s| s.tables.len()).sum();

    let mut g = RelsGraph::new();

    // Comments + VML.
    if has_comments {
        let n = sheet_idx + 1;
        g.add_with_id(
            RelId(rel_ids.comments().expect("comments relationship id")),
            rt::COMMENTS,
            &format!("../comments/comments{n}.xml"),
            TargetMode::Internal,
        );
        g.add_with_id(
            RelId(rel_ids.vml_drawing().expect("VML relationship id")),
            rt::VML_DRAWING,
            &format!("../drawings/vmlDrawing{n}.vml"),
            TargetMode::Internal,
        );
    }

    // Tables.
    for (local_idx, _table) in sheet.tables.iter().enumerate() {
        let global_id = tables_before + local_idx + 1;
        g.add_with_id(
            RelId(rel_ids.table(local_idx as u32)),
            rt::TABLE,
            &format!("../tables/table{global_id}.xml"),
            TargetMode::Internal,
        );
    }

    // External hyperlinks (URLs, not internal `#Sheet!A1` references).
    for (external_idx, (_cell_ref, hyperlink)) in external_hyperlinks.iter().enumerate() {
        g.add_with_id(
            RelId(rel_ids.external_hyperlink(external_idx as u32)),
            rt::HYPERLINK,
            &hyperlink.target,
            TargetMode::External,
        );
    }

    if has_drawing {
        // drawingN.xml is numbered globally — count how many earlier
        // sheets had a drawing (image or chart) to compute this
        // sheet's drawing N.
        let drawings_before: usize = wb.sheets[..sheet_idx]
            .iter()
            .filter(|s| !s.images.is_empty() || !s.charts.is_empty())
            .count();
        let drawing_n = drawings_before + 1;
        g.add_with_id(
            RelId(rel_ids.drawing().expect("drawing relationship id")),
            rt::DRAWING,
            &format!("../drawings/drawing{drawing_n}.xml"),
            TargetMode::Internal,
        );
    }

    // RFC-068 / G08: threadedCommentsN rel — sheet-numbered (matches
    // commentsN.xml). Only emitted when this sheet has threaded comments.
    if !sheet.threaded_comments.is_empty() {
        let n = sheet_idx + 1;
        g.add_with_id(
            RelId(
                rel_ids
                    .threaded_comments()
                    .expect("threadedComments relationship id"),
            ),
            rt::THREADED_COMMENTS,
            &format!("../threadedComments/threadedComments{n}.xml"),
            TargetMode::Internal,
        );
    }

    g.serialize()
}

/// Emit `xl/drawings/_rels/drawingN.xml.rels` for image-only drawings.
///
/// Each image becomes one `image` relationship pointing at
/// `../media/imageM.<ext>` where M is the global image index assigned by the
/// caller (`image_indices` is parallel to `sheet.images`). Returns the
/// allocated `rId`s in image order so the drawings emitter can reference them.
pub fn emit_drawing_rels(
    sheet: &crate::model::worksheet::Worksheet,
    image_indices: &[u32],
) -> (Vec<u8>, Vec<String>) {
    debug_assert_eq!(sheet.images.len(), image_indices.len());
    let mut g = RelsGraph::new();
    let mut rids: Vec<String> = Vec::with_capacity(sheet.images.len());
    for (img, &n) in sheet.images.iter().zip(image_indices.iter()) {
        let rid = g.add(
            rt::IMAGE,
            &format!("../media/image{n}.{}", img.ext),
            TargetMode::Internal,
        );
        rids.push(rid.0);
    }
    (g.serialize(), rids)
}

/// Emit `xl/drawings/_rels/drawingN.xml.rels` for mixed image/chart drawings.
///
/// Returns the rels bytes plus two parallel `Vec<String>` of rIds: one for
/// images (in `sheet.images` order) and one for charts (in `sheet.charts`
/// order). Image rels come first so existing image-only sheets keep their
/// rId allocation stable.
pub fn emit_drawing_rels_with_charts(
    sheet: &crate::model::worksheet::Worksheet,
    image_indices: &[u32],
    chart_indices: &[u32],
) -> (Vec<u8>, Vec<String>, Vec<String>) {
    debug_assert_eq!(sheet.images.len(), image_indices.len());
    debug_assert_eq!(sheet.charts.len(), chart_indices.len());

    let mut g = RelsGraph::new();
    let mut image_rids: Vec<String> = Vec::with_capacity(sheet.images.len());
    let mut chart_rids: Vec<String> = Vec::with_capacity(sheet.charts.len());

    for (img, &n) in sheet.images.iter().zip(image_indices.iter()) {
        let rid = g.add(
            rt::IMAGE,
            &format!("../media/image{n}.{}", img.ext),
            TargetMode::Internal,
        );
        image_rids.push(rid.0);
    }
    for &n in chart_indices.iter() {
        let rid = g.add(
            rt::CHART,
            &format!("../charts/chart{n}.xml"),
            TargetMode::Internal,
        );
        chart_rids.push(rid.0);
    }
    (g.serialize(), image_rids, chart_rids)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::comment::Comment;
    use crate::model::table::{Table, TableColumn};
    use crate::model::worksheet::{Hyperlink, Worksheet};
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn wb_with_sheets(n: usize) -> Workbook {
        let mut wb = Workbook::new();
        for i in 1..=n {
            wb.add_sheet(Worksheet::new(format!("Sheet{i}")));
        }
        wb
    }

    fn parse_ok(bytes: &[u8]) {
        let text = std::str::from_utf8(bytes).expect("utf8");
        let mut reader = Reader::from_str(text);
        let mut buf = Vec::new();
        loop {
            match reader.read_event_into(&mut buf) {
                Ok(Event::Eof) => break,
                Err(e) => panic!("parse error: {e}"),
                _ => (),
            }
            buf.clear();
        }
    }

    #[test]
    fn root_rels_has_three_relationships() {
        let wb = wb_with_sheets(1);
        let bytes = emit_root(&wb);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("Id=\"rId1\""));
        assert!(text.contains("Id=\"rId2\""));
        assert!(text.contains("Id=\"rId3\""));
        assert!(text.contains("Target=\"xl/workbook.xml\""));
        assert!(text.contains("Target=\"docProps/core.xml\""));
        assert!(text.contains("Target=\"docProps/app.xml\""));
    }

    #[test]
    fn workbook_rels_numbers_sheets_then_styles_then_sst() {
        let wb = wb_with_sheets(3);
        let bytes = emit_workbook(&wb);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("Id=\"rId1\"") && text.contains("worksheets/sheet1.xml"));
        assert!(text.contains("Id=\"rId2\"") && text.contains("worksheets/sheet2.xml"));
        assert!(text.contains("Id=\"rId3\"") && text.contains("worksheets/sheet3.xml"));
        assert!(text.contains("Id=\"rId4\"") && text.contains("Target=\"styles.xml\""));
        assert!(text.contains("Id=\"rId5\"") && text.contains("Target=\"sharedStrings.xml\""));
    }

    #[test]
    fn sheet_rels_empty_when_nothing_to_reference() {
        let wb = wb_with_sheets(1);
        let bytes = emit_sheet(&wb, 0);
        assert!(bytes.is_empty(), "no rels needed for bare sheet");
    }

    #[test]
    fn sheet_rels_out_of_range_returns_empty() {
        let wb = wb_with_sheets(1);
        let bytes = emit_sheet(&wb, 5);
        assert!(bytes.is_empty());
    }

    #[test]
    fn sheet_rels_with_comments_emits_two_relationships() {
        let mut wb = wb_with_sheets(1);
        wb.sheets[0].comments.insert(
            "A1".into(),
            Comment {
                text: "hello".into(),
                author_id: 0,
                width_pt: None,
                height_pt: None,
                visible: false,
            },
        );
        let bytes = emit_sheet(&wb, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("../comments/comments1.xml"));
        assert!(text.contains("../drawings/vmlDrawing1.vml"));
        assert!(text.contains("Id=\"rId1\""));
        assert!(text.contains("Id=\"rId2\""));
    }

    #[test]
    fn sheet_rels_external_hyperlink_marked_external() {
        let mut wb = wb_with_sheets(1);
        wb.sheets[0].hyperlinks.insert(
            "A1".into(),
            Hyperlink {
                target: "https://example.com".into(),
                location: None,
                is_internal: false,
                display: None,
                tooltip: None,
            },
        );
        let bytes = emit_sheet(&wb, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("TargetMode=\"External\""));
        assert!(text.contains("https://example.com"));
    }

    #[test]
    fn sheet_rels_internal_hyperlink_skipped() {
        let mut wb = wb_with_sheets(1);
        wb.sheets[0].hyperlinks.insert(
            "A1".into(),
            Hyperlink {
                target: "Sheet2!A1".into(),
                location: None,
                is_internal: true,
                display: None,
                tooltip: None,
            },
        );
        // No tables, no comments, only internal link → no rels file.
        let bytes = emit_sheet(&wb, 0);
        assert!(bytes.is_empty());
    }

    #[test]
    fn sheet_rels_tables_use_global_numbering() {
        let mut wb = wb_with_sheets(2);
        let mk = || Table {
            name: "t".into(),
            display_name: None,
            range: "A1:B2".into(),
            columns: vec![TableColumn {
                name: "a".into(),
                totals_function: None,
                totals_label: None,
            }],
            header_row: true,
            totals_row: false,
            style: None,
            autofilter: false,
        };
        wb.sheets[0].tables.push(mk());
        wb.sheets[0].tables.push(mk());
        wb.sheets[1].tables.push(mk());

        let bytes0 = emit_sheet(&wb, 0);
        let text0 = String::from_utf8(bytes0).unwrap();
        assert!(text0.contains("../tables/table1.xml"));
        assert!(text0.contains("../tables/table2.xml"));

        let bytes1 = emit_sheet(&wb, 1);
        let text1 = String::from_utf8(bytes1).unwrap();
        assert!(text1.contains("../tables/table3.xml"));
        assert!(!text1.contains("../tables/table1.xml"));
    }

    #[test]
    fn sheet_rels_all_three_kinds_coexist() {
        let mut wb = wb_with_sheets(1);
        wb.sheets[0].comments.insert(
            "A1".into(),
            Comment {
                text: "n".into(),
                author_id: 0,
                width_pt: None,
                height_pt: None,
                visible: false,
            },
        );
        wb.sheets[0].tables.push(Table {
            name: "t".into(),
            display_name: None,
            range: "A1:B2".into(),
            columns: vec![TableColumn {
                name: "a".into(),
                totals_function: None,
                totals_label: None,
            }],
            header_row: true,
            totals_row: false,
            style: None,
            autofilter: false,
        });
        wb.sheets[0].hyperlinks.insert(
            "B1".into(),
            Hyperlink {
                target: "https://example.com/path?q=1&r=2".into(),
                location: None,
                is_internal: false,
                display: None,
                tooltip: None,
            },
        );
        let bytes = emit_sheet(&wb, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        // rId1 = comments, rId2 = vml, rId3 = table, rId4 = hyperlink
        assert!(text.contains("Id=\"rId1\""));
        assert!(text.contains("Id=\"rId2\""));
        assert!(text.contains("Id=\"rId3\""));
        assert!(text.contains("Id=\"rId4\""));
        // Ampersand in URL must be escaped.
        assert!(text.contains("q=1&amp;r=2"));
    }
}
