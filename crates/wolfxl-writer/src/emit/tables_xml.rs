//! `xl/tables/table{N}.xml` emitter. Wave 3B.

use crate::model::table::Table;
use crate::xml_escape;

/// Emit the bytes of `xl/tables/table{table_idx+1}.xml`.
///
/// `_sheet_idx` is unused by this emitter but is kept in the signature because
/// the orchestrator always passes it. `table_idx` is 0-based; the XML `id`
/// attribute is `table_idx + 1` (1-based, per OOXML spec).
pub fn emit(table: &Table, _sheet_idx: usize, table_idx: usize) -> Vec<u8> {
    let mut out = String::with_capacity(1024);

    let table_id = table_idx + 1;
    let display_name = table.display_name.as_deref().unwrap_or(&table.name);

    // XML declaration
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");

    // Root <table> element
    out.push_str(&format!(
        "<table xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" \
         id=\"{id}\" name=\"{name}\" displayName=\"{display_name}\" ref=\"{range}\" \
         totalsRowCount=\"{totals_count}\" totalsRowShown=\"{totals}\">",
        id = table_id,
        name = xml_escape::attr(&table.name),
        display_name = xml_escape::attr(display_name),
        range = xml_escape::attr(&table.range),
        totals_count = if table.totals_row { "1" } else { "0" },
        totals = if table.totals_row { "1" } else { "0" },
    ));

    // <autoFilter> — omitted entirely when autofilter == false
    if table.autofilter {
        out.push_str(&format!(
            "<autoFilter ref=\"{}\"/>",
            xml_escape::attr(&table.range)
        ));
    }

    // <tableColumns count="N">
    out.push_str(&format!("<tableColumns count=\"{}\">", table.columns.len()));
    for (i, col) in table.columns.iter().enumerate() {
        let col_id = i + 1;
        out.push_str(&format!(
            "<tableColumn id=\"{}\" name=\"{}\"",
            col_id,
            xml_escape::attr(&col.name)
        ));
        if let Some(func) = &col.totals_function {
            out.push_str(&format!(
                " totalsRowFunction=\"{}\"",
                xml_escape::attr(func)
            ));
        }
        if let Some(label) = &col.totals_label {
            out.push_str(&format!(" totalsRowLabel=\"{}\"", xml_escape::attr(label)));
        }
        out.push_str("/>");
    }
    out.push_str("</tableColumns>");

    // <tableStyleInfo>
    match &table.style {
        None => {}
        Some(style) => {
            out.push_str(&format!(
                "<tableStyleInfo name=\"{name}\" \
                 showFirstColumn=\"{first}\" showLastColumn=\"{last}\" \
                 showRowStripes=\"{rows}\" showColumnStripes=\"{cols}\"/>",
                name = xml_escape::attr(&style.name),
                first = if style.show_first_column { "1" } else { "0" },
                last = if style.show_last_column { "1" } else { "0" },
                rows = if style.show_row_stripes { "1" } else { "0" },
                cols = if style.show_column_stripes { "1" } else { "0" },
            ));
        }
    }

    out.push_str("</table>");

    out.into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::table::{Table, TableColumn, TableStyle};
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn parse_ok(bytes: &[u8]) {
        let text = std::str::from_utf8(bytes).expect("utf8");
        let mut reader = Reader::from_str(text);
        let mut buf = Vec::new();
        loop {
            match reader.read_event_into(&mut buf) {
                Ok(Event::Eof) => break,
                Err(e) => panic!("XML parse error: {e}"),
                _ => {}
            }
            buf.clear();
        }
    }

    fn make_table(name: &str, range: &str, cols: Vec<&str>) -> Table {
        Table {
            name: name.into(),
            display_name: None,
            range: range.into(),
            columns: cols
                .into_iter()
                .map(|c| TableColumn {
                    name: c.into(),
                    totals_function: None,
                    totals_label: None,
                })
                .collect(),
            header_row: true,
            totals_row: false,
            style: None,
            autofilter: true,
        }
    }

    // --- 1. basic_table_well_formed ---

    #[test]
    fn basic_table_well_formed() {
        let table = make_table("MyTable", "A1:B10", vec!["Col1", "Col2"]);
        let bytes = emit(&table, 0, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<table "), "has table element: {text}");
        assert!(text.contains("id=\"1\""), "id=1: {text}");
        assert!(text.contains("name=\"MyTable\""), "name attr: {text}");
        assert!(
            text.contains("displayName=\"MyTable\""),
            "displayName attr: {text}"
        );
        assert!(
            text.contains("<autoFilter ref=\"A1:B10\"/>"),
            "autoFilter: {text}"
        );
        assert!(
            text.contains("<tableColumns count=\"2\">"),
            "count=2: {text}"
        );
        assert!(text.contains("<tableColumn id=\"1\""), "col id=1: {text}");
        assert!(text.contains("<tableColumn id=\"2\""), "col id=2: {text}");
        assert!(
            !text.contains("<tableStyleInfo"),
            "no style element when table.style is None: {text}"
        );
        assert!(
            text.contains("totalsRowShown=\"0\""),
            "totalsRowShown=0: {text}"
        );
    }

    // --- 2. display_name_differs_from_name ---

    #[test]
    fn display_name_differs_from_name() {
        let table = Table {
            name: "MyTable".into(),
            display_name: Some("Display".into()),
            range: "A1:B5".into(),
            columns: vec![TableColumn {
                name: "C1".into(),
                totals_function: None,
                totals_label: None,
            }],
            header_row: true,
            totals_row: false,
            style: None,
            autofilter: true,
        };
        let bytes = emit(&table, 0, 0);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("name=\"MyTable\""), "name attr: {text}");
        assert!(
            text.contains("displayName=\"Display\""),
            "displayName differs: {text}"
        );
    }

    // --- 3. autofilter_false_omits_element ---

    #[test]
    fn autofilter_false_omits_element() {
        let mut table = make_table("T", "A1:B5", vec!["X"]);
        table.autofilter = false;
        let bytes = emit(&table, 0, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            !text.contains("<autoFilter"),
            "no autoFilter when false: {text}"
        );
    }

    // --- 4. totals_row_true_sets_attr ---

    #[test]
    fn totals_row_true_sets_attr() {
        let mut table = make_table("T", "A1:B10", vec!["X"]);
        table.totals_row = true;
        let bytes = emit(&table, 0, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            text.contains("totalsRowShown=\"1\""),
            "totalsRowShown=1: {text}"
        );
        assert!(
            text.contains("totalsRowCount=\"1\""),
            "totalsRowCount=1: {text}"
        );
    }

    // --- 5. totals_function_and_label_on_column ---

    #[test]
    fn totals_function_and_label_on_column() {
        let table = Table {
            name: "T".into(),
            display_name: None,
            range: "A1:B10".into(),
            columns: vec![TableColumn {
                name: "Header".into(),
                totals_function: Some("sum".into()),
                totals_label: Some("Total".into()),
            }],
            header_row: true,
            totals_row: true,
            style: None,
            autofilter: true,
        };
        let bytes = emit(&table, 0, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            text.contains("totalsRowFunction=\"sum\""),
            "totalsRowFunction: {text}"
        );
        assert!(
            text.contains("totalsRowLabel=\"Total\""),
            "totalsRowLabel: {text}"
        );
    }

    // --- 6. column_without_totals_function_omits_attr ---

    #[test]
    fn column_without_totals_function_omits_attr() {
        let table = make_table("T", "A1:B5", vec!["X"]);
        let bytes = emit(&table, 0, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        // Column should have id and name but no totals attrs
        assert!(
            !text.contains("totalsRowFunction"),
            "no totalsRowFunction: {text}"
        );
        assert!(
            !text.contains("totalsRowLabel"),
            "no totalsRowLabel: {text}"
        );
        // Verify the tableColumn tag is self-closing: id="1" name="X"/>
        assert!(
            text.contains("<tableColumn id=\"1\" name=\"X\"/>"),
            "self-closing col: {text}"
        );
    }

    // --- 7. custom_table_style_overrides_default ---

    #[test]
    fn custom_table_style_overrides_default() {
        let mut table = make_table("T", "A1:B5", vec!["X"]);
        table.style = Some(TableStyle {
            name: "TableStyleLight1".into(),
            show_first_column: true,
            show_last_column: false,
            show_row_stripes: false,
            show_column_stripes: true,
        });
        let bytes = emit(&table, 0, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            text.contains("name=\"TableStyleLight1\""),
            "custom style name: {text}"
        );
        assert!(
            text.contains("showFirstColumn=\"1\""),
            "showFirstColumn: {text}"
        );
        assert!(
            text.contains("showLastColumn=\"0\""),
            "showLastColumn: {text}"
        );
        assert!(
            text.contains("showRowStripes=\"0\""),
            "showRowStripes: {text}"
        );
        assert!(
            text.contains("showColumnStripes=\"1\""),
            "showColumnStripes: {text}"
        );
        // Should NOT use default name
        assert!(
            !text.contains("TableStyleMedium9"),
            "no default style: {text}"
        );
    }

    // --- 8. xml_attr_escape_in_column_name ---

    #[test]
    fn xml_attr_escape_in_column_name() {
        let table = Table {
            name: "T".into(),
            display_name: None,
            range: "A1:B5".into(),
            columns: vec![TableColumn {
                name: "a < b & c".into(),
                totals_function: None,
                totals_label: None,
            }],
            header_row: true,
            totals_row: false,
            style: None,
            autofilter: false,
        };
        let bytes = emit(&table, 0, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        // The column name must be XML-escaped
        assert!(text.contains("&lt;"), "escaped lt: {text}");
        assert!(text.contains("&amp;"), "escaped amp: {text}");
        assert!(!text.contains("a < b"), "raw < must not appear: {text}");
    }

    // --- 9. table_id_uses_idx_plus_one ---

    #[test]
    fn table_id_uses_idx_plus_one() {
        let table0 = make_table("T0", "A1:B5", vec!["X"]);
        let table3 = make_table("T3", "C1:D5", vec!["Y"]);

        let bytes0 = emit(&table0, 0, 0);
        let text0 = String::from_utf8(bytes0).unwrap();
        assert!(text0.contains("id=\"1\""), "table_idx=0 -> id=1: {text0}");

        let bytes3 = emit(&table3, 0, 3);
        let text3 = String::from_utf8(bytes3).unwrap();
        assert!(text3.contains("id=\"4\""), "table_idx=3 -> id=4: {text3}");
    }

    // --- 10. well_formed_under_quick_xml (large fixture) ---

    #[test]
    fn well_formed_under_quick_xml() {
        let table = Table {
            name: "SalesData".into(),
            display_name: Some("Sales Data".into()),
            range: "A1:E50".into(),
            columns: vec![
                TableColumn {
                    name: "Region".into(),
                    totals_function: None,
                    totals_label: Some("All".into()),
                },
                TableColumn {
                    name: "Q1".into(),
                    totals_function: Some("sum".into()),
                    totals_label: None,
                },
                TableColumn {
                    name: "Q2".into(),
                    totals_function: Some("sum".into()),
                    totals_label: None,
                },
                TableColumn {
                    name: "Q3".into(),
                    totals_function: Some("average".into()),
                    totals_label: None,
                },
                TableColumn {
                    name: "Total".into(),
                    totals_function: Some("sum".into()),
                    totals_label: Some("Grand Total".into()),
                },
            ],
            header_row: true,
            totals_row: true,
            style: Some(TableStyle {
                name: "TableStyleDark4".into(),
                show_first_column: false,
                show_last_column: true,
                show_row_stripes: true,
                show_column_stripes: false,
            }),
            autofilter: true,
        };
        let bytes = emit(&table, 0, 2);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("id=\"3\""), "table_idx=2 -> id=3: {text}");
        assert!(
            text.contains("<tableColumns count=\"5\">"),
            "5 columns: {text}"
        );
        assert!(text.contains("totalsRowShown=\"1\""), "totals row: {text}");
        assert!(
            text.contains("displayName=\"Sales Data\""),
            "displayName: {text}"
        );
    }
}
