//! Worksheet-level drawing relationship refs for `sheetN.xml`.

use super::sheet_rel_ids::SheetRelIdPlan;
use crate::model::worksheet::Worksheet;

/// Emit `<drawing r:id="rIdN"/>` when the sheet has images or charts.
///
/// The drawing relationship is allocated after comments/VML, table parts, and
/// external hyperlinks. This mirrors `rels::emit_sheet` so the sheet XML and
/// relationship part stay in lock-step.
pub fn emit_drawing(out: &mut String, sheet: &Worksheet) {
    if sheet.images.is_empty() && sheet.charts.is_empty() {
        return;
    }

    let rid = SheetRelIdPlan::new(sheet)
        .drawing()
        .expect("drawing relationship id");
    out.push_str(&format!("<drawing r:id=\"{rid}\"/>"));
}

/// Emit `<legacyDrawing r:id="rId2"/>` when comments exist.
pub fn emit_legacy(out: &mut String, sheet: &Worksheet) {
    if !sheet.comments.is_empty() {
        out.push_str("<legacyDrawing r:id=\"rId2\"/>");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::comment::Comment;
    use crate::model::image::{ImageAnchor, SheetImage};
    use crate::model::table::{Table, TableColumn};
    use crate::model::worksheet::Hyperlink;

    fn image() -> SheetImage {
        SheetImage {
            data: vec![1, 2, 3],
            ext: "png".into(),
            width_px: 1,
            height_px: 1,
            anchor: ImageAnchor::one_cell(0, 0),
        }
    }

    fn table() -> Table {
        Table {
            name: "T".into(),
            display_name: None,
            range: "A1:A2".into(),
            columns: vec![TableColumn {
                name: "A".into(),
                totals_function: None,
                totals_label: None,
            }],
            header_row: true,
            totals_row: false,
            style: None,
            autofilter: true,
        }
    }

    #[test]
    fn drawing_absent_without_images_or_charts() {
        let sheet = Worksheet::new("S");
        let mut out = String::new();
        emit_drawing(&mut out, &sheet);
        assert!(out.is_empty());
    }

    #[test]
    fn drawing_rid_starts_at_one_for_image_only() {
        let mut sheet = Worksheet::new("S");
        sheet.images.push(image());

        let mut out = String::new();
        emit_drawing(&mut out, &sheet);
        assert_eq!(out, "<drawing r:id=\"rId1\"/>");
    }

    #[test]
    fn drawing_rid_accounts_for_comments_tables_and_external_links() {
        let mut sheet = Worksheet::new("S");
        sheet.images.push(image());
        sheet.tables.push(table());
        sheet.comments.insert(
            "A1".into(),
            Comment {
                author_id: 0,
                text: "Note".into(),
                width_pt: None,
                height_pt: None,
                visible: false,
            },
        );
        sheet.hyperlinks.insert(
            "B2".into(),
            Hyperlink {
                target: "https://example.com".into(),
                location: None,
                is_internal: false,
                display: None,
                tooltip: None,
            },
        );

        let mut out = String::new();
        emit_drawing(&mut out, &sheet);
        assert_eq!(out, "<drawing r:id=\"rId5\"/>");
    }

    #[test]
    fn legacy_drawing_uses_reserved_comment_vml_rid() {
        let mut sheet = Worksheet::new("S");
        sheet.comments.insert(
            "A1".into(),
            Comment {
                author_id: 0,
                text: "Note".into(),
                width_pt: None,
                height_pt: None,
                visible: false,
            },
        );

        let mut out = String::new();
        emit_legacy(&mut out, &sheet);
        assert_eq!(out, "<legacyDrawing r:id=\"rId2\"/>");
    }
}
