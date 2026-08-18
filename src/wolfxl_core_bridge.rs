//! PyO3 bridge to `wolfxl-core` classifiers.
//!
//! Sprint 2 task #22a. This module is purely additive: it exposes
//! `wolfxl_core`'s value-add functions (`classify_format`,
//! `classify_sheet`, `infer_sheet_schema`) to Python so cdylib call sites can
//! share the same heuristics instead of reimplementing them. The duplicate
//! per-cell classifiers inside the cdylib are *not* replaced here — that
//! wiring is task #22b, which lands as a follow-up PR to keep this one easy to
//! review.
//!
//! The three wrappers all follow the same shape:
//!
//! 1. Accept native Python inputs (strings, lists of lists of scalars).
//! 2. Convert to `wolfxl_core`'s types (`Cell`, `CellValue`, `Sheet`).
//! 3. Call the core function.
//! 4. Convert the result back to a Python value (string, dict).
//!
//! Invariant B1 from the sprint plan says `wolfxl-core` is the
//! semantic authority. This bridge is how the PyO3 surface starts
//! honoring that invariant.
//!
//! ## Supported input shapes
//!
//! Row-of-cells conversion handles the usual Python scalars a caller
//! might already have:
//!
//! - `None`                → [`CellValue::Empty`]
//! - `bool`                → [`CellValue::Bool`]
//! - `int`                 → [`CellValue::Int`]
//! - `float`               → [`CellValue::Float`]
//! - `str`                 → [`CellValue::String`]
//! - `datetime.datetime`   → [`CellValue::DateTime`]
//! - `datetime.date`       → [`CellValue::Date`]
//! - `datetime.time`       → [`CellValue::Time`]
//!
//! Anything else is coerced to its `str()` representation and stored
//! as a string. This matches what a caller would get if they piped
//! through `str(value)` themselves. If an object's `__str__` raises,
//! that Python exception is propagated.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBool, PyDate, PyDateTime, PyDict, PyFloat, PyInt, PyList, PyTime};

use chrono::{NaiveDate, NaiveDateTime, NaiveTime};

use wolfxl_core::{
    classify_format as core_classify_format, classify_sheet as core_classify_sheet,
    infer_sheet_schema as core_infer_sheet_schema, Cell, CellValue, Sheet,
};

/// Convert a single Python object into a [`Cell`]. Unknown types are
/// stringified via `str()` and treated as strings. If that `__str__`
/// implementation raises, the exception propagates.
fn py_to_cell(obj: &Bound<'_, PyAny>) -> PyResult<Cell> {
    if obj.is_none() {
        return Ok(Cell::empty());
    }

    // Order matters: `bool` is a subclass of `int` in Python, so match
    // it first. `datetime.datetime` is a subclass of `datetime.date`,
    // so match datetime before date.
    if let Ok(b) = obj.cast::<PyBool>() {
        return Ok(Cell {
            value: CellValue::Bool(b.extract()?),
            number_format: None,
        });
    }
    if let Ok(i) = obj.cast::<PyInt>() {
        if let Ok(n) = i.extract::<i64>() {
            return Ok(Cell {
                value: CellValue::Int(n),
                number_format: None,
            });
        }
        let s: String = obj.str()?.to_string();
        return Ok(Cell {
            value: CellValue::String(s),
            number_format: None,
        });
    }
    if let Ok(f) = obj.cast::<PyFloat>() {
        return Ok(Cell {
            value: CellValue::Float(f.extract()?),
            number_format: None,
        });
    }

    if let Ok(dt) = obj.cast::<PyDateTime>() {
        let ndt = naive_datetime_from_py(dt)?;
        return Ok(Cell {
            value: CellValue::DateTime(ndt),
            number_format: None,
        });
    }
    if let Ok(t) = obj.cast::<PyTime>() {
        let nt = naive_time_from_py(t)?;
        return Ok(Cell {
            value: CellValue::Time(nt),
            number_format: None,
        });
    }
    if let Ok(d) = obj.cast::<PyDate>() {
        let nd = naive_date_from_py(d)?;
        return Ok(Cell {
            value: CellValue::Date(nd),
            number_format: None,
        });
    }

    // Strings + everything unknown land here. `str()` on a string is
    // a no-op, and on unknown types it gives the caller a rendered
    // representation unless that object's __str__ raises.
    let s: String = obj.str()?.to_string();
    Ok(Cell {
        value: CellValue::String(s),
        number_format: None,
    })
}

fn naive_date_from_py(d: &Bound<'_, PyDate>) -> PyResult<NaiveDate> {
    let year: i32 = d.getattr("year")?.extract()?;
    let month: u32 = d.getattr("month")?.extract()?;
    let day: u32 = d.getattr("day")?.extract()?;
    NaiveDate::from_ymd_opt(year, month, day)
        .ok_or_else(|| PyValueError::new_err(format!("invalid date: {year}-{month}-{day}")))
}

fn naive_time_from_py(t: &Bound<'_, PyTime>) -> PyResult<NaiveTime> {
    let hour: u32 = t.getattr("hour")?.extract()?;
    let minute: u32 = t.getattr("minute")?.extract()?;
    let second: u32 = t.getattr("second")?.extract()?;
    let micro: u32 = t.getattr("microsecond")?.extract()?;
    NaiveTime::from_hms_micro_opt(hour, minute, second, micro)
        .ok_or_else(|| PyValueError::new_err(format!("invalid time: {hour}:{minute}:{second}")))
}

fn naive_datetime_from_py(dt: &Bound<'_, PyDateTime>) -> PyResult<NaiveDateTime> {
    let year: i32 = dt.getattr("year")?.extract()?;
    let month: u32 = dt.getattr("month")?.extract()?;
    let day: u32 = dt.getattr("day")?.extract()?;
    let hour: u32 = dt.getattr("hour")?.extract()?;
    let minute: u32 = dt.getattr("minute")?.extract()?;
    let second: u32 = dt.getattr("second")?.extract()?;
    let micro: u32 = dt.getattr("microsecond")?.extract()?;
    let d = NaiveDate::from_ymd_opt(year, month, day)
        .ok_or_else(|| PyValueError::new_err(format!("invalid date: {year}-{month}-{day}")))?;
    let t = NaiveTime::from_hms_micro_opt(hour, minute, second, micro)
        .ok_or_else(|| PyValueError::new_err(format!("invalid time: {hour}:{minute}:{second}")))?;
    Ok(NaiveDateTime::new(d, t))
}

/// Convert Python `List[List[Any]]` into a `wolfxl_core::Sheet`. The
/// outer list is rows, the inner list is cells. Ragged rows are padded
/// to the widest row with empty cells before entering `wolfxl_core`. When
/// `number_formats` is provided, it must be the same shape as `rows`
/// (or `None` entries where no format applies) and its values are
/// attached to each cell's `number_format` field. This is how the
/// Python worksheet bridge ships per-cell `number_format` strings
/// alongside values so schema inference sees the same format
/// metadata as `wolfxl schema` on the same workbook — without it the
/// CLI and Python paths disagree on `format_category`.
fn build_sheet(
    name: &str,
    rows: &Bound<'_, PyList>,
    number_formats: Option<&Bound<'_, PyList>>,
) -> PyResult<Sheet> {
    if let Some(fmts) = number_formats {
        if fmts.len() != rows.len() {
            return Err(PyValueError::new_err(format!(
                "number_formats row count ({}) must match rows ({})",
                fmts.len(),
                rows.len()
            )));
        }
    }

    let mut grid: Vec<Vec<Cell>> = Vec::with_capacity(rows.len());
    for (row_idx, row_obj) in rows.iter().enumerate() {
        let row = row_obj
            .cast::<PyList>()
            .map_err(|_| PyValueError::new_err("each row must be a list of cell values"))?;

        let fmt_row = if let Some(fmts) = number_formats {
            let entry = fmts.get_item(row_idx)?;
            let fmt_list = entry
                .cast::<PyList>()
                .map_err(|_| {
                    PyValueError::new_err("each number_formats row must be a list of Optional[str]")
                })?
                .clone();
            if fmt_list.len() != row.len() {
                return Err(PyValueError::new_err(format!(
                    "number_formats[{}] length ({}) must match rows[{}] length ({})",
                    row_idx,
                    fmt_list.len(),
                    row_idx,
                    row.len()
                )));
            }
            Some(fmt_list)
        } else {
            None
        };

        let mut cells: Vec<Cell> = Vec::with_capacity(row.len());
        for (col_idx, cell_obj) in row.iter().enumerate() {
            let mut cell = py_to_cell(&cell_obj)?;
            if let Some(fmt_list) = &fmt_row {
                let fmt_obj = fmt_list.get_item(col_idx)?;
                if !fmt_obj.is_none() {
                    let fmt_str: String = fmt_obj.extract().map_err(|_| {
                        PyValueError::new_err("number_formats entries must be str or None")
                    })?;
                    cell.number_format = Some(fmt_str);
                }
            }
            cells.push(cell);
        }
        grid.push(cells);
    }
    let max_width = grid.iter().map(Vec::len).max().unwrap_or(0);
    for row in &mut grid {
        row.resize_with(max_width, Cell::empty);
    }
    Ok(Sheet::from_rows(name.to_string(), grid))
}

/// Python-visible `classify_format(fmt: str) -> str`.
///
/// Returns the category string (`"general"`, `"currency"`, `"date"`,
/// etc.) — the same string that `wolfxl_core::FormatCategory::as_str`
/// returns and that `wolfxl schema --format json` emits in the
/// `format` field. Thin wrapper; kept Python-visible so the sibling
/// Python layer can route format-category questions through the
/// single authoritative classifier.
#[pyfunction]
pub fn classify_format(fmt: &str) -> String {
    core_classify_format(fmt).as_str().to_string()
}

/// Python-visible `classify_sheet(rows: List[List[Any]], name: str) -> str`.
///
/// Returns the sheet-class string (`"empty"`, `"readme"`,
/// `"summary"`, `"data"`) — the same classification that
/// `wolfxl map --format json` emits in the `class` field. Callers
/// that already hold the populated cell grid can classify without
/// round-tripping through a file.
#[pyfunction]
#[pyo3(signature = (rows, name = "Sheet1"))]
pub fn classify_sheet(rows: &Bound<'_, PyList>, name: &str) -> PyResult<String> {
    let sheet = build_sheet(name, rows, None)?;
    Ok(core_classify_sheet(&sheet).as_str().to_string())
}

/// Python-visible `infer_sheet_schema(rows, name, number_formats) -> dict`.
///
/// Returns the column-schema dict in the same JSON shape as
/// `wolfxl schema --format json` emits per sheet, minus the outer
/// `"sheets"` wrapper. Keys match the CLI output exactly so
/// downstream callers can consume either surface interchangeably —
/// that byte-identical parity is what `tests/test_classifier_parity.py`
/// asserts on every run.
///
/// The optional `number_formats` argument is a parallel
/// `List[List[Optional[str]]]` the same shape as `rows`. When
/// provided, each entry populates `Cell::number_format`, so per-column
/// `format_category` matches what the CLI sees on the same workbook.
/// Without it, every cell's `number_format` defaults to `None` and
/// every column's `format` falls back to `"general"`, which causes
/// the CLI/Python surfaces to disagree on currency / percentage /
/// date workbooks.
///
/// Shape:
///
/// ```json
/// {
///   "name": "Sheet1",
///   "rows": 50,
///   "columns": [
///     {
///       "name": "Account",
///       "type": "string",
///       "format": "general",
///       "null_count": 0,
///       "unique_count": 12,
///       "unique_capped": false,
///       "cardinality": "categorical",
///       "samples": ["Revenue", "COGS", "Gross Profit"]
///     },
///     ...
///   ]
/// }
/// ```
#[pyfunction]
#[pyo3(signature = (rows, name = "Sheet1", number_formats = None))]
pub fn infer_sheet_schema<'py>(
    py: Python<'py>,
    rows: &Bound<'py, PyList>,
    name: &str,
    number_formats: Option<&Bound<'py, PyList>>,
) -> PyResult<Bound<'py, PyDict>> {
    let sheet = build_sheet(name, rows, number_formats)?;
    let schema = core_infer_sheet_schema(&sheet);

    let out = PyDict::new(py);
    out.set_item("name", &schema.sheet)?;
    out.set_item("rows", schema.rows)?;

    let cols = PyList::empty(py);
    for col in &schema.columns {
        let d = PyDict::new(py);
        d.set_item("name", &col.name)?;
        d.set_item("type", col.inferred_type.as_str())?;
        d.set_item("format", col.format_category.as_str())?;
        d.set_item("null_count", col.null_count)?;
        d.set_item("unique_count", col.unique_count)?;
        d.set_item("unique_capped", col.unique_capped)?;
        d.set_item("cardinality", col.cardinality.as_str())?;
        let samples = PyList::new(py, &col.sample_values)?;
        d.set_item("samples", samples)?;
        cols.append(d)?;
    }
    out.set_item("columns", cols)?;
    Ok(out)
}

/// Register bridge functions on the `_rust` extension module.
///
/// Exposed as a free function rather than folded into `lib.rs`'s
/// `#[pymodule]` macro so the bridge module owns its own registration
/// surface — easier to audit, and keeps `lib.rs` from accreting
/// knowledge of every bridge function name.
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(classify_format, m)?)?;
    m.add_function(wrap_pyfunction!(classify_sheet, m)?)?;
    m.add_function(wrap_pyfunction!(infer_sheet_schema, m)?)?;
    Ok(())
}
