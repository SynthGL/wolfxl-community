//! Shared string table (SST) parser for `xl/sharedStrings.xml`.
//!
//! The SST maps integer indices to string values.  Cell elements with `t="s"`
//! store the index in `<v>`, so we need the table to resolve those back to text
//! when patching existing cells.
//!
//! WolfXL writes **inline strings** (`t="str"`) for new/modified cells, so we
//! never need to *append* to the SST — only read it.

use quick_xml::events::Event;
use quick_xml::Reader as XmlReader;

/// Parse `xl/sharedStrings.xml` into an ordered `Vec<String>`.
///
/// Each `<si>` element becomes one entry.  Plain text lives in `<si><t>`;
/// rich-text runs live in `<si><r><t>`.  Rich-text runs are concatenated.
pub fn parse_shared_strings(xml: &str) -> Vec<String> {
    let mut reader = XmlReader::from_str(xml);
    reader.config_mut().trim_text(false);
    let mut buf: Vec<u8> = Vec::new();

    let mut strings: Vec<String> = Vec::new();
    let mut current: Option<String> = None;
    let mut in_t = false; // inside a <t> element

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let tag = e.local_name();
                if tag.as_ref() == b"si" {
                    current = Some(String::new());
                } else if tag.as_ref() == b"t" {
                    in_t = true;
                }
            }
            Ok(Event::End(e)) => {
                let tag = e.local_name();
                if tag.as_ref() == b"si" {
                    strings.push(current.take().unwrap_or_default());
                } else if tag.as_ref() == b"t" {
                    in_t = false;
                }
            }
            Ok(Event::Text(e)) => {
                if in_t {
                    if let Some(ref mut s) = current {
                        if let Ok(text) = e.unescape() {
                            s.push_str(&text);
                        }
                    }
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }

    strings
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_plain_strings() {
        let xml = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3">
  <si><t>Hello</t></si>
  <si><t>World</t></si>
  <si><t>Test 123</t></si>
</sst>"#;
        let result = parse_shared_strings(xml);
        assert_eq!(result, vec!["Hello", "World", "Test 123"]);
    }

    #[test]
    fn test_rich_text_runs() {
        let xml = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" uniqueCount="1">
  <si>
    <r><rPr><b/></rPr><t>Bold</t></r>
    <r><t> Normal</t></r>
  </si>
</sst>"#;
        let result = parse_shared_strings(xml);
        assert_eq!(result, vec!["Bold Normal"]);
    }

    #[test]
    fn test_empty_sst() {
        let xml = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="0" uniqueCount="0">
</sst>"#;
        let result = parse_shared_strings(xml);
        assert!(result.is_empty());
    }

    #[test]
    fn test_mixed_plain_and_rich() {
        let xml = r#"<sst count="3" uniqueCount="3">
  <si><t>Plain</t></si>
  <si><r><t>Rich</t></r><r><t> Text</t></r></si>
  <si><t>Also plain</t></si>
</sst>"#;
        let result = parse_shared_strings(xml);
        assert_eq!(result, vec!["Plain", "Rich Text", "Also plain"]);
    }

    #[test]
    fn test_xml_entities() {
        let xml = r#"<sst count="1" uniqueCount="1">
  <si><t>A &amp; B &lt; C</t></si>
</sst>"#;
        let result = parse_shared_strings(xml);
        assert_eq!(result, vec!["A & B < C"]);
    }

    #[test]
    fn test_empty_string_entry() {
        let xml = r#"<sst count="2" uniqueCount="2">
  <si><t></t></si>
  <si><t>After empty</t></si>
</sst>"#;
        let result = parse_shared_strings(xml);
        assert_eq!(result, vec!["", "After empty"]);
    }
}
