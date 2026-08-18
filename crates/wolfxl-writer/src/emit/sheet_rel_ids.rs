//! Shared worksheet relationship-id planner.

use crate::model::worksheet::Worksheet;

/// Relationship ids used by a worksheet XML part and its `.rels` sidecar.
pub(crate) struct SheetRelIdPlan {
    has_comments: bool,
    table_count: u32,
    external_hyperlink_count: u32,
    has_drawing: bool,
    has_threaded_comments: bool,
}

impl SheetRelIdPlan {
    /// Build the id plan for one worksheet.
    pub(crate) fn new(sheet: &Worksheet) -> Self {
        Self {
            has_comments: !sheet.comments.is_empty(),
            table_count: sheet.tables.len() as u32,
            external_hyperlink_count: sheet.hyperlinks.values().filter(|h| !h.is_internal).count()
                as u32,
            has_drawing: !sheet.images.is_empty() || !sheet.charts.is_empty(),
            has_threaded_comments: !sheet.threaded_comments.is_empty(),
        }
    }

    /// Return whether the sheet needs a relationship sidecar at all.
    pub(crate) fn has_relationships(&self) -> bool {
        self.has_comments
            || self.table_count > 0
            || self.external_hyperlink_count > 0
            || self.has_drawing
            || self.has_threaded_comments
    }

    /// Return the comments relationship id when comments exist.
    pub(crate) fn comments(&self) -> Option<String> {
        self.has_comments.then(|| rel_id(1))
    }

    /// Return the VML relationship id when comments exist.
    pub(crate) fn vml_drawing(&self) -> Option<String> {
        self.has_comments.then(|| rel_id(2))
    }

    /// Return the relationship id for a local table index.
    pub(crate) fn table(&self, local_idx: u32) -> String {
        rel_id(self.comments_offset() + local_idx + 1)
    }

    /// Return the relationship id for an external hyperlink index.
    pub(crate) fn external_hyperlink(&self, external_idx: u32) -> String {
        rel_id(self.comments_offset() + self.table_count + external_idx + 1)
    }

    /// Return the drawing relationship id when images or charts exist.
    pub(crate) fn drawing(&self) -> Option<String> {
        self.has_drawing.then(|| {
            rel_id(self.comments_offset() + self.table_count + self.external_hyperlink_count + 1)
        })
    }

    /// Return the threadedComments relationship id when threaded comments
    /// exist on this sheet (RFC-068). Allocated *after* the drawing slot so
    /// existing rId numbering stays stable for sheets that don't use
    /// threaded comments.
    pub(crate) fn threaded_comments(&self) -> Option<String> {
        self.has_threaded_comments.then(|| {
            let drawing_slot = if self.has_drawing { 1 } else { 0 };
            rel_id(
                self.comments_offset()
                    + self.table_count
                    + self.external_hyperlink_count
                    + drawing_slot
                    + 1,
            )
        })
    }

    fn comments_offset(&self) -> u32 {
        if self.has_comments {
            2
        } else {
            0
        }
    }
}

fn rel_id(n: u32) -> String {
    format!("rId{n}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::comment::Comment;
    use crate::model::image::{ImageAnchor, SheetImage};
    use crate::model::table::{Table, TableColumn};
    use crate::model::worksheet::Hyperlink;

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

    fn image() -> SheetImage {
        SheetImage {
            data: vec![1, 2, 3],
            ext: "png".into(),
            width_px: 1,
            height_px: 1,
            anchor: ImageAnchor::one_cell(0, 0),
        }
    }

    fn external(target: &str) -> Hyperlink {
        Hyperlink {
            target: target.into(),
            location: None,
            is_internal: false,
            display: None,
            tooltip: None,
        }
    }

    #[test]
    fn empty_sheet_has_no_relationships() {
        let sheet = Worksheet::new("S");
        let plan = SheetRelIdPlan::new(&sheet);

        assert!(!plan.has_relationships());
        assert_eq!(plan.comments(), None);
        assert_eq!(plan.vml_drawing(), None);
        assert_eq!(plan.drawing(), None);
    }

    #[test]
    fn comments_reserve_first_two_ids() {
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
        sheet.tables.push(table());
        sheet
            .hyperlinks
            .insert("B1".into(), external("https://example.com"));
        sheet.images.push(image());

        let plan = SheetRelIdPlan::new(&sheet);

        assert_eq!(plan.comments(), Some("rId1".into()));
        assert_eq!(plan.vml_drawing(), Some("rId2".into()));
        assert_eq!(plan.table(0), "rId3");
        assert_eq!(plan.external_hyperlink(0), "rId4");
        assert_eq!(plan.drawing(), Some("rId5".into()));
    }

    #[test]
    fn internal_hyperlinks_do_not_consume_relationship_ids() {
        let mut sheet = Worksheet::new("S");
        sheet.tables.push(table());
        sheet.hyperlinks.insert(
            "A1".into(),
            Hyperlink {
                target: "Sheet2!A1".into(),
                location: None,
                is_internal: true,
                display: None,
                tooltip: None,
            },
        );
        sheet
            .hyperlinks
            .insert("B1".into(), external("https://example.com"));
        sheet.images.push(image());

        let plan = SheetRelIdPlan::new(&sheet);

        assert_eq!(plan.table(0), "rId1");
        assert_eq!(plan.external_hyperlink(0), "rId2");
        assert_eq!(plan.drawing(), Some("rId3".into()));
    }
}
