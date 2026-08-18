//! Ancillary part registry — per-sheet inventory of comments, VML drawings,
//! tables, DrawingML drawings, controls, hyperlinks, and legacy drawings,
//! lazily populated from the source
//! ZIP's `_rels/sheetN.xml.rels` files.
//!
//! Scaffolding for RFC-022 (Hyperlinks), RFC-023 (Comments), RFC-024 (Tables),
//! and RFC-035 (Copy Worksheet). Lives on [`crate::wolfxl::XlsxPatcher`] but
//! has **no live caller** in the slice that introduces it: the registry's
//! [`AncillaryPartRegistry::populate_for_sheet`] method is invoked only by
//! future RFCs that need to know "what comments part / table parts / etc.
//! does this sheet already own?" before they can mutate or replace those
//! parts.
//!
//! Lazy by design: `populate_for_sheet` is the single entry point; calling it
//! once per sheet caches the result. `XlsxPatcher::open()` does not eagerly
//! walk every sheet's rels file because most modify-mode invocations only
//! touch cell values, where the registry is irrelevant.
//!
//! See `Plans/rfcs/013-patcher-infra-extensions.md` §4.2 for the full design.

use std::collections::HashMap;
use std::io::{Read, Seek};

use wolfxl_rels::{rt, RelId, RelsGraph};
use zip::ZipArchive;

use crate::ooxml_util;

/// All ancillary parts referenced from one sheet's `*.rels` file, classified
/// by relationship type.
///
/// Targets are resolved to absolute ZIP paths (e.g. `"xl/comments3.xml"`,
/// `"xl/tables/table1.xml"`) at populate time so future callers don't have
/// to re-resolve `..`-prefixed targets against the sheet's parent directory.
///
/// Empty (`Default`) when the sheet has no `_rels/sheetN.xml.rels` file or
/// when that file lists no recognized relationships.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SheetAncillary {
    /// Absolute ZIP path of the comments part, if the sheet has one.
    /// Each sheet has at most one comments part per OOXML.
    pub comments_part: Option<String>,
    /// Absolute ZIP path of the VML drawing part, if the sheet has one.
    /// VML drawings are how comment markers (the red triangles) are rendered.
    pub vml_drawing_part: Option<String>,
    /// Absolute ZIP paths of all table parts on this sheet, in source order.
    /// One sheet can own many tables.
    pub table_parts: Vec<String>,
    /// Absolute ZIP path of the DrawingML drawing part, if the sheet has one.
    pub drawing_part: Option<String>,
    /// Absolute ZIP paths of all form-control property parts on this sheet.
    pub ctrl_prop_parts: Vec<String>,
    /// `rId`s of hyperlink relationships on this sheet, in source order.
    /// Sheets typically have <50 hyperlinks; keeping the rIds (rather than
    /// targets) lets RFC-022 dedupe by id when adding new hyperlinks.
    pub hyperlinks_rels: Vec<RelId>,
    /// `rId` of the VML drawing relationship, if any. Mirrors
    /// `vml_drawing_part` but at the rel-id layer — RFC-023 needs this to
    /// emit `<legacyDrawing r:id="rIdN"/>` on a sheet that's gaining its
    /// first comment block.
    pub legacy_drawing_rid: Option<RelId>,
}

/// Per-sheet cache of [`SheetAncillary`]. Indexed by sheet name (matching
/// the patcher's `sheet_paths` and `sheet_order`).
#[derive(Debug, Default)]
pub struct AncillaryPartRegistry {
    per_sheet: HashMap<String, SheetAncillary>,
}

impl AncillaryPartRegistry {
    /// Empty registry. The patcher's `open()` initializes one of these and
    /// holds it; lazy callers later trigger [`populate_for_sheet`] as needed.
    pub fn new() -> Self {
        Self {
            per_sheet: HashMap::new(),
        }
    }

    /// Populate `per_sheet[sheet_name]` from the source ZIP, classifying every
    /// relationship in the sheet's `_rels/sheetN.xml.rels` file.
    ///
    /// Idempotent: a second call for the same `sheet_name` is a no-op (the
    /// cached entry is returned without re-parsing).
    ///
    /// Returns the cached [`SheetAncillary`]. If the sheet has no rels file,
    /// or the rels file lists no recognized relationships, the cached entry
    /// is the default-empty value (still inserted, so subsequent
    /// `get(sheet_name)` returns `Some(&empty)` rather than `None`).
    ///
    /// Errors:
    /// - returns `Err` if the rels file exists but is malformed XML
    /// - missing `Id` / `Type` / `Target` on individual `<Relationship>`
    ///   entries silently skips that entry (matches `wolfxl_rels` parser
    ///   behavior — see RFC-010 §lenient parser)
    pub fn populate_for_sheet<R: Read + Seek>(
        &mut self,
        zip: &mut ZipArchive<R>,
        sheet_name: &str,
        sheet_path: &str,
    ) -> Result<&SheetAncillary, String> {
        if self.per_sheet.contains_key(sheet_name) {
            // Idempotent fast path. Re-borrow to satisfy the lifetime on
            // the `&mut self` receiver — `contains_key` ended its borrow.
            return Ok(self
                .per_sheet
                .get(sheet_name)
                .expect("just checked containment"));
        }

        let ancillary = match read_rels_for_sheet(zip, sheet_path)? {
            Some(rels_xml) => classify(&rels_xml, sheet_path)?,
            None => SheetAncillary::default(),
        };
        self.per_sheet.insert(sheet_name.to_string(), ancillary);
        Ok(self
            .per_sheet
            .get(sheet_name)
            .expect("just inserted this entry"))
    }

    /// Return the cached [`SheetAncillary`] for `sheet_name`, if it has been
    /// populated. Returns `None` otherwise (does NOT lazily populate — the
    /// caller must invoke [`populate_for_sheet`] first).
    pub fn get(&self, sheet_name: &str) -> Option<&SheetAncillary> {
        self.per_sheet.get(sheet_name)
    }

    /// Number of populated sheets. Mostly for tests.
    #[allow(dead_code)]
    pub fn len(&self) -> usize {
        self.per_sheet.len()
    }

    /// True when no sheets have been populated yet.
    #[allow(dead_code)]
    pub fn is_empty(&self) -> bool {
        self.per_sheet.is_empty()
    }
}

/// Read the `_rels/sheetN.xml.rels` for a sheet path. Returns `None` if the
/// rels entry isn't present in the source ZIP (which is normal — sheets with
/// no relationships have no rels file at all).
fn read_rels_for_sheet<R: Read + Seek>(
    zip: &mut ZipArchive<R>,
    sheet_path: &str,
) -> Result<Option<Vec<u8>>, String> {
    let Some(rels_path) = wolfxl_rels::rels_path_for(sheet_path) else {
        return Ok(None);
    };
    let mut entry = match zip.by_name(&rels_path) {
        Ok(e) => e,
        Err(zip::result::ZipError::FileNotFound) => return Ok(None),
        Err(e) => return Err(format!("zip read {rels_path}: {e}")),
    };
    let mut buf = Vec::with_capacity(entry.size() as usize);
    entry
        .read_to_end(&mut buf)
        .map_err(|e| format!("zip read {rels_path}: {e}"))?;
    Ok(Some(buf))
}

/// Walk a parsed [`RelsGraph`] and classify each entry into a
/// [`SheetAncillary`]. Targets are resolved relative to the sheet's parent
/// directory (e.g. `xl/worksheets/`) so callers store absolute ZIP paths.
fn classify(rels_xml: &[u8], sheet_path: &str) -> Result<SheetAncillary, String> {
    let graph = RelsGraph::parse(rels_xml)?;
    let base_dir = sheet_parent_dir(sheet_path);
    let mut out = SheetAncillary::default();
    for rel in graph.iter() {
        let abs = ooxml_util::join_and_normalize(&base_dir, &rel.target);
        match rel.rel_type.as_str() {
            rt::COMMENTS => {
                // First match wins; OOXML disallows >1 comments part per sheet.
                if out.comments_part.is_none() {
                    out.comments_part = Some(abs);
                }
            }
            rt::VML_DRAWING => {
                if out.vml_drawing_part.is_none() {
                    out.vml_drawing_part = Some(abs);
                    out.legacy_drawing_rid = Some(rel.id.clone());
                }
            }
            rt::TABLE => {
                out.table_parts.push(abs);
            }
            rt::DRAWING => {
                if out.drawing_part.is_none() {
                    out.drawing_part = Some(abs);
                }
            }
            rt::CTRL_PROP => {
                out.ctrl_prop_parts.push(abs);
            }
            rt::HYPERLINK => {
                // Hyperlink targets are external URIs (TargetMode="External");
                // we keep the rId so RFC-022 can dedupe by id rather than URI.
                out.hyperlinks_rels.push(rel.id.clone());
            }
            // DRAWING (DrawingML), IMAGE, OLE_OBJECT, PRINTER_SETTINGS, etc.
            // are not part of RFC-013's scope — left for the RFC that needs
            // them. Future enhancements add fields, not separate registries.
            _ => {}
        }
    }
    Ok(out)
}

/// Compute the directory portion of a part path, with trailing slash —
/// suitable for [`ooxml_util::join_and_normalize`] which expects a
/// `base_dir` that includes the trailing `/`.
///
/// `xl/worksheets/sheet1.xml` → `"xl/worksheets/"`
/// `xl/sheet1.xml`            → `"xl/"`
fn sheet_parent_dir(sheet_path: &str) -> String {
    match sheet_path.rfind('/') {
        Some(idx) => sheet_path[..=idx].to_string(),
        None => String::new(),
    }
}

// ---------------------------------------------------------------------------
// Tests
//
// As with the rest of `src/wolfxl/`, these are inline pure-Rust tests. They
// compile under `cargo build -p wolfxl` but cannot link standalone via
// `cargo test -p wolfxl --lib` (the cdylib links against Python). Behavior
// is exercised end-to-end via pytest integration tests in `tests/` once a
// real caller exists (RFC-022 is the first).
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;
    use zip::write::SimpleFileOptions;
    use zip::{CompressionMethod, ZipWriter};

    /// Build a synthetic in-memory ZIP containing the given (path, bytes)
    /// entries — enough for `populate_for_sheet` to see the rels file.
    fn make_zip(entries: &[(&str, &[u8])]) -> Vec<u8> {
        let mut buf = Cursor::new(Vec::new());
        {
            let mut writer = ZipWriter::new(&mut buf);
            let opts = SimpleFileOptions::default().compression_method(CompressionMethod::Deflated);
            for (path, bytes) in entries {
                writer.start_file(*path, opts).unwrap();
                writer.write_all(bytes).unwrap();
            }
            writer.finish().unwrap();
        }
        buf.into_inner()
    }

    fn open_zip(bytes: Vec<u8>) -> ZipArchive<Cursor<Vec<u8>>> {
        ZipArchive::new(Cursor::new(bytes)).unwrap()
    }

    use std::io::Write;

    fn rels_xml(rels: &[(&str, &str, &str)]) -> Vec<u8> {
        // (Id, Type, Target)
        let mut s = String::from(
            r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">"#,
        );
        for (id, ty, target) in rels {
            s.push_str(&format!(
                r#"<Relationship Id="{id}" Type="{ty}" Target="{target}"/>"#
            ));
        }
        s.push_str("</Relationships>");
        s.into_bytes()
    }

    #[test]
    fn populate_no_rels_file_returns_empty() {
        // Sheet exists but has no _rels/sheet1.xml.rels.
        let bytes = make_zip(&[("xl/worksheets/sheet1.xml", b"<sheet/>")]);
        let mut zip = open_zip(bytes);
        let mut reg = AncillaryPartRegistry::new();
        let anc = reg
            .populate_for_sheet(&mut zip, "Sheet1", "xl/worksheets/sheet1.xml")
            .unwrap();
        assert_eq!(anc, &SheetAncillary::default());
        assert_eq!(reg.len(), 1, "still cached as empty entry");
    }

    #[test]
    fn populate_with_comments_only() {
        let xml = rels_xml(&[
            ("rId1", rt::COMMENTS, "../comments1.xml"),
            ("rId2", rt::VML_DRAWING, "../drawings/vmlDrawing1.vml"),
        ]);
        let bytes = make_zip(&[
            ("xl/worksheets/sheet1.xml", b"<sheet/>"),
            ("xl/worksheets/_rels/sheet1.xml.rels", &xml),
        ]);
        let mut zip = open_zip(bytes);
        let mut reg = AncillaryPartRegistry::new();
        let anc = reg
            .populate_for_sheet(&mut zip, "Sheet1", "xl/worksheets/sheet1.xml")
            .unwrap();
        assert_eq!(anc.comments_part.as_deref(), Some("xl/comments1.xml"));
        assert_eq!(
            anc.vml_drawing_part.as_deref(),
            Some("xl/drawings/vmlDrawing1.vml")
        );
        assert_eq!(anc.legacy_drawing_rid, Some(RelId("rId2".into())));
        assert!(anc.table_parts.is_empty());
        assert!(anc.hyperlinks_rels.is_empty());
    }

    #[test]
    fn populate_with_table_and_drawing() {
        let xml = rels_xml(&[
            ("rId1", rt::TABLE, "../tables/table1.xml"),
            ("rId2", rt::TABLE, "../tables/table2.xml"),
        ]);
        let bytes = make_zip(&[
            ("xl/worksheets/sheet1.xml", b"<sheet/>"),
            ("xl/worksheets/_rels/sheet1.xml.rels", &xml),
        ]);
        let mut zip = open_zip(bytes);
        let mut reg = AncillaryPartRegistry::new();
        let anc = reg
            .populate_for_sheet(&mut zip, "Sheet1", "xl/worksheets/sheet1.xml")
            .unwrap();
        assert_eq!(
            anc.table_parts,
            vec!["xl/tables/table1.xml", "xl/tables/table2.xml"]
        );
        assert!(anc.comments_part.is_none());
    }

    #[test]
    fn populate_idempotent() {
        let xml = rels_xml(&[("rId1", rt::COMMENTS, "../comments7.xml")]);
        let bytes = make_zip(&[
            ("xl/worksheets/sheet3.xml", b"<sheet/>"),
            ("xl/worksheets/_rels/sheet3.xml.rels", &xml),
        ]);
        let mut zip = open_zip(bytes);
        let mut reg = AncillaryPartRegistry::new();
        let anc1 = reg
            .populate_for_sheet(&mut zip, "Sheet3", "xl/worksheets/sheet3.xml")
            .unwrap()
            .clone();
        let anc2 = reg
            .populate_for_sheet(&mut zip, "Sheet3", "xl/worksheets/sheet3.xml")
            .unwrap()
            .clone();
        assert_eq!(anc1, anc2);
        assert_eq!(reg.len(), 1);
    }

    #[test]
    fn populate_classifies_hyperlinks() {
        let xml = rels_xml(&[
            ("rId1", rt::HYPERLINK, "https://example.com"),
            ("rId2", rt::HYPERLINK, "mailto:x@y"),
            ("rId3", rt::TABLE, "../tables/table1.xml"),
        ]);
        let bytes = make_zip(&[
            ("xl/worksheets/sheet1.xml", b"<sheet/>"),
            ("xl/worksheets/_rels/sheet1.xml.rels", &xml),
        ]);
        let mut zip = open_zip(bytes);
        let mut reg = AncillaryPartRegistry::new();
        let anc = reg
            .populate_for_sheet(&mut zip, "Sheet1", "xl/worksheets/sheet1.xml")
            .unwrap();
        assert_eq!(
            anc.hyperlinks_rels,
            vec![RelId("rId1".into()), RelId("rId2".into())]
        );
        assert_eq!(anc.table_parts.len(), 1);
    }

    #[test]
    fn populate_handles_relative_paths() {
        // ../comments1.xml from xl/worksheets/ → xl/comments1.xml
        // ../../docProps/foo.xml from xl/worksheets/ → docProps/foo.xml
        let xml = rels_xml(&[
            ("rId1", rt::COMMENTS, "../comments1.xml"),
            ("rId2", rt::TABLE, "tables/inline.xml"),
        ]);
        let bytes = make_zip(&[
            ("xl/worksheets/sheet1.xml", b"<sheet/>"),
            ("xl/worksheets/_rels/sheet1.xml.rels", &xml),
        ]);
        let mut zip = open_zip(bytes);
        let mut reg = AncillaryPartRegistry::new();
        let anc = reg
            .populate_for_sheet(&mut zip, "Sheet1", "xl/worksheets/sheet1.xml")
            .unwrap();
        assert_eq!(anc.comments_part.as_deref(), Some("xl/comments1.xml"));
        // tables/inline.xml is relative to xl/worksheets/ → xl/worksheets/tables/inline.xml
        assert_eq!(
            anc.table_parts,
            vec!["xl/worksheets/tables/inline.xml".to_string()]
        );
    }

    #[test]
    fn get_returns_none_for_unpopulated_sheet() {
        let reg = AncillaryPartRegistry::new();
        assert!(reg.get("Sheet1").is_none());
        assert!(reg.is_empty());
    }

    #[test]
    fn sheet_parent_dir_cases() {
        assert_eq!(
            sheet_parent_dir("xl/worksheets/sheet1.xml"),
            "xl/worksheets/"
        );
        assert_eq!(sheet_parent_dir("xl/sheet1.xml"), "xl/");
        assert_eq!(sheet_parent_dir("sheet1.xml"), "");
    }
}
