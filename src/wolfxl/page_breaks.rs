//! RFC-062 Phase 2.5r — page-breaks queue parser + drain helpers.
//!
//! Consumes the §10 dict shape produced by
//! `Worksheet.to_rust_page_breaks_dict()` and
//! `Worksheet.to_rust_sheet_format_dict()` on the Python side and
//! turns them into typed Rust specs ready to feed the emitters in
//! `wolfxl_writer::parse::page_breaks`. The patcher's Phase 2.5r
//! then turns those specs into bytes and emits one
//! [`wolfxl_merger::SheetBlock`] per non-empty block for splice via
//! `merge_blocks`.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use wolfxl_writer::parse::page_breaks::{BreakSpec, PageBreakList, SheetFormatProperties};

// ---------------------------------------------------------------------------
// QueuedPageBreaks — the patcher's per-sheet queue entry.
// ---------------------------------------------------------------------------

/// One queued page-breaks + sheet-format mutation, keyed in
/// [`crate::XlsxPatcher::queued_page_breaks`] by sheet title.
///
/// All three slots can be `None` independently: a queue entry with
/// every slot `None` is treated as "user reset everything to default"
/// and Phase 2.5r drops the entry on Python's `_flush` no-op pass.
#[derive(Debug, Clone, Default)]
pub struct QueuedPageBreaks {
    pub row_breaks: Option<PageBreakList>,
    pub col_breaks: Option<PageBreakList>,
    pub sheet_format: Option<SheetFormatProperties>,
}

impl QueuedPageBreaks {
    /// `True` iff every slot is `None`. Phase 2.5r short-circuits.
    pub fn is_empty(&self) -> bool {
        self.row_breaks.is_none() && self.col_breaks.is_none() && self.sheet_format.is_none()
    }
}

// ---------------------------------------------------------------------------
// Parser — Python dict → typed specs
// ---------------------------------------------------------------------------

fn extract_u32(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<u32>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract::<u32>()?)),
        _ => Ok(None),
    }
}

fn extract_bool(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<bool>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract::<bool>()?)),
        _ => Ok(None),
    }
}

fn extract_f64(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<f64>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract::<f64>()?)),
        _ => Ok(None),
    }
}

fn parse_break(d: &Bound<'_, PyDict>) -> PyResult<BreakSpec> {
    Ok(BreakSpec {
        id: extract_u32(d, "id")?.unwrap_or(0),
        min: extract_u32(d, "min")?,
        max: extract_u32(d, "max")?,
        man: extract_bool(d, "man")?.unwrap_or(true),
        pt: extract_bool(d, "pt")?.unwrap_or(false),
    })
}

fn parse_page_break_list(d: &Bound<'_, PyDict>) -> PyResult<PageBreakList> {
    let count = extract_u32(d, "count")?.unwrap_or(0);
    let manual_break_count = extract_u32(d, "manual_break_count")?.unwrap_or(0);
    let breaks: Vec<BreakSpec> = match d.get_item("breaks")? {
        Some(v) if !v.is_none() => {
            let list = v.cast::<PyList>().map_err(|_| {
                PyValueError::new_err("queue_page_breaks_update: 'breaks' must be a list or None")
            })?;
            let mut out = Vec::with_capacity(list.len());
            for item in list.iter() {
                let bd = item.cast::<PyDict>().map_err(|_| {
                    PyValueError::new_err("queue_page_breaks_update: 'breaks' items must be dicts")
                })?;
                out.push(parse_break(bd)?);
            }
            out
        }
        _ => Vec::new(),
    };
    Ok(PageBreakList {
        count,
        manual_break_count,
        breaks,
    })
}

fn parse_sheet_format(d: &Bound<'_, PyDict>) -> PyResult<SheetFormatProperties> {
    let mut spec = SheetFormatProperties::default();
    if let Some(n) = extract_u32(d, "base_col_width")? {
        spec.base_col_width = n;
    }
    spec.default_col_width = extract_f64(d, "default_col_width")?;
    if let Some(h) = extract_f64(d, "default_row_height")? {
        spec.default_row_height = h;
    }
    if let Some(b) = extract_bool(d, "custom_height")? {
        spec.custom_height = Some(b);
    }
    if let Some(b) = extract_bool(d, "zero_height")? {
        spec.zero_height = Some(b);
    }
    if let Some(b) = extract_bool(d, "thick_top")? {
        spec.thick_top = Some(b);
    }
    if let Some(b) = extract_bool(d, "thick_bottom")? {
        spec.thick_bottom = Some(b);
    }
    if let Some(n) = extract_u32(d, "outline_level_row")? {
        spec.outline_level_row = n;
    }
    if let Some(n) = extract_u32(d, "outline_level_col")? {
        spec.outline_level_col = n;
    }
    Ok(spec)
}

/// Parse a Python dict matching RFC-062 §10 into a typed
/// [`QueuedPageBreaks`].
///
/// `payload` shape:
///
/// ```text
/// {
///   "row_breaks":   {...} | None,   # PageBreakList dict
///   "col_breaks":   {...} | None,
///   "sheet_format": {...} | None,
/// }
/// ```
pub fn parse_page_breaks_payload(payload: &Bound<'_, PyDict>) -> PyResult<QueuedPageBreaks> {
    let row_breaks = match payload.get_item("row_breaks")? {
        Some(v) if !v.is_none() => Some(parse_page_break_list(v.cast::<PyDict>().map_err(
            |_| {
                PyValueError::new_err(
                    "queue_page_breaks_update: 'row_breaks' must be a dict or None",
                )
            },
        )?)?),
        _ => None,
    };
    let col_breaks = match payload.get_item("col_breaks")? {
        Some(v) if !v.is_none() => Some(parse_page_break_list(v.cast::<PyDict>().map_err(
            |_| {
                PyValueError::new_err(
                    "queue_page_breaks_update: 'col_breaks' must be a dict or None",
                )
            },
        )?)?),
        _ => None,
    };
    let sheet_format = match payload.get_item("sheet_format")? {
        Some(v) if !v.is_none() => Some(parse_sheet_format(v.cast::<PyDict>().map_err(|_| {
            PyValueError::new_err("queue_page_breaks_update: 'sheet_format' must be a dict or None")
        })?)?),
        _ => None,
    };
    Ok(QueuedPageBreaks {
        row_breaks,
        col_breaks,
        sheet_format,
    })
}

/// PyO3 entrypoint exposed at module top-level — serialize a single
/// page-breaks dict (row + col + sheet_format slots) to a flat
/// `(row_xml, col_xml, sheet_format_xml)` triple. Used by tests and
/// by external callers wanting to pre-emit XML for the splice.
#[pyfunction]
pub fn serialize_page_breaks_dict(
    payload: &Bound<'_, PyDict>,
) -> PyResult<(Vec<u8>, Vec<u8>, Vec<u8>)> {
    let queued = parse_page_breaks_payload(payload)?;
    let row_xml = queued
        .row_breaks
        .as_ref()
        .map(wolfxl_writer::parse::page_breaks::emit_row_breaks)
        .unwrap_or_default();
    let col_xml = queued
        .col_breaks
        .as_ref()
        .map(wolfxl_writer::parse::page_breaks::emit_col_breaks)
        .unwrap_or_default();
    let fmt_xml = queued
        .sheet_format
        .as_ref()
        .map(wolfxl_writer::parse::page_breaks::emit_sheet_format_pr)
        .unwrap_or_default();
    Ok((row_xml, col_xml, fmt_xml))
}
