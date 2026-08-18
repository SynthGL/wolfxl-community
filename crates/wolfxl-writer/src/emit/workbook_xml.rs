//! `xl/workbook.xml` emitter. Wave 2C.
//!
//! Emits the workbook XML part that lists sheets, defined names,
//! and a handful of fixed metadata elements that Excel requires.

use crate::model::defined_name::{BuiltinName, DefinedName};
use crate::model::workbook::Workbook;
use crate::model::worksheet::SheetVisibility;
use crate::parse::workbook_security::{emit_file_sharing, emit_workbook_protection};
use crate::refs::quote_sheet_name_if_needed;
use crate::xml_escape;

const NS_MAIN: &str = "http://schemas.openxmlformats.org/spreadsheetml/2006/main";
const NS_R: &str = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

/// Return the `_xlnm.` prefixed name for a built-in defined name.
fn builtin_name_str(b: BuiltinName) -> &'static str {
    match b {
        BuiltinName::PrintArea => "_xlnm.Print_Area",
        BuiltinName::PrintTitles => "_xlnm.Print_Titles",
        BuiltinName::FilterDatabase => "_xlnm._FilterDatabase",
    }
}

/// True iff `defined_names` already carries a `PrintArea` builtin scoped
/// to sheet `idx`. Used to suppress the `Worksheet::print_area` auto-inject
/// when the caller has declared the print area explicitly via `DefinedName`.
fn has_user_print_area_for_sheet(defined_names: &[DefinedName], idx: usize) -> bool {
    defined_names.iter().any(|dn| {
        matches!(dn.builtin, Some(BuiltinName::PrintArea)) && dn.scope_sheet_index == Some(idx)
    })
}

fn emit_defined_names(out: &mut String, wb: &Workbook) {
    let has_user_names = !wb.defined_names.is_empty();
    let has_print_areas = wb.sheets.iter().any(|s| s.print_area.is_some());

    if !has_user_names && !has_print_areas {
        return;
    }

    out.push_str("<definedNames>");
    emit_user_defined_names(out, &wb.defined_names);
    emit_sheet_print_areas(out, wb);
    out.push_str("</definedNames>");
}

fn emit_user_defined_names(out: &mut String, defined_names: &[DefinedName]) {
    for dn in defined_names {
        let name_str = match dn.builtin {
            Some(b) => builtin_name_str(b).to_string(),
            None => dn.name.clone(),
        };
        let name_escaped = xml_escape::attr(&name_str);

        let local_attr = match dn.scope_sheet_index {
            Some(idx) => format!(" localSheetId=\"{idx}\""),
            None => String::new(),
        };

        // ECMA-376 §18.2.5 attribute order matches openpyxl's emit order
        // so wolfxl-written workbooks diff cleanly against openpyxl-written
        // ones. Attribute is omitted when its value is the XML default.
        let mut extra = String::new();
        emit_opt_str(&mut extra, "comment", dn.comment.as_deref());
        emit_opt_str(&mut extra, "customMenu", dn.custom_menu.as_deref());
        emit_opt_str(&mut extra, "description", dn.description.as_deref());
        emit_opt_str(&mut extra, "help", dn.help.as_deref());
        emit_opt_str(&mut extra, "statusBar", dn.status_bar.as_deref());
        emit_opt_str(&mut extra, "shortcutKey", dn.shortcut_key.as_deref());
        if dn.hidden {
            extra.push_str(" hidden=\"1\"");
        }
        emit_opt_bool_true(&mut extra, "function", dn.function);
        emit_opt_bool_true(&mut extra, "vbProcedure", dn.vb_procedure);
        emit_opt_bool_true(&mut extra, "xlm", dn.xlm);
        if let Some(id) = dn.function_group_id {
            extra.push_str(&format!(" functionGroupId=\"{id}\""));
        }
        emit_opt_bool_true(&mut extra, "publishToServer", dn.publish_to_server);
        emit_opt_bool_true(&mut extra, "workbookParameter", dn.workbook_parameter);

        let formula_escaped = xml_escape::text(&dn.formula);
        out.push_str(&format!(
            "<definedName name=\"{name_escaped}\"{local_attr}{extra}>{formula_escaped}</definedName>"
        ));
    }
}

fn emit_opt_str(out: &mut String, attr: &str, value: Option<&str>) {
    if let Some(v) = value {
        out.push_str(&format!(" {attr}=\"{}\"", xml_escape::attr(v)));
    }
}

fn emit_opt_bool_true(out: &mut String, attr: &str, value: Option<bool>) {
    if value == Some(true) {
        out.push_str(&format!(" {attr}=\"1\""));
    }
}

fn emit_sheet_print_areas(out: &mut String, wb: &Workbook) {
    for (idx, sheet) in wb.sheets.iter().enumerate() {
        if let Some(ref range) = sheet.print_area {
            if has_user_print_area_for_sheet(&wb.defined_names, idx) {
                continue;
            }
            let quoted_name = quote_sheet_name_if_needed(&sheet.name);
            let formula = format!("{quoted_name}!{range}");
            let formula_escaped = xml_escape::text(&formula);
            out.push_str(&format!(
                "<definedName name=\"_xlnm.Print_Area\" localSheetId=\"{idx}\">{formula_escaped}</definedName>"
            ));
        }
    }
}

/// Emit `xl/workbook.xml` as UTF-8 bytes.
pub fn emit(wb: &Workbook) -> Vec<u8> {
    let mut out = String::with_capacity(1024);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!(
        "<workbook xmlns=\"{NS_MAIN}\" xmlns:r=\"{NS_R}\">"
    ));

    // Fixed file-version and workbook-properties elements.
    // Attribute values mirror what openpyxl writes; Excel accepts them unchanged.
    out.push_str(
        "<fileVersion appName=\"xl\" lastEdited=\"7\" lowestEdited=\"7\" rupBuild=\"10000\"/>",
    );

    // <fileSharing> sits between <fileVersion> and <workbookPr> per
    // ECMA-376 CT_Workbook child ordering. Empty bytes mean no element.
    if let Some(spec) = wb.security.file_sharing.as_ref() {
        let bytes = emit_file_sharing(spec);
        if !bytes.is_empty() {
            // Fragment is UTF-8 (xml_escape::attr preserves the encoding
            // of the input string).
            out.push_str(&String::from_utf8_lossy(&bytes));
        }
    }

    let date1904 = if wb.date1904 { "1" } else { "false" };
    out.push_str(&format!("<workbookPr date1904=\"{date1904}\"/>"));

    // <workbookProtection> sits between <workbookPr> and <bookViews>.
    // Empty bytes mean no element.
    if let Some(spec) = wb.security.workbook_protection.as_ref() {
        let bytes = emit_workbook_protection(spec);
        if !bytes.is_empty() {
            out.push_str(&String::from_utf8_lossy(&bytes));
        }
    }

    out.push_str(
        "<bookViews>\
         <workbookView visibility=\"visible\" minimized=\"0\" showHorizontalScroll=\"1\" showVerticalScroll=\"1\" showSheetTabs=\"1\" tabRatio=\"600\" firstSheet=\"0\" activeTab=\"0\" autoFilterDateGrouping=\"1\"/>\
         </bookViews>",
    );

    // Sheets.
    out.push_str("<sheets>");
    for (idx, sheet) in wb.sheets.iter().enumerate() {
        let n = idx + 1;
        let name_escaped = xml_escape::attr(&sheet.name);
        let state_attr = match sheet.visibility {
            SheetVisibility::Visible => String::new(),
            SheetVisibility::Hidden => " state=\"hidden\"".to_string(),
            SheetVisibility::VeryHidden => " state=\"veryHidden\"".to_string(),
        };
        out.push_str(&format!(
            "<sheet name=\"{name_escaped}\" sheetId=\"{n}\" r:id=\"rId{n}\"{state_attr}/>"
        ));
    }
    out.push_str("</sheets>");

    emit_defined_names(&mut out, wb);

    // calcId="171027" is the openpyxl-matching stamp; Excel accepts it unchanged.
    out.push_str("<calcPr calcId=\"171027\"/>");
    out.push_str("</workbook>");
    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::defined_name::{BuiltinName, DefinedName};
    use crate::model::workbook::Workbook;
    use crate::model::worksheet::{SheetVisibility, Worksheet};
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn parse_ok(bytes: &[u8]) {
        let text = std::str::from_utf8(bytes).expect("utf8");
        let mut reader = Reader::from_str(text);
        reader.config_mut().check_end_names = true;
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

    fn text_of(bytes: &[u8]) -> String {
        String::from_utf8(bytes.to_vec()).expect("utf8")
    }

    // 1. Single sheet minimal.
    #[test]
    fn single_sheet_minimal() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(
            text.contains("<sheet name=\"Sheet1\" sheetId=\"1\" r:id=\"rId1\"/>"),
            "{text}"
        );
        assert!(
            !text.contains("<definedNames>"),
            "no defined names expected: {text}"
        );
    }

    // 2. Multiple sheets numbered correctly.
    #[test]
    fn multiple_sheets_numbered_correctly() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("a"));
        wb.add_sheet(Worksheet::new("b"));
        wb.add_sheet(Worksheet::new("c"));
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(text.contains("sheetId=\"1\" r:id=\"rId1\""), "{text}");
        assert!(text.contains("sheetId=\"2\" r:id=\"rId2\""), "{text}");
        assert!(text.contains("sheetId=\"3\" r:id=\"rId3\""), "{text}");
    }

    // 3. Hidden and VeryHidden sheets emit correct state attribute.
    #[test]
    fn hidden_and_veryhidden_emit_state() {
        let mut wb = Workbook::new();
        let mut visible = Worksheet::new("Visible");
        visible.visibility = SheetVisibility::Visible;
        let mut hidden = Worksheet::new("Hidden");
        hidden.visibility = SheetVisibility::Hidden;
        let mut very_hidden = Worksheet::new("VeryHidden");
        very_hidden.visibility = SheetVisibility::VeryHidden;
        wb.add_sheet(visible);
        wb.add_sheet(hidden);
        wb.add_sheet(very_hidden);
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        // Visible: no state attribute.
        assert!(
            text.contains("<sheet name=\"Visible\" sheetId=\"1\" r:id=\"rId1\"/>"),
            "visible sheet should have no state attr: {text}"
        );
        assert!(text.contains("state=\"hidden\""), "{text}");
        assert!(text.contains("state=\"veryHidden\""), "{text}");
    }

    // 4. Workbook-scope defined name.
    #[test]
    fn defined_name_workbook_scope() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        wb.defined_names.push(DefinedName {
            name: "myRange".to_string(),
            formula: "Sheet1!A1:B2".to_string(),
            scope_sheet_index: None,
            builtin: None,
            hidden: false,
            ..Default::default()
        });
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(
            text.contains("<definedName name=\"myRange\">Sheet1!A1:B2</definedName>"),
            "{text}"
        );
        // No localSheetId when scope is workbook.
        assert!(
            !text.contains("localSheetId"),
            "unexpected localSheetId for workbook-scope name: {text}"
        );
    }

    // 5. Sheet-scope defined name has localSheetId.
    #[test]
    fn defined_name_sheet_scope() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        wb.add_sheet(Worksheet::new("Sheet2"));
        wb.defined_names.push(DefinedName {
            name: "localRange".to_string(),
            formula: "Sheet2!C3:D4".to_string(),
            scope_sheet_index: Some(1),
            builtin: None,
            hidden: false,
            ..Default::default()
        });
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(text.contains("localSheetId=\"1\""), "{text}");
    }

    // 6. Auto-inject print area from sheet.
    #[test]
    fn auto_inject_print_area_from_sheet() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        let mut sheet2 = Worksheet::new("Sheet2");
        sheet2.print_area = Some("A1:D20".to_string());
        wb.add_sheet(sheet2);
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(
            text.contains("<definedName name=\"_xlnm.Print_Area\" localSheetId=\"1\">Sheet2!A1:D20</definedName>"),
            "{text}"
        );
    }

    // 7. Print area quotes sheet name containing spaces.
    #[test]
    fn print_area_quotes_sheet_name_with_spaces() {
        let mut wb = Workbook::new();
        let mut sheet = Worksheet::new("Data Set");
        sheet.print_area = Some("A1:D20".to_string());
        wb.add_sheet(sheet);
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(
            text.contains("'Data Set'!A1:D20"),
            "expected quoted sheet name in formula: {text}"
        );
    }

    // 8. No <definedNames> block when both collections are empty.
    #[test]
    fn defined_names_block_omitted_when_both_empty() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(
            !text.contains("<definedNames>"),
            "unexpected <definedNames> when both collections empty: {text}"
        );
    }

    // 9. Sheet name with XML special chars is attribute-escaped.
    #[test]
    fn sheet_name_with_xml_special_char_escaped() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("A & B"));
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(text.contains("name=\"A &amp; B\""), "{text}");
        // Raw ampersand must not appear inside attributes.
        assert!(
            !text.contains("name=\"A & B\""),
            "raw & in attribute: {text}"
        );
    }

    // 10. Formula text content is text-escaped.
    #[test]
    fn formula_text_escaped() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        wb.defined_names.push(DefinedName {
            name: "badFormula".to_string(),
            formula: "Sheet1!A1 & B1".to_string(),
            scope_sheet_index: None,
            builtin: None,
            hidden: false,
            ..Default::default()
        });
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(
            text.contains("Sheet1!A1 &amp; B1"),
            "expected escaped & in formula text: {text}"
        );
    }

    // 11. Builtin prefix replaces the name attribute.
    #[test]
    fn builtin_prefix_applied_correctly() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        wb.defined_names.push(DefinedName {
            name: "foo".to_string(),
            formula: "Sheet1!A1:B2".to_string(),
            scope_sheet_index: Some(0),
            builtin: Some(BuiltinName::PrintArea),
            hidden: false,
            ..Default::default()
        });
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        // The rendered name must be the xlnm prefix, not the user name.
        assert!(
            text.contains("name=\"_xlnm.Print_Area\""),
            "expected _xlnm.Print_Area: {text}"
        );
        // The original user name "foo" must not appear as a name= attribute.
        assert!(
            !text.contains("name=\"foo\""),
            "user name 'foo' should not appear: {text}"
        );
    }

    // 12a. User-declared PrintArea DefinedName suppresses the sheet.print_area
    // auto-inject so the emitter never writes two `_xlnm.Print_Area` entries
    // for the same sheet (which Excel treats as a malformed workbook).
    #[test]
    fn user_print_area_suppresses_auto_inject() {
        let mut wb = Workbook::new();
        let mut sheet = Worksheet::new("Sheet1");
        sheet.print_area = Some("A1:D20".to_string());
        wb.add_sheet(sheet);
        wb.defined_names.push(DefinedName {
            name: "ignored".to_string(),
            formula: "Sheet1!A1:C10".to_string(),
            scope_sheet_index: Some(0),
            builtin: Some(BuiltinName::PrintArea),
            hidden: false,
            ..Default::default()
        });
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert_eq!(
            text.matches("_xlnm.Print_Area").count(),
            1,
            "expected a single _xlnm.Print_Area entry when both paths set it: {text}"
        );
        // The user-declared formula wins; the auto-inject's A1:D20 must not appear.
        assert!(
            text.contains("Sheet1!A1:C10"),
            "user-declared formula should win: {text}"
        );
        assert!(
            !text.contains("Sheet1!A1:D20"),
            "auto-inject formula must be suppressed: {text}"
        );
    }

    // 12b. An unrelated PrintArea entry (different sheet index) does NOT
    // suppress auto-inject on the sheet that actually has `print_area` set.
    #[test]
    fn user_print_area_for_other_sheet_does_not_suppress() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        let mut sheet2 = Worksheet::new("Sheet2");
        sheet2.print_area = Some("A1:B5".to_string());
        wb.add_sheet(sheet2);
        wb.defined_names.push(DefinedName {
            name: "pa1".to_string(),
            formula: "Sheet1!A1:C3".to_string(),
            scope_sheet_index: Some(0),
            builtin: Some(BuiltinName::PrintArea),
            hidden: false,
            ..Default::default()
        });
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert_eq!(
            text.matches("_xlnm.Print_Area").count(),
            2,
            "expected both the user-declared and auto-injected entries: {text}"
        );
        assert!(text.contains("localSheetId=\"0\""), "{text}");
        assert!(text.contains("localSheetId=\"1\""), "{text}");
    }

    // 14. <workbookProtection> emits between <workbookPr> and <bookViews>.
    #[test]
    fn workbook_protection_emitted_between_pr_and_book_views() {
        use crate::parse::workbook_security::{WorkbookProtectionSpec, WorkbookSecurity};

        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        wb.security = WorkbookSecurity {
            workbook_protection: Some(WorkbookProtectionSpec {
                lock_structure: true,
                lock_windows: true,
                workbook_algorithm_name: Some("SHA-512".into()),
                workbook_hash_value: Some("HASH==".into()),
                workbook_salt_value: Some("SALT==".into()),
                workbook_spin_count: Some(100_000),
                ..Default::default()
            }),
            file_sharing: None,
        };
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        let pr = text.find("<workbookPr ").expect("workbookPr present");
        let prot = text
            .find("<workbookProtection ")
            .expect("workbookProtection present");
        let bv = text.find("<bookViews>").expect("bookViews present");
        assert!(pr < prot, "workbookProtection must come AFTER workbookPr");
        assert!(prot < bv, "workbookProtection must come BEFORE bookViews");
        assert!(text.contains("lockStructure=\"1\""));
        assert!(text.contains("lockWindows=\"1\""));
    }

    // 15. <fileSharing> emits between <fileVersion> and <workbookPr>.
    #[test]
    fn file_sharing_emitted_between_file_version_and_workbook_pr() {
        use crate::parse::workbook_security::{FileSharingSpec, WorkbookSecurity};

        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        wb.security = WorkbookSecurity {
            workbook_protection: None,
            file_sharing: Some(FileSharingSpec {
                read_only_recommended: true,
                user_name: Some("alice".into()),
                ..Default::default()
            }),
        };
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        let fv = text.find("<fileVersion ").expect("fileVersion present");
        let fs = text.find("<fileSharing ").expect("fileSharing present");
        let pr = text.find("<workbookPr ").expect("workbookPr present");
        assert!(fv < fs, "fileSharing must come AFTER fileVersion");
        assert!(fs < pr, "fileSharing must come BEFORE workbookPr");
        assert!(text.contains("readOnlyRecommended=\"1\""));
        assert!(text.contains("userName=\"alice\""));
    }

    // 16. Empty security emits no new XML elements.
    #[test]
    fn empty_security_emits_nothing() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(!text.contains("workbookProtection"));
        assert!(!text.contains("fileSharing"));
    }

    // 17. Both security blocks emit at correct positions.
    #[test]
    fn both_security_blocks_canonical_positions() {
        use crate::parse::workbook_security::{
            FileSharingSpec, WorkbookProtectionSpec, WorkbookSecurity,
        };

        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        wb.security = WorkbookSecurity {
            workbook_protection: Some(WorkbookProtectionSpec {
                lock_structure: true,
                ..Default::default()
            }),
            file_sharing: Some(FileSharingSpec {
                read_only_recommended: true,
                ..Default::default()
            }),
        };
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        // Expected order: fileVersion → fileSharing → workbookPr →
        // workbookProtection → bookViews → sheets
        let positions: Vec<usize> = [
            "<fileVersion ",
            "<fileSharing ",
            "<workbookPr ",
            "<workbookProtection ",
            "<bookViews>",
            "<sheets>",
        ]
        .iter()
        .map(|tag| text.find(tag).unwrap_or_else(|| panic!("missing {tag}")))
        .collect();
        for window in positions.windows(2) {
            assert!(window[0] < window[1], "ordering violated: {positions:?}");
        }
    }

    // 13. Hidden flag emitted.
    #[test]
    fn hidden_flag_emitted() {
        let mut wb = Workbook::new();
        wb.add_sheet(Worksheet::new("Sheet1"));
        wb.defined_names.push(DefinedName {
            name: "secret".to_string(),
            formula: "Sheet1!A1".to_string(),
            scope_sheet_index: None,
            builtin: None,
            hidden: true,
            ..Default::default()
        });
        let bytes = emit(&wb);
        parse_ok(&bytes);
        let text = text_of(&bytes);
        assert!(text.contains("hidden=\"1\""), "{text}");
    }
}
