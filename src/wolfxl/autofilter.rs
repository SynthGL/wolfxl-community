//! Sprint Ο Pod 1B (RFC-056) — AutoFilter patcher integration.
//!
//! This module is **Phase 2.5o**, sequenced AFTER pivots (Phase 2.5m)
//! and BEFORE Phase 3 cell patches per RFC-056 §5. The code here is
//! the PyO3-bound boundary; the typed model + emit + evaluation logic
//! all lives in the PyO3-free `wolfxl-autofilter` crate.
//!
//! Drainage steps per sheet with a queued AutoFilter:
//!
//!   1. Collect the current cell values inside `auto_filter.ref` from
//!      the sheet's existing XML (read-back path, mirrors how
//!      `Cell.value` reads cell content).
//!   2. Call `wolfxl_autofilter::evaluate` to compute the
//!      `hidden_row_indices` permutation. The sort permutation is
//!      returned but not applied (RFC-056 §8: physical row reorder
//!      deferred to v2.1).
//!   3. Splice the new `<autoFilter>` block via
//!      `SheetBlock::AutoFilter` (the merger replaces any existing
//!      `<autoFilter>` element idempotently).
//!   4. Emit `<row r="N" hidden="1">` markers via row patches.
//!
//! See `Plans/rfcs/056-autofilter-eval.md` and `src/wolfxl/pivot.rs`
//! (Phase 2.5m) for the structural template.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::BTreeMap;

type PyObject = Py<PyAny>;

use wolfxl_autofilter::{
    emit as af_emit, evaluate as af_evaluate, parse as af_parse, AutoFilter, Cell, DictValue,
};

// ---------------------------------------------------------------------------
// Queue payload — held on `XlsxPatcher` per sheet.
// ---------------------------------------------------------------------------

/// One AutoFilter queued for emit + evaluation at Phase 2.5o.
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct QueuedAutoFilter {
    /// Owner sheet title.
    pub sheet: String,
    /// Pre-emitted §10 dict marshalled by the Python coordinator.
    /// Stored as DictValue so this struct is PyO3-free at rest.
    pub dict: DictValue,
}

// ---------------------------------------------------------------------------
// PyDict ⇄ DictValue conversion.
// ---------------------------------------------------------------------------

/// Lift a `PyAny` value into a `DictValue` tree. Used both at
/// `queue_autofilter` time and inside the `evaluate_autofilter`
/// PyO3 function.
pub(crate) fn pyany_to_dictvalue(v: &Bound<'_, PyAny>) -> PyResult<DictValue> {
    if v.is_none() {
        return Ok(DictValue::Null);
    }
    if let Ok(b) = v.extract::<bool>() {
        return Ok(DictValue::Bool(b));
    }
    if let Ok(i) = v.extract::<i64>() {
        return Ok(DictValue::Int(i));
    }
    if let Ok(f) = v.extract::<f64>() {
        return Ok(DictValue::Float(f));
    }
    if let Ok(s) = v.extract::<String>() {
        return Ok(DictValue::Str(s));
    }
    if let Ok(d) = v.cast::<PyDict>() {
        let mut out = BTreeMap::new();
        for (k, val) in d.iter() {
            let key: String = k.extract()?;
            out.insert(key, pyany_to_dictvalue(&val)?);
        }
        return Ok(DictValue::Dict(out));
    }
    if let Ok(l) = v.cast::<PyList>() {
        let mut out = Vec::with_capacity(l.len());
        for item in l.iter() {
            out.push(pyany_to_dictvalue(&item)?);
        }
        return Ok(DictValue::List(out));
    }
    // Fallback: try sequence iteration.
    if let Ok(it) = v.try_iter() {
        let mut out = Vec::new();
        for item in it {
            out.push(pyany_to_dictvalue(&item?)?);
        }
        return Ok(DictValue::List(out));
    }
    Err(PyValueError::new_err(format!(
        "unsupported value type in autofilter dict: {:?}",
        v.get_type().name()?
    )))
}

// ---------------------------------------------------------------------------
// PyO3 functions — top-level serialiser + evaluator.
// ---------------------------------------------------------------------------

/// Serialise a §10 autofilter dict to `<autoFilter>` XML bytes.
#[pyfunction]
pub fn serialize_autofilter_dict(d: &Bound<'_, PyDict>) -> PyResult<Vec<u8>> {
    let dv = pyany_to_dictvalue(&d.as_any().clone())?;
    let af: AutoFilter = af_parse::parse_autofilter(&dv).map_err(PyValueError::new_err)?;
    Ok(af_emit::emit(&af))
}

/// Evaluate an autofilter dict against a row matrix.
///
/// `rows_data` is a list of rows; each row is a list of cells. A cell
/// is one of:
///   * `None` → empty
///   * `bool`, `int`, `float` → numeric/bool
///   * `str` → string
///   * `{"date": <serial>}` → an Excel serial (number cell, but
///     dynamic-date filters dispatch on it).
///
/// Returns `{"hidden": [int], "sort_order": [int] | None}`.
#[pyfunction]
#[pyo3(signature = (d, rows_data, ref_date_serial=None))]
pub fn evaluate_autofilter(
    py: Python<'_>,
    d: &Bound<'_, PyDict>,
    rows_data: &Bound<'_, PyList>,
    ref_date_serial: Option<f64>,
) -> PyResult<PyObject> {
    let dv = pyany_to_dictvalue(&d.as_any().clone())?;
    let af: AutoFilter = af_parse::parse_autofilter(&dv).map_err(PyValueError::new_err)?;

    // Convert rows_data to Vec<Vec<Cell>>.
    let mut rows: Vec<Vec<Cell>> = Vec::with_capacity(rows_data.len());
    for row in rows_data.iter() {
        let row_list = row
            .cast::<PyList>()
            .map_err(|_| PyValueError::new_err("rows_data: each row must be a list"))?;
        let mut cells: Vec<Cell> = Vec::with_capacity(row_list.len());
        for cell in row_list.iter() {
            cells.push(pyany_to_cell(&cell)?);
        }
        rows.push(cells);
    }

    let result = af_evaluate::evaluate_autofilter(&rows, &af, ref_date_serial);

    let out = PyDict::new(py);
    let hidden = PyList::new(py, result.hidden_row_indices.iter().copied())?;
    out.set_item("hidden", hidden)?;
    match result.sort_order {
        Some(order) => {
            out.set_item("sort_order", PyList::new(py, order.iter().copied())?)?;
        }
        None => {
            out.set_item("sort_order", py.None())?;
        }
    }
    Ok(out.into())
}

fn pyany_to_cell(v: &Bound<'_, PyAny>) -> PyResult<Cell> {
    if v.is_none() {
        return Ok(Cell::Empty);
    }
    if let Ok(d) = v.cast::<PyDict>() {
        if let Ok(Some(date)) = d.get_item("date") {
            let n: f64 = date.extract()?;
            return Ok(Cell::Date(n));
        }
    }
    if let Ok(b) = v.extract::<bool>() {
        // bool BEFORE int because bool is a subclass of int in Python.
        // But pyo3 extracts bool first reliably.
        return Ok(Cell::Bool(b));
    }
    if let Ok(i) = v.extract::<i64>() {
        return Ok(Cell::Number(i as f64));
    }
    if let Ok(f) = v.extract::<f64>() {
        return Ok(Cell::Number(f));
    }
    if let Ok(s) = v.extract::<String>() {
        return Ok(Cell::String(s));
    }
    Err(PyValueError::new_err(format!(
        "unsupported cell value type: {:?}",
        v.get_type().name()?
    )))
}

// ---------------------------------------------------------------------------
// Patcher Phase 2.5o — drainage helper.
// ---------------------------------------------------------------------------

/// Result of running Phase 2.5o for one sheet: the autoFilter block
/// bytes (for `SheetBlock::AutoFilter`) plus the rows to mark hidden.
#[derive(Debug, Clone, Default)]
pub struct AutoFilterDrainResult {
    /// Pre-rendered `<autoFilter>` payload bytes. Empty if there's
    /// nothing to splice.
    pub block_bytes: Vec<u8>,
    /// 0-based row offsets within `auto_filter.ref` that the
    /// evaluator marked hidden. The patcher converts these to
    /// 1-based sheet rows when emitting `<row hidden>` markers.
    pub hidden_offsets: Vec<u32>,
    /// Sort permutation (best-effort; v2.0 stores it for inspection
    /// but does not physically reorder rows). RFC-056 §8 deferral.
    #[allow(dead_code)]
    pub sort_order: Option<Vec<u32>>,
}

/// Run the evaluation half of Phase 2.5o on the typed model. Pure
/// PyO3-free helper; the cdylib's `apply_autofilter_phase` calls this
/// after extracting cell values via the existing read-back path.
pub fn drain_autofilter(
    queued: &QueuedAutoFilter,
    rows: &[Vec<Cell>],
    ref_date_serial: Option<f64>,
) -> Result<AutoFilterDrainResult, String> {
    let af = af_parse::parse_autofilter(&queued.dict)?;
    let block_bytes = af_emit::emit(&af);
    let result = af_evaluate::evaluate_autofilter(rows, &af, ref_date_serial);
    Ok(AutoFilterDrainResult {
        block_bytes,
        hidden_offsets: result.hidden_row_indices,
        sort_order: result.sort_order,
    })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_dict() -> DictValue {
        let mut m = BTreeMap::new();
        m.insert("ref".to_string(), DictValue::Str("A1:B3".into()));
        m.insert(
            "filter_columns".to_string(),
            DictValue::List(vec![{
                let mut fc = BTreeMap::new();
                fc.insert("col_id".to_string(), DictValue::Int(0));
                fc.insert(
                    "filter".to_string(),
                    DictValue::Dict({
                        let mut fd = BTreeMap::new();
                        fd.insert("kind".to_string(), DictValue::Str("number".into()));
                        fd.insert(
                            "filters".to_string(),
                            DictValue::List(vec![DictValue::Float(2.0)]),
                        );
                        fd
                    }),
                );
                DictValue::Dict(fc)
            }]),
        );
        m.insert("sort_state".to_string(), DictValue::Null);
        DictValue::Dict(m)
    }

    #[test]
    fn drain_yields_block_and_hidden() {
        let q = QueuedAutoFilter {
            sheet: "Sheet1".into(),
            dict: dummy_dict(),
        };
        let rows = vec![
            vec![Cell::Number(1.0)],
            vec![Cell::Number(2.0)],
            vec![Cell::Number(3.0)],
        ];
        let r = drain_autofilter(&q, &rows, None).unwrap();
        assert!(!r.block_bytes.is_empty());
        // Row offset 0 (=1) and 2 (=3) hide; offset 1 (=2) keeps.
        assert_eq!(r.hidden_offsets, vec![0, 2]);
    }
}
