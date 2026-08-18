//! `<dimension>` emitter for worksheet XML.

use crate::model::cell::WriteCellValue;
use crate::model::worksheet::Worksheet;
use crate::refs;

/// Compute populated-cell bounds and emit `<dimension ref="..."/>`.
///
/// Blank cells without a style do not contribute to the sheet dimension,
/// matching the native writer's cell-emission behavior. Styled blanks do
/// count because they still materialize as `<c .../>` elements.
pub fn emit(out: &mut String, sheet: &Worksheet) {
    // Streaming write_only sheets keep `rows` empty and track the
    // bounding box on the StreamingSheet itself. Min row is implicitly
    // 1 because openpyxl's write_only API auto-numbers from row 1.
    if let Some(stream) = sheet.streaming.as_ref() {
        let max_row = stream.row_count();
        let max_col = stream.max_col();
        if max_row == 0 || max_col == 0 {
            out.push_str("<dimension ref=\"A1\"/>");
        } else {
            let range = refs::format_range((1, 1), (max_row, max_col));
            out.push_str(&format!("<dimension ref=\"{}\"/>", range));
        }
        return;
    }

    let mut min_row = u32::MAX;
    let mut max_row = 0u32;
    let mut min_col = u32::MAX;
    let mut max_col = 0u32;

    for (&row_num, row) in &sheet.rows {
        for (&col_num, cell) in &row.cells {
            if matches!(cell.value, WriteCellValue::Blank) && cell.style_id.is_none() {
                continue;
            }
            min_row = min_row.min(row_num);
            max_row = max_row.max(row_num);
            min_col = min_col.min(col_num);
            max_col = max_col.max(col_num);
        }
        // Rows with only custom attrs do not expand the dimension; OOXML
        // dimension represents the range of materialized cell data.
    }

    if max_row == 0 {
        out.push_str("<dimension ref=\"A1\"/>");
    } else {
        let range = refs::format_range((min_row, min_col), (max_row, max_col));
        out.push_str(&format!("<dimension ref=\"{}\"/>", range));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::cell::WriteCellValue;

    #[test]
    fn empty_sheet_defaults_to_a1() {
        let sheet = Worksheet::new("S");
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(out, "<dimension ref=\"A1\"/>");
    }

    #[test]
    fn unstyled_blank_cells_do_not_expand_dimension() {
        let mut sheet = Worksheet::new("S");
        sheet.write_cell(10, 5, WriteCellValue::Blank, None);
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(out, "<dimension ref=\"A1\"/>");
    }

    #[test]
    fn populated_cells_expand_dimension_to_bounding_range() {
        let mut sheet = Worksheet::new("S");
        sheet.write_cell(1, 1, WriteCellValue::Number(1.0), None);
        sheet.write_cell(10, 4, WriteCellValue::Number(2.0), None);
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(out, "<dimension ref=\"A1:D10\"/>");
    }

    #[test]
    fn styled_blank_cells_expand_dimension() {
        let mut sheet = Worksheet::new("S");
        sheet.write_cell(10, 5, WriteCellValue::Blank, Some(3));
        let mut out = String::new();

        emit(&mut out, &sheet);

        assert_eq!(out, "<dimension ref=\"E10\"/>");
    }
}
