//! `xl/threadedComments/threadedComments{N}.xml` emitter — Excel 365
//! threaded payload (RFC-068 / G08).
//!
//! Each `<threadedComment>` carries the real text, GUID `id`, `personId`,
//! ISO timestamp `dT`, optional `parentId` for replies, and optional `done`
//! flag. Top-level threads and replies are flat siblings; the parent/child
//! relationship is by GUID, not by XML nesting.

use crate::model::comment::Comment;
use crate::model::threaded_comment::ThreadedComment;
use crate::model::workbook::Workbook;
use crate::xml_escape;

const NS: &str = "http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments";

/// Synthesize legacy-comment placeholders for every top-level threaded
/// comment in the workbook.
///
/// Excel 365's threaded-comment design pairs each top-level thread with a
/// legacy `<comment>` whose body is the literal `"[Threaded comment]"`
/// and whose `authorId` references a synthetic author of the form
/// `tc={threadGuid}`. That `tc=` author convention is how Excel matches a
/// legacy placeholder to its threaded payload.
///
/// This function runs before any emit pass so that:
///   1. The author table contains all `tc={guid}` entries (so authorIds
///      resolve at emit time).
///   2. Every sheet that has top-level threads also has a matching legacy
///      placeholder Comment at the same cell ref.
///
/// Idempotent — calling it twice produces the same workbook state.
/// No-op when the workbook has no threaded comments.
pub(crate) fn synthesize_legacy_placeholders(wb: &mut Workbook) {
    for sheet in &mut wb.sheets {
        for tc in &sheet.threaded_comments {
            // Only top-level threads need a legacy placeholder. Replies
            // share the parent's cell ref and the parent's placeholder.
            if tc.parent_id.is_some() {
                continue;
            }
            if sheet.comments.contains_key(&tc.cell_ref) {
                // Caller already supplied a legacy comment at this cell
                // (e.g., modify mode preserving a hand-authored placeholder).
                // Trust the caller's authorId — do not overwrite.
                continue;
            }
            let synthetic_author = format!("tc={}", tc.id);
            let author_id = wb.comment_authors.intern(synthetic_author);
            sheet.comments.insert(
                tc.cell_ref.clone(),
                Comment {
                    text: "[Threaded comment]".to_string(),
                    author_id,
                    width_pt: None,
                    height_pt: None,
                    visible: false,
                },
            );
        }
    }
}

pub fn emit(threads: &[ThreadedComment]) -> Vec<u8> {
    if threads.is_empty() {
        return Vec::new();
    }

    let mut out = String::with_capacity(2048);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!("<ThreadedComments xmlns=\"{NS}\">"));

    for tc in threads {
        out.push_str("<threadedComment");
        out.push_str(&format!(" ref=\"{}\"", xml_escape::attr(&tc.cell_ref)));
        out.push_str(&format!(" dT=\"{}\"", xml_escape::attr(&tc.created)));
        out.push_str(&format!(
            " personId=\"{}\"",
            xml_escape::attr(&tc.person_id)
        ));
        out.push_str(&format!(" id=\"{}\"", xml_escape::attr(&tc.id)));
        if let Some(parent) = &tc.parent_id {
            out.push_str(&format!(" parentId=\"{}\"", xml_escape::attr(parent)));
        }
        if tc.done {
            out.push_str(" done=\"1\"");
        }
        out.push('>');
        out.push_str("<text>");
        out.push_str(&xml_escape::text(&tc.text));
        out.push_str("</text>");
        out.push_str("</threadedComment>");
    }

    out.push_str("</ThreadedComments>");
    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
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

    fn make(id: &str, parent: Option<&str>, text: &str) -> ThreadedComment {
        ThreadedComment {
            id: id.into(),
            cell_ref: "A1".into(),
            person_id: "{P}".into(),
            created: "2024-09-12T15:31:01.42".into(),
            parent_id: parent.map(|s| s.into()),
            text: text.into(),
            done: false,
        }
    }

    #[test]
    fn empty_returns_empty_bytes() {
        let bytes = emit(&[]);
        assert!(bytes.is_empty());
    }

    #[test]
    fn single_top_level_thread_well_formed() {
        let threads = vec![make("{A}", None, "the text")];
        let bytes = emit(&threads);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            text.contains(
                "xmlns=\"http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments\""
            ),
            "namespace: {text}"
        );
        assert!(text.contains("ref=\"A1\""));
        assert!(text.contains("personId=\"{P}\""));
        assert!(text.contains("id=\"{A}\""));
        assert!(text.contains("<text>the text</text>"));
        assert!(
            !text.contains("parentId="),
            "top-level must not emit parentId: {text}"
        );
        assert!(
            !text.contains("done=\"1\""),
            "default done flag suppressed: {text}"
        );
    }

    #[test]
    fn reply_emits_parent_id_attribute() {
        let threads = vec![
            make("{A}", None, "parent"),
            make("{B}", Some("{A}"), "reply"),
        ];
        let bytes = emit(&threads);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        let reply_pos = text.find("<text>reply</text>").expect("reply text present");
        let parent_attr = text.find("parentId=\"{A}\"").expect("parentId attr");
        assert!(parent_attr < reply_pos, "parentId precedes reply text");
    }

    #[test]
    fn done_flag_emits_when_true() {
        let mut tc = make("{A}", None, "topic");
        tc.done = true;
        let bytes = emit(&[tc]);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("done=\"1\""));
    }

    #[test]
    fn text_xml_escaped() {
        let bytes = emit(&[make("{A}", None, "<b> & \"hi\"")]);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        // Element text only needs `<`, `>`, and `&` escaped per the XML spec
        // (and `xml_escape::text` follows that). Quotes pass through.
        assert!(
            text.contains("<text>&lt;b&gt; &amp; \"hi\"</text>"),
            "escaped: {text}"
        );
    }

    #[test]
    fn synthesize_creates_placeholder_comment_with_tc_author() {
        let mut wb = Workbook::new();
        let mut sheet = Worksheet::new("S");
        sheet.threaded_comments.push(make("{TID}", None, "topic"));
        wb.add_sheet(sheet);

        synthesize_legacy_placeholders(&mut wb);

        let placeholder = wb.sheets[0]
            .comments
            .get("A1")
            .expect("placeholder Comment created at A1");
        assert_eq!(placeholder.text, "[Threaded comment]");

        // The author table should contain `tc={TID}` exactly once.
        let authors: Vec<_> = wb
            .comment_authors
            .iter()
            .map(|(a, id)| (a.name.clone(), id))
            .collect();
        assert_eq!(authors.len(), 1, "{authors:?}");
        assert_eq!(authors[0].0, "tc={TID}");
        assert_eq!(placeholder.author_id, authors[0].1);
    }

    #[test]
    fn synthesize_only_for_top_level_not_replies() {
        let mut wb = Workbook::new();
        let mut sheet = Worksheet::new("S");
        sheet.threaded_comments.push(make("{T1}", None, "parent"));
        sheet
            .threaded_comments
            .push(make("{T2}", Some("{T1}"), "reply"));
        wb.add_sheet(sheet);

        synthesize_legacy_placeholders(&mut wb);

        // Replies share the parent's cell ref — only one placeholder, one
        // synthetic author.
        assert_eq!(wb.sheets[0].comments.len(), 1);
        assert_eq!(wb.comment_authors.len(), 1);
    }

    #[test]
    fn synthesize_preserves_existing_legacy_comment() {
        let mut wb = Workbook::new();
        let mut sheet = Worksheet::new("S");
        // User supplied their own legacy Comment at A1.
        let alice = wb.comment_authors.intern("Alice");
        sheet.comments.insert(
            "A1".to_string(),
            Comment {
                text: "user-authored".to_string(),
                author_id: alice,
                width_pt: None,
                height_pt: None,
                visible: false,
            },
        );
        sheet.threaded_comments.push(make("{TID}", None, "thread"));
        wb.add_sheet(sheet);

        synthesize_legacy_placeholders(&mut wb);

        // The caller's legacy comment is preserved; no `tc=` author injected
        // because the cell already had a Comment.
        let preserved = wb.sheets[0].comments.get("A1").unwrap();
        assert_eq!(preserved.text, "user-authored");
        assert_eq!(preserved.author_id, alice);
        let names: Vec<_> = wb
            .comment_authors
            .iter()
            .map(|(a, _)| a.name.clone())
            .collect();
        assert!(!names.iter().any(|n| n.starts_with("tc=")), "{names:?}");
    }

    #[test]
    fn synthesize_is_idempotent() {
        let mut wb = Workbook::new();
        let mut sheet = Worksheet::new("S");
        sheet.threaded_comments.push(make("{TID}", None, "topic"));
        wb.add_sheet(sheet);

        synthesize_legacy_placeholders(&mut wb);
        let after_first = (wb.sheets[0].comments.len(), wb.comment_authors.len());
        synthesize_legacy_placeholders(&mut wb);
        let after_second = (wb.sheets[0].comments.len(), wb.comment_authors.len());
        assert_eq!(after_first, after_second);
    }

    #[test]
    fn multiple_threads_preserved_in_input_order() {
        let threads = vec![
            make("{A}", None, "first"),
            make("{B}", None, "second"),
            make("{C}", Some("{A}"), "reply-to-first"),
        ];
        let bytes = emit(&threads);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        let p_first = text.find("<text>first</text>").unwrap();
        let p_second = text.find("<text>second</text>").unwrap();
        let p_reply = text.find("<text>reply-to-first</text>").unwrap();
        assert!(p_first < p_second);
        assert!(p_second < p_reply);
    }
}
