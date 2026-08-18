//! `docProps/core.xml` + `docProps/app.xml` emitter.
//!
//! These two parts surface in Excel's File → Info pane:
//!
//! - **core** — Dublin Core metadata (title, creator, keywords, created /
//!   modified timestamps). Present in every OOXML file, not just xlsx.
//! - **app** — Office-specific application metadata (which app wrote the
//!   file, the list of sheet names in `TitlesOfParts`, company, etc.).
//!
//! Both parts are small, so we generate them as raw strings rather than
//! going through `quick_xml::Writer`. XML escaping for user-supplied text
//! is performed locally in [`xml_text_escape`] / [`xml_attr_escape`].

use crate::model::workbook::Workbook;

const NS_CP: &str = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties";
const NS_DC: &str = "http://purl.org/dc/elements/1.1/";
const NS_DCTERMS: &str = "http://purl.org/dc/terms/";
const NS_DCMITYPE: &str = "http://purl.org/dc/dcmitype/";
const NS_XSI: &str = "http://www.w3.org/2001/XMLSchema-instance";

const NS_EXT_PROPS: &str =
    "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties";
const NS_VT: &str = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes";

const DEFAULT_CREATOR: &str = "wolfxl";

/// XML text-node escape. Applies to values between tags.
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

/// Current timestamp in ISO-8601 UTC form (`2024-01-01T00:00:00Z`).
///
/// Honors `WOLFXL_TEST_EPOCH` for deterministic output.
fn current_timestamp_iso8601() -> String {
    if let Some(secs) = crate::zip::test_epoch_override() {
        if let Some(dt) = chrono::DateTime::<chrono::Utc>::from_timestamp(secs, 0) {
            return dt.format("%Y-%m-%dT%H:%M:%SZ").to_string();
        }
    }
    chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string()
}

/// Format a `NaiveDateTime` in ISO-8601 UTC (always treated as UTC).
fn format_naive(dt: &chrono::NaiveDateTime) -> String {
    dt.format("%Y-%m-%dT%H:%M:%SZ").to_string()
}

/// Emit a `<tag>value</tag>` child, text-escaping `value`. Callers omit
/// the child entirely when `value` is `None`.
fn push_optional_element(out: &mut String, tag: &str, value: Option<&str>) {
    if let Some(v) = value {
        out.push_str(&format!("<{tag}>{}</{tag}>", xml_text_escape(v)));
    }
}

/// `docProps/core.xml` — Dublin Core + basic Office metadata.
pub fn emit_core(wb: &Workbook) -> Vec<u8> {
    let props = &wb.doc_props;

    let now = current_timestamp_iso8601();
    let created = props
        .created
        .as_ref()
        .map(format_naive)
        .unwrap_or_else(|| now.clone());
    let modified = props.modified.as_ref().map(format_naive).unwrap_or(now);

    let creator = props
        .creator
        .clone()
        .unwrap_or_else(|| DEFAULT_CREATOR.to_string());
    let last_modified_by = props
        .last_modified_by
        .clone()
        .or_else(|| props.creator.clone())
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

    push_optional_element(&mut out, "dc:title", props.title.as_deref());
    push_optional_element(&mut out, "dc:subject", props.subject.as_deref());
    out.push_str(&format!(
        "<dc:creator>{}</dc:creator>",
        xml_text_escape(&creator)
    ));
    push_optional_element(&mut out, "cp:keywords", props.keywords.as_deref());
    push_optional_element(&mut out, "dc:description", props.description.as_deref());
    out.push_str(&format!(
        "<cp:lastModifiedBy>{}</cp:lastModifiedBy>",
        xml_text_escape(&last_modified_by)
    ));
    push_optional_element(&mut out, "cp:category", props.category.as_deref());
    // OOXML schema places <cp:contentStatus> after <cp:category> and before
    // the dcterms:created/modified pair. Excel reads this case-sensitively;
    // `xml_text_escape` handles the `<` / `&` Excel cares about.
    push_optional_element(
        &mut out,
        "cp:contentStatus",
        props.content_status.as_deref(),
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

/// `docProps/app.xml` — application-specific metadata.
pub fn emit_app(wb: &Workbook) -> Vec<u8> {
    let props = &wb.doc_props;
    let n_sheets = wb.sheets.len();

    let mut out = String::with_capacity(1024);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!(
        "<Properties xmlns=\"{NS_EXT_PROPS}\" xmlns:vt=\"{NS_VT}\">"
    ));

    out.push_str("<Application>wolfxl</Application>");

    // Sheet count + names (Excel displays this as "Sheets: 3" in the info pane).
    out.push_str("<DocSecurity>0</DocSecurity>");
    out.push_str("<ScaleCrop>false</ScaleCrop>");

    // HeadingPairs: one heading ("Worksheets") mapped to a count.
    out.push_str("<HeadingPairs>");
    out.push_str(&format!(
        "<vt:vector size=\"2\" baseType=\"variant\">\
         <vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>\
         <vt:variant><vt:i4>{n_sheets}</vt:i4></vt:variant>\
         </vt:vector>"
    ));
    out.push_str("</HeadingPairs>");

    // TitlesOfParts: vector of sheet names.
    out.push_str("<TitlesOfParts>");
    out.push_str(&format!(
        "<vt:vector size=\"{n_sheets}\" baseType=\"lpstr\">"
    ));
    for sheet in &wb.sheets {
        out.push_str(&format!(
            "<vt:lpstr>{}</vt:lpstr>",
            xml_text_escape(&sheet.name)
        ));
    }
    out.push_str("</vt:vector>");
    out.push_str("</TitlesOfParts>");

    push_optional_element(&mut out, "Company", props.company.as_deref());
    push_optional_element(&mut out, "Manager", props.manager.as_deref());

    out.push_str("<LinksUpToDate>false</LinksUpToDate>");
    out.push_str("<SharedDoc>false</SharedDoc>");
    out.push_str("<HyperlinksChanged>false</HyperlinksChanged>");
    // OOXML §22.2.2.3 (ECMA-376): AppVersion must be dotted-decimal of form
    // `XX.YYYY`, matching the application's major.minor build number — not
    // a semver. openpyxl and Excel both emit this shape; validators (e.g.
    // strict OOXML schema checks, some Excel repair paths) reject semver
    // like "0.1.0". Track the wolfxl ABI here as one monotonic integer
    // pair; bump on user-visible writer changes, not on Cargo patch bumps.
    out.push_str("<AppVersion>1.0000</AppVersion>");

    out.push_str("</Properties>");
    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::worksheet::Worksheet;
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn parse_ok(bytes: &[u8]) {
        let text = std::str::from_utf8(bytes).expect("utf8");
        let mut reader = Reader::from_str(text);
        let mut buf = Vec::new();
        loop {
            match reader.read_event_into(&mut buf) {
                Ok(Event::Eof) => break,
                Err(e) => panic!("parse error: {e}"),
                _ => (),
            }
            buf.clear();
        }
    }

    #[test]
    fn core_is_well_formed_minimal_workbook() {
        let wb = Workbook::new();
        let bytes = emit_core(&wb);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<cp:coreProperties"));
        assert!(text.contains("xmlns:dc=\"http://purl.org/dc/elements/1.1/\""));
        assert!(text.contains("<dc:creator>wolfxl</dc:creator>"));
        assert!(text.contains("<cp:lastModifiedBy>wolfxl</cp:lastModifiedBy>"));
        assert!(text.contains("<dcterms:created"));
        assert!(text.contains("<dcterms:modified"));
    }

    #[test]
    fn core_emits_user_metadata() {
        let mut wb = Workbook::new();
        wb.doc_props.title = Some("My Title".into());
        wb.doc_props.subject = Some("My Subject".into());
        wb.doc_props.creator = Some("Alice".into());
        wb.doc_props.keywords = Some("alpha, beta".into());
        wb.doc_props.description = Some("A test file.".into());
        wb.doc_props.last_modified_by = Some("Bob".into());
        wb.doc_props.category = Some("Testing".into());
        wb.doc_props.content_status = Some("Draft".into());

        let bytes = emit_core(&wb);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<dc:title>My Title</dc:title>"));
        assert!(text.contains("<dc:subject>My Subject</dc:subject>"));
        assert!(text.contains("<dc:creator>Alice</dc:creator>"));
        assert!(text.contains("<cp:keywords>alpha, beta</cp:keywords>"));
        assert!(text.contains("<dc:description>A test file.</dc:description>"));
        assert!(text.contains("<cp:lastModifiedBy>Bob</cp:lastModifiedBy>"));
        assert!(text.contains("<cp:category>Testing</cp:category>"));
        assert!(text.contains("<cp:contentStatus>Draft</cp:contentStatus>"));
        // OOXML schema order: contentStatus immediately after category,
        // before dcterms:created — guard the position so a future emitter
        // refactor doesn't silently move it (Excel reads strictly).
        let cat_pos = text.find("<cp:category>").unwrap();
        let status_pos = text.find("<cp:contentStatus>").unwrap();
        let created_pos = text.find("<dcterms:created").unwrap();
        assert!(cat_pos < status_pos && status_pos < created_pos);
    }

    #[test]
    fn core_omits_content_status_when_unset() {
        let wb = Workbook::new();
        let text = String::from_utf8(emit_core(&wb)).unwrap();
        assert!(!text.contains("<cp:contentStatus"));
    }

    #[test]
    fn core_escapes_xml_special_chars() {
        let mut wb = Workbook::new();
        wb.doc_props.title = Some("A & B < C > D".into());
        let bytes = emit_core(&wb);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("A &amp; B &lt; C &gt; D"));
        // Must not leave the raw characters unescaped in the text body.
        assert!(!text.contains("<dc:title>A & B"));
    }

    #[test]
    fn core_last_modified_by_falls_back_to_creator() {
        let mut wb = Workbook::new();
        wb.doc_props.creator = Some("Alice".into());
        wb.doc_props.last_modified_by = None;
        let text = String::from_utf8(emit_core(&wb)).unwrap();
        assert!(text.contains("<cp:lastModifiedBy>Alice</cp:lastModifiedBy>"));
    }

    #[test]
    fn core_uses_explicit_created_and_modified() {
        use chrono::NaiveDate;
        let mut wb = Workbook::new();
        wb.doc_props.created = Some(
            NaiveDate::from_ymd_opt(2024, 1, 2)
                .unwrap()
                .and_hms_opt(3, 4, 5)
                .unwrap(),
        );
        wb.doc_props.modified = Some(
            NaiveDate::from_ymd_opt(2024, 6, 7)
                .unwrap()
                .and_hms_opt(8, 9, 10)
                .unwrap(),
        );
        let text = String::from_utf8(emit_core(&wb)).unwrap();
        assert!(text.contains(
            "<dcterms:created xsi:type=\"dcterms:W3CDTF\">2024-01-02T03:04:05Z</dcterms:created>"
        ));
        assert!(text.contains(
            "<dcterms:modified xsi:type=\"dcterms:W3CDTF\">2024-06-07T08:09:10Z</dcterms:modified>"
        ));
    }

    #[test]
    fn app_is_well_formed() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("First"));
        wb.add_sheet(Worksheet::new("Second & More"));
        let bytes = emit_app(&wb);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<Application>wolfxl</Application>"));
        assert!(text.contains("<AppVersion>"));
        assert!(text.contains("vt:vector size=\"2\" baseType=\"lpstr\""));
        assert!(text.contains("<vt:lpstr>First</vt:lpstr>"));
        assert!(text.contains("<vt:lpstr>Second &amp; More</vt:lpstr>"));
        assert!(text.contains("<vt:i4>2</vt:i4>"));
    }

    #[test]
    fn app_includes_company_and_manager_when_set() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("A"));
        wb.doc_props.company = Some("Acme Corp".into());
        wb.doc_props.manager = Some("Eve".into());
        let text = String::from_utf8(emit_app(&wb)).unwrap();
        assert!(text.contains("<Company>Acme Corp</Company>"));
        assert!(text.contains("<Manager>Eve</Manager>"));
    }

    #[test]
    fn app_omits_optional_fields_when_unset() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("A"));
        let text = String::from_utf8(emit_app(&wb)).unwrap();
        assert!(!text.contains("<Company>"));
        assert!(!text.contains("<Manager>"));
    }

    #[test]
    fn current_timestamp_honors_test_epoch() {
        let _g = crate::test_utils::EpochGuard::set("0");
        assert_eq!(current_timestamp_iso8601(), "1970-01-01T00:00:00Z");
    }

    #[test]
    fn app_version_is_ooxml_dotted_decimal_not_semver() {
        // OOXML §22.2.2.3 forbids semver; validators reject "0.1.0".
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("A"));
        let text = String::from_utf8(emit_app(&wb)).unwrap();
        assert!(text.contains("<AppVersion>1.0000</AppVersion>"));
        assert!(!text.contains("<AppVersion>0.1.0</AppVersion>"));
    }
}
