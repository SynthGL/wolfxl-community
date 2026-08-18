//! Emit `xl/pivotCache/pivotCacheRecords{N}.xml`.
//!
//! See RFC-047 §2.3 + §10.6 + §10.7. One `<r>` per `CacheRecord`,
//! children mirror the field's `RecordCell` variant.

use super::{esc_attr, fmt_num, push_attr, xml_decl};
use crate::model::cache::PivotCache;
use crate::model::records::{CacheRecord, RecordCell};

/// Emit pivotCacheRecords XML. Empty records list still emits the
/// `<pivotCacheRecords count="0"/>` envelope (Excel rejects a missing
/// records part if the cache definition's `recordCount > 0`, so we
/// always emit).
pub fn pivot_cache_records_xml(pc: &PivotCache) -> Vec<u8> {
    let mut out = String::with_capacity(1024 + pc.records.len() * 32);
    xml_decl(&mut out);

    out.push_str("<pivotCacheRecords");
    push_attr(&mut out, "xmlns", crate::ns::SPREADSHEETML);
    push_attr(&mut out, "xmlns:r", crate::ns::RELATIONSHIPS);
    push_attr(&mut out, "count", &pc.records.len().to_string());

    if pc.records.is_empty() {
        out.push_str("/>");
        return out.into_bytes();
    }

    out.push('>');
    for r in &pc.records {
        emit_record(&mut out, r);
    }
    out.push_str("</pivotCacheRecords>");
    out.into_bytes()
}

fn emit_record(out: &mut String, r: &CacheRecord) {
    out.push_str("<r>");
    for c in &r.cells {
        emit_cell(out, c);
    }
    out.push_str("</r>");
}

fn emit_cell(out: &mut String, c: &RecordCell) {
    match c {
        RecordCell::Index(i) => {
            out.push_str("<x v=\"");
            out.push_str(&i.to_string());
            out.push_str("\"/>");
        }
        RecordCell::Number(n) => {
            out.push_str("<n v=\"");
            out.push_str(&fmt_num(*n));
            out.push_str("\"/>");
        }
        RecordCell::String(s) => {
            out.push_str("<s v=\"");
            esc_attr(s, out);
            out.push_str("\"/>");
        }
        RecordCell::Boolean(b) => {
            out.push_str("<b v=\"");
            out.push_str(if *b { "1" } else { "0" });
            out.push_str("\"/>");
        }
        RecordCell::Date(d) => {
            out.push_str("<d v=\"");
            esc_attr(d, out);
            out.push_str("\"/>");
        }
        RecordCell::Missing => {
            out.push_str("<m/>");
        }
        RecordCell::Error(s) => {
            out.push_str("<e v=\"");
            esc_attr(s, out);
            out.push_str("\"/>");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::cache::WorksheetSource;
    use crate::model::records::CacheRecord;

    #[test]
    fn empty_records_self_closes() {
        let pc = PivotCache::new(
            0,
            WorksheetSource {
                sheet: "S".into(),
                range: "A1:A1".into(),
                name: None,
            },
            vec![],
        );
        let xml = pivot_cache_records_xml(&pc);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("<pivotCacheRecords"));
        assert!(s.contains("count=\"0\""));
        assert!(s.contains("/>"));
        assert!(!s.contains("</pivotCacheRecords>"));
    }

    #[test]
    fn three_records_two_fields() {
        let mut pc = PivotCache::new(
            0,
            WorksheetSource {
                sheet: "S".into(),
                range: "A1:B3".into(),
                name: None,
            },
            vec![],
        );
        pc.records = vec![
            CacheRecord {
                cells: vec![RecordCell::Index(0), RecordCell::Number(100.0)],
            },
            CacheRecord {
                cells: vec![RecordCell::Index(1), RecordCell::Number(250.5)],
            },
            CacheRecord {
                cells: vec![RecordCell::Missing, RecordCell::Error("#REF!".into())],
            },
        ];
        let xml = pivot_cache_records_xml(&pc);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("count=\"3\""));
        assert!(s.contains("<r><x v=\"0\"/><n v=\"100\"/></r>"));
        assert!(s.contains("<r><x v=\"1\"/><n v=\"250.5\"/></r>"));
        assert!(s.contains("<r><m/><e v=\"#REF!\"/></r>"));
    }

    #[test]
    fn boolean_string_date_cells() {
        let mut pc = PivotCache::new(
            0,
            WorksheetSource {
                sheet: "S".into(),
                range: "A1:C2".into(),
                name: None,
            },
            vec![],
        );
        pc.records = vec![CacheRecord {
            cells: vec![
                RecordCell::Boolean(true),
                RecordCell::String("hello".into()),
                RecordCell::Date("2026-01-15T00:00:00".into()),
            ],
        }];
        let xml = pivot_cache_records_xml(&pc);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("<b v=\"1\"/>"));
        assert!(s.contains("<s v=\"hello\"/>"));
        assert!(s.contains("<d v=\"2026-01-15T00:00:00\"/>"));
    }

    #[test]
    fn xml_special_chars_escape() {
        let mut pc = PivotCache::new(
            0,
            WorksheetSource {
                sheet: "S".into(),
                range: "A1:A1".into(),
                name: None,
            },
            vec![],
        );
        pc.records = vec![CacheRecord {
            cells: vec![RecordCell::String("a&b<c".into())],
        }];
        let xml = pivot_cache_records_xml(&pc);
        let s = std::str::from_utf8(&xml).unwrap();
        assert!(s.contains("a&amp;b&lt;c"));
    }

    #[test]
    fn deterministic() {
        let mut pc = PivotCache::new(
            0,
            WorksheetSource {
                sheet: "S".into(),
                range: "A1:B3".into(),
                name: None,
            },
            vec![],
        );
        pc.records = vec![
            CacheRecord {
                cells: vec![RecordCell::Index(0), RecordCell::Number(1.5)],
            },
            CacheRecord {
                cells: vec![RecordCell::Index(2), RecordCell::Number(99.0)],
            },
        ];
        assert_eq!(pivot_cache_records_xml(&pc), pivot_cache_records_xml(&pc));
    }
}
