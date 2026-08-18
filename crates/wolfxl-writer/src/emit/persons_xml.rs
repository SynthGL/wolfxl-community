//! `xl/persons/personList.xml` emitter — workbook-scope threaded-comment
//! person registry (RFC-068 / G08).
//!
//! Excel always uses the singular `personList.xml` filename; the part is
//! workbook-scoped, not sheet-scoped. Insertion order is preserved by
//! [`PersonTable`] so two saves of the same workbook produce identical
//! bytes.

use crate::model::threaded_comment::PersonTable;
use crate::xml_escape;

const NS: &str = "http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments";

pub fn emit(persons: &PersonTable) -> Vec<u8> {
    if persons.is_empty() {
        return Vec::new();
    }

    let mut out = String::with_capacity(512);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!("<personList xmlns=\"{NS}\">"));

    for p in persons.iter() {
        out.push_str("<person");
        out.push_str(&format!(
            " displayName=\"{}\"",
            xml_escape::attr(&p.display_name)
        ));
        out.push_str(&format!(" id=\"{}\"", xml_escape::attr(&p.id)));
        out.push_str(&format!(" userId=\"{}\"", xml_escape::attr(&p.user_id)));
        out.push_str(&format!(
            " providerId=\"{}\"",
            xml_escape::attr(&p.provider_id)
        ));
        out.push_str("/>");
    }

    out.push_str("</personList>");
    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::threaded_comment::Person;
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

    fn person(name: &str, id: &str, user_id: &str) -> Person {
        Person {
            display_name: name.to_string(),
            id: id.to_string(),
            user_id: user_id.to_string(),
            provider_id: "None".to_string(),
        }
    }

    #[test]
    fn empty_returns_empty_bytes() {
        let table = PersonTable::default();
        let bytes = emit(&table);
        assert!(bytes.is_empty());
    }

    #[test]
    fn single_person_well_formed() {
        let mut table = PersonTable::default();
        table.push(person("Alice", "{A}", "alice@example.com"));
        let bytes = emit(&table);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            text.contains(
                "xmlns=\"http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments\""
            ),
            "namespace: {text}"
        );
        assert!(text.contains("displayName=\"Alice\""));
        assert!(text.contains("id=\"{A}\""));
        assert!(text.contains("userId=\"alice@example.com\""));
        assert!(text.contains("providerId=\"None\""));
    }

    #[test]
    fn insertion_order_preserved() {
        let mut table = PersonTable::default();
        table.push(person("Bob", "{B}", ""));
        table.push(person("Alice", "{A}", ""));
        table.push(person("Charlie", "{C}", ""));
        let bytes = emit(&table);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        let p_bob = text.find("displayName=\"Bob\"").unwrap();
        let p_alice = text.find("displayName=\"Alice\"").unwrap();
        let p_charlie = text.find("displayName=\"Charlie\"").unwrap();
        assert!(p_bob < p_alice);
        assert!(p_alice < p_charlie);
    }

    #[test]
    fn display_name_xml_escaped() {
        let mut table = PersonTable::default();
        table.push(person("R&D \"Team\"", "{X}", ""));
        let bytes = emit(&table);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            text.contains("displayName=\"R&amp;D &quot;Team&quot;\""),
            "escaped: {text}"
        );
    }

    #[test]
    fn empty_user_id_emitted_as_empty_attribute() {
        let mut table = PersonTable::default();
        table.push(person("Anon", "{A}", ""));
        let bytes = emit(&table);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("userId=\"\""));
    }
}
