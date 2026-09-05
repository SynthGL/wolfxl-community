//! `xl/worksheets/sheet{N}.xml` emitter: rows, cells, merges, panes,
//! columns, print area, and sheet-scope feature blocks.
//!
//! # Element ordering
//!
//! CT_Worksheet's `<xsd:sequence>` declares 38 ordered child elements
//! (ECMA-376 §18.3.1.99). This emitter walks them in the order pinned
//! by [`wolfxl_merger::ct_worksheet_order::ECMA_ORDER`] — the same
//! table the modify-mode merger uses to insert sibling blocks into an
//! existing sheet. Section comments below cite the slot number from
//! that table (e.g. `slot 6: <sheetData>`); if the spec is ever
//! extended, update `ECMA_ORDER` once and both this emitter and the
//! merger pick it up.
//!
//! # rId convention (must match [`crate::emit::rels::emit_sheet`])
//!
//! Sheet-level relationships are allocated in this order inside
//! `xl/worksheets/_rels/sheet{N}.xml.rels`:
//!
//! 1. **Comments** (if any): `rId1` points at `commentsN.xml`,
//!    `rId2` at `vmlDrawingN.vml`.
//! 2. **Tables**: the next contiguous block. With no comments,
//!    tables start at `rId1`; with comments, at `rId3`.
//! 3. **External hyperlinks** (targets that do not start with `#`):
//!    the tail of the rId range.
//!
//! The emitter MUST walk [`Worksheet::hyperlinks`] with the same
//! filter + iteration order as `rels::emit_sheet` uses when assigning
//! `r:id` attributes in `<hyperlink>` elements, or Excel will follow
//! mismatched rIds and silently drop hyperlink targets.
//!
use crate::intern::SstBuilder;
use crate::model::format::StylesBuilder;
use crate::model::worksheet::Worksheet;

/// Emit `xl/worksheets/sheet{N}.xml` bytes for one sheet.
///
/// `sheet_idx` is zero-based; the caller converts to 1-based for any
/// user-facing references (`sheet1.xml`, `commentsN.xml`, etc.).
///
/// `sst` is mutable because string cells intern at emit time, not model
/// construction time. `styles` is immutable because all interning already
/// happened during `WriteCell` construction.
pub fn emit(
    sheet: &Worksheet,
    sheet_idx: u32,
    sst: &mut SstBuilder,
    _styles: &StylesBuilder,
) -> Vec<u8> {
    let mut out = String::with_capacity(4096);

    // XML declaration + root element
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str("<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">");

    // Slot 2: <dimension>
    super::dimension::emit(&mut out, sheet);

    // Slot 3: <sheetViews>
    //
    // If the user set a typed `views` spec on the Worksheet, prefer it;
    // the legacy path is still used otherwise so freeze/split panes set
    // via `set_freeze`/`set_split` continue to work.
    super::sheet_setup::emit_sheet_views(&mut out, sheet, sheet_idx);

    // Slot 4: <sheetFormatPr>
    //
    // If the user set a typed `sheet_format` spec on the Worksheet,
    // prefer it; the legacy hardcoded default is still emitted otherwise
    // so unmodified sheets keep byte-stable.
    super::sheet_setup::emit_sheet_format(&mut out, sheet);

    // Slot 5: <cols> (only if non-empty)
    if !sheet.columns.is_empty() {
        super::columns::emit(&mut out, sheet);
    }

    // Slot 6: <sheetData>
    //
    // Streaming write_only mode (G20 / RFC-073): if the sheet has a
    // finalized [`StreamingSheet`] attached, splice its temp-file
    // contents straight into the `<sheetData>` body instead of walking
    // the (always-empty) eager BTreeMap. Identical XML on the wire as
    // the eager path because both paths share `sheet_data::emit_row_to`.
    if let Some(stream) = sheet.streaming.as_ref() {
        if stream.row_count() == 0 {
            out.push_str("<sheetData/>");
        } else {
            out.push_str("<sheetData>");
            // I/O failure here would corrupt the sheet bytes; surface
            // it as a panic since the writer crate has no Result
            // return-channel and the FFI bridge will translate panics
            // to PyExceptions on save.
            stream
                .splice_into(&mut out)
                .expect("streaming temp file splice");
            out.push_str("</sheetData>");
        }
    } else {
        super::sheet_data::emit(&mut out, sheet, sst);
    }

    // Slot 8: <sheetProtection>
    super::sheet_setup::emit_sheet_protection(&mut out, sheet);

    // Slot 11: <autoFilter>. The bytes are pre-emitted by the
    // workbook-level coordinator from the Python
    // `ws.auto_filter.to_rust_dict()` payload via
    // `wolfxl_autofilter::emit::emit`.
    if let Some(bytes) = &sheet.auto_filter_xml {
        out.push_str(std::str::from_utf8(bytes).unwrap_or(""));
    }

    // Slot 15: <mergeCells> (only if non-empty)
    if !sheet.merges.is_empty() {
        super::merges::emit(&mut out, sheet);
    }

    // Slot 17: <conditionalFormatting>; 0..N elements per spec
    super::conditional_formats::emit(&mut out, sheet);

    // Slot 18: <dataValidations>
    super::data_validations::emit(&mut out, sheet);

    // Slot 19: <hyperlinks> (only if any exist)
    if !sheet.hyperlinks.is_empty() {
        super::hyperlinks::emit(&mut out, sheet);
    }

    // Slot 20: <printOptions>; only emitted when set.
    super::sheet_setup::emit_print_options(&mut out, sheet);

    // Slot 21: <pageMargins>; typed override or default.
    super::sheet_setup::emit_page_margins(&mut out, sheet);

    // Slot 22: <pageSetup>; only emitted when set.
    super::sheet_setup::emit_page_setup(&mut out, sheet);

    // Slot 23: <headerFooter>; only emitted when set.
    super::sheet_setup::emit_header_footer(&mut out, sheet);

    // Slot 24: <rowBreaks>; only emitted when set and non-empty.
    // Slot 25: <colBreaks>; only emitted when set and non-empty.
    super::page_breaks::emit(&mut out, sheet);

    // Slot 30: <drawing r:id="..."/>. Emitted when the sheet has images or
    // charts. The rId is appended at the end of the sheet's rels graph
    // (after comments, vml, tables, and external hyperlinks) so the
    // existing rId conventions for those entries are preserved.
    super::drawing_refs::emit_drawing(&mut out, sheet);

    // Slot 31: <legacyDrawing>; emitted when the sheet has comments.
    super::drawing_refs::emit_legacy(&mut out, sheet);

    // Slot 37: <tableParts>; one <tablePart r:id=...> per table
    super::table_parts::emit(&mut out, sheet);

    // Slot numbers above match wolfxl_merger::ct_worksheet_order::ECMA_ORDER
    // (the merger crate's own tests assert the table is the canonical 38-slot
    // §18.3.1.99 sequence; this emitter takes those numbers as the contract).
    out.push_str("</worksheet>");

    out.into_bytes()
}

/// Streaming variant of [`emit`] for write_only worksheets (G20 / RFC-073 v2).
///
/// Writes `xl/worksheets/sheet{N}.xml` straight into a streaming `io::Write`
/// sink (typically a `ZipWriter` opened on `BufWriter<File>`) without ever
/// holding the full sheet body in a single `String`. Closes the per-sheet
/// emit-time peak: at 1M rows × 5 cols the eager [`emit`] path holds ~150 MiB
/// in `out`; this path holds a few KiB of pre-/post-sheetData markup plus an
/// 8 KiB chunk for the temp-file splice.
///
/// Slot ordering is identical to [`emit`] — the same per-slot emitters write
/// into a small `String` for the head (slots 1-5) and tail (slots 8-37);
/// only the slot 6 `<sheetData>` body is `io::copy`d straight from the
/// per-sheet temp file managed by [`crate::streaming::StreamingSheet`].
///
/// Requires `sheet.streaming.is_some()`. The eager `[emit]` function
/// continues to handle non-streaming sheets and remains the path used by
/// modify-mode and the diff harness.
///
/// SST is not mutated here — streaming sheets intern strings during
/// `append_row`, so by the time we get to emit the SST is already final.
pub fn emit_streaming_to<W: std::io::Write>(
    sheet: &Worksheet,
    sheet_idx: u32,
    _styles: &StylesBuilder,
    dest: &mut W,
) -> std::io::Result<()> {
    assert!(
        sheet.streaming.is_some(),
        "emit_streaming_to requires a streaming sheet"
    );
    emit_to(sheet, sheet_idx, None, dest)
}

/// Stream either an eager worksheet or an existing write-only spool.
pub(crate) fn emit_to<W: std::io::Write>(
    sheet: &Worksheet,
    sheet_idx: u32,
    sst: Option<&mut SstBuilder>,
    dest: &mut W,
) -> std::io::Result<()> {
    // --- Head (XML decl, root, slots 2-5, opening <sheetData>) ---
    //
    // Tiny by construction: dimension + sheetViews + sheetFormatPr + cols
    // total a few hundred bytes for typical sheets, ~few KiB even with
    // many columns. Buffered into a String so the per-slot emitters
    // (which all take `&mut String`) work unchanged.
    let mut head = String::with_capacity(2048);
    head.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    head.push_str("<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">");
    super::dimension::emit(&mut head, sheet);
    super::sheet_setup::emit_sheet_views(&mut head, sheet, sheet_idx);
    super::sheet_setup::emit_sheet_format(&mut head, sheet);
    if !sheet.columns.is_empty() {
        super::columns::emit(&mut head, sheet);
    }

    // Slot 6: <sheetData>. Empty streaming sheet → self-closing tag,
    // single small write. Otherwise: write the head ending with the
    // opening tag, splice the temp file, then write `</sheetData>`.
    if let Some(stream) = sheet.streaming.as_ref() {
        if stream.row_count() == 0 {
            head.push_str("<sheetData/>");
            dest.write_all(head.as_bytes())?;
        } else {
            head.push_str("<sheetData>");
            dest.write_all(head.as_bytes())?;
            drop(head);
            stream.splice_into_writer(dest)?;
            dest.write_all(b"</sheetData>")?;
        }
    } else {
        dest.write_all(head.as_bytes())?;
        drop(head);
        super::sheet_data::emit_to(dest, sheet, sst.expect("eager sheet requires SST"))?;
    }

    // --- Tail (slots 8-37 + closing </worksheet>) ---
    //
    // In write_only mode most slots are no-ops:
    //   - merges, hyperlinks, drawing, legacy_drawing, tableParts,
    //     conditional_formats, data_validations, autoFilter — all
    //     forbidden by `_FORBIDDEN_ATTRS` in
    //     `python/wolfxl/_worksheet_write_only.py`.
    //   - sheet_protection only fires if the user set `ws.protection`,
    //     which the WriteOnlyWorksheet API doesn't expose.
    //   - page_setup, header_footer, page_breaks default to empty.
    // pageMargins always emits (typed override or default), so the
    // tail is dominated by that single ~80-byte element.
    //
    // We still call every emitter to preserve byte-parity with the
    // eager path: if a future write_only feature flips one of these
    // on, this path emits it without code changes.
    let mut tail = String::with_capacity(512);
    super::sheet_setup::emit_sheet_protection(&mut tail, sheet);
    if let Some(bytes) = &sheet.auto_filter_xml {
        tail.push_str(std::str::from_utf8(bytes).unwrap_or(""));
    }
    if !sheet.merges.is_empty() {
        super::merges::emit(&mut tail, sheet);
    }
    super::conditional_formats::emit(&mut tail, sheet);
    super::data_validations::emit(&mut tail, sheet);
    if !sheet.hyperlinks.is_empty() {
        super::hyperlinks::emit(&mut tail, sheet);
    }
    super::sheet_setup::emit_print_options(&mut tail, sheet);
    super::sheet_setup::emit_page_margins(&mut tail, sheet);
    super::sheet_setup::emit_page_setup(&mut tail, sheet);
    super::sheet_setup::emit_header_footer(&mut tail, sheet);
    super::page_breaks::emit(&mut tail, sheet);
    super::drawing_refs::emit_drawing(&mut tail, sheet);
    super::drawing_refs::emit_legacy(&mut tail, sheet);
    super::table_parts::emit(&mut tail, sheet);
    tail.push_str("</worksheet>");
    dest.write_all(tail.as_bytes())?;

    Ok(())
}

/// Compile-time assertion that the slot numbers cited in `emit`'s section
/// comments match `wolfxl_merger::ct_worksheet_order::ECMA_ORDER`. If a
/// future ECMA extension renumbers a slot, this fails to compile until both
/// this emitter and the merger are updated together.
#[allow(dead_code)]
const _PIN_SLOT_NUMBERS: () = {
    let order = wolfxl_merger::ct_worksheet_order::ECMA_ORDER;
    // Slots cited in `emit` above (zero-indexed positions in ECMA_ORDER).
    assert!(order[1].1 == 2); // dimension
    assert!(order[5].1 == 6); // sheetData
    assert!(order[14].1 == 15); // mergeCells
    assert!(order[16].1 == 17); // conditionalFormatting
    assert!(order[17].1 == 18); // dataValidations
    assert!(order[18].1 == 19); // hyperlinks
    assert!(order[20].1 == 21); // pageMargins
    assert!(order[30].1 == 31); // legacyDrawing
    assert!(order[36].1 == 37); // tableParts
};

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::cell::{FormulaResult, WriteCell, WriteCellValue};
    use crate::model::worksheet::{Column, FreezePane, Hyperlink, Merge, Worksheet};
    use quick_xml::events::Event;
    use quick_xml::Reader;

    #[test]
    fn eager_stream_matches_buffered_dense_sparse_and_escaped_data() {
        let mut sheet = Worksheet::new("S");
        for row in 1..=2000 {
            sheet
                .append_dense_row(
                    row,
                    1,
                    vec![
                        WriteCell::new(WriteCellValue::Number(row as f64 / 3.0)),
                        WriteCell::new(WriteCellValue::String(format!(" 日本語 & <{row}> "))),
                    ],
                )
                .unwrap();
        }
        sheet.set_cell(
            3,
            2,
            WriteCell::new(WriteCellValue::String("overwritten".into())),
        );
        sheet.set_cell(
            4,
            9,
            WriteCell::new(WriteCellValue::Formula {
                expr: "IF(A1<2,1,0)".repeat(20_000),
                result: None,
            }),
        );
        for empty in [false, true] {
            let empty_sheet = Worksheet::new("Empty");
            let current = if empty { &empty_sheet } else { &sheet };
            let styles = StylesBuilder::default();
            let mut reference_sst = SstBuilder::default();
            let reference = emit(&current, 0, &mut reference_sst, &styles);
            let mut actual_sst = SstBuilder::default();
            let mut actual = Vec::new();
            emit_to(&current, 0, Some(&mut actual_sst), &mut actual).unwrap();
            assert_eq!(reference, actual);
            assert_eq!(reference_sst.total_count(), actual_sst.total_count());
            assert_eq!(
                super::super::shared_strings_xml::emit(&reference_sst),
                super::super::shared_strings_xml::emit(&actual_sst)
            );
        }
    }

    #[test]
    fn eager_stream_propagates_original_io_error() {
        struct Fails;
        impl std::io::Write for Fails {
            fn write(&mut self, _: &[u8]) -> std::io::Result<usize> {
                Err(std::io::Error::new(
                    std::io::ErrorKind::BrokenPipe,
                    "test sink",
                ))
            }
            fn flush(&mut self) -> std::io::Result<()> {
                Ok(())
            }
        }
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::Number(1.0)));
        let error =
            super::super::sheet_data::emit_to(&mut Fails, &sheet, &mut SstBuilder::default())
                .unwrap_err();
        assert_eq!(error.kind(), std::io::ErrorKind::BrokenPipe);
        assert_eq!(error.to_string(), "test sink");
    }

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

    fn emit_sheet(sheet: &Worksheet, sheet_idx: u32) -> (Vec<u8>, SstBuilder) {
        let mut sst = SstBuilder::default();
        let styles = crate::model::format::StylesBuilder::default();
        let bytes = emit(sheet, sheet_idx, &mut sst, &styles);
        (bytes, sst)
    }

    // --- 1. Empty sheet ---

    #[test]
    fn empty_sheet_emits_minimal_valid_xml() {
        let sheet = Worksheet::new("X");
        let (bytes, _sst) = emit_sheet(&sheet, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(
            text.contains("<dimension ref=\"A1\"/>"),
            "dimension: {text}"
        );
        // sheetData should be empty self-close or open+close
        assert!(
            text.contains("<sheetData/>") || text.contains("<sheetData></sheetData>"),
            "empty sheetData: {text}"
        );
    }

    // --- 31. Kitchen-sink well-formed ---

    #[test]
    fn xml_well_formed_under_quick_xml() {
        let mut sheet = Worksheet::new("Kitchen");

        // Cells of each type
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::Number(42.0)));
        sheet.set_cell(1, 2, WriteCell::new(WriteCellValue::String("hello".into())));
        sheet.set_cell(1, 3, WriteCell::new(WriteCellValue::Boolean(true)));
        sheet.set_cell(
            2,
            1,
            WriteCell::new(WriteCellValue::Formula {
                expr: "SUM(A1:A1)".into(),
                result: Some(FormulaResult::Number(42.0)),
            }),
        );
        sheet.set_cell(2, 2, WriteCell::new(WriteCellValue::DateSerial(44927.0)));
        sheet.set_cell(2, 3, WriteCell::new(WriteCellValue::Blank).with_style(1));

        // Merge
        sheet.merge(Merge {
            top_row: 3,
            left_col: 1,
            bottom_row: 3,
            right_col: 2,
        });

        // Freeze
        sheet.freeze = Some(FreezePane {
            freeze_row: 1,
            freeze_col: 0,
            top_left: None,
        });

        // Column
        sheet.set_column(
            1,
            Column {
                width: Some(15.0),
                ..Default::default()
            },
        );

        // Hyperlinks (both internal and external)
        sheet.hyperlinks.insert(
            "A1".to_string(),
            Hyperlink {
                target: "https://example.com".into(),
                location: None,
                is_internal: false,
                display: Some("Example".into()),
                tooltip: None,
            },
        );
        sheet.hyperlinks.insert(
            "B1".to_string(),
            Hyperlink {
                target: "Sheet2!A1".into(),
                location: None,
                is_internal: true,
                display: None,
                tooltip: Some("Go to sheet2".into()),
            },
        );

        let (bytes, _) = emit_sheet(&sheet, 0);
        parse_ok(&bytes);
    }

    use crate::model::conditional::{ConditionalFormat, ConditionalKind, ConditionalRule};
    use crate::model::validation::{
        DataValidation, ErrorStyle, ValidationOperator, ValidationType,
    };

    fn make_cf(sqref: &str, rules: Vec<ConditionalRule>) -> ConditionalFormat {
        ConditionalFormat {
            sqref: sqref.to_string(),
            rules,
        }
    }

    fn make_rule(
        kind: ConditionalKind,
        dxf_id: Option<u32>,
        stop_if_true: bool,
    ) -> ConditionalRule {
        ConditionalRule {
            kind,
            dxf_id,
            stop_if_true,
            priority: None,
        }
    }

    fn make_dv(
        sqref: &str,
        validation_type: ValidationType,
        operator: ValidationOperator,
        formula_a: Option<&str>,
        formula_b: Option<&str>,
    ) -> DataValidation {
        DataValidation {
            sqref: sqref.to_string(),
            validation_type,
            operator,
            formula_a: formula_a.map(|s| s.to_string()),
            formula_b: formula_b.map(|s| s.to_string()),
            allow_blank: false,
            show_dropdown: false,
            show_error_message: false,
            error_style: ErrorStyle::Stop,
            error_title: None,
            error_message: None,
            show_input_message: false,
            input_title: None,
            input_message: None,
        }
    }

    // --- 52. DV ordering: CF before DV before hyperlinks ---

    #[test]
    fn dv_ordering_between_cf_and_hyperlinks() {
        let mut sheet = Worksheet::new("S");
        // Add a conditional format
        let cf_rule = make_rule(
            ConditionalKind::Expression {
                formula: "A1>0".into(),
            },
            None,
            false,
        );
        sheet.conditional_formats.push(make_cf("A1", vec![cf_rule]));

        // Add a data validation
        let dv = make_dv(
            "B1",
            ValidationType::Whole,
            ValidationOperator::GreaterThan,
            Some("0"),
            None,
        );
        sheet.validations.push(dv);

        // Add an external hyperlink
        sheet.hyperlinks.insert(
            "C1".to_string(),
            Hyperlink {
                target: "https://example.com".into(),
                location: None,
                is_internal: false,
                display: None,
                tooltip: None,
            },
        );

        let (bytes, _) = emit_sheet(&sheet, 0);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();

        let pos_cf = text.find("<conditionalFormatting").expect("CF position");
        let pos_dv = text.find("<dataValidations").expect("DV position");
        let pos_hl = text.find("<hyperlinks>").expect("hyperlinks position");

        assert!(pos_cf < pos_dv, "CF before DV: cf={pos_cf} dv={pos_dv}");
        assert!(
            pos_dv < pos_hl,
            "DV before hyperlinks: dv={pos_dv} hl={pos_hl}"
        );
    }
}
