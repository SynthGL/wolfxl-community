//! G17 / RFC-070 — PyO3 bindings for the minimal pivot mutation
//! parser. Used by the Python load path to populate
//! `Worksheet.pivot_tables` handles in modify mode.
//!
//! Two functions are exported:
//!
//! - `parse_pivot_table_meta(xml: bytes) -> dict` — extracts `name`,
//!   `location_ref`, `cache_id` from a `pivotTable*.xml` part.
//! - `parse_pivot_cache_source(xml: bytes) -> dict` — extracts
//!   `range`, `sheet`, `field_count` from a `pivotCacheDefinition*.xml`
//!   part.
//!
//! Both raise `ValueError` on any malformed-input or missing-element
//! case. The Python caller wraps these in `PivotTableHandle` instances.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use wolfxl_pivot::mutate::{
    parse_pivot_cache_source as core_parse_cache, parse_pivot_table_meta as core_parse_table,
};

/// Parse a pivot-table part's metadata.
#[pyfunction]
pub fn parse_pivot_table_meta<'py>(py: Python<'py>, xml: &[u8]) -> PyResult<Bound<'py, PyDict>> {
    let meta = core_parse_table(xml).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let d = PyDict::new(py);
    d.set_item("name", meta.name)?;
    d.set_item("location_ref", meta.location_ref)?;
    d.set_item("cache_id", meta.cache_id)?;
    Ok(d)
}

/// Parse a pivot cache definition's source metadata.
#[pyfunction]
pub fn parse_pivot_cache_source<'py>(py: Python<'py>, xml: &[u8]) -> PyResult<Bound<'py, PyDict>> {
    let meta = core_parse_cache(xml).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let d = PyDict::new(py);
    d.set_item("range", meta.range)?;
    d.set_item("sheet", meta.sheet)?;
    d.set_item("field_count", meta.field_count)?;
    Ok(d)
}
