//! Cell comments (what Excel calls "Notes" since 365).
//!
//! Comments live in two OOXML parts simultaneously:
//!
//! - `xl/comments/commentsN.xml` — the text + author metadata
//! - `xl/drawings/vmlDrawingN.vml` — the floating yellow rectangle shape
//!
//! Plus three relationships per sheet that links them. The Wave 3 emitter
//! modules ([`crate::emit::comments_xml`] and [`crate::emit::drawings_vml`])
//! handle the cross-referencing; this module is just data.

use indexmap::IndexMap;

/// One comment attached to a cell.
#[derive(Debug, Clone, PartialEq)]
pub struct Comment {
    /// The rich text body. Stored as plain text in the MVP — rich-text
    /// runs are out of scope per the plan.
    pub text: String,

    /// Which author wrote this comment. References the workbook-scope
    /// [`CommentAuthorTable`] by index.
    pub author_id: u32,

    /// Optional visible-box sizing. `None` means Excel picks a default.
    pub width_pt: Option<f64>,
    pub height_pt: Option<f64>,

    /// Whether the comment box is shown pinned or only on hover.
    pub visible: bool,
}

/// A comment author. Authors are deduped at the workbook level via
/// [`CommentAuthorTable::intern`]. Insertion order is preserved by the
/// `IndexMap` — this fixes the rust_xlsxwriter BTreeMap bug that
/// corrupted mixed-author workbooks.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct CommentAuthor {
    pub name: String,
}

#[derive(Debug, Clone, Default)]
pub struct CommentAuthorTable {
    /// Insertion-ordered author registry. The `u32` value is the stable
    /// author id referenced from [`Comment::author_id`].
    authors: IndexMap<CommentAuthor, u32>,
}

impl CommentAuthorTable {
    pub fn intern(&mut self, name: impl Into<String>) -> u32 {
        let key = CommentAuthor { name: name.into() };
        if let Some(&id) = self.authors.get(&key) {
            return id;
        }
        let id = self.authors.len() as u32;
        self.authors.insert(key, id);
        id
    }

    pub fn iter(&self) -> impl Iterator<Item = (&CommentAuthor, u32)> {
        self.authors.iter().map(|(author, id)| (author, *id))
    }

    pub fn len(&self) -> usize {
        self.authors.len()
    }

    pub fn is_empty(&self) -> bool {
        self.authors.is_empty()
    }
}
