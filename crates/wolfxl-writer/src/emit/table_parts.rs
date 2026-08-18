//! `<tableParts>` emitter for worksheet XML.

use super::sheet_rel_ids::SheetRelIdPlan;
use crate::model::worksheet::Worksheet;

/// Emit `<tableParts count="N">...<tablePart r:id="rIdX"/>...</tableParts>`.
///
/// Sheet relationships reserve `rId1` and `rId2` for comments/VML when
/// comments exist, so table rIds start at `rId3` in that case and `rId1`
/// otherwise.
pub fn emit(out: &mut String, sheet: &Worksheet) {
    if sheet.tables.is_empty() {
        return;
    }

    let rel_ids = SheetRelIdPlan::new(sheet);
    out.push_str(&format!("<tableParts count=\"{}\">", sheet.tables.len()));
    for (local_idx, _) in sheet.tables.iter().enumerate() {
        let rid = rel_ids.table(local_idx as u32);
        out.push_str(&format!("<tablePart r:id=\"{}\"/>", rid));
    }
    out.push_str("</tableParts>");
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::comment::Comment;
    use crate::model::table::{Table, TableColumn};

    fn table(name: &str) -> Table {
        Table {
            name: name.into(),
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
    fn absent_when_no_tables() {
        let sheet = Worksheet::new("S");
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert!(out.is_empty());
    }

    #[test]
    fn no_comments_starts_at_rid1() {
        let mut sheet = Worksheet::new("S");
        sheet.tables.push(table("Table1"));
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(
            out,
            "<tableParts count=\"1\"><tablePart r:id=\"rId1\"/></tableParts>"
        );
    }

    #[test]
    fn comments_reserve_first_two_rids() {
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
        sheet.tables.push(table("Table1"));
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(
            out,
            "<tableParts count=\"1\"><tablePart r:id=\"rId3\"/></tableParts>"
        );
    }

    #[test]
    fn multiple_tables_get_sequential_rids() {
        let mut sheet = Worksheet::new("S");
        sheet.tables.push(table("Table1"));
        sheet.tables.push(table("Table2"));
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(
            out,
            "<tableParts count=\"2\"><tablePart r:id=\"rId1\"/><tablePart r:id=\"rId2\"/></tableParts>"
        );
    }

    #[test]
    fn multiple_tables_after_comments_get_sequential_offset_rids() {
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
        sheet.tables.push(table("Table1"));
        sheet.tables.push(table("Table2"));
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(
            out,
            "<tableParts count=\"2\"><tablePart r:id=\"rId3\"/><tablePart r:id=\"rId4\"/></tableParts>"
        );
    }
}
