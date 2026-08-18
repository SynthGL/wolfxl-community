//! XML escape helpers shared by every emitter.
//!
//! Two entry points:
//!
//! - [`text`] — escape a value that will appear between element tags
//!   (`<t>…</t>`). Replaces `&`, `<`, `>`.
//! - [`attr`] — escape a value that will appear inside double-quoted
//!   attribute syntax (`foo="…"`). Replaces `&`, `<`, `>`, `"`, `'`.
//!
//! Both return owned `String`s so callers can compose with `format!`.
//! Neither touches control characters or does Unicode normalization —
//! OOXML allows raw UTF-8 throughout and Excel accepts it.
//!
//! # Why two functions
//!
//! An attribute escape inside a text node over-escapes (double quotes
//! are legal in element text). A text escape inside an attribute
//! under-escapes (bare double quote breaks the attribute). The helpers
//! refuse to merge because the call site always knows which context it's in.
//!
//! # History
//!
//! These were previously inlined in `emit/doc_props.rs` and `emit/rels.rs`
//! (named `xml_text_escape` and `xml_attr_escape` respectively). Wave 2
//! promoted them so the three new emitters (styles, sheet, SST) could
//! share one implementation.

/// Escape XML text-node content. For values between element tags.
///
/// Replaces `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`. Does not touch
/// `"` or `'` — those are legal inside element text.
pub fn text(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars() {
        match ch {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            _ => out.push(ch),
        }
    }
    out
}

/// Escape XML attribute-value content. For values inside `attr="…"`.
///
/// Replaces `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`, `"` → `&quot;`,
/// `'` → `&apos;`. The single-quote escape is strictly unneeded for
/// double-quoted attribute syntax, but including it is harmless and
/// matches what openpyxl emits.
pub fn attr(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars() {
        match ch {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&apos;"),
            _ => out.push(ch),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn text_escapes_only_three_chars() {
        assert_eq!(text("A & B < C > D"), "A &amp; B &lt; C &gt; D");
        // Quotes are unchanged inside element text.
        assert_eq!(
            text(r#"She said "hi" and it's fine"#),
            r#"She said "hi" and it's fine"#
        );
    }

    #[test]
    fn text_passes_through_unicode() {
        assert_eq!(text("日本語 🦀"), "日本語 🦀");
    }

    #[test]
    fn text_empty_input() {
        assert_eq!(text(""), "");
    }

    #[test]
    fn attr_escapes_all_five_chars() {
        assert_eq!(
            attr(r#"A & B < C > D " E ' F"#),
            "A &amp; B &lt; C &gt; D &quot; E &apos; F"
        );
    }

    #[test]
    fn attr_handles_url_with_query_string() {
        assert_eq!(
            attr("https://example.com/path?q=1&r=2"),
            "https://example.com/path?q=1&amp;r=2"
        );
    }

    #[test]
    fn attr_empty_input() {
        assert_eq!(attr(""), "");
    }

    #[test]
    fn text_ampersand_first_then_nested() {
        // Don't double-escape: `&amp;` must become `&amp;amp;` in literal
        // input text, not stay as `&amp;`.
        assert_eq!(text("&amp;"), "&amp;amp;");
    }
}
