//! `xl/comments/comments{N}.xml` emitter — multi-author comments with
//! insertion-ordered authors (fixes the rust_xlsxwriter BTreeMap bug).
//! Wave 3A.

use crate::model::comment::CommentAuthorTable;
use crate::model::worksheet::Worksheet;
use crate::xml_escape;

pub fn emit(sheet: &Worksheet, authors: &CommentAuthorTable) -> Vec<u8> {
    if sheet.comments.is_empty() {
        return Vec::new();
    }

    let mut out = String::with_capacity(2048);

    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str("<comments xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">");

    // Always emit the full <authors> block — authorId indices are workbook-global.
    out.push_str("<authors>");
    for (author, _id) in authors.iter() {
        out.push_str("<author>");
        out.push_str(&xml_escape::text(&author.name));
        out.push_str("</author>");
    }
    out.push_str("</authors>");

    out.push_str("<commentList>");
    for (cell_ref, comment) in &sheet.comments {
        out.push_str(&format!(
            "<comment ref=\"{}\" authorId=\"{}\">",
            xml_escape::attr(cell_ref),
            comment.author_id,
        ));
        out.push_str("<text><t>");
        out.push_str(&xml_escape::text(&comment.text));
        out.push_str("</t></text>");
        out.push_str("</comment>");
    }
    out.push_str("</commentList>");

    out.push_str("</comments>");

    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::comment::{Comment, CommentAuthorTable};
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

    fn make_author_table(names: &[&str]) -> CommentAuthorTable {
        let mut table = CommentAuthorTable::default();
        for name in names {
            table.intern(*name);
        }
        table
    }

    fn make_comment(author_id: u32, text: &str) -> Comment {
        Comment {
            text: text.to_string(),
            author_id,
            width_pt: None,
            height_pt: None,
            visible: false,
        }
    }

    // 1. Empty sheet returns empty bytes
    #[test]
    fn empty_sheet_returns_empty_bytes() {
        let sheet = Worksheet::new("S");
        let authors = CommentAuthorTable::default();
        let result = emit(&sheet, &authors);
        assert!(
            result.is_empty(),
            "expected empty Vec, got {} bytes",
            result.len()
        );
    }

    // 2. Single comment single author well-formed
    #[test]
    fn single_comment_single_author_well_formed() {
        let mut sheet = Worksheet::new("S");
        sheet
            .comments
            .insert("A1".to_string(), make_comment(0, "the text"));
        let mut authors = make_author_table(&["Alice"]);
        let _ = authors.intern("Alice"); // already interned, just verify dedup

        let bytes = emit(&sheet, &authors);
        assert!(!bytes.is_empty());
        parse_ok(&bytes);

        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<authors>"), "has <authors>: {text}");
        assert!(
            text.contains("<author>Alice</author>"),
            "author Alice: {text}"
        );
        assert!(text.contains("</authors>"), "has </authors>: {text}");
        assert!(
            text.contains("<comment ref=\"A1\" authorId=\"0\">"),
            "comment ref: {text}"
        );
        assert!(text.contains("<t>the text</t>"), "comment text: {text}");
    }

    // 3. Three authors insertion order — NOT alphabetical
    #[test]
    fn three_authors_insertion_order() {
        let mut sheet = Worksheet::new("S");
        let mut authors = CommentAuthorTable::default();
        let bob_id = authors.intern("Bob");
        let alice_id = authors.intern("Alice");
        let charlie_id = authors.intern("Charlie");

        sheet
            .comments
            .insert("A1".to_string(), make_comment(bob_id, "from bob"));
        sheet
            .comments
            .insert("B2".to_string(), make_comment(alice_id, "from alice"));
        sheet
            .comments
            .insert("C3".to_string(), make_comment(charlie_id, "from charlie"));

        let bytes = emit(&sheet, &authors);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();

        // Exact authors block — insertion order Bob, Alice, Charlie (NOT alphabetical)
        assert!(
            text.contains("<authors><author>Bob</author><author>Alice</author><author>Charlie</author></authors>"),
            "insertion order Bob/Alice/Charlie: {text}"
        );
    }

    // 4. Comment text XML escape
    #[test]
    fn comment_text_xml_escape() {
        let mut sheet = Worksheet::new("S");
        sheet
            .comments
            .insert("A1".to_string(), make_comment(0, "<b> & >"));
        let authors = make_author_table(&["Author"]);

        let bytes = emit(&sheet, &authors);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();

        assert!(
            text.contains("&lt;b&gt; &amp; &gt;"),
            "escaped text: {text}"
        );
    }

    // 5. Author name XML escape
    #[test]
    fn author_name_xml_escape() {
        let mut sheet = Worksheet::new("S");
        sheet
            .comments
            .insert("A1".to_string(), make_comment(0, "note"));
        let authors = make_author_table(&["R&D Team"]);

        let bytes = emit(&sheet, &authors);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();

        assert!(
            text.contains("<author>R&amp;D Team</author>"),
            "escaped author: {text}"
        );
    }

    // 6. Multiple comments in A1 order (BTreeMap natural order)
    #[test]
    fn multiple_comments_in_a1_order() {
        let mut sheet = Worksheet::new("S");
        // Insert in non-A1 order — BTreeMap will sort them
        sheet
            .comments
            .insert("Z3".to_string(), make_comment(0, "last"));
        sheet
            .comments
            .insert("A1".to_string(), make_comment(0, "first"));
        sheet
            .comments
            .insert("B2".to_string(), make_comment(0, "middle"));

        let authors = make_author_table(&["Author"]);
        let bytes = emit(&sheet, &authors);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();

        let pos_a1 = text.find("ref=\"A1\"").expect("A1 comment");
        let pos_b2 = text.find("ref=\"B2\"").expect("B2 comment");
        let pos_z3 = text.find("ref=\"Z3\"").expect("Z3 comment");
        assert!(pos_a1 < pos_b2, "A1 before B2: {text}");
        assert!(pos_b2 < pos_z3, "B2 before Z3: {text}");
    }

    // 7. Well-formed under quick_xml with 5+ comments and 3 authors
    #[test]
    fn well_formed_under_quick_xml() {
        let mut sheet = Worksheet::new("S");
        let mut authors = CommentAuthorTable::default();
        let a_id = authors.intern("Alice");
        let b_id = authors.intern("Bob");
        let c_id = authors.intern("Charlie");

        sheet
            .comments
            .insert("A1".to_string(), make_comment(a_id, "note1"));
        sheet
            .comments
            .insert("B2".to_string(), make_comment(b_id, "note2"));
        sheet
            .comments
            .insert("C3".to_string(), make_comment(c_id, "note3"));
        sheet
            .comments
            .insert("D4".to_string(), make_comment(a_id, "note4"));
        sheet
            .comments
            .insert("E5".to_string(), make_comment(b_id, "note5"));

        let bytes = emit(&sheet, &authors);
        assert!(!bytes.is_empty());
        parse_ok(&bytes);
    }
}
