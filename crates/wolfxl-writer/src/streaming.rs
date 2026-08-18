//! Per-sheet streaming write state for `Workbook(write_only=True)`.
//!
//! The eager write path materializes rows in four memory layers: the
//! Python `_append_buffer`, the Python `_cells` dict, the Rust
//! `Worksheet::rows: BTreeMap<u32, Row>`, and finally a single `String`
//! accumulator inside [`crate::emit::sheet_xml::emit`]. For 10M-row ETL
//! exports — wolfxl's natural use case — the BTreeMap is the dominant
//! cost: per-row tree node overhead plus retained custom heights, style
//! ids, and per-cell `WriteCell` boxing.
//!
//! Streaming mode breaks that dependency. Each `ws.append(row)` call
//! immediately encodes a `<row>...</row>` element into a per-sheet temp
//! file via the same [`crate::emit::sheet_data::emit_row_to`] helper the
//! eager path uses. At save time, [`crate::emit::sheet_xml::emit`]
//! detects [`Worksheet::streaming`] is `Some` and splices the temp
//! file's contents into the `<sheetData>` slot. Everything else in the
//! 38-slot ECMA emit sequence is unchanged.
//!
//! What stays in memory: the shared-string table (one entry per unique
//! string across the whole workbook) and the styles builder. Both
//! match openpyxl's `lxml.xmlfile` model exactly — they're irreducible
//! costs of the OOXML format, not wolfxl design choices.
//!
//! # Lifecycle
//!
//! 1. `enable(name)` — create the temp file, install a `BufWriter`,
//!    leave the writer open for appends.
//! 2. `append_row(...)` — encode one row into the open writer; bump
//!    `row_count` and `max_col`.
//! 3. `finalize()` — flush the `BufWriter` and drop it. The temp path
//!    survives so the splice phase can read it.
//! 4. `splice_into(...)` — open the temp file fresh, read its bytes,
//!    push them into the caller's `String` accumulator. Called from
//!    the `<sheetData>` slot of [`crate::emit::sheet_xml::emit`].
//! 5. `Drop` — `tempfile::NamedTempFile` deletes the file when the
//!    struct drops, even on early-return / panic paths.
//!
//! # Crash safety
//!
//! `tempfile::NamedTempFile` registers an OS-level cleanup hook on
//! graceful drop. On SIGKILL the kernel reaps file handles but the
//! temp file persists; the prefix `wolfxl-stream-{pid}-{sheet_idx}-`
//! lets admins find and clean up orphans, and reasonable temp-dir
//! retention policies (systemd-tmpfiles, macOS's periodic cleanup)
//! handle the rest.

use core::fmt;
use std::io::{self, BufWriter, Read, Write};

use tempfile::NamedTempFile;

use crate::emit::sheet_data::emit_row_to;
use crate::intern::SstBuilder;
use crate::model::worksheet::Row;

/// Per-sheet streaming state. Mutually exclusive with eager
/// [`crate::model::worksheet::Worksheet::rows`].
#[derive(Debug)]
pub struct StreamingSheet {
    /// Open temp file backing this sheet's `<sheetData>` body.
    /// Wrapped in `Option` so [`StreamingSheet::finalize`] can
    /// drop the file handle while keeping the path alive for the
    /// splice phase.
    file: Option<NamedTempFile>,
    /// `BufWriter` over the same file. `None` after [`finalize`].
    /// Buffer size of 64KiB is tuned to match the typical L2 cache
    /// line so syscall amortisation lines up with cache eviction.
    writer: Option<BufWriter<std::fs::File>>,
    /// Number of rows appended so far. Used by `<dimension>` emit and
    /// surfaced to Python via the FFI for diagnostic logging.
    row_count: u32,
    /// Highest 1-based column index seen across every appended row.
    /// Used by `<dimension>` emit to compute the bottom-right cell.
    max_col: u32,
    /// Last error captured by an append. Streaming append uses
    /// `fmt::Write`, which can only signal `fmt::Error`; any underlying
    /// `io::Error` from the file is captured here so `finalize()` can
    /// surface it back to Python.
    last_io_err: Option<io::Error>,
}

impl StreamingSheet {
    /// Open a fresh per-sheet temp file under `std::env::temp_dir()`
    /// with a `wolfxl-stream-{pid}-{sheet_idx}-` prefix.
    pub fn new(sheet_idx: u32) -> io::Result<Self> {
        let prefix = format!("wolfxl-stream-{}-{}-", std::process::id(), sheet_idx);
        let file = tempfile::Builder::new()
            .prefix(&prefix)
            .suffix(".xml")
            .tempfile()?;
        // Reopen the underlying file so the BufWriter and the
        // NamedTempFile drop guard each own their own handle. The
        // NamedTempFile keeps the path alive; the BufWriter does the
        // actual writes.
        let writer_file = file.reopen()?;
        Ok(Self {
            file: Some(file),
            writer: Some(BufWriter::with_capacity(64 * 1024, writer_file)),
            row_count: 0,
            max_col: 0,
            last_io_err: None,
        })
    }

    /// Append one row using the same encoder the eager path uses.
    ///
    /// Returns `Ok` when the row was successfully encoded into the
    /// in-memory `BufWriter` buffer. The buffer flushes lazily; any
    /// `io::Error` surfaced by an actual `write` syscall is captured
    /// in [`last_io_err`] and re-raised by [`finalize`]. Callers MUST
    /// invoke [`finalize`] before reading [`temp_path`] for the
    /// splice phase.
    pub fn append_row(&mut self, row_num: u32, row: &Row, sst: &mut SstBuilder) -> io::Result<()> {
        let writer = self.writer.as_mut().ok_or_else(|| {
            io::Error::new(io::ErrorKind::Other, "streaming sheet already finalized")
        })?;
        let mut adapter = IoFmtAdapter {
            inner: writer,
            err: None,
        };
        // Row encoder writes UTF-8 bytes through the adapter. fmt::Error
        // bubbles up only if write_str failed; we surface the original
        // io::Error captured by the adapter.
        match emit_row_to(&mut adapter, row_num, row, sst) {
            Ok(()) => {
                self.row_count = self.row_count.saturating_add(1);
                let n_cols = row.cells.keys().copied().max().unwrap_or(0);
                if n_cols > self.max_col {
                    self.max_col = n_cols;
                }
                Ok(())
            }
            Err(_fmt_err) => {
                let io_err = adapter.err.take().unwrap_or_else(|| {
                    io::Error::new(io::ErrorKind::Other, "fmt::Write returned Err")
                });
                self.last_io_err = Some(clone_io_err(&io_err));
                Err(io_err)
            }
        }
    }

    /// Flush the buffered writer and drop it. Idempotent — a second
    /// call is a no-op so the FFI bridge can call this defensively
    /// before save without tracking finalization state on the Python side.
    pub fn finalize(&mut self) -> io::Result<()> {
        if let Some(mut writer) = self.writer.take() {
            writer.flush()?;
        }
        if let Some(err) = self.last_io_err.take() {
            return Err(err);
        }
        Ok(())
    }

    /// Splice this sheet's `<sheetData>` body into `out` by reading the
    /// finalized temp file from disk. Called by the buffered eager-shape
    /// emitter at the slot-6 position when the surrounding sheet is
    /// being built up as a single `String`.
    ///
    /// Prefer [`splice_into_writer`] when emitting straight into a ZIP
    /// entry — it `io::copy`s the temp file in 8 KiB chunks instead of
    /// loading the whole body into memory.
    pub fn splice_into(&self, out: &mut String) -> io::Result<()> {
        // The writer must have been finalized — we can't read past the
        // end of an unflushed buffered stream and get correct bytes.
        debug_assert!(self.writer.is_none(), "splice_into called before finalize");

        let path = self
            .file
            .as_ref()
            .ok_or_else(|| io::Error::new(io::ErrorKind::Other, "streaming temp file dropped"))?
            .path();

        let mut buf = String::new();
        std::fs::File::open(path)?.read_to_string(&mut buf)?;
        out.push_str(&buf);
        Ok(())
    }

    /// Splice this sheet's `<sheetData>` body straight into a streaming
    /// `io::Write` sink (e.g. a `ZipWriter` opened on a `BufWriter<File>`).
    ///
    /// Uses `std::io::copy`, which buffers in 8 KiB chunks — peak in-flight
    /// memory is bounded by that chunk regardless of sheet size. This is
    /// the path that closes the per-sheet `String` accumulator: at 1M
    /// rows × 5 cols the accumulator is ~150 MiB; the 8 KiB chunk leaves
    /// it at a few KiB.
    pub fn splice_into_writer<W: Write>(&self, dest: &mut W) -> io::Result<()> {
        debug_assert!(
            self.writer.is_none(),
            "splice_into_writer called before finalize",
        );

        let path = self
            .file
            .as_ref()
            .ok_or_else(|| io::Error::new(io::ErrorKind::Other, "streaming temp file dropped"))?
            .path();

        let mut src = std::fs::File::open(path)?;
        std::io::copy(&mut src, dest)?;
        Ok(())
    }

    pub fn row_count(&self) -> u32 {
        self.row_count
    }

    pub fn max_col(&self) -> u32 {
        self.max_col
    }
}

/// Bridges `std::fmt::Write` over a `std::io::Write` sink so the same
/// row encoder feeds both the eager `String` and the streaming temp
/// file. Captures the underlying `io::Error` separately because
/// `fmt::Error` is a unit type and would otherwise lose the cause.
struct IoFmtAdapter<'a, W: Write> {
    inner: &'a mut W,
    err: Option<io::Error>,
}

impl<W: Write> fmt::Write for IoFmtAdapter<'_, W> {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        match self.inner.write_all(s.as_bytes()) {
            Ok(()) => Ok(()),
            Err(e) => {
                self.err = Some(e);
                Err(fmt::Error)
            }
        }
    }
}

/// Clone an `io::Error` defensively. The std `io::Error` is not
/// `Clone` because it can wrap an arbitrary `Box<dyn Error + Send +
/// Sync>`; reconstruct one from the kind + message so the original
/// can be returned to the caller while a copy stays on `last_io_err`
/// for the eventual `finalize()` re-raise.
fn clone_io_err(err: &io::Error) -> io::Error {
    io::Error::new(err.kind(), err.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::cell::{WriteCell, WriteCellValue};
    use crate::model::worksheet::Row;

    fn row_with(cells: &[(u32, WriteCellValue)]) -> Row {
        let mut row = Row::default();
        for (col, val) in cells {
            row.cells.insert(*col, WriteCell::new(val.clone()));
        }
        row
    }

    #[test]
    fn append_row_writes_well_formed_xml() {
        let mut sheet = StreamingSheet::new(0).expect("temp file");
        let mut sst = SstBuilder::default();

        let row = row_with(&[
            (1, WriteCellValue::Number(42.0)),
            (2, WriteCellValue::String("hi".into())),
        ]);
        sheet.append_row(1, &row, &mut sst).unwrap();
        sheet.finalize().unwrap();

        let mut out = String::new();
        sheet.splice_into(&mut out).unwrap();
        assert!(out.contains("<row r=\"1\""));
        assert!(out.contains("<c r=\"A1\"><v>42</v></c>"));
        assert!(out.contains("<c r=\"B1\" t=\"s\"><v>0</v></c>"));
    }

    #[test]
    fn sst_interns_strings_during_streaming() {
        let mut sheet = StreamingSheet::new(0).expect("temp file");
        let mut sst = SstBuilder::default();

        sheet
            .append_row(
                1,
                &row_with(&[(1, WriteCellValue::String("x".into()))]),
                &mut sst,
            )
            .unwrap();
        sheet
            .append_row(
                2,
                &row_with(&[(1, WriteCellValue::String("y".into()))]),
                &mut sst,
            )
            .unwrap();
        sheet
            .append_row(
                3,
                &row_with(&[(1, WriteCellValue::String("x".into()))]),
                &mut sst,
            )
            .unwrap();
        sheet.finalize().unwrap();

        assert_eq!(sst.unique_count(), 2);
        assert_eq!(sst.total_count(), 3);
    }

    #[test]
    fn row_count_and_max_col_track_appends() {
        let mut sheet = StreamingSheet::new(0).expect("temp file");
        let mut sst = SstBuilder::default();

        sheet
            .append_row(
                1,
                &row_with(&[
                    (1, WriteCellValue::Number(1.0)),
                    (3, WriteCellValue::Number(3.0)),
                ]),
                &mut sst,
            )
            .unwrap();
        sheet
            .append_row(2, &row_with(&[(7, WriteCellValue::Number(7.0))]), &mut sst)
            .unwrap();
        sheet.finalize().unwrap();

        assert_eq!(sheet.row_count(), 2);
        assert_eq!(sheet.max_col(), 7);
    }

    #[test]
    fn finalize_is_idempotent() {
        let mut sheet = StreamingSheet::new(0).expect("temp file");
        let mut sst = SstBuilder::default();
        sheet
            .append_row(1, &row_with(&[(1, WriteCellValue::Number(1.0))]), &mut sst)
            .unwrap();
        sheet.finalize().unwrap();
        // Second finalize is a no-op, not an error.
        sheet.finalize().unwrap();
    }
}
