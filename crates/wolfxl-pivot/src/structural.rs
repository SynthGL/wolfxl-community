//! RFC-035 §10 — pivot-table deep-clone helpers.
//!
//! See `Plans/rfcs/047-pivot-caches.md` §6 + `Plans/rfcs/048-pivot-tables.md`
//! §6 for the rules. **Caches** stay aliased (workbook-scoped — N tables
//! can share one cache; deep-cloning would duplicate ~MB of records).
//! **Tables** become deep-cloned (each table is sheet-scoped: own
//! `<location>` and possibly own `<worksheetSource sheet="…"/>` rewrite
//! when the cache's source range is also being copied).
//!
//! Pure-Rust, PyO3-free; consumed by `crates/wolfxl-structural/src/sheet_copy.rs`.

use std::borrow::Cow;

/// Optional A1-range remap to apply to the cloned table's
/// `<location ref="…">` attribute. Sprint Ν Pod-γ keeps this `None`
/// (sheet copies preserve the same anchor); callers that move the
/// pivot's anchor cell can plug in their own A1 mapping.
#[derive(Debug, Clone, Default)]
pub struct LocationRewrite {
    /// New `ref` value to substitute for the existing `<location ref="…"/>`.
    pub new_ref: Option<String>,
}

/// Deep-clone a pivot-table XML body for a sheet copy.
///
/// Rewrites:
/// - `<worksheetSource sheet="<src_sheet>" …/>` → `sheet="<dst_sheet>"`
///   (only when the cache's source sheet matches `src_sheet` — see
///   "self-cache copy" handling at the call site).
/// - Optionally `<location ref="…"/>` → `<location ref="<new_ref>"/>`
///   when `location_remap` is provided.
///
/// All other bytes survive verbatim. The rewriter is byte-level (no XML
/// parse) since the attributes we touch are flat string attrs on
/// fixed-name elements, and OOXML pivot XML is normalised at emit
/// (Pod-α emits canonical attribute order).
pub fn deep_clone_pivot_table(
    table_xml: &[u8],
    src_sheet: &str,
    dst_sheet: &str,
    location_remap: Option<&LocationRewrite>,
) -> Vec<u8> {
    // Rewrite `worksheetSource sheet="…"`. The cache definition's
    // worksheetSource attr is the only place `sheet="…"` appears in a
    // pivot-table XML (the table itself uses cacheId, not sheet names).
    // We look for `sheet="<src_sheet>"` literally.
    let s = String::from_utf8_lossy(table_xml);
    let src_pat = format!("sheet=\"{}\"", xml_attr_escape(src_sheet));
    let dst_pat = format!("sheet=\"{}\"", xml_attr_escape(dst_sheet));
    let after_sheet = if s.contains(&src_pat) {
        Cow::Owned(s.replace(&src_pat, &dst_pat))
    } else {
        s
    };

    let after_loc: Cow<str> = if let Some(remap) = location_remap {
        if let Some(new_ref) = &remap.new_ref {
            // Replace the FIRST `<location ref="…"` attribute. We rely
            // on the canonical emit ordering: `ref` is the first attr
            // on `<location>`. For other inputs we'd need a SAX walk;
            // keep this byte-level for simplicity since pivot table XML
            // is always Pod-α-emitted in v2.0 (no openpyxl-emitted
            // pivot tables are deep-cloned via this path — those go
            // through sheet_copy.rs's verbatim-alias branch).
            match rewrite_location_ref(after_sheet.as_ref(), new_ref) {
                Cow::Owned(s) => Cow::Owned(s),
                Cow::Borrowed(_) => after_sheet,
            }
        } else {
            after_sheet
        }
    } else {
        after_sheet
    };

    after_loc.into_owned().into_bytes()
}

/// Deep-clone a pivot-cache XML when the cache's source sheet is the
/// sheet being copied. Used only for "self-cache copy" — RFC-047 §6.
/// The general case keeps caches aliased.
pub fn deep_clone_pivot_cache(cache_xml: &[u8], src_sheet: &str, dst_sheet: &str) -> Vec<u8> {
    let s = String::from_utf8_lossy(cache_xml);
    let src_pat = format!("sheet=\"{}\"", xml_attr_escape(src_sheet));
    let dst_pat = format!("sheet=\"{}\"", xml_attr_escape(dst_sheet));
    if s.contains(&src_pat) {
        s.replace(&src_pat, &dst_pat).into_bytes()
    } else {
        cache_xml.to_vec()
    }
}

fn rewrite_location_ref<'a>(s: &'a str, new_ref: &str) -> Cow<'a, str> {
    if let Some(start) = s.find("<location ref=\"") {
        let after = start + "<location ref=\"".len();
        if let Some(rel_end) = s[after..].find('"') {
            let end = after + rel_end;
            let mut out = String::with_capacity(s.len());
            out.push_str(&s[..after]);
            for c in new_ref.chars() {
                match c {
                    '&' => out.push_str("&amp;"),
                    '<' => out.push_str("&lt;"),
                    '>' => out.push_str("&gt;"),
                    '"' => out.push_str("&quot;"),
                    _ => out.push(c),
                }
            }
            out.push_str(&s[end..]);
            return Cow::Owned(out);
        }
    }
    Cow::Borrowed(s)
}

fn xml_attr_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            _ => out.push(c),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rewrite_sheet_attr_in_table_xml() {
        let xml = br#"<pivotTableDefinition xmlns="x" name="P"><location ref="F2:G5"/><pivotFields/></pivotTableDefinition>"#;
        let out = deep_clone_pivot_table(xml, "Sheet1", "Sheet1 (Copy)", None);
        assert_eq!(out, xml.to_vec(), "no-op when no sheet attr present");
    }

    #[test]
    fn rewrite_sheet_attr_in_cache_xml() {
        let xml = br#"<pivotCacheDefinition><cacheSource type="worksheet"><worksheetSource ref="A1:D100" sheet="Sheet1"/></cacheSource></pivotCacheDefinition>"#;
        let out = deep_clone_pivot_cache(xml, "Sheet1", "Cloned");
        let s = String::from_utf8(out).unwrap();
        assert!(s.contains(r#"sheet="Cloned""#));
        assert!(!s.contains(r#"sheet="Sheet1""#));
    }

    #[test]
    fn rewrite_location_ref_in_table() {
        let xml = br#"<pivotTableDefinition><location ref="F2:G5"/></pivotTableDefinition>"#;
        let out = deep_clone_pivot_table(
            xml,
            "Sheet1",
            "Sheet2",
            Some(&LocationRewrite {
                new_ref: Some("J10:K15".into()),
            }),
        );
        let s = String::from_utf8(out).unwrap();
        assert!(s.contains(r#"<location ref="J10:K15""#));
        assert!(!s.contains(r#"ref="F2:G5""#));
    }

    #[test]
    fn idempotent_no_remap() {
        let xml = br#"<pivotTableDefinition><location ref="F2"/></pivotTableDefinition>"#;
        let out = deep_clone_pivot_table(xml, "Other", "Different", None);
        assert_eq!(out, xml.to_vec());
    }
}
