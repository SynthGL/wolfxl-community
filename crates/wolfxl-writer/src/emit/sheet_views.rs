//! Legacy `<sheetViews>` emitter for worksheet XML.

use crate::model::worksheet::{FreezePane, SplitPane, Worksheet};
use crate::refs;

/// Emit `<sheetViews><sheetView ...>...</sheetView></sheetViews>`.
///
/// Typed sheet-view specs are emitted by `parse::sheet_setup`; this module is
/// the legacy fallback used by write-mode freeze/split pane fields.
pub fn emit(out: &mut String, sheet: &Worksheet, sheet_idx: u32) {
    let _ = sheet_idx;
    out.push_str("<sheetViews>");
    out.push_str("<sheetView workbookViewId=\"0\">");

    if let Some(freeze) = &sheet.freeze {
        emit_freeze_pane(out, freeze);
    } else if let Some(split) = &sheet.split {
        emit_split_pane(out, split);
    }

    out.push_str("</sheetView>");
    out.push_str("</sheetViews>");
}

/// Emit `<pane .../>` for a freeze pane.
///
/// OOXML pane semantics with `state="frozen"`:
/// `xSplit` = number of columns frozen and `ySplit` = number of rows frozen.
/// The model stores the freeze cell coordinate, so the emitted count is
/// `(coord - 1)`.
fn emit_freeze_pane(out: &mut String, freeze: &FreezePane) {
    let y_split = freeze.freeze_row.saturating_sub(1);
    let x_split = freeze.freeze_col.saturating_sub(1);
    let has_row = y_split > 0;
    let has_col = x_split > 0;
    if !has_row && !has_col {
        return;
    }

    let tl_row =
        freeze
            .top_left
            .map(|t| t.0)
            .unwrap_or_else(|| if has_row { freeze.freeze_row } else { 1 });
    let tl_col =
        freeze
            .top_left
            .map(|t| t.1)
            .unwrap_or_else(|| if has_col { freeze.freeze_col } else { 1 });

    let active_pane = if has_row && has_col {
        "bottomRight"
    } else if has_row {
        "bottomLeft"
    } else {
        "topRight"
    };

    out.push_str("<pane");
    if has_col {
        out.push_str(&format!(" xSplit=\"{}\"", x_split));
    }
    if has_row {
        out.push_str(&format!(" ySplit=\"{}\"", y_split));
    }
    let top_left_cell = refs::format_a1(tl_row, tl_col);
    out.push_str(&format!(" topLeftCell=\"{}\"", top_left_cell));
    out.push_str(&format!(" activePane=\"{}\"", active_pane));
    out.push_str(" state=\"frozen\"/>");
}

/// Emit `<pane .../>` for a split (non-frozen) pane.
fn emit_split_pane(out: &mut String, split: &SplitPane) {
    let tl_row = split.top_left.map(|t| t.0).unwrap_or(1);
    let tl_col = split.top_left.map(|t| t.1).unwrap_or(1);

    let has_x = split.x_split != 0.0;
    let has_y = split.y_split != 0.0;

    let active_pane = if has_x && has_y {
        "bottomRight"
    } else if has_y {
        "bottomLeft"
    } else {
        "topRight"
    };

    out.push_str("<pane");
    if has_x {
        out.push_str(&format!(" xSplit=\"{:.2}\"", split.x_split));
    }
    if has_y {
        out.push_str(&format!(" ySplit=\"{:.2}\"", split.y_split));
    }

    let top_left_cell = refs::format_a1(tl_row, tl_col);
    out.push_str(&format!(" topLeftCell=\"{}\"", top_left_cell));
    out.push_str(&format!(" activePane=\"{}\"/>", active_pane));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn first_sheet_is_not_tab_selected_by_default() {
        let sheet = Worksheet::new("S");
        let mut out = String::new();

        emit(&mut out, &sheet, 0);

        assert!(out.contains("<sheetView workbookViewId=\"0\">"));
        assert!(!out.contains("tabSelected"));
    }

    #[test]
    fn second_sheet_is_not_tab_selected() {
        let sheet = Worksheet::new("S");
        let mut out = String::new();

        emit(&mut out, &sheet, 1);

        assert!(out.contains("<sheetView workbookViewId=\"0\">"));
        assert!(!out.contains("tabSelected"));
    }

    #[test]
    fn freeze_rows_only_emits_bottom_left_pane() {
        let mut sheet = Worksheet::new("S");
        sheet.freeze = Some(FreezePane {
            freeze_row: 3,
            freeze_col: 0,
            top_left: None,
        });
        let mut out = String::new();

        emit(&mut out, &sheet, 0);

        assert!(out.contains("ySplit=\"2\""), "ySplit: {out}");
        assert!(out.contains("state=\"frozen\""), "state=frozen: {out}");
        assert!(
            out.contains("activePane=\"bottomLeft\""),
            "activePane: {out}"
        );
        assert!(!out.contains("xSplit"), "no xSplit: {out}");
    }

    #[test]
    fn freeze_cols_only_emits_top_right_pane() {
        let mut sheet = Worksheet::new("S");
        sheet.freeze = Some(FreezePane {
            freeze_row: 0,
            freeze_col: 2,
            top_left: None,
        });
        let mut out = String::new();

        emit(&mut out, &sheet, 0);

        assert!(out.contains("xSplit=\"1\""), "xSplit: {out}");
        assert!(out.contains("state=\"frozen\""), "state=frozen: {out}");
        assert!(out.contains("activePane=\"topRight\""), "activePane: {out}");
        assert!(!out.contains("ySplit"), "no ySplit: {out}");
    }

    #[test]
    fn freeze_both_emits_bottom_right_pane() {
        let mut sheet = Worksheet::new("S");
        sheet.freeze = Some(FreezePane {
            freeze_row: 2,
            freeze_col: 3,
            top_left: None,
        });
        let mut out = String::new();

        emit(&mut out, &sheet, 0);

        assert!(out.contains("xSplit=\"2\""), "xSplit: {out}");
        assert!(out.contains("ySplit=\"1\""), "ySplit: {out}");
        assert!(out.contains("state=\"frozen\""), "state=frozen: {out}");
        assert!(
            out.contains("activePane=\"bottomRight\""),
            "activePane: {out}"
        );
    }

    #[test]
    fn freeze_b2_emits_one_row_and_column_split() {
        let mut sheet = Worksheet::new("S");
        sheet.set_freeze(2, 2, None);
        let mut out = String::new();

        emit(&mut out, &sheet, 0);

        assert!(out.contains(
            "<pane xSplit=\"1\" ySplit=\"1\" topLeftCell=\"B2\" activePane=\"bottomRight\" state=\"frozen\"/>"
        ));
        assert!(!out.contains("xSplit=\"2\""), "xSplit must not be 2: {out}");
        assert!(!out.contains("ySplit=\"2\""), "ySplit must not be 2: {out}");
    }

    #[test]
    fn freeze_c5_emits_asymmetric_counts() {
        let mut sheet = Worksheet::new("S");
        sheet.freeze = Some(FreezePane {
            freeze_row: 5,
            freeze_col: 3,
            top_left: None,
        });
        let mut out = String::new();

        emit(&mut out, &sheet, 0);

        assert!(out.contains("xSplit=\"2\""), "xSplit: {out}");
        assert!(out.contains("ySplit=\"4\""), "ySplit: {out}");
        assert!(out.contains("topLeftCell=\"C5\""), "topLeftCell: {out}");
    }

    #[test]
    fn freeze_a1_is_no_op() {
        let mut sheet = Worksheet::new("S");
        sheet.freeze = Some(FreezePane {
            freeze_row: 1,
            freeze_col: 1,
            top_left: None,
        });
        let mut out = String::new();

        emit(&mut out, &sheet, 0);

        assert!(!out.contains("<pane"), "must not emit pane for A1: {out}");
    }

    #[test]
    fn split_pane_omits_frozen_state() {
        let mut sheet = Worksheet::new("S");
        sheet.set_split(100.0, 50.0, Some((3, 4)));
        let mut out = String::new();

        emit(&mut out, &sheet, 0);

        assert!(out.contains(
            "<pane xSplit=\"100.00\" ySplit=\"50.00\" topLeftCell=\"D3\" activePane=\"bottomRight\"/>"
        ));
        assert!(!out.contains("state=\"frozen\""));
    }

    #[test]
    fn split_pane_without_top_left_emits_default_cell() {
        let mut sheet = Worksheet::new("S");
        sheet.split = Some(SplitPane {
            x_split: 1200.0,
            y_split: 600.0,
            top_left: None,
        });
        let mut out = String::new();

        emit(&mut out, &sheet, 0);

        assert!(out.contains("<pane"), "has pane: {out}");
        assert!(
            out.contains("topLeftCell=\"A1\""),
            "default top-left: {out}"
        );
        assert!(
            !out.contains("state=\"frozen\""),
            "no frozen for split: {out}"
        );
    }
}
