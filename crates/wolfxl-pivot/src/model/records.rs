//! `pivotCacheRecords{N}.xml` — denormalised data snapshot.
//!
//! Mirrors RFC-047 §10.6 and §10.7. One `CacheRecord` per source-data
//! row; one `RecordCell` per cache field, in cache-field order.

use super::cache::CacheValue;

/// A single source-data row, denormalised. The `cells` vector has
/// length `cache.fields.len()`, in field order.
#[derive(Debug, Clone, PartialEq)]
pub struct CacheRecord {
    pub cells: Vec<RecordCell>,
}

/// One cell within a `CacheRecord`. RFC-047 §10.7.
///
/// `Index` references `cache.fields[i].shared_items.items[N]` (the
/// 0-based shared-items index). Inline variants (`Number`, `String`,
/// `Boolean`, `Date`) embed the value directly in the `<n>`/`<s>`/
/// `<b>`/`<d>` element. `Missing` emits `<m/>`. `Error` emits
/// `<e v="…"/>`.
#[derive(Debug, Clone, PartialEq)]
pub enum RecordCell {
    Index(u32),
    Number(f64),
    String(String),
    Boolean(bool),
    /// ISO 8601 date-time string.
    Date(String),
    Missing,
    Error(String),
}

impl RecordCell {
    /// Convert a shared-items `CacheValue` into an inline
    /// `RecordCell` of the same kind (used when the field doesn't
    /// enumerate shared items).
    pub fn from_inline(v: &CacheValue) -> Self {
        match v {
            CacheValue::String(s) => Self::String(s.clone()),
            CacheValue::Number(n) => Self::Number(*n),
            CacheValue::Boolean(b) => Self::Boolean(*b),
            CacheValue::Date(d) => Self::Date(d.clone()),
            CacheValue::Missing => Self::Missing,
            CacheValue::Error(s) => Self::Error(s.clone()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn from_inline_string() {
        let v = CacheValue::String("North".into());
        assert!(matches!(RecordCell::from_inline(&v), RecordCell::String(_)));
    }

    #[test]
    fn from_inline_missing() {
        let v = CacheValue::Missing;
        assert_eq!(RecordCell::from_inline(&v), RecordCell::Missing);
    }
}
