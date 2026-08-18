//! Integration tests for `Workbook(write_only=True)` streaming write
//! mode (G20 / RFC-073).
//!
//! These cases exercise the splice between the per-sheet
//! [`StreamingSheet`] temp file and the [`sheet_xml::emit`] slot-6
//! `<sheetData>` block. The streaming path must produce byte-identical
//! XML to the eager path because both share `sheet_data::emit_row_to`;
//! the splice exists only to remove the BTreeMap accumulation cost.
//!
//! What we check:
//!
//! 1. `streaming_row_xml_well_formed` — the spliced sheet XML parses
//!    cleanly with quick-xml end-to-end.
//! 2. `streaming_strings_intern_into_sst` — string interning still
//!    flows through `SstBuilder` during streaming append, so a save
//!    that includes streaming sheets builds the same SST as eager.
//! 3. `streaming_save_splices_temp_file` — running a full
//!    `emit_xlsx` over a workbook with a streaming sheet yields a
//!    valid xlsx with the appended rows present in `sheet1.xml`.
//! 4. `streaming_empty_emits_self_closing_sheetdata` — a streaming
//!    sheet that received zero appends emits `<sheetData/>` exactly,
//!    matching the eager empty-sheet path.
//! 5. `streaming_byte_equal_to_eager` — appending the same N rows
//!    through streaming vs. setting them via the eager BTreeMap path
//!    produces byte-identical sheet XML. This is the structural
//!    guarantee that the two paths can never silently diverge.

use std::io::Read;

use wolfxl_writer::emit::sheet_xml;
use wolfxl_writer::intern::SstBuilder;
use wolfxl_writer::model::cell::{WriteCell, WriteCellValue};
use wolfxl_writer::model::format::StylesBuilder;
use wolfxl_writer::model::worksheet::{Row, Worksheet};
use wolfxl_writer::streaming::StreamingSheet;
use wolfxl_writer::Workbook;

fn row_with(cells: &[(u32, WriteCellValue)]) -> Row {
    let mut row = Row::default();
    for (col, val) in cells {
        row.cells.insert(*col, WriteCell::new(val.clone()));
    }
    row
}

#[test]
fn streaming_row_xml_well_formed() {
    let mut sheet = Worksheet::new("Stream");
    let mut stream = StreamingSheet::new(0).expect("temp file");
    let mut sst = SstBuilder::default();

    for r in 1..=3 {
        let row = row_with(&[
            (1, WriteCellValue::Number(r as f64)),
            (2, WriteCellValue::String(format!("row{}", r))),
        ]);
        stream.append_row(r, &row, &mut sst).unwrap();
    }
    stream.finalize().unwrap();
    sheet.streaming = Some(stream);

    let styles = StylesBuilder::default();
    let bytes = sheet_xml::emit(&sheet, 0, &mut sst, &styles);

    // quick-xml round-trips parses the bytes without errors.
    let text = std::str::from_utf8(&bytes).expect("utf8");
    let mut reader = quick_xml::Reader::from_str(text);
    let mut buf = Vec::new();
    loop {
        match reader.read_event_into(&mut buf) {
            Ok(quick_xml::events::Event::Eof) => break,
            Err(e) => panic!("XML parse error: {e}"),
            _ => {}
        }
        buf.clear();
    }
    // All three rows are present.
    for r in 1..=3 {
        let needle = format!("<row r=\"{}\"", r);
        assert!(text.contains(&needle), "missing row {r}: {text}");
    }
}

#[test]
fn streaming_strings_intern_into_sst() {
    let mut sheet = Worksheet::new("Stream");
    let mut stream = StreamingSheet::new(0).expect("temp file");
    let mut sst = SstBuilder::default();

    stream
        .append_row(
            1,
            &row_with(&[(1, WriteCellValue::String("alpha".into()))]),
            &mut sst,
        )
        .unwrap();
    stream
        .append_row(
            2,
            &row_with(&[(1, WriteCellValue::String("beta".into()))]),
            &mut sst,
        )
        .unwrap();
    stream
        .append_row(
            3,
            &row_with(&[(1, WriteCellValue::String("alpha".into()))]),
            &mut sst,
        )
        .unwrap();
    stream.finalize().unwrap();
    sheet.streaming = Some(stream);

    // Two unique strings, three total uses — same SST shape as eager
    // mode would produce for the same three rows.
    assert_eq!(sst.unique_count(), 2);
    assert_eq!(sst.total_count(), 3);

    // Sanity-check that the SST indices made it onto the encoded
    // <c .../> elements.
    let styles = StylesBuilder::default();
    let bytes = sheet_xml::emit(&sheet, 0, &mut sst, &styles);
    let text = std::str::from_utf8(&bytes).expect("utf8");
    assert!(text.contains("<c r=\"A1\" t=\"s\"><v>0</v></c>"));
    assert!(text.contains("<c r=\"A2\" t=\"s\"><v>1</v></c>"));
    assert!(text.contains("<c r=\"A3\" t=\"s\"><v>0</v></c>"));
}

#[test]
fn streaming_save_splices_temp_file() {
    // Drive a streaming sheet through the full `emit_xlsx` pipeline
    // and confirm the saved xlsx round-trips with the appended row
    // payloads visible in `sheet1.xml`.
    let mut wb = Workbook::new();
    let mut sheet = Worksheet::new("Streamed");
    let mut stream = StreamingSheet::new(0).expect("temp file");
    let mut tmp_sst = SstBuilder::default();

    stream
        .append_row(
            1,
            &row_with(&[
                (1, WriteCellValue::Number(1.0)),
                (2, WriteCellValue::String("apple".into())),
            ]),
            &mut tmp_sst,
        )
        .unwrap();
    stream
        .append_row(
            2,
            &row_with(&[
                (1, WriteCellValue::Number(2.0)),
                (2, WriteCellValue::String("banana".into())),
            ]),
            &mut tmp_sst,
        )
        .unwrap();
    stream.finalize().unwrap();
    sheet.streaming = Some(stream);

    // The SST built during streaming append must be merged into the
    // workbook's SST before the eager emitter runs (the workbook's
    // emit_xlsx walks workbook.sst, not the per-sheet temp SST).
    // We do that by re-interning during the eager save: in the
    // production path the FFI bridge interns directly into
    // workbook.sst from the start. For this integration test we
    // re-create the streaming sheet against the workbook's SST so
    // the two stay aligned.
    let mut sheet = Worksheet::new("Streamed");
    let mut stream = StreamingSheet::new(0).expect("temp file");
    stream
        .append_row(
            1,
            &row_with(&[
                (1, WriteCellValue::Number(1.0)),
                (2, WriteCellValue::String("apple".into())),
            ]),
            &mut wb.sst,
        )
        .unwrap();
    stream
        .append_row(
            2,
            &row_with(&[
                (1, WriteCellValue::Number(2.0)),
                (2, WriteCellValue::String("banana".into())),
            ]),
            &mut wb.sst,
        )
        .unwrap();
    stream.finalize().unwrap();
    sheet.streaming = Some(stream);
    wb.add_sheet(sheet);

    let bytes = wolfxl_writer::emit_xlsx(&mut wb);

    // Crack open the resulting ZIP and confirm sheet1.xml has both rows.
    let cursor = std::io::Cursor::new(&bytes);
    let mut zip = zip::ZipArchive::new(cursor).expect("zip open");
    let mut sheet1 = String::new();
    zip.by_name("xl/worksheets/sheet1.xml")
        .expect("sheet1.xml")
        .read_to_string(&mut sheet1)
        .unwrap();

    assert!(sheet1.contains("<row r=\"1\""), "row 1 missing: {sheet1}");
    assert!(sheet1.contains("<row r=\"2\""), "row 2 missing: {sheet1}");
    assert!(sheet1.contains("<v>1</v>"));
    assert!(sheet1.contains("<v>2</v>"));
    // String values went through SST.
    assert!(sheet1.contains("t=\"s\""));
}

#[test]
fn streaming_empty_emits_self_closing_sheetdata() {
    let mut sheet = Worksheet::new("Empty");
    let stream = StreamingSheet::new(0).expect("temp file");
    sheet.streaming = Some(stream);

    let mut sst = SstBuilder::default();
    let styles = StylesBuilder::default();
    let bytes = sheet_xml::emit(&sheet, 0, &mut sst, &styles);
    let text = std::str::from_utf8(&bytes).expect("utf8");

    assert!(
        text.contains("<sheetData/>"),
        "empty streaming sheet must self-close <sheetData/>: {text}"
    );
    // Dimension stays at A1 (matches eager empty-sheet behavior).
    assert!(text.contains("<dimension ref=\"A1\"/>"));
}

#[test]
fn streaming_byte_equal_to_eager() {
    // Same ten rows, two ways. Streaming XML inside <sheetData>...
    // </sheetData> must match the eager path byte-for-byte. Both
    // call `sheet_data::emit_row_to`, so any divergence would be a
    // bug in either the splice plumbing or row attribute handling.
    let make_rows = || {
        (1..=10u32)
            .map(|r| {
                row_with(&[
                    (1, WriteCellValue::Number(r as f64)),
                    (2, WriteCellValue::Boolean(r % 2 == 0)),
                    (3, WriteCellValue::String(format!("v{}", r))),
                ])
            })
            .collect::<Vec<_>>()
    };

    // Eager path.
    let mut eager_sheet = Worksheet::new("E");
    for (i, row) in make_rows().into_iter().enumerate() {
        let r = (i as u32) + 1;
        for (col, cell) in row.cells {
            eager_sheet.set_cell(r, col, cell);
        }
    }
    let mut eager_sst = SstBuilder::default();
    let eager_styles = StylesBuilder::default();
    let eager_bytes = sheet_xml::emit(&eager_sheet, 0, &mut eager_sst, &eager_styles);
    let eager_text = std::str::from_utf8(&eager_bytes).unwrap();
    let eager_inner = extract_sheet_data(eager_text);

    // Streaming path.
    let mut stream_sheet = Worksheet::new("S");
    let mut stream = StreamingSheet::new(0).expect("temp file");
    let mut stream_sst = SstBuilder::default();
    for (i, row) in make_rows().into_iter().enumerate() {
        let r = (i as u32) + 1;
        stream.append_row(r, &row, &mut stream_sst).unwrap();
    }
    stream.finalize().unwrap();
    stream_sheet.streaming = Some(stream);
    let stream_styles = StylesBuilder::default();
    let stream_bytes = sheet_xml::emit(&stream_sheet, 0, &mut stream_sst, &stream_styles);
    let stream_text = std::str::from_utf8(&stream_bytes).unwrap();
    let stream_inner = extract_sheet_data(stream_text);

    assert_eq!(
        eager_inner, stream_inner,
        "streaming and eager <sheetData> must be byte-identical"
    );
}

fn extract_sheet_data(s: &str) -> &str {
    let start = s.find("<sheetData").expect("sheetData start");
    let after_open = s[start..]
        .find('>')
        .map(|i| start + i + 1)
        .expect("sheetData open >");
    let close = s.find("</sheetData>").expect("sheetData close");
    &s[after_open..close]
}

#[test]
fn streaming_save_emits_byte_identical_sheet_to_eager() {
    // RFC-073 v2: the streaming-direct save path (`emit_streaming_to`)
    // bypasses the eager [`sheet_xml::emit`] String accumulator and writes
    // straight into the ZipWriter. The two paths must still produce the
    // same `xl/worksheets/sheet1.xml` bytes — both call the same per-slot
    // emitters; only the slot-6 body assembly differs.
    //
    // We pin `WOLFXL_TEST_EPOCH=0` so the surrounding ZIP container's
    // mtimes are identical; without it, the per-entry mtime differs and
    // the archive bytes diverge.
    let _epoch = EpochGuard::set("0");

    let make_rows = || {
        (1..=20u32)
            .map(|r| {
                row_with(&[
                    (1, WriteCellValue::Number(r as f64)),
                    (2, WriteCellValue::Boolean(r % 2 == 0)),
                    (3, WriteCellValue::String(format!("row-{}", r))),
                ])
            })
            .collect::<Vec<_>>()
    };

    // -- Eager path: build a regular Worksheet, save, extract sheet1.xml --
    let mut eager_wb = Workbook::new();
    let mut eager_sheet = Worksheet::new("Streamed");
    for (i, row) in make_rows().into_iter().enumerate() {
        let r = (i as u32) + 1;
        for (col, cell) in row.cells {
            eager_sheet.set_cell(r, col, cell);
        }
    }
    eager_wb.add_sheet(eager_sheet);
    let eager_archive = wolfxl_writer::emit_xlsx(&mut eager_wb);
    let eager_sheet_bytes = read_zip_entry(&eager_archive, "xl/worksheets/sheet1.xml");

    // -- Streaming path: same data via StreamingSheet, save, extract sheet1.xml --
    let mut stream_wb = Workbook::new();
    let mut stream_sheet = Worksheet::new("Streamed");
    let mut stream_obj = StreamingSheet::new(0).expect("temp file");
    for (i, row) in make_rows().into_iter().enumerate() {
        let r = (i as u32) + 1;
        stream_obj
            .append_row(r, &row, &mut stream_wb.sst)
            .expect("append");
    }
    stream_obj.finalize().expect("finalize");
    stream_sheet.streaming = Some(stream_obj);
    stream_wb.add_sheet(stream_sheet);
    let stream_archive = wolfxl_writer::emit_xlsx(&mut stream_wb);
    let stream_sheet_bytes = read_zip_entry(&stream_archive, "xl/worksheets/sheet1.xml");

    assert_eq!(
        eager_sheet_bytes, stream_sheet_bytes,
        "streaming-direct save path must produce byte-identical sheet1.xml to eager"
    );

    // SST is also identical (same strings interned in the same order).
    let eager_sst = read_zip_entry(&eager_archive, "xl/sharedStrings.xml");
    let stream_sst = read_zip_entry(&stream_archive, "xl/sharedStrings.xml");
    assert_eq!(
        eager_sst, stream_sst,
        "streaming-direct save path must produce byte-identical sharedStrings.xml to eager"
    );
}

fn read_zip_entry(archive_bytes: &[u8], path: &str) -> Vec<u8> {
    let cursor = std::io::Cursor::new(archive_bytes);
    let mut zip = zip::ZipArchive::new(cursor).expect("zip open");
    let mut entry = zip.by_name(path).expect("entry");
    let mut buf = Vec::new();
    entry.read_to_end(&mut buf).expect("read");
    buf
}

/// Restores the previous `WOLFXL_TEST_EPOCH` value when dropped.
struct EpochGuard {
    prev: Option<String>,
}

impl EpochGuard {
    fn set(value: &str) -> Self {
        let prev = std::env::var("WOLFXL_TEST_EPOCH").ok();
        // SAFETY: tests in this module never run concurrently with other
        // tests that read this env var (cargo test does run tests in
        // parallel by default, but this var is only read inside the
        // package_to / emit_xlsx_to dispatch — the guard is per-test).
        // Use the unsafe API consistent with the rest of the writer's
        // test harness.
        unsafe { std::env::set_var("WOLFXL_TEST_EPOCH", value) };
        Self { prev }
    }
}

impl Drop for EpochGuard {
    fn drop(&mut self) {
        match &self.prev {
            Some(v) => unsafe { std::env::set_var("WOLFXL_TEST_EPOCH", v) },
            None => unsafe { std::env::remove_var("WOLFXL_TEST_EPOCH") },
        }
    }
}
