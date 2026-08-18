//! `xl/drawings/vmlDrawing{N}.vml` emitter: legacy VML anchor shapes for
//! comment boxes.
//!
//! VML is an ancient Microsoft XML dialect kept around specifically for
//! comment boxes and form controls. Modern OOXML uses DrawingML for
//! everything else, but comments still need VML to show Excel a
//! yellow-rectangle shape anchored to a cell.
//!
//! ## Per-column width handling
//!
//! [`compute_margin_with_widths`] mirrors the modify-mode patcher's
//! `compute_margin_with_widths` in `src/wolfxl/comments.rs`: when a
//! sheet has a `<cols>` block with overrides, the comment's
//! `margin-left` is summed from per-column widths (in points) instead
//! of multiplying by the OOXML default of 48pt. The two helpers must
//! stay in agreement; see the parity test in
//! `tests/test_native_writer_comments.py`.

use crate::model::worksheet::Worksheet;
use crate::refs;

/// Default per-column shape origin offset (pt); assumes Excel's
/// default column width. The math `col0 * COL_WIDTH_PT + ORIGIN_LEFT_PT`
/// matches `rust_xlsxwriter`'s VML output exactly, so any cell with a
/// comment lands at the same on-screen position under either backend.
const COL_WIDTH_PT: f64 = 48.0;
const ROW_HEIGHT_PT: f64 = 12.75;
const ORIGIN_LEFT_PT: f64 = 59.25;
const ORIGIN_TOP_PT: f64 = 1.5;

/// Compute the VML `<x:Anchor>` 8-integer tuple
/// `(colLeft, offLeft, rowTop, offTop, colRight, offRight, rowBottom, offBottom)`
/// for a comment anchored to the cell at 0-based `(row0, col0)`.
///
/// Box spans 2 columns wide × 3 rows tall, starting one column to the
/// right and one row above the anchor cell (row 0 cells start at row 0
/// since `saturating_sub(1)` clamps).
fn compute_anchor(row0: u32, col0: u32) -> (u32, u32, u32, u32, u32, u32, u32, u32) {
    let col_left = col0 + 1;
    let row_top = row0.saturating_sub(1);
    let col_right = col0 + 3;
    let row_bottom = row0 + 3;
    (col_left, 15, row_top, 10, col_right, 15, row_bottom, 4)
}

/// Convert Excel "max-digit-width" column units to points. Mirrors
/// `src/wolfxl/comments.rs::col_units_to_pt` so writer-side and
/// patcher-side margin math agree.
fn col_units_to_pt(units: f64) -> f64 {
    let px = ((units * 7.0 + 5.0) / 7.0 * 7.0 + 5.0).trunc();
    px * 72.0 / 96.0
}

/// Compute the `(margin-left, margin-top)` shape origin in points,
/// honoring any per-column width overrides on `sheet`. When the
/// sheet has no `<cols>` overrides, falls back to the legacy
/// `col0 * 48pt` math — keeps byte-identical output for the common
/// case while fixing the visual mispositioning when the user set a
/// non-default width on any column to the LEFT of the comment.
fn compute_margin_with_widths(sheet: &Worksheet, row0: u32, col0: u32) -> (f64, f64) {
    let margin_top = (row0 as f64) * ROW_HEIGHT_PT + ORIGIN_TOP_PT;

    // Fast path: no overrides at all → legacy math byte-stable.
    if sheet.columns.is_empty() {
        let margin_left = (col0 as f64) * COL_WIDTH_PT + ORIGIN_LEFT_PT;
        return (margin_left, margin_top);
    }

    // Slow path: walk every column 0..col0 and sum its width in pt.
    // Columns without an override contribute the OOXML default. The
    // 1-based-vs-0-based conversion lives here because the model
    // stores `columns` keyed by 1-based index.
    let mut margin_left = ORIGIN_LEFT_PT;
    for c0 in 0..col0 {
        let width_pt = sheet
            .columns
            .get(&(c0 + 1))
            .and_then(|col| col.width)
            .map(col_units_to_pt)
            .unwrap_or(COL_WIDTH_PT);
        margin_left += width_pt;
    }
    (margin_left, margin_top)
}

/// Legacy fixed-width margin computation, kept for tests that pin the
/// historical math without going through a `Worksheet`. Callers that
/// have a `Worksheet` should prefer [`compute_margin_with_widths`].
#[allow(dead_code)]
fn compute_margin(row0: u32, col0: u32) -> (f64, f64) {
    let margin_left = (col0 as f64) * COL_WIDTH_PT + ORIGIN_LEFT_PT;
    let margin_top = (row0 as f64) * ROW_HEIGHT_PT + ORIGIN_TOP_PT;
    (margin_left, margin_top)
}

pub fn emit(sheet: &Worksheet) -> Vec<u8> {
    if sheet.comments.is_empty() {
        return Vec::new();
    }

    let mut out = String::with_capacity(2048);

    // No <?xml?> declaration — VML convention; the root element is literally <xml>
    out.push_str(
        "<xml xmlns:v=\"urn:schemas-microsoft-com:vml\"\
 xmlns:o=\"urn:schemas-microsoft-com:office:office\"\
 xmlns:x=\"urn:schemas-microsoft-com:office:excel\">",
    );

    // Shape layout
    out.push_str(
        "<o:shapelayout v:ext=\"edit\">\
<o:idmap v:ext=\"edit\" data=\"1\"/>\
</o:shapelayout>",
    );

    // Shape type definition (shared for all comment boxes)
    out.push_str(
        "<v:shapetype id=\"_x0000_t202\" coordsize=\"21600,21600\" o:spt=\"202\"\
 path=\"m,l,21600r21600,l21600,xe\">\
<v:stroke joinstyle=\"miter\"/>\
<v:path gradientshapeok=\"t\" o:connecttype=\"rect\"/>\
</v:shapetype>",
    );

    // One <v:shape> per comment — BTreeMap gives A1 order
    for (idx, (cell_ref, comment)) in sheet.comments.iter().enumerate() {
        // VML shape IDs conventionally start at 1025 per sheet (Excel's internal reserved range 0..=1024).
        let shape_num = 1025 + idx as u32;

        // Parse row/col from the A1 key (1-based), convert to 0-based
        let (row0, col0) = match refs::parse_a1(cell_ref) {
            Some((r, c)) => (r - 1, c - 1),
            None => (0, 0), // fallback for malformed refs (should not happen)
        };

        let width = match comment.width_pt {
            Some(w) => format!("{}pt", w),
            None => "96pt".to_string(),
        };
        let height = match comment.height_pt {
            Some(h) => format!("{}pt", h),
            None => "55.5pt".to_string(),
        };

        let (margin_left, margin_top) = compute_margin_with_widths(sheet, row0, col0);

        out.push_str(&format!(
            "<v:shape id=\"_x0000_s{}\" type=\"#_x0000_t202\"\
 style=\"position:absolute; margin-left:{}pt; margin-top:{}pt;\
 width:{}; height:{}; z-index:1; visibility:hidden\"\
 fillcolor=\"#ffffe1\" o:insetmode=\"auto\">",
            shape_num, margin_left, margin_top, width, height,
        ));

        out.push_str("<v:fill color2=\"#ffffe1\"/>");
        out.push_str("<v:shadow on=\"t\" color=\"black\" obscured=\"t\"/>");
        out.push_str("<v:path o:connecttype=\"none\"/>");
        out.push_str("<v:textbox style=\"mso-direction-alt:auto\"><div style=\"text-align:left\"/></v:textbox>");
        out.push_str("<x:ClientData ObjectType=\"Note\">");
        out.push_str("<x:MoveWithCells/>");
        out.push_str("<x:SizeWithCells/>");
        // VML anchor: 8-integer tuple encoding (colLeft, offLeft, rowTop, offTop, colRight, offRight, rowBottom, offBottom).
        // The box spans 2 columns × 3 rows starting one column right of the anchor cell.
        let (cl, ol, rt, ot, cr, or_, rb, ob) = compute_anchor(row0, col0);
        out.push_str(&format!(
            "<x:Anchor>{}, {}, {}, {}, {}, {}, {}, {}</x:Anchor>",
            cl, ol, rt, ot, cr, or_, rb, ob
        ));
        out.push_str("<x:AutoFill>False</x:AutoFill>");
        out.push_str(&format!("<x:Row>{}</x:Row>", row0));
        out.push_str(&format!("<x:Column>{}</x:Column>", col0));

        // <x:Visible/> is present only when visible == true
        if comment.visible {
            out.push_str("<x:Visible/>");
        }

        out.push_str("</x:ClientData>");
        out.push_str("</v:shape>");
    }

    out.push_str("</xml>");

    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::comment::Comment;
    use crate::model::worksheet::Worksheet;
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn parse_ok(bytes: &[u8]) {
        let text = std::str::from_utf8(bytes).expect("utf8");
        let mut reader = Reader::from_str(text);
        let mut buf = Vec::new();
        loop {
            match reader.read_event_into(&mut buf) {
                Ok(Event::Eof) => break,
                Err(e) => panic!("XML parse error: {e}"),
                _ => {}
            }
            buf.clear();
        }
    }

    fn make_comment(visible: bool, width_pt: Option<f64>, height_pt: Option<f64>) -> Comment {
        Comment {
            text: "note".to_string(),
            author_id: 0,
            width_pt,
            height_pt,
            visible,
        }
    }

    // 1. Empty sheet returns empty bytes
    #[test]
    fn empty_sheet_returns_empty_bytes() {
        let sheet = Worksheet::new("S");
        let result = emit(&sheet);
        assert!(
            result.is_empty(),
            "expected empty Vec, got {} bytes",
            result.len()
        );
    }

    // 2. Root declares three namespaces
    #[test]
    fn root_declares_three_namespaces() {
        let mut sheet = Worksheet::new("S");
        sheet
            .comments
            .insert("A1".to_string(), make_comment(false, None, None));
        let bytes = emit(&sheet);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("xmlns:v="), "xmlns:v missing: {text}");
        assert!(text.contains("xmlns:o="), "xmlns:o missing: {text}");
        assert!(text.contains("xmlns:x="), "xmlns:x missing: {text}");
    }

    // 3. Shape IDs start at 1025 and increment
    #[test]
    fn shape_ids_start_at_1025_and_increment() {
        let mut sheet = Worksheet::new("S");
        // A1 < B2 — BTreeMap gives them in this order
        sheet
            .comments
            .insert("A1".to_string(), make_comment(false, None, None));
        sheet
            .comments
            .insert("B2".to_string(), make_comment(false, None, None));

        let bytes = emit(&sheet);
        let text = String::from_utf8(bytes).unwrap();

        assert!(
            text.contains("id=\"_x0000_s1025\""),
            "first shape 1025: {text}"
        );
        assert!(
            text.contains("id=\"_x0000_s1026\""),
            "second shape 1026: {text}"
        );
    }

    // 4. Visible true emits element; visible false omits it
    #[test]
    fn visible_true_emits_visible_element() {
        // visible=true
        let mut sheet_visible = Worksheet::new("S");
        sheet_visible
            .comments
            .insert("A1".to_string(), make_comment(true, None, None));
        let bytes_v = emit(&sheet_visible);
        let text_v = String::from_utf8(bytes_v).unwrap();
        assert!(
            text_v.contains("<x:Visible/>"),
            "visible=true needs <x:Visible/>: {text_v}"
        );

        // visible=false
        let mut sheet_hidden = Worksheet::new("S");
        sheet_hidden
            .comments
            .insert("A1".to_string(), make_comment(false, None, None));
        let bytes_h = emit(&sheet_hidden);
        let text_h = String::from_utf8(bytes_h).unwrap();
        assert!(
            !text_h.contains("<x:Visible"),
            "visible=false must omit <x:Visible: {text_h}"
        );
    }

    // 5. Row and column are 0-based
    #[test]
    fn row_column_are_zero_based() {
        let mut sheet = Worksheet::new("S");
        // C3 = row 3, col 3 (1-based) → <x:Row>2</x:Row>, <x:Column>2</x:Column>
        sheet
            .comments
            .insert("C3".to_string(), make_comment(false, None, None));
        let bytes = emit(&sheet);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<x:Row>2</x:Row>"), "row 0-based: {text}");
        assert!(
            text.contains("<x:Column>2</x:Column>"),
            "col 0-based: {text}"
        );
    }

    // 6. Width and height flow into style
    #[test]
    fn width_height_flow_into_style() {
        let mut sheet = Worksheet::new("S");
        sheet.comments.insert(
            "A1".to_string(),
            make_comment(false, Some(150.0), Some(80.0)),
        );
        let bytes = emit(&sheet);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("width:150pt"), "custom width: {text}");
        assert!(text.contains("height:80pt"), "custom height: {text}");
    }

    // 7. Well-formed under quick_xml with multiple comments
    #[test]
    fn well_formed_under_quick_xml() {
        let mut sheet = Worksheet::new("S");
        sheet
            .comments
            .insert("A1".to_string(), make_comment(true, None, None));
        sheet.comments.insert(
            "B2".to_string(),
            make_comment(false, Some(120.0), Some(60.0)),
        );
        sheet
            .comments
            .insert("C3".to_string(), make_comment(true, None, Some(45.0)));

        let bytes = emit(&sheet);
        assert!(!bytes.is_empty());
        parse_ok(&bytes);
    }

    // 8. R1 regression: anchor for cell A1 must be cell-relative.
    #[test]
    fn anchor_for_a1_is_cell_relative() {
        let (cl, ol, rt, ot, cr, or_, rb, ob) = compute_anchor(0, 0);
        // colLeft=1 (col0+1), rowTop=0 (saturating_sub clamps), colRight=3, rowBottom=3
        assert_eq!(
            (cl, ol, rt, ot, cr, or_, rb, ob),
            (1, 15, 0, 10, 3, 15, 3, 4)
        );
    }

    // 9. R1 regression: anchor for D5 must shift with the cell — matches oracle.
    #[test]
    fn anchor_for_d5_matches_oracle() {
        // D5 is (row0=4, col0=3). Oracle emits "4, 15, 3, 10, 6, 15, 7, 4".
        let (cl, ol, rt, ot, cr, or_, rb, ob) = compute_anchor(4, 3);
        assert_eq!(
            (cl, ol, rt, ot, cr, or_, rb, ob),
            (4, 15, 3, 10, 6, 15, 7, 4)
        );
    }

    // 10. R1 regression: margin origin must shift with the cell — matches oracle.
    #[test]
    fn margin_for_d5_matches_oracle() {
        // Oracle for D5 (row0=4, col0=3): margin-left=203.25pt, margin-top=52.5pt.
        let (ml, mt) = compute_margin(4, 3);
        assert!(
            (ml - 203.25).abs() < 1e-6,
            "margin-left expected 203.25 got {ml}"
        );
        assert!(
            (mt - 52.5).abs() < 1e-6,
            "margin-top expected 52.5 got {mt}"
        );
    }

    // 11. R1 regression: anchor for Z100 (col0=25, row0=99) shifts correctly.
    #[test]
    fn anchor_for_z100_far_cell() {
        let (cl, ol, rt, ot, cr, or_, rb, ob) = compute_anchor(99, 25);
        assert_eq!(
            (cl, ol, rt, ot, cr, or_, rb, ob),
            (26, 15, 98, 10, 28, 15, 102, 4)
        );
    }

    // 12. R1 regression: emit() output for D5 contains the cell-relative anchor.
    #[test]
    fn emit_d5_contains_cell_relative_anchor_and_margin() {
        let mut sheet = Worksheet::new("S");
        sheet
            .comments
            .insert("D5".to_string(), make_comment(false, None, None));
        let bytes = emit(&sheet);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            text.contains("<x:Anchor>4, 15, 3, 10, 6, 15, 7, 4</x:Anchor>"),
            "D5 anchor cell-relative: {text}"
        );
        assert!(
            text.contains("margin-left:203.25pt") && text.contains("margin-top:52.5pt"),
            "D5 margin cell-relative: {text}"
        );
    }

    // 13. D3: margin honors per-column widths when sheet has <cols> overrides.
    #[test]
    fn margin_left_uses_per_column_widths() {
        use crate::model::worksheet::Column;

        // Sheet with column 1 set to width=4 (max-digit-width units),
        // and a comment at B1 (col0=1). The legacy fixed-width math
        // would put margin-left at 1 * 48 + 59.25 = 107.25pt. With
        // the override, column 1 contributes col_units_to_pt(4) ≈ 32pt,
        // so margin-left = 59.25 + 32 = 91.25pt.
        let mut sheet = Worksheet::new("S");
        sheet.set_column(
            1,
            Column {
                width: Some(4.0),
                ..Default::default()
            },
        );
        sheet
            .comments
            .insert("B1".to_string(), make_comment(false, None, None));

        let (ml, _mt) = compute_margin_with_widths(&sheet, 0, 1);
        let expected = ORIGIN_LEFT_PT + col_units_to_pt(4.0);
        assert!(
            (ml - expected).abs() < 1e-6,
            "margin-left expected {expected} got {ml}"
        );

        // emit() should reflect the same margin in the rendered output.
        let bytes = emit(&sheet);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            text.contains(&format!("margin-left:{}pt", expected)),
            "rendered margin-left should match per-column math: {text}"
        );
    }

    // 14. D3: empty <cols> map keeps the legacy default-width math
    // byte-stable so existing fixtures don't break.
    #[test]
    fn empty_cols_map_uses_legacy_default_math() {
        let mut sheet = Worksheet::new("S");
        sheet
            .comments
            .insert("D5".to_string(), make_comment(false, None, None));
        let (ml, mt) = compute_margin_with_widths(&sheet, 4, 3);
        // 3 * 48 + 59.25 = 203.25; 4 * 12.75 + 1.5 = 52.5
        assert!((ml - 203.25).abs() < 1e-6, "ml {ml}");
        assert!((mt - 52.5).abs() < 1e-6, "mt {mt}");
    }

    // 15. D3 parity: matches the patcher's behavior when only some
    // columns to the left of the comment have overrides — the rest
    // contribute the OOXML default.
    #[test]
    fn mixed_overrides_use_default_for_uncustomized_cols() {
        use crate::model::worksheet::Column;

        let mut sheet = Worksheet::new("S");
        // Column 1 has a custom width; column 2 does not.
        sheet.set_column(
            1,
            Column {
                width: Some(4.0),
                ..Default::default()
            },
        );
        sheet
            .comments
            .insert("D1".to_string(), make_comment(false, None, None));
        // D1 is col0=3 → walks columns 1,2,3 (1-based).
        // col1 = col_units_to_pt(4)
        // col2 = COL_WIDTH_PT
        // col3 = COL_WIDTH_PT
        let expected = ORIGIN_LEFT_PT + col_units_to_pt(4.0) + COL_WIDTH_PT + COL_WIDTH_PT;
        let (ml, _) = compute_margin_with_widths(&sheet, 0, 3);
        assert!(
            (ml - expected).abs() < 1e-6,
            "margin-left expected {expected} got {ml}"
        );
    }
}
