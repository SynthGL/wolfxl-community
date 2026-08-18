//! PyO3 bridge for the pure-Rust external-link parsers in
//! `wolfxl_reader::external_links` (RFC-071 / G18).
//!
//! The pure parsers live in `crates/wolfxl-reader/src/external_links.rs`
//! so they can be unit-tested without an embedded Python interpreter.
//! This file is the thin layer that converts the parsed structs into
//! Python dicts/lists for the load path in `python/wolfxl/_external_links.py`.

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};

use wolfxl_reader::external_links::{parse_part, parse_rels};

/// Parse `xl/externalLinks/externalLinkN.xml`.
///
/// Returns a dict with shape::
///
///     {
///         "book_rid": "rId1" | None,
///         "sheet_names": ["Sheet1", ...],
///         "cached_data": {sheet_id_str: [{"r": "A1", "v": "..."}], ...},
///     }
///
/// Malformed XML raises `ValueError`.
#[pyfunction]
pub fn parse_external_link_part<'py>(
    py: Python<'py>,
    xml: &Bound<'py, PyBytes>,
) -> PyResult<Bound<'py, PyDict>> {
    let parsed = parse_part(xml.as_bytes())
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e))?;

    let out = PyDict::new(py);
    match parsed.book_rid {
        Some(s) => out.set_item("book_rid", s)?,
        None => out.set_item("book_rid", py.None())?,
    }
    let names = PyList::empty(py);
    for n in parsed.sheet_names {
        names.append(n)?;
    }
    out.set_item("sheet_names", names)?;

    let cached_dict = PyDict::new(py);
    for (sid, cells) in parsed.cached_data {
        let row_list = PyList::empty(py);
        for c in cells {
            let cell = PyDict::new(py);
            cell.set_item("r", c.r#ref)?;
            cell.set_item("v", c.value)?;
            row_list.append(cell)?;
        }
        cached_dict.set_item(sid, row_list)?;
    }
    out.set_item("cached_data", cached_dict)?;
    Ok(out)
}

/// Parse `xl/externalLinks/_rels/externalLinkN.xml.rels`.
///
/// Returns a dict::
///
///     {
///         "target": "ext.xlsx" | None,
///         "target_mode": "External" | "Internal" | None,
///         "rid": "rId1" | None,
///     }
#[pyfunction]
pub fn parse_external_link_rels<'py>(
    py: Python<'py>,
    xml: &Bound<'py, PyBytes>,
) -> PyResult<Bound<'py, PyDict>> {
    let parsed = parse_rels(xml.as_bytes())
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e))?;

    let out = PyDict::new(py);
    match parsed.target {
        Some(s) => out.set_item("target", s)?,
        None => out.set_item("target", py.None())?,
    }
    match parsed.target_mode {
        Some(wolfxl_rels::TargetMode::External) => out.set_item("target_mode", "External")?,
        Some(wolfxl_rels::TargetMode::Internal) => out.set_item("target_mode", "Internal")?,
        None => out.set_item("target_mode", py.None())?,
    }
    match parsed.rid {
        Some(s) => out.set_item("rid", s)?,
        None => out.set_item("rid", py.None())?,
    }
    Ok(out)
}
