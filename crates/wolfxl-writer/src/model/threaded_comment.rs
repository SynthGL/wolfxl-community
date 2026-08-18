//! Threaded comments (Excel 365 conversational notes) — RFC-068 / G08.
//!
//! Threaded comments live in three OOXML parts:
//!
//! - `xl/threadedComments/threadedCommentsN.xml` (per sheet)  — the real
//!   payload (text + GUID + author + timestamp)
//! - `xl/persons/personList.xml` (workbook-scoped) — display-name lookup
//!   for `personId` references inside the threaded payload
//! - `xl/comments/commentsN.xml` (per sheet, existing) — receives a
//!   placeholder `[Threaded comment]` legacy entry plus `<extLst>`
//!   back-reference so older Excel versions still see *something*
//!
//! This module is just data; the emitters in [`crate::emit::threaded_comments_xml`]
//! and [`crate::emit::persons_xml`] consume it.

/// One person referenced by threaded comments.
///
/// `id` is a brace-wrapped uppercase GUID (e.g. `"{8B0E8A60-...}"`).
/// `provider_id` defaults to the literal string `"None"` when no identity
/// provider is attached — Excel's own convention.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Person {
    pub display_name: String,
    pub id: String,
    pub user_id: String,
    pub provider_id: String,
}

/// Workbook-scoped person registry.
///
/// Insertion order is preserved so two saves of the same workbook produce
/// identical bytes. Deduplication is the responsibility of the caller (the
/// Python `PersonRegistry` already enforces idempotency on
/// `(user_id, provider_id)`).
#[derive(Debug, Clone, Default)]
pub struct PersonTable {
    persons: Vec<Person>,
}

impl PersonTable {
    pub fn push(&mut self, person: Person) {
        self.persons.push(person);
    }

    pub fn iter(&self) -> impl Iterator<Item = &Person> {
        self.persons.iter()
    }

    pub fn len(&self) -> usize {
        self.persons.len()
    }

    pub fn is_empty(&self) -> bool {
        self.persons.is_empty()
    }

    pub fn contains_id(&self, id: &str) -> bool {
        self.persons.iter().any(|p| p.id == id)
    }
}

/// One threaded comment payload — either a top-level thread or a reply.
///
/// The shape mirrors OOXML: replies are flat siblings linked to their parent
/// by `parent_id` GUID, *not* nested under the parent. Top-level threads have
/// `parent_id == None`.
#[derive(Debug, Clone, PartialEq)]
pub struct ThreadedComment {
    /// Brace-wrapped uppercase GUID (e.g. `"{A1B2-...}"`).
    pub id: String,

    /// A1-style cell reference (e.g. `"A1"`). Top-level + all replies for the
    /// same thread share the same `cell_ref`.
    pub cell_ref: String,

    /// `personId` reference into the workbook's [`PersonTable`].
    pub person_id: String,

    /// ISO 8601 timestamp without timezone, with millisecond precision
    /// (e.g. `"2024-09-12T15:31:01.42"`). Excel writes 2 fractional digits.
    pub created: String,

    /// `Some(parent_id)` for replies; `None` for top-level threads.
    pub parent_id: Option<String>,

    /// Plain-text body. Rich text + @-mentions are out of scope per RFC-068 §8.
    pub text: String,

    /// Resolved/done flag. Round-tripped but not enforced.
    pub done: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn person(name: &str, id: &str) -> Person {
        Person {
            display_name: name.to_string(),
            id: id.to_string(),
            user_id: String::new(),
            provider_id: "None".to_string(),
        }
    }

    #[test]
    fn person_table_preserves_insertion_order() {
        let mut table = PersonTable::default();
        table.push(person("Alice", "{A}"));
        table.push(person("Bob", "{B}"));
        table.push(person("Charlie", "{C}"));

        let names: Vec<_> = table.iter().map(|p| p.display_name.as_str()).collect();
        assert_eq!(names, ["Alice", "Bob", "Charlie"]);
        assert_eq!(table.len(), 3);
    }

    #[test]
    fn person_table_contains_id_lookup() {
        let mut table = PersonTable::default();
        table.push(person("Alice", "{A}"));
        assert!(table.contains_id("{A}"));
        assert!(!table.contains_id("{B}"));
    }

    #[test]
    fn person_table_is_empty_by_default() {
        let table = PersonTable::default();
        assert!(table.is_empty());
        assert_eq!(table.len(), 0);
    }

    #[test]
    fn threaded_comment_top_level_has_no_parent() {
        let tc = ThreadedComment {
            id: "{A1}".into(),
            cell_ref: "A1".into(),
            person_id: "{P}".into(),
            created: "2024-09-12T15:31:01.42".into(),
            parent_id: None,
            text: "topic".into(),
            done: false,
        };
        assert!(tc.parent_id.is_none());
    }

    #[test]
    fn threaded_comment_reply_has_parent() {
        let reply = ThreadedComment {
            id: "{B1}".into(),
            cell_ref: "A1".into(),
            person_id: "{P}".into(),
            created: "2024-09-12T15:33:00.00".into(),
            parent_id: Some("{A1}".into()),
            text: "reply".into(),
            done: false,
        };
        assert_eq!(reply.parent_id.as_deref(), Some("{A1}"));
    }
}
