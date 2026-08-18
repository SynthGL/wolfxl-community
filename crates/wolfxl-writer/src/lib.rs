//! wolfxl-writer — native xlsx writer for wolfxl.
//!
//! # Design
//!
//! A pure-Rust OOXML emitter that replaces `rust_xlsxwriter`. The writer is
//! split into three layers:
//!
//! 1. [`model`] — pure data (Workbook, Worksheet, Row, WriteCell, format specs).
//!    No I/O, no XML. You build a model, then hand it to the emitter.
//! 2. [`emit`] — one module per OOXML part (styles.xml, sheet1.xml, workbook.xml, ...).
//!    Each module takes the relevant slice of the model and returns UTF-8 bytes.
//! 3. [`zip`] — deterministic ZIP packager that assembles emitted parts into a
//!    valid xlsx container.
//!
//! The top-level [`Workbook`] facade orchestrates all three.
//!
//! # Determinism
//!
//! Byte-identical output is a non-goal for shipping but a gold-star target for
//! the differential test harness. To get close:
//!
//! - `WOLFXL_TEST_EPOCH=0` env var → ZIP entry mtimes are forced to the Unix
//!   epoch (1970-01-01) so two runs produce identical bytes.
//! - `BTreeMap` for row/cell collections → emission order matches the OOXML
//!   spec's "sorted ascending by `r` attribute" rule without an extra sort pass.
//! - `IndexMap` for author lists → preserves insertion order (fixes the
//!   `rust_xlsxwriter` BTreeMap bug that corrupted mixed-author comment files).
//!
//! # Status
//!
//! Skeleton — public surface is stubbed while Wave 1 subagents fill in
//! `refs` and `zip`. Full usage docs arrive at Wave 4 integration.

pub mod emit;
pub mod intern;
pub mod model;
pub mod parse;
pub mod refs;
pub mod rich_text;
pub mod streaming;
pub mod xml_escape;
pub mod zip;

#[cfg(test)]
mod test_utils;

pub use model::workbook::Workbook;
pub use model::worksheet::Worksheet;

/// Render a complete `.xlsx` archive from the in-memory workbook.
///
/// This is the W4 entry point used by the `NativeWorkbook` pyclass and by
/// the `tests/roundtrip_minimal.rs` integration test. It emits every Wave
/// 1+2+3 part, packages them in canonical ZIP order, and returns the raw
/// bytes — the caller writes them to disk (or hands them to a diff tool).
///
/// Thin wrapper around [`emit_xlsx_to`]: allocates a `Vec<u8>` and writes
/// the archive into it. Prefer [`emit_xlsx_to`] when you have a destination
/// `Write + Seek` sink (e.g. `BufWriter<File>`) — it skips the final
/// in-memory ZIP materialisation (RFC-073 v1.5).
///
/// Mutates `wb` because sheet emission interns strings into the workbook's
/// shared-string table; SST emission has to run AFTER all sheets to see
/// the final intern set. The mutation is monotonic (only string indices
/// are added) — calling `emit_xlsx` twice on the same workbook produces
/// the same archive both times.
pub fn emit_xlsx(wb: &mut Workbook) -> Vec<u8> {
    let mut buf = std::io::Cursor::new(Vec::<u8>::new());
    emit_xlsx_to(wb, &mut buf).expect("emit_xlsx_to into Vec");
    buf.into_inner()
}

/// Stream a complete `.xlsx` archive directly into `dest`.
///
/// Same contract as [`emit_xlsx`] for parts and ordering, but skips the
/// final in-memory ZIP materialisation. Sheet/styles/SST bodies are still
/// built up as `Vec<u8>` entries because most emitters build them via
/// `String` accumulators; only the final ZIP container streams to `dest`.
///
/// `dest` must be `Write + Seek` because `ZipWriter` patches local-file-
/// header sizes after each entry. Production callers pass a
/// `BufWriter<File>`.
pub fn emit_xlsx_to<W: std::io::Write + std::io::Seek>(
    wb: &mut Workbook,
    dest: &mut W,
) -> Result<(), std::io::Error> {
    use crate::emit::drawings::DrawingItem;
    use crate::emit::{
        calc_chain_xml, charts, comments_xml, content_types, doc_props, drawings, drawings_vml,
        persons_xml, rels, shared_strings_xml, sheet_xml, styles_xml, tables_xml,
        threaded_comments_xml, workbook_xml,
    };
    use crate::zip::ZipEntry;

    // RFC-068: synthesize legacy comment placeholders + tc= authors before
    // any sheet emit runs, so each top-level threaded comment has a paired
    // legacy `<comment>` and the workbook author table contains the
    // `tc={guid}` synthetic author entries.
    threaded_comments_xml::synthesize_legacy_placeholders(wb);

    // RFC-073 v2 (sheet-body streaming): each sheet entry is either a
    // pre-computed `Vec<u8>` (eager path) or an in-place stream from a
    // per-sheet temp file (write_only path). Eager-sheet emit mutates the
    // SST as it walks string cells; streaming sheets already interned at
    // `append_row` time, so by save the SST is final regardless. Both
    // paths end up at the same SST state before `shared_strings_xml::emit`
    // runs below.
    let mut sheet_ops: Vec<EmitOp> = Vec::with_capacity(wb.sheets.len());
    for (idx, sheet) in wb.sheets.iter().enumerate() {
        let path = format!("xl/worksheets/sheet{}.xml", idx + 1);
        if sheet.streaming.is_some() {
            sheet_ops.push(EmitOp::SheetStream {
                path,
                sheet_idx: idx,
            });
        } else {
            let bytes = sheet_xml::emit(sheet, idx as u32, &mut wb.sst, &wb.styles);
            sheet_ops.push(EmitOp::Bytes(ZipEntry { path, bytes }));
        }
    }

    let mut ops: Vec<EmitOp> = vec![
        EmitOp::Bytes(ZipEntry {
            path: "[Content_Types].xml".to_string(),
            bytes: content_types::emit(wb),
        }),
        EmitOp::Bytes(ZipEntry {
            path: "_rels/.rels".to_string(),
            bytes: rels::emit_root(wb),
        }),
        EmitOp::Bytes(ZipEntry {
            path: "xl/workbook.xml".to_string(),
            bytes: workbook_xml::emit(wb),
        }),
        EmitOp::Bytes(ZipEntry {
            path: "xl/_rels/workbook.xml.rels".to_string(),
            bytes: rels::emit_workbook(wb),
        }),
    ];
    ops.append(&mut sheet_ops);
    for idx in 0..wb.sheets.len() {
        let sheet_rels = rels::emit_sheet(wb, idx);
        if !sheet_rels.is_empty() {
            ops.push(EmitOp::Bytes(ZipEntry {
                path: format!("xl/worksheets/_rels/sheet{}.xml.rels", idx + 1),
                bytes: sheet_rels,
            }));
        }
    }

    // Wave 3 rich-feature parts: emit only for sheets that actually use them.
    // Tables are globally numbered (table1.xml, table2.xml, ...) across all
    // sheets — this counter mirrors the rels allocation logic in emit_sheet.
    let mut global_table_idx: usize = 1;
    for (idx, sheet) in wb.sheets.iter().enumerate() {
        if !sheet.comments.is_empty() {
            ops.push(EmitOp::Bytes(ZipEntry {
                path: format!("xl/comments/comments{}.xml", idx + 1),
                bytes: comments_xml::emit(sheet, &wb.comment_authors),
            }));
            ops.push(EmitOp::Bytes(ZipEntry {
                path: format!("xl/drawings/vmlDrawing{}.vml", idx + 1),
                bytes: drawings_vml::emit(sheet),
            }));
        }
        if !sheet.threaded_comments.is_empty() {
            ops.push(EmitOp::Bytes(ZipEntry {
                path: format!("xl/threadedComments/threadedComments{}.xml", idx + 1),
                bytes: threaded_comments_xml::emit(&sheet.threaded_comments),
            }));
        }
        for table in &sheet.tables {
            // The path counter is 1-based (table1.xml, table2.xml, …);
            // `tables_xml::emit` interprets its third argument as a
            // 0-based `table_idx` and emits `id="(idx+1)"`. Subtract
            // one so the emitted `id` matches the part filename
            // (RFC-024 cross-mode parity gate; modify-mode allocates
            // workbook-unique ids starting at 1, which matches the
            // emit fn's contract from
            // `tables_xml::tests::table_id_uses_idx_plus_one`).
            ops.push(EmitOp::Bytes(ZipEntry {
                path: format!("xl/tables/table{}.xml", global_table_idx),
                bytes: tables_xml::emit(table, idx, global_table_idx - 1),
            }));
            global_table_idx += 1;
        }
    }

    // Sprint Λ Pod-β + Sprint Μ Pod-α — drawings + media + charts.
    // Drawings are numbered globally per sheet that has at least one
    // image or chart; media + charts are numbered globally across all
    // sheets. All counters reset to 1 at the start of save (write
    // mode is always a fresh workbook — no existing-on-disk
    // allocations to seed around).
    let mut global_drawing_idx: usize = 1;
    let mut global_image_idx: u32 = 1;
    let mut global_chart_idx: u32 = 1;
    for (sheet_idx, sheet) in wb.sheets.iter().enumerate() {
        if sheet.images.is_empty() && sheet.charts.is_empty() {
            continue;
        }
        // Allocate global indices for images and charts on this sheet.
        let image_indices: Vec<u32> = sheet
            .images
            .iter()
            .map(|_| {
                let n = global_image_idx;
                global_image_idx += 1;
                n
            })
            .collect();
        let chart_indices: Vec<u32> = sheet
            .charts
            .iter()
            .map(|_| {
                let n = global_chart_idx;
                global_chart_idx += 1;
                n
            })
            .collect();

        // Emit the drawing rels (image + chart rIds inside the drawing part).
        let (drawing_rels_bytes, image_rids, chart_rids) =
            rels::emit_drawing_rels_with_charts(sheet, &image_indices, &chart_indices);
        ops.push(EmitOp::Bytes(ZipEntry {
            path: format!("xl/drawings/_rels/drawing{}.xml.rels", global_drawing_idx),
            bytes: drawing_rels_bytes,
        }));

        // Build a unified DrawingItem list (images first, then charts —
        // matches the drawing-rels rId order).
        let mut items: Vec<DrawingItem> =
            Vec::with_capacity(sheet.images.len() + sheet.charts.len());
        for (img, rid) in sheet.images.iter().zip(image_rids.iter()) {
            items.push(DrawingItem::Image {
                image: img.clone(),
                rid: rid.clone(),
            });
        }
        for ((idx, ch), rid) in sheet.charts.iter().enumerate().zip(chart_rids.iter()) {
            items.push(DrawingItem::Chart {
                anchor: ch.anchor.clone(),
                rid: rid.clone(),
                chart_id: (idx + 1) as u32,
                name: format!("Chart {}", idx + 1),
            });
        }
        // Emit the drawing part itself (graphicFrame for charts +
        // pic for images).
        let drawing_bytes = drawings::emit_drawing_xml(&items);
        ops.push(EmitOp::Bytes(ZipEntry {
            path: format!("xl/drawings/drawing{}.xml", global_drawing_idx),
            bytes: drawing_bytes,
        }));

        // Emit the media bytes for images.
        for (img, &n) in sheet.images.iter().zip(image_indices.iter()) {
            ops.push(EmitOp::Bytes(ZipEntry {
                path: format!("xl/media/image{}.{}", n, img.ext),
                bytes: img.data.clone(),
            }));
        }

        // Emit chart parts (one xl/charts/chartN.xml per chart).
        for (chart, &n) in sheet.charts.iter().zip(chart_indices.iter()) {
            ops.push(EmitOp::Bytes(ZipEntry {
                path: format!("xl/charts/chart{}.xml", n),
                bytes: charts::emit_chart_xml(chart),
            }));
        }

        let _ = sheet_idx; // silence unused when not building debug
        global_drawing_idx += 1;
    }

    ops.extend([
        EmitOp::Bytes(ZipEntry {
            path: "xl/styles.xml".to_string(),
            bytes: styles_xml::emit(&wb.styles),
        }),
        EmitOp::Bytes(ZipEntry {
            path: "xl/sharedStrings.xml".to_string(),
            bytes: shared_strings_xml::emit(&wb.sst),
        }),
        EmitOp::Bytes(ZipEntry {
            path: "docProps/core.xml".to_string(),
            bytes: doc_props::emit_core(wb),
        }),
        EmitOp::Bytes(ZipEntry {
            path: "docProps/app.xml".to_string(),
            bytes: doc_props::emit_app(wb),
        }),
    ]);

    // RFC-068: workbook-scoped personList — only emit when at least one
    // person is registered. Excel always uses the singular file name.
    if !wb.persons.is_empty() {
        ops.push(EmitOp::Bytes(ZipEntry {
            path: "xl/persons/personList.xml".to_string(),
            bytes: persons_xml::emit(&wb.persons),
        }));
    }

    // Sprint Θ Pod-C3: write-mode calcChain. Only emit when the
    // workbook has at least one formula cell — Excel transparently
    // works without it, so an empty workbook should ship without the
    // part (matching openpyxl's behaviour).
    if let Some(cc_bytes) = calc_chain_xml::emit(wb) {
        ops.push(EmitOp::Bytes(ZipEntry {
            path: "xl/calcChain.xml".to_string(),
            bytes: cc_bytes,
        }));
    }

    package_emit_ops(&ops, wb, dest)
}

/// One queued OOXML part awaiting packaging.
///
/// Most parts are pre-built `Vec<u8>` byte buffers (`Bytes`). For
/// `Workbook(write_only=True)` sheets, the body is too large to materialise
/// in RAM, so we defer body emission until the `ZipWriter` has opened the
/// file entry — `SheetStream` carries the sheet index, and the dispatch
/// loop calls [`emit::sheet_xml::emit_streaming_to`] straight into the
/// open ZIP entry.
enum EmitOp {
    Bytes(crate::zip::ZipEntry),
    SheetStream {
        path: String,
        /// Index into [`Workbook::sheets`].
        sheet_idx: usize,
    },
}

/// Walk the canonical-order ops list and stream each part into `dest`.
///
/// Mirrors the body of [`crate::zip::package_to`] for the `Bytes` arm so
/// byte-equality vs the buffered `package` path is preserved entry-by-entry.
/// For the `SheetStream` arm, opens the ZIP entry with DEFLATE (sheet
/// bodies are always over the STORE threshold) and hands the writer to
/// [`emit::sheet_xml::emit_streaming_to`], which `io::copy`s the
/// per-sheet temp file straight through.
fn package_emit_ops<W: std::io::Write + std::io::Seek>(
    ops: &[EmitOp],
    wb: &crate::Workbook,
    dest: &mut W,
) -> Result<(), std::io::Error> {
    use ::zip::write::SimpleFileOptions;
    use ::zip::{CompressionMethod, ZipWriter};

    /// Match the const in `zip.rs`. Tiny entries (rels stubs, docProps)
    /// gain nothing from DEFLATE so we use STORE for parity with the
    /// buffered `package_to` path.
    const DEFLATE_MIN_BYTES: usize = 128;
    const FAST_SAVE_DEFLATE_LEVEL: i64 = 1;

    let mut writer = ZipWriter::new(dest);
    let epoch_override = crate::zip::test_epoch_override().and_then(epoch_to_zip_datetime);

    let zip_to_io = |e: ::zip::result::ZipError| std::io::Error::other(e.to_string());

    for op in ops {
        match op {
            EmitOp::Bytes(entry) => {
                let method = if entry.bytes.len() < DEFLATE_MIN_BYTES {
                    CompressionMethod::Stored
                } else {
                    CompressionMethod::Deflated
                };
                let mut opts = SimpleFileOptions::default().compression_method(method);
                if method == CompressionMethod::Deflated {
                    opts = opts.compression_level(Some(FAST_SAVE_DEFLATE_LEVEL));
                }
                if let Some(dt) = epoch_override {
                    opts = opts.last_modified_time(dt);
                }
                writer
                    .start_file(entry.path.clone(), opts)
                    .map_err(zip_to_io)?;
                std::io::Write::write_all(&mut writer, &entry.bytes)?;
            }
            EmitOp::SheetStream { path, sheet_idx } => {
                // Streaming sheet bodies are always large enough to deflate;
                // even an empty sheet emits ~300 bytes of head/tail markup.
                let mut opts = SimpleFileOptions::default()
                    .compression_method(CompressionMethod::Deflated)
                    .compression_level(Some(FAST_SAVE_DEFLATE_LEVEL));
                if let Some(dt) = epoch_override {
                    opts = opts.last_modified_time(dt);
                }
                writer.start_file(path.clone(), opts).map_err(zip_to_io)?;
                let sheet = &wb.sheets[*sheet_idx];
                crate::emit::sheet_xml::emit_streaming_to(
                    sheet,
                    *sheet_idx as u32,
                    &wb.styles,
                    &mut writer,
                )?;
            }
        }
    }
    writer.finish().map_err(zip_to_io)?;
    Ok(())
}

/// Mirror of `zip::epoch_to_zip_datetime`. Kept private to this module so
/// the dispatch loop has access without exposing the zip-module helper.
fn epoch_to_zip_datetime(epoch_secs: i64) -> Option<::zip::DateTime> {
    let dt = chrono::DateTime::<chrono::Utc>::from_timestamp(epoch_secs, 0)?;
    let year: u16 = dt
        .naive_utc()
        .date()
        .format("%Y")
        .to_string()
        .parse()
        .ok()?;
    if year < 1980 {
        return ::zip::DateTime::from_date_and_time(1980, 1, 1, 0, 0, 0).ok();
    }
    if year > 2107 {
        return ::zip::DateTime::from_date_and_time(2107, 12, 31, 23, 59, 58).ok();
    }
    use chrono::{Datelike, Timelike};
    let naive = dt.naive_utc();
    ::zip::DateTime::from_date_and_time(
        naive.year() as u16,
        naive.month() as u8,
        naive.day() as u8,
        naive.hour() as u8,
        naive.minute() as u8,
        naive.second() as u8,
    )
    .ok()
}
