//! `<cols>` emitter for worksheet XML.

use crate::model::worksheet::{Column, Worksheet};

/// Emit `<cols>...</cols>` for non-default column metadata.
pub fn emit(out: &mut String, sheet: &Worksheet) {
    out.push_str("<cols>");

    for (&col_idx, col) in &sheet.columns {
        emit_column(out, col_idx, col);
    }

    out.push_str("</cols>");
}

fn emit_column(out: &mut String, col_idx: u32, col: &Column) {
    if col.width.is_none() && !col.hidden && col.outline_level == 0 && col.style_id.is_none() {
        return;
    }

    out.push_str(&format!("<col min=\"{}\" max=\"{}\"", col_idx, col_idx));

    if let Some(w) = col.width {
        out.push_str(&format!(" width=\"{}\" customWidth=\"1\"", format_f64(w)));
    }
    if col.hidden {
        out.push_str(" hidden=\"1\"");
    }
    if col.outline_level > 0 {
        out.push_str(&format!(" outlineLevel=\"{}\"", col.outline_level));
    }
    if let Some(s) = col.style_id {
        out.push_str(&format!(" style=\"{}\" customFormat=\"1\"", s));
    }

    out.push_str("/>");
}

/// Format an f64 for attribute values. Uses Rust's Display behavior while
/// keeping whole numbers tidy.
fn format_f64(n: f64) -> String {
    if n == (n as i64) as f64 && n.abs() < 1e15 {
        format!("{}", n as i64)
    } else {
        format!("{}", n)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_columns_are_skipped_inside_wrapper() {
        let mut sheet = Worksheet::new("S");
        sheet.columns.insert(2, Column::default());
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(out, "<cols></cols>");
    }

    #[test]
    fn width_emits_custom_width() {
        let mut sheet = Worksheet::new("S");
        sheet.columns.insert(
            2,
            Column {
                width: Some(12.5),
                ..Default::default()
            },
        );
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(
            out,
            "<cols><col min=\"2\" max=\"2\" width=\"12.5\" customWidth=\"1\"/></cols>"
        );
    }

    #[test]
    fn hidden_outline_and_style_emit_attributes() {
        let mut sheet = Worksheet::new("S");
        sheet.columns.insert(
            4,
            Column {
                width: None,
                hidden: true,
                style_id: Some(7),
                outline_level: 2,
            },
        );
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(
            out,
            "<cols><col min=\"4\" max=\"4\" hidden=\"1\" outlineLevel=\"2\" style=\"7\" customFormat=\"1\"/></cols>"
        );
    }

    #[test]
    fn sheet_set_column_emits_single_min_max() {
        let mut sheet = Worksheet::new("S");
        sheet.set_column(
            3,
            Column {
                width: Some(12.5),
                ..Default::default()
            },
        );
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(
            out,
            "<cols><col min=\"3\" max=\"3\" width=\"12.5\" customWidth=\"1\"/></cols>"
        );
    }

    #[test]
    fn hidden_outline_without_width_omits_width_attrs() {
        let mut sheet = Worksheet::new("S");
        sheet.set_column(
            3,
            Column {
                width: None,
                hidden: true,
                outline_level: 2,
                style_id: None,
            },
        );
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(
            out,
            "<cols><col min=\"3\" max=\"3\" hidden=\"1\" outlineLevel=\"2\"/></cols>"
        );
        assert!(!out.contains("width="), "no width when none: {out}");
        assert!(
            !out.contains("customWidth="),
            "no customWidth when none: {out}"
        );
    }

    #[test]
    fn column_style_id_emits_custom_format() {
        let mut sheet = Worksheet::new("S");
        sheet.set_column(
            2,
            Column {
                width: Some(10.0),
                style_id: Some(4),
                ..Default::default()
            },
        );
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(
            out,
            "<cols><col min=\"2\" max=\"2\" width=\"10\" customWidth=\"1\" style=\"4\" customFormat=\"1\"/></cols>"
        );
    }
}
