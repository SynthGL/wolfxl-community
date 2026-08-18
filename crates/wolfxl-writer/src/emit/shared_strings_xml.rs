//! `xl/sharedStrings.xml` emitter. Wave 2C.
//!
//! Emits the final SST after all sheets have been streamed so that the
//! string-count attributes reflect what was actually referenced.
//!
//! # Whitespace preservation
//!
//! When a string starts or ends with a whitespace character, the `<t>` element
//! carries `xml:space="preserve"`. Without this attribute, XML parsers (and
//! Excel itself) are allowed to strip leading and trailing whitespace from text
//! content. The attribute is omitted for strings that only have internal
//! whitespace.

use crate::intern::SstBuilder;
use crate::xml_escape;

/// Emit `xl/sharedStrings.xml` as UTF-8 bytes.
///
/// Returns a self-closing `<sst …/>` when the table is empty.
pub fn emit(sst: &SstBuilder) -> Vec<u8> {
    const NS: &str = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";

    let mut out = String::with_capacity(512 + sst.unique_count() as usize * 32);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");

    if sst.is_empty() {
        out.push_str(&format!(
            "<sst xmlns=\"{NS}\" count=\"0\" uniqueCount=\"0\"/>"
        ));
        return out.into_bytes();
    }

    let total = sst.total_count();
    let unique = sst.unique_count();
    out.push_str(&format!(
        "<sst xmlns=\"{NS}\" count=\"{total}\" uniqueCount=\"{unique}\">"
    ));

    for (_idx, s) in sst.iter() {
        let needs_preserve = s.chars().next().is_some_and(|c| c.is_whitespace())
            || s.chars().next_back().is_some_and(|c| c.is_whitespace());

        let escaped = xml_escape::text(s);
        if needs_preserve {
            out.push_str(&format!("<si><t xml:space=\"preserve\">{escaped}</t></si>"));
        } else {
            out.push_str(&format!("<si><t>{escaped}</t></si>"));
        }
    }

    out.push_str("</sst>");
    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::intern::SstBuilder;
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn parse_ok(bytes: &[u8]) {
        let text = std::str::from_utf8(bytes).expect("utf8");
        let mut reader = Reader::from_str(text);
        reader.config_mut().check_end_names = true;
        let mut buf = Vec::new();
        loop {
            match reader.read_event_into(&mut buf) {
                Ok(Event::Eof) => break,
                Err(e) => panic!("parse error: {e}"),
                _ => (),
            }
            buf.clear();
        }
    }

    fn text_of(bytes: &[u8]) -> String {
        String::from_utf8(bytes.to_vec()).expect("utf8")
    }

    // 1. Empty SST emits a valid self-closing element.
    #[test]
    fn empty_sst_emits_valid_self_closing() {
        let sst = SstBuilder::default();
        let bytes = emit(&sst);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(text.contains("count=\"0\""), "missing count=\"0\": {text}");
        assert!(
            text.contains("uniqueCount=\"0\""),
            "missing uniqueCount=\"0\": {text}"
        );
        // Self-closing: no <si> elements.
        assert!(
            !text.contains("<si>"),
            "unexpected <si> in empty SST: {text}"
        );
    }

    // 2. Single string.
    #[test]
    fn single_string_interns_and_emits() {
        let mut sst = SstBuilder::default();
        sst.intern("hello");
        let bytes = emit(&sst);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(text.contains("count=\"1\""), "{text}");
        assert!(text.contains("uniqueCount=\"1\""), "{text}");
        assert!(text.contains("<si><t>hello</t></si>"), "{text}");
    }

    // 3. Duplicates affect count but not uniqueCount.
    #[test]
    fn duplicate_strings_dedup_in_unique_count() {
        let mut sst = SstBuilder::default();
        sst.intern("a");
        sst.intern("a");
        sst.intern("b");
        let bytes = emit(&sst);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(text.contains("count=\"3\""), "{text}");
        assert!(text.contains("uniqueCount=\"2\""), "{text}");
        // Two <si> elements (one per unique string), not three.
        let si_count = text.matches("<si>").count();
        assert_eq!(
            si_count, 2,
            "expected 2 <si> elements, got {si_count}: {text}"
        );
    }

    // 4. Leading/trailing whitespace triggers xml:space="preserve".
    #[test]
    fn whitespace_preserved_with_xml_space() {
        let mut sst = SstBuilder::default();
        sst.intern("  hi  ");
        let bytes = emit(&sst);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(
            text.contains("<t xml:space=\"preserve\">  hi  </t>"),
            "expected preserve attribute: {text}"
        );
    }

    // 5. Internal-only whitespace does NOT trigger xml:space="preserve".
    #[test]
    fn whitespace_only_not_leading_or_trailing_skips_preserve() {
        let mut sst = SstBuilder::default();
        sst.intern("a b");
        let bytes = emit(&sst);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(
            !text.contains("xml:space=\"preserve\""),
            "unexpected preserve attribute for internal-only space: {text}"
        );
        assert!(text.contains("<si><t>a b</t></si>"), "{text}");
    }

    // 6. XML entities are escaped in text nodes.
    #[test]
    fn xml_entities_escaped_in_text() {
        let mut sst = SstBuilder::default();
        sst.intern("A & B < C > \"quote\"");
        let bytes = emit(&sst);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(text.contains("A &amp; B &lt; C &gt;"), "{text}");
        // Double-quotes are legal in text nodes — they must NOT be escaped.
        assert!(
            text.contains("\"quote\""),
            "quotes should be literal in text: {text}"
        );
    }

    // 7. Unicode passes through as UTF-8.
    #[test]
    fn unicode_passes_through() {
        let mut sst = SstBuilder::default();
        sst.intern("日本語 🦀");
        let bytes = emit(&sst);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(text.contains("日本語 🦀"), "{text}");
    }

    // 8. Insertion order preserved.
    #[test]
    fn insertion_order_preserved_in_iter() {
        let mut sst = SstBuilder::default();
        sst.intern("beta");
        sst.intern("alpha");
        sst.intern("gamma");
        let bytes = emit(&sst);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        let beta_pos = text.find("beta").expect("beta not found");
        let alpha_pos = text.find("alpha").expect("alpha not found");
        let gamma_pos = text.find("gamma").expect("gamma not found");
        assert!(
            beta_pos < alpha_pos && alpha_pos < gamma_pos,
            "insertion order not preserved: beta={beta_pos}, alpha={alpha_pos}, gamma={gamma_pos}"
        );
    }
}
