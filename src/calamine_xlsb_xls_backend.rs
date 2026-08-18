//! Sprint Κ Pod-α — Calamine-backed legacy `.xls` value-only reads.
//!
//! [`CalamineXlsBook`] presents the same Python-facing value-read API as
//! the native readers for **values + cached formula results + sheet names +
//! dimensions + bulk cell records**. All style-related accessors strictly raise
//! `NotImplementedError` with the message
//! `"styles not supported for .xls files; use .xlsx for
//! style-aware reads"`.
//!
//! The backend accepts paths *and* raw bytes (via `open_from_bytes`).
//! Reader inputs are wrapped in a small `XlsSource` enum that delegates
//! `Read + Seek` to either a `BufReader<File>` or a `Cursor<Vec<u8>>`,
//! sidestepping the non-object-safe `calamine_styles::Reader` trait.
//!
//! This module also provides [`classify_file_format_bytes`] /
//! [`classify_file_format_path`] for magic-byte sniffing — exposed
//! to Python via `_rust.classify_file_format(path_or_bytes) -> str`
//! returning `"xlsx" | "xlsb" | "xls" | "ods" | "unknown"`.

use pyo3::exceptions::{PyIOError, PyNotImplementedError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};

type PyObject = Py<PyAny>;

use std::collections::HashMap;
use std::fs::File;
use std::io::{BufReader, Cursor};

use calamine_styles::{Data, Range, Reader, Xls};
use chrono::NaiveTime;

use crate::util::{a1_to_row_col, cell_blank, cell_with_value, parse_iso_date, parse_iso_datetime};

pub use wolfxl_classify::{classify_file_format_bytes, classify_file_format_path, XlsSource};
// `FileFormat` and `XlsxSource` are re-exported by `wolfxl_classify`
// for downstream consumers; the cdylib doesn't reference them
// directly, but keeping the dependency surface small avoids
// version-skew between the cdylib and the helper crate.

// ---------------------------------------------------------------------------
// Local helpers for the binary-format value contract.
// ---------------------------------------------------------------------------

fn map_error_value(err_str: &str) -> &'static str {
    let e = err_str.to_ascii_uppercase();
    match e.as_str() {
        "DIV0" | "DIV/0" | "#DIV/0!" => "#DIV/0!",
        "NA" | "#N/A" => "#N/A",
        "VALUE" | "#VALUE!" => "#VALUE!",
        "REF" | "#REF!" => "#REF!",
        "NAME" | "#NAME?" => "#NAME?",
        "NUM" | "#NUM!" => "#NUM!",
        "NULL" | "#NULL!" => "#NULL!",
        _ => "#ERROR!",
    }
}

/// Convert a calamine [`Data`] cell value to the dict-shaped Python payload
/// used by the workbook-source dispatcher.
fn data_to_py(py: Python<'_>, value: &Data) -> PyResult<PyObject> {
    match value {
        Data::Empty => cell_blank(py),
        Data::String(s) => cell_with_value(py, "string", s.clone()),
        Data::Float(f) => cell_with_value(py, "number", *f),
        Data::Int(i) => cell_with_value(py, "number", *i as f64),
        Data::Bool(b) => cell_with_value(py, "boolean", *b),
        Data::DateTime(dt) => {
            if let Some(ndt) = dt.as_datetime() {
                let midnight = NaiveTime::from_hms_opt(0, 0, 0).unwrap();
                if ndt.time() == midnight {
                    cell_with_value(py, "date", ndt.date().format("%Y-%m-%d").to_string())
                } else {
                    cell_with_value(py, "datetime", ndt.format("%Y-%m-%dT%H:%M:%S").to_string())
                }
            } else {
                cell_with_value(py, "number", dt.as_f64())
            }
        }
        Data::DateTimeIso(s) => {
            let raw = s.trim_end_matches('Z');
            if let Some(d) = parse_iso_date(raw) {
                cell_with_value(py, "date", d.format("%Y-%m-%d").to_string())
            } else if let Some(ndt) = parse_iso_datetime(raw) {
                let midnight = NaiveTime::from_hms_opt(0, 0, 0).unwrap();
                if ndt.time() == midnight {
                    cell_with_value(py, "date", ndt.date().format("%Y-%m-%d").to_string())
                } else {
                    cell_with_value(py, "datetime", ndt.format("%Y-%m-%dT%H:%M:%S").to_string())
                }
            } else {
                cell_with_value(py, "datetime", s.clone())
            }
        }
        Data::DurationIso(s) => cell_with_value(py, "string", s.clone()),
        Data::RichText(rt) => cell_with_value(py, "string", rt.plain_text()),
        Data::Error(e) => {
            let normalized = map_error_value(&format!("{e:?}"));
            let d = PyDict::new(py);
            d.set_item("type", "error")?;
            d.set_item("value", normalized)?;
            Ok(d.into())
        }
    }
}

/// Build a `(row, col) -> formula_text` map from a calamine
/// `Range<String>` produced by `Reader::worksheet_formula`.  Mirrors
/// what the xlsx fast-path builds via direct sheet-XML parsing.
fn build_formula_map(range: &Range<String>) -> HashMap<(u32, u32), String> {
    let mut out: HashMap<(u32, u32), String> = HashMap::new();
    let (height, width) = range.get_size();
    if height == 0 || width == 0 {
        return out;
    }
    let start = range.start().unwrap_or((0, 0));
    for r in 0..height as u32 {
        for c in 0..width as u32 {
            let abs = (start.0 + r, start.1 + c);
            if let Some(f) = range.get_value(abs) {
                if !f.is_empty() {
                    out.insert(abs, f.clone());
                }
            }
        }
    }
    out
}

/// Resolve the start/end (inclusive) iteration window for a sheet
/// view.  Used by both `read_sheet_values` and `read_sheet_records`.
fn resolve_window(
    range: &Range<Data>,
    cell_range: Option<&str>,
) -> PyResult<Option<(u32, u32, u32, u32)>> {
    if let Some(cr) = cell_range {
        if !cr.is_empty() {
            let clean = cr.replace('$', "").to_ascii_uppercase();
            let parts: Vec<&str> = clean.split(':').collect();
            let a = parts[0];
            let b = if parts.len() > 1 { parts[1] } else { a };
            let (r0, c0) = a1_to_row_col(a).map_err(|msg| PyErr::new::<PyValueError, _>(msg))?;
            let (r1, c1) = a1_to_row_col(b).map_err(|msg| PyErr::new::<PyValueError, _>(msg))?;
            return Ok(Some((r0.min(r1), c0.min(c1), r0.max(r1), c0.max(c1))));
        }
    }
    let (h, w) = range.get_size();
    if h == 0 || w == 0 {
        return Ok(None);
    }
    let start = range.start().unwrap_or((0, 0));
    Ok(Some((
        start.0,
        start.1,
        start.0 + h as u32 - 1,
        start.1 + w as u32 - 1,
    )))
}

/// Python entry point — accepts either a `str` path or a `bytes`
/// payload and returns the format name.
#[pyfunction]
pub fn classify_file_format(py: Python<'_>, input: &Bound<'_, PyAny>) -> PyResult<String> {
    let _ = py;
    if let Ok(b) = input.cast::<PyBytes>() {
        return Ok(classify_file_format_bytes(b.as_bytes())
            .as_str()
            .to_string());
    }
    if let Ok(s) = input.extract::<String>() {
        return Ok(classify_file_format_path(&s).as_str().to_string());
    }
    Err(PyErr::new::<PyValueError, _>(
        "classify_file_format: expected str path or bytes",
    ))
}

// ---------------------------------------------------------------------------
// Shared "raise NotImplementedError for styles" helper
// ---------------------------------------------------------------------------

#[inline]
fn styles_unsupported<T>(format_name: &str) -> PyResult<T> {
    Err(PyErr::new::<PyNotImplementedError, _>(format!(
        "styles not supported for .{format_name} files; use .xlsx for style-aware reads"
    )))
}

// ---------------------------------------------------------------------------
// Macro: define the value-only API shared by both pyclasses.
// ---------------------------------------------------------------------------
//
// We keep this as a macro (rather than a generic struct) so each
// pyclass remains a concrete monomorphisation calamine + pyo3 can
// reason about, and so the per-format `NotImplementedError` message
// can hardcode the right extension string.

macro_rules! define_calamine_book {
    (
        struct_name = $StructName:ident,
        reader_ty   = $ReaderTy:ty,
        source_ty   = $SourceTy:ident,
        format_name = $format_name:literal,
        new_impl    = $new_fn:expr,
    ) => {
        /// Value-only calamine-backed pyclass for the indicated
        /// legacy/binary spreadsheet format.  Style accessors raise
        /// `NotImplementedError`; everything else mirrors the
        /// subset of the xlsx surface that does not require
        /// `xl/styles.xml` parsing.
        #[pyclass(unsendable)]
        pub struct $StructName {
            workbook: $ReaderTy,
            sheet_names: Vec<String>,
            file_path: Option<String>,
            range_cache: HashMap<String, Range<Data>>,
            formula_map_cache: HashMap<String, HashMap<(u32, u32), String>>,
        }

        impl $StructName {
            fn ensure_sheet_exists(&self, sheet: &str) -> PyResult<()> {
                if self.sheet_names.iter().any(|n| n == sheet) {
                    Ok(())
                } else {
                    Err(PyErr::new::<PyValueError, _>(format!(
                        "Unknown sheet: {sheet}"
                    )))
                }
            }

            fn ensure_value_caches(&mut self, sheet: &str) -> PyResult<()> {
                if self.range_cache.contains_key(sheet) {
                    return Ok(());
                }
                let range = self.workbook.worksheet_range(sheet).map_err(|e| {
                    PyErr::new::<PyIOError, _>(format!("Failed to read sheet {sheet}: {e:?}"))
                })?;
                self.range_cache.insert(sheet.to_string(), range);

                // Formulas are independently cached; failure here is
                // non-fatal — many workbooks simply have no formulas.
                if !self.formula_map_cache.contains_key(sheet) {
                    let fmap = match self.workbook.worksheet_formula(sheet) {
                        Ok(r) => build_formula_map(&r),
                        Err(_) => HashMap::new(),
                    };
                    self.formula_map_cache.insert(sheet.to_string(), fmap);
                }
                Ok(())
            }
        }

        #[pymethods]
        impl $StructName {
            /// Open a workbook from a filesystem path.
            #[staticmethod]
            pub fn open(path: &str) -> PyResult<Self> {
                let f = File::open(path)
                    .map_err(|e| PyErr::new::<PyIOError, _>(format!("Failed to open file: {e}")))?;
                let source = $SourceTy::File(BufReader::new(f));
                let wb = $new_fn(source)?;
                let names = wb.sheet_names().to_vec();
                Ok(Self {
                    workbook: wb,
                    sheet_names: names,
                    file_path: Some(path.to_string()),
                    range_cache: HashMap::new(),
                    formula_map_cache: HashMap::new(),
                })
            }

            /// Open a workbook from raw bytes (Pod-β bytes-input path).
            #[staticmethod]
            pub fn open_from_bytes(data: &[u8]) -> PyResult<Self> {
                let source = $SourceTy::Bytes(Cursor::new(data.to_vec()));
                let wb = $new_fn(source)?;
                let names = wb.sheet_names().to_vec();
                Ok(Self {
                    workbook: wb,
                    sheet_names: names,
                    file_path: None,
                    range_cache: HashMap::new(),
                    formula_map_cache: HashMap::new(),
                })
            }

            /// Sheet names in workbook order.
            pub fn sheet_names(&self) -> Vec<String> {
                self.sheet_names.clone()
            }

            /// Optional file path (None when opened from bytes).
            pub fn source_path(&self) -> Option<String> {
                self.file_path.clone()
            }

            /// True when the underlying workbook was loaded from an
            /// in-memory bytes buffer rather than a file on disk.
            pub fn opened_from_bytes(&self) -> bool {
                self.file_path.is_none()
            }

            /// Return the (height, width) of the cached value range,
            /// or `None` for empty sheets.  Mirrors the xlsx
            /// `read_sheet_dimensions` shape (1-based max-row,
            /// max-col).
            pub fn read_sheet_dimensions(&mut self, sheet: &str) -> PyResult<Option<(u32, u32)>> {
                self.ensure_sheet_exists(sheet)?;
                self.ensure_value_caches(sheet)?;
                let range = self.range_cache.get(sheet).unwrap();
                let (h, w) = range.get_size();
                if h == 0 || w == 0 {
                    return Ok(None);
                }
                let start = range.start().unwrap_or((0, 0));
                Ok(Some((start.0 + h as u32, start.1 + w as u32)))
            }

            /// 1-based ``(min_row, min_col, max_row, max_col)`` used
            /// range bounds.
            pub fn read_sheet_bounds(
                &mut self,
                sheet: &str,
            ) -> PyResult<Option<(u32, u32, u32, u32)>> {
                self.ensure_sheet_exists(sheet)?;
                self.ensure_value_caches(sheet)?;
                let range = self.range_cache.get(sheet).unwrap();
                let (h, w) = range.get_size();
                if h == 0 || w == 0 {
                    return Ok(None);
                }
                let start = range.start().unwrap_or((0, 0));
                Ok(Some((
                    start.0 + 1,
                    start.1 + 1,
                    start.0 + h as u32,
                    start.1 + w as u32,
                )))
            }

            /// Bulk-read all sheet values as a `list[list[dict]]`.
            #[pyo3(signature = (sheet, cell_range = None, data_only = false))]
            pub fn read_sheet_values(
                &mut self,
                py: Python<'_>,
                sheet: &str,
                cell_range: Option<&str>,
                data_only: bool,
            ) -> PyResult<PyObject> {
                self.ensure_sheet_exists(sheet)?;
                self.ensure_value_caches(sheet)?;
                let range = self.range_cache.get(sheet).unwrap();
                let win = match resolve_window(range, cell_range)? {
                    Some(w) => w,
                    None => return Ok(PyList::empty(py).into()),
                };
                let (start_row, start_col, end_row, end_col) = win;
                let fmap = self.formula_map_cache.get(sheet);

                let outer = PyList::empty(py);
                for row in start_row..=end_row {
                    let inner = PyList::empty(py);
                    for col in start_col..=end_col {
                        if !data_only {
                            if let Some(fm) = fmap {
                                if let Some(f) = fm.get(&(row, col)) {
                                    let formula = if f.starts_with('=') {
                                        f.clone()
                                    } else {
                                        format!("={f}")
                                    };
                                    let d = PyDict::new(py);
                                    d.set_item("type", "formula")?;
                                    d.set_item("formula", &formula)?;
                                    d.set_item("value", &formula)?;
                                    inner.append(d)?;
                                    continue;
                                }
                            }
                        }
                        match range.get_value((row, col)) {
                            None => inner.append(cell_blank(py)?)?,
                            Some(v) => inner.append(data_to_py(py, v)?)?,
                        }
                    }
                    outer.append(inner)?;
                }
                Ok(outer.into())
            }

            /// Read a single cell value as the same dict shape used
            /// by `read_sheet_values`.  Useful for spot reads.
            #[pyo3(signature = (sheet, a1, data_only = false))]
            pub fn read_cell_value(
                &mut self,
                py: Python<'_>,
                sheet: &str,
                a1: &str,
                data_only: bool,
            ) -> PyResult<PyObject> {
                let (row, col) = a1_to_row_col(a1).map_err(|m| PyErr::new::<PyValueError, _>(m))?;
                self.ensure_sheet_exists(sheet)?;
                self.ensure_value_caches(sheet)?;
                if !data_only {
                    if let Some(fm) = self.formula_map_cache.get(sheet) {
                        if let Some(f) = fm.get(&(row, col)) {
                            let formula = if f.starts_with('=') {
                                f.clone()
                            } else {
                                format!("={f}")
                            };
                            let d = PyDict::new(py);
                            d.set_item("type", "formula")?;
                            d.set_item("formula", &formula)?;
                            d.set_item("value", &formula)?;
                            return Ok(d.into());
                        }
                    }
                }
                let range = self.range_cache.get(sheet).unwrap();
                match range.get_value((row, col)) {
                    None => cell_blank(py),
                    Some(v) => data_to_py(py, v),
                }
            }

            /// Return the `(row, col) -> formula_text` map for a sheet.
            pub fn read_sheet_formulas(
                &mut self,
                sheet: &str,
            ) -> PyResult<HashMap<(u32, u32), String>> {
                self.ensure_sheet_exists(sheet)?;
                self.ensure_value_caches(sheet)?;
                Ok(self
                    .formula_map_cache
                    .get(sheet)
                    .cloned()
                    .unwrap_or_default())
            }

            // ---- Style accessors: strict NotImplementedError ----

            pub fn read_cell_font(&self, _row: u32, _col: u32, _sheet: &str) -> PyResult<()> {
                styles_unsupported($format_name)
            }
            pub fn read_cell_fill(&self, _row: u32, _col: u32, _sheet: &str) -> PyResult<()> {
                styles_unsupported($format_name)
            }
            pub fn read_cell_border(&self, _row: u32, _col: u32, _sheet: &str) -> PyResult<()> {
                styles_unsupported($format_name)
            }
            pub fn read_cell_alignment(&self, _row: u32, _col: u32, _sheet: &str) -> PyResult<()> {
                styles_unsupported($format_name)
            }
            pub fn read_cell_number_format(
                &self,
                _row: u32,
                _col: u32,
                _sheet: &str,
            ) -> PyResult<()> {
                styles_unsupported($format_name)
            }
            pub fn read_column_styles(&self, _sheet: &str) -> PyResult<()> {
                styles_unsupported($format_name)
            }
            pub fn read_row_styles(&self, _sheet: &str) -> PyResult<()> {
                styles_unsupported($format_name)
            }
            pub fn read_sheet_records(
                &self,
                _sheet: &str,
                _cell_range: Option<&str>,
                _data_only: bool,
                _include_format: bool,
            ) -> PyResult<()> {
                styles_unsupported($format_name)
            }
        }
    };
}

define_calamine_book! {
    struct_name = CalamineXlsBook,
    reader_ty   = Xls<XlsSource>,
    source_ty   = XlsSource,
    format_name = "xls",
    new_impl    = (|src: XlsSource| -> PyResult<Xls<XlsSource>> {
        Xls::new(src).map_err(|e| {
            PyErr::new::<PyIOError, _>(format!("Failed to parse xls: {e:?}"))
        })
    }),
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

// Pure-Rust tests for the format classifier and the source enums
// live in the sibling `wolfxl-classify` crate so that
// `cargo test --workspace --exclude wolfxl` exercises them
// directly (the cdylib here cannot link a standalone test binary
// against the Python framework on macOS).
