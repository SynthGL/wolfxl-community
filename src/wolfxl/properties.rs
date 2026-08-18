//! `docProps/core.xml` + `docProps/app.xml` rewriters for modify mode
//! (RFC-020).
//!
//! These are full-rewrite emitters: when the patcher's
//! `queued_props` is non-`None`, the entire core/app part is regenerated
//! from the [`DocPropertiesPayload`] fields. We do NOT diff against the
//! source — round-tripping unchanged fields is the Python coordinator's
//! responsibility (it threads the source values back into `queued_props`).
//!
//! ## Why this lives here, not in `wolfxl-writer`
//!
//! The writer's `crates/wolfxl-writer/src/emit/doc_props.rs::emit_core`
//! takes `&Workbook` and reads from `wb.doc_props` (a `DocProperties`
//! struct that lives in the writer's model layer). The patcher has no
//! `Workbook`; it has Python-supplied dict values transported through
//! `XlsxPatcher::queue_properties`. So we duplicate ~90 LOC of emitter
//! logic here against a flat [`DocPropertiesPayload`] input. The
//! duplication is the cost of keeping `wolfxl-core` PyO3-free and not
//! refactoring the writer's `emit_core` signature in this slice.
//!
//! See `Plans/rfcs/020-document-properties.md` §4.2 for the choice
//! rationale (Option 2 = duplicate-now). When a third caller appears
//! (e.g. CLI), consolidate into a `wolfxl_writer::doc_props_emit_v2`
//! that takes `&DocPropertiesPayload`.

// TODO(RFC-020 follow-up): Consolidate with
// crates/wolfxl-writer/src/emit/doc_props.rs once a third caller appears.

const NS_CP: &str = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties";
const NS_DC: &str = "http://purl.org/dc/elements/1.1/";
const NS_DCTERMS: &str = "http://purl.org/dc/terms/";
const NS_DCMITYPE: &str = "http://purl.org/dc/dcmitype/";
const NS_XSI: &str = "http://www.w3.org/2001/XMLSchema-instance";
const NS_EXT_PROPS: &str =
    "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties";
const NS_VT: &str = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes";

const DEFAULT_CREATOR: &str = "wolfxl";

/// Flat payload — what the Python coordinator hands across the PyO3
/// boundary via `XlsxPatcher::queue_properties`. All fields are optional
/// to support partial updates: an unset field round-trips as either the
/// source value (the coordinator threads source through) or absent. The
/// Rust-side default is to omit unset elements entirely from the emitted
/// XML, except for `creator` and `last_modified_by` which fall back to
/// `"wolfxl"` per OOXML convention.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct DocPropertiesPayload {
    /// `dc:title`. Excel's File → Info → Title.
    pub title: Option<String>,
    /// `dc:subject`.
    pub subject: Option<String>,
    /// `dc:creator`. Defaults to `"wolfxl"` if absent.
    pub creator: Option<String>,
    /// `cp:keywords`. Comma- or semicolon-separated, no enforced format.
    pub keywords: Option<String>,
    /// `dc:description`.
    pub description: Option<String>,
    /// `cp:lastModifiedBy`. Falls back to `creator`, then to `"wolfxl"`.
    pub last_modified_by: Option<String>,
    /// `cp:category`.
    pub category: Option<String>,
    /// `cp:contentStatus` (e.g. `"Draft"`, `"Final"`).
    pub content_status: Option<String>,
    /// `dcterms:created` as ISO-8601 UTC (`2024-01-01T00:00:00Z`). When
    /// `None`, the rewriter stamps with [`current_timestamp_iso8601`].
    pub created_iso: Option<String>,
    /// `dcterms:modified`. Same shape as `created_iso`.
    pub modified_iso: Option<String>,
    /// Sheet names in document order, used for `app.xml`'s
    /// `<TitlesOfParts>` block. Caller must supply this in
    /// source-document order; modify mode threads
    /// `XlsxPatcher::sheet_order` into this field.
    pub sheet_names: Vec<String>,
}

/// XML text-node escape — applies between tags. Lifted from the writer's
/// emitter and kept identical so write-mode and modify-mode produce the
/// same byte shape for identical inputs.
fn xml_text_escape(s: &str) -> String {
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

fn push_optional_element(out: &mut String, tag: &str, value: Option<&str>) {
    if let Some(v) = value {
        out.push_str(&format!("<{tag}>{}</{tag}>", xml_text_escape(v)));
    }
}

/// Current UTC timestamp in ISO-8601 (`2024-01-01T00:00:00Z`).
///
/// Honors `WOLFXL_TEST_EPOCH` for deterministic output:
/// - `WOLFXL_TEST_EPOCH=0` → `"1970-01-01T00:00:00Z"`
/// - any other valid integer → that Unix-epoch second
/// - unset / invalid → `chrono::Utc::now()`
pub(crate) fn current_timestamp_iso8601() -> String {
    if let Ok(raw) = std::env::var("WOLFXL_TEST_EPOCH") {
        if let Ok(secs) = raw.parse::<i64>() {
            if let Some(dt) = chrono::DateTime::<chrono::Utc>::from_timestamp(secs, 0) {
                return dt.format("%Y-%m-%dT%H:%M:%SZ").to_string();
            }
        }
    }
    chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string()
}

/// Rewrite `docProps/core.xml` from a [`DocPropertiesPayload`].
///
/// Element order is fixed by the OOXML schema (Excel reads strictly):
/// `title`, `subject`, `creator`, `keywords`, `description`,
/// `lastModifiedBy`, `category`, `contentStatus`, `created`, `modified`.
///
/// `creator` and `lastModifiedBy` are required by OOXML. If either is
/// unset, [`DEFAULT_CREATOR`] (`"wolfxl"`) fills it. `lastModifiedBy`
/// additionally falls back to `creator` when both are unset, matching
/// the writer's emitter and openpyxl's auto-stamp behavior.
///
/// Timestamps default to `current_timestamp_iso8601()` when unset; this
/// makes a fresh save stamp the modification time correctly while still
/// honoring `WOLFXL_TEST_EPOCH=0` for byte-identical golden tests.
pub fn rewrite_core_props(payload: &DocPropertiesPayload) -> Vec<u8> {
    let now = current_timestamp_iso8601();
    let created = payload.created_iso.clone().unwrap_or_else(|| now.clone());
    let modified = payload.modified_iso.clone().unwrap_or(now);

    let creator = payload
        .creator
        .clone()
        .unwrap_or_else(|| DEFAULT_CREATOR.to_string());
    let last_modified_by = payload
        .last_modified_by
        .clone()
        .or_else(|| payload.creator.clone())
        .unwrap_or_else(|| DEFAULT_CREATOR.to_string());

    let mut out = String::with_capacity(768);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!(
        "<cp:coreProperties \
         xmlns:cp=\"{NS_CP}\" \
         xmlns:dc=\"{NS_DC}\" \
         xmlns:dcterms=\"{NS_DCTERMS}\" \
         xmlns:dcmitype=\"{NS_DCMITYPE}\" \
         xmlns:xsi=\"{NS_XSI}\">"
    ));

    push_optional_element(&mut out, "dc:title", payload.title.as_deref());
    push_optional_element(&mut out, "dc:subject", payload.subject.as_deref());
    out.push_str(&format!(
        "<dc:creator>{}</dc:creator>",
        xml_text_escape(&creator)
    ));
    push_optional_element(&mut out, "cp:keywords", payload.keywords.as_deref());
    push_optional_element(&mut out, "dc:description", payload.description.as_deref());
    out.push_str(&format!(
        "<cp:lastModifiedBy>{}</cp:lastModifiedBy>",
        xml_text_escape(&last_modified_by)
    ));
    push_optional_element(&mut out, "cp:category", payload.category.as_deref());
    push_optional_element(
        &mut out,
        "cp:contentStatus",
        payload.content_status.as_deref(),
    );
    out.push_str(&format!(
        "<dcterms:created xsi:type=\"dcterms:W3CDTF\">{}</dcterms:created>",
        xml_text_escape(&created)
    ));
    out.push_str(&format!(
        "<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{}</dcterms:modified>",
        xml_text_escape(&modified)
    ));
    out.push_str("</cp:coreProperties>");
    out.into_bytes()
}

/// Rewrite `docProps/app.xml` from a [`DocPropertiesPayload`]. Sheet
/// names appear in `payload.sheet_names` order (caller supplies).
///
/// Note: this slice does NOT round-trip `<Company>`, `<Manager>`,
/// `<lastPrinted>`, `<revision>`, `<version>` or other Office-specific
/// fields the source may have carried — `DocPropertiesPayload` doesn't
/// model them. RFC-020 §10 documents this regression. The pytest test
/// `test_app_xml_drops_company_manager_known_loss` (commit 9) guards the
/// loss so a future patch that accidentally fixes it surfaces clearly.
pub fn rewrite_app_props(payload: &DocPropertiesPayload) -> Vec<u8> {
    let n_sheets = payload.sheet_names.len();

    let mut out = String::with_capacity(1024);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!(
        "<Properties xmlns=\"{NS_EXT_PROPS}\" xmlns:vt=\"{NS_VT}\">"
    ));
    out.push_str("<Application>wolfxl</Application>");
    out.push_str("<DocSecurity>0</DocSecurity>");
    out.push_str("<ScaleCrop>false</ScaleCrop>");

    out.push_str("<HeadingPairs>");
    out.push_str(&format!(
        "<vt:vector size=\"2\" baseType=\"variant\">\
         <vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>\
         <vt:variant><vt:i4>{n_sheets}</vt:i4></vt:variant>\
         </vt:vector>"
    ));
    out.push_str("</HeadingPairs>");

    out.push_str("<TitlesOfParts>");
    out.push_str(&format!(
        "<vt:vector size=\"{n_sheets}\" baseType=\"lpstr\">"
    ));
    for name in &payload.sheet_names {
        out.push_str(&format!("<vt:lpstr>{}</vt:lpstr>", xml_text_escape(name)));
    }
    out.push_str("</vt:vector>");
    out.push_str("</TitlesOfParts>");

    out.push_str("<LinksUpToDate>false</LinksUpToDate>");
    out.push_str("<SharedDoc>false</SharedDoc>");
    out.push_str("<HyperlinksChanged>false</HyperlinksChanged>");
    // OOXML §22.2.2.3 — dotted-decimal `XX.YYYY`, not semver.
    out.push_str("<AppVersion>1.0000</AppVersion>");
    out.push_str("</Properties>");
    out.into_bytes()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn empty_payload() -> DocPropertiesPayload {
        DocPropertiesPayload::default()
    }

    fn one_sheet() -> Vec<String> {
        vec!["Sheet1".to_string()]
    }

    #[test]
    fn core_round_trip_all_fields() {
        let payload = DocPropertiesPayload {
            title: Some("Q1 Report".into()),
            subject: Some("Sales".into()),
            creator: Some("Alice".into()),
            keywords: Some("alpha, beta".into()),
            description: Some("A test file.".into()),
            last_modified_by: Some("Bob".into()),
            category: Some("Internal".into()),
            content_status: Some("Draft".into()),
            created_iso: Some("2024-01-02T03:04:05Z".into()),
            modified_iso: Some("2024-06-07T08:09:10Z".into()),
            sheet_names: one_sheet(),
        };
        let bytes = rewrite_core_props(&payload);
        let text = std::str::from_utf8(&bytes).expect("utf8");
        assert!(text.contains("<dc:title>Q1 Report</dc:title>"));
        assert!(text.contains("<dc:subject>Sales</dc:subject>"));
        assert!(text.contains("<dc:creator>Alice</dc:creator>"));
        assert!(text.contains("<cp:keywords>alpha, beta</cp:keywords>"));
        assert!(text.contains("<dc:description>A test file.</dc:description>"));
        assert!(text.contains("<cp:lastModifiedBy>Bob</cp:lastModifiedBy>"));
        assert!(text.contains("<cp:category>Internal</cp:category>"));
        assert!(text.contains("<cp:contentStatus>Draft</cp:contentStatus>"));
        assert!(text.contains(
            "<dcterms:created xsi:type=\"dcterms:W3CDTF\">2024-01-02T03:04:05Z</dcterms:created>"
        ));
        assert!(text.contains(
            "<dcterms:modified xsi:type=\"dcterms:W3CDTF\">2024-06-07T08:09:10Z</dcterms:modified>"
        ));
    }

    #[test]
    fn core_omits_empty_fields() {
        let payload = empty_payload();
        let text = String::from_utf8(rewrite_core_props(&payload)).unwrap();
        // Default creator + lastModifiedBy stamped.
        assert!(text.contains("<dc:creator>wolfxl</dc:creator>"));
        assert!(text.contains("<cp:lastModifiedBy>wolfxl</cp:lastModifiedBy>"));
        // Optional fields absent.
        assert!(!text.contains("<dc:title"));
        assert!(!text.contains("<dc:subject"));
        assert!(!text.contains("<cp:keywords"));
        assert!(!text.contains("<cp:contentStatus"));
    }

    #[test]
    fn core_escapes_special_chars() {
        let payload = DocPropertiesPayload {
            title: Some("A & B < C > D".into()),
            ..empty_payload()
        };
        let text = String::from_utf8(rewrite_core_props(&payload)).unwrap();
        assert!(text.contains("A &amp; B &lt; C &gt; D"));
        assert!(!text.contains("A & B < C"));
    }

    #[test]
    fn core_modified_iso_falls_back_to_test_epoch() {
        std::env::set_var("WOLFXL_TEST_EPOCH", "0");
        let payload = empty_payload();
        let text = String::from_utf8(rewrite_core_props(&payload)).unwrap();
        std::env::remove_var("WOLFXL_TEST_EPOCH");
        assert!(
            text.contains("<dcterms:created xsi:type=\"dcterms:W3CDTF\">1970-01-01T00:00:00Z"),
            "WOLFXL_TEST_EPOCH=0 must produce 1970-01-01T00:00:00Z; got: {text}"
        );
        assert!(text.contains("<dcterms:modified xsi:type=\"dcterms:W3CDTF\">1970-01-01T00:00:00Z"));
    }

    #[test]
    fn core_last_modified_by_falls_back_to_creator() {
        let payload = DocPropertiesPayload {
            creator: Some("Alice".into()),
            last_modified_by: None,
            ..empty_payload()
        };
        let text = String::from_utf8(rewrite_core_props(&payload)).unwrap();
        assert!(text.contains("<cp:lastModifiedBy>Alice</cp:lastModifiedBy>"));
    }

    #[test]
    fn app_titles_of_parts_in_order() {
        let payload = DocPropertiesPayload {
            sheet_names: vec!["Apples".into(), "Bananas".into(), "Cherries".into()],
            ..empty_payload()
        };
        let bytes = rewrite_app_props(&payload);
        let text = std::str::from_utf8(&bytes).expect("utf8");
        let i_a = text.find("<vt:lpstr>Apples</vt:lpstr>").expect("apples");
        let i_b = text.find("<vt:lpstr>Bananas</vt:lpstr>").expect("bananas");
        let i_c = text
            .find("<vt:lpstr>Cherries</vt:lpstr>")
            .expect("cherries");
        assert!(i_a < i_b && i_b < i_c);
        assert!(text.contains("vt:vector size=\"3\" baseType=\"lpstr\""));
        assert!(text.contains("<vt:i4>3</vt:i4>"));
    }

    #[test]
    fn app_application_field_is_wolfxl() {
        let payload = DocPropertiesPayload {
            sheet_names: one_sheet(),
            ..empty_payload()
        };
        let text = String::from_utf8(rewrite_app_props(&payload)).unwrap();
        assert!(text.contains("<Application>wolfxl</Application>"));
        assert!(text.contains("<AppVersion>1.0000</AppVersion>"));
        // Per OOXML §22.2.2.3, AppVersion must be dotted-decimal not semver.
        assert!(!text.contains("<AppVersion>0.1.0"));
    }
}
