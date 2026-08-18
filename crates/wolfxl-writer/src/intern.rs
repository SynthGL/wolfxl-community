//! Shared string table (SST) builder.
//!
//! Every string value in the workbook is routed through this table on
//! insertion. The sheet emitter writes the *index* (`<v>5</v>`) into each
//! `<c t="s">` cell and `sharedStrings.xml` is emitted last — after all
//! sheets have streamed — so the table reflects every string that was
//! actually used.
//!
//! # Why always use SST
//!
//! OOXML allows both inline strings (`<c t="inlineStr">`) and SST-referenced
//! strings (`<c t="s">`). Most real-world files use SST exclusively because
//! repeated strings (column headers, category names) compress from O(N*L)
//! to O(U + N*log(U)) — N rows, L avg length, U distinct strings. Always
//! interning means a predictable emitter and cleaner diffs against openpyxl.

use indexmap::IndexMap;

/// Deduplicating string table.
///
/// Insertion order is preserved (`IndexMap`) so that re-running the same
/// workbook build produces the same `sharedStrings.xml` byte-for-byte.
#[derive(Debug, Clone, Default)]
pub struct SstBuilder {
    strings: IndexMap<String, u32>,
    /// Total references (not distinct count). Excel likes the `count="…"`
    /// attribute on `<sst>` to be the total reference count, while
    /// `uniqueCount="…"` is the distinct count.
    total_refs: u32,
}

impl SstBuilder {
    /// Intern a string and return its index.
    pub fn intern(&mut self, s: &str) -> u32 {
        self.total_refs += 1;
        if let Some(&id) = self.strings.get(s) {
            return id;
        }
        let id = self.strings.len() as u32;
        self.strings.insert(s.to_string(), id);
        id
    }

    pub fn is_empty(&self) -> bool {
        self.strings.is_empty()
    }

    pub fn unique_count(&self) -> u32 {
        self.strings.len() as u32
    }

    pub fn total_count(&self) -> u32 {
        self.total_refs
    }

    /// Iterator over (index, string) pairs in insertion order.
    pub fn iter(&self) -> impl Iterator<Item = (u32, &str)> {
        self.strings.iter().map(|(s, &id)| (id, s.as_str()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repeated_intern_returns_same_index() {
        let mut b = SstBuilder::default();
        assert_eq!(b.intern("hello"), 0);
        assert_eq!(b.intern("world"), 1);
        assert_eq!(b.intern("hello"), 0);
        assert_eq!(b.unique_count(), 2);
        assert_eq!(b.total_count(), 3);
    }

    #[test]
    fn insertion_order_is_preserved() {
        let mut b = SstBuilder::default();
        b.intern("beta");
        b.intern("alpha");
        b.intern("gamma");
        let collected: Vec<&str> = b.iter().map(|(_, s)| s).collect();
        assert_eq!(collected, vec!["beta", "alpha", "gamma"]);
    }
}
