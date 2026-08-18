//! `<mergeCells>` emitter for worksheet XML.

use crate::model::worksheet::Worksheet;
use crate::refs;

/// Emit `<mergeCells count="N">…</mergeCells>`.
///
/// The ranges are sorted by top-left coordinate to keep worksheet XML
/// deterministic even when merges were registered in a different order.
pub fn emit(out: &mut String, sheet: &Worksheet) {
    let mut merges = sheet.merges.clone();
    merges.sort_by(|a, b| a.top_row.cmp(&b.top_row).then(a.left_col.cmp(&b.left_col)));

    out.push_str(&format!("<mergeCells count=\"{}\">", merges.len()));

    for merge in &merges {
        let range = refs::format_range(
            (merge.top_row, merge.left_col),
            (merge.bottom_row, merge.right_col),
        );
        out.push_str(&format!("<mergeCell ref=\"{}\"/>", range));
    }

    out.push_str("</mergeCells>");
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::intern::SstBuilder;
    use crate::model::format::StylesBuilder;
    use crate::model::worksheet::Merge;
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn parse_ok(text: &str) {
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

    #[test]
    fn merges_sorted_ascending() {
        let mut sheet = Worksheet::new("S");
        // Add in reverse order.
        sheet.merge(Merge {
            top_row: 3,
            left_col: 3,
            bottom_row: 4,
            right_col: 4,
        });
        sheet.merge(Merge {
            top_row: 1,
            left_col: 1,
            bottom_row: 2,
            right_col: 2,
        });

        let mut text = String::new();
        emit(&mut text, &sheet);
        parse_ok(&text);

        let pos_a1 = text.find("ref=\"A1:B2\"").expect("A1:B2");
        let pos_c3 = text.find("ref=\"C3:D4\"").expect("C3:D4");
        assert!(pos_a1 < pos_c3, "A1:B2 should come before C3:D4: {text}");
    }

    #[test]
    fn merges_element_omitted_when_empty() {
        let sheet = Worksheet::new("S");
        let mut sst = SstBuilder::default();
        let styles = StylesBuilder::default();
        let bytes = crate::emit::sheet_xml::emit(&sheet, 0, &mut sst, &styles);
        let text = String::from_utf8(bytes).unwrap();

        assert!(
            !text.contains("<mergeCells"),
            "no mergeCells when none: {text}"
        );
    }
}
