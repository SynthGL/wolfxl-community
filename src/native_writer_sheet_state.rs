//! Sheet-state adapters for the native writer backend.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use wolfxl_writer::model::{Column, Worksheet};
use wolfxl_writer::refs;

/// Apply a 1-based row height to a worksheet.
pub(crate) fn apply_row_height(ws: &mut Worksheet, row: u32, height: f64) {
    ws.set_row_height(row, height);
}

/// Apply per-row metadata from the openpyxl-shaped RowDimension proxy.
pub(crate) fn apply_row_dimension(
    ws: &mut Worksheet,
    row_num: u32,
    payload: &Bound<'_, PyDict>,
) -> PyResult<()> {
    let height = payload
        .get_item("height")?
        .and_then(|value| value.extract::<f64>().ok());
    let hidden = payload
        .get_item("hidden")?
        .and_then(|value| value.extract::<bool>().ok())
        .unwrap_or(false);
    let _outline_level = payload
        .get_item("outline_level")?
        .and_then(|value| value.extract::<u8>().ok())
        .unwrap_or(0);

    if let Some(height) = height {
        ws.set_row_height(row_num, height);
    }

    let row = ws.rows.entry(row_num).or_default();
    row.hidden = hidden;
    Ok(())
}

/// Apply a column width from an Excel column-letter string.
pub(crate) fn apply_column_width(ws: &mut Worksheet, col_str: &str, width: f64) -> PyResult<()> {
    let col = refs::letters_to_col(col_str)
        .ok_or_else(|| PyValueError::new_err(format!("Invalid column letter: {col_str}")))?;
    ws.set_column_width(col, width);
    Ok(())
}

/// Apply per-column metadata from the openpyxl-shaped ColumnDimension proxy.
pub(crate) fn apply_column_dimension(
    ws: &mut Worksheet,
    col_str: &str,
    payload: &Bound<'_, PyDict>,
) -> PyResult<()> {
    let col = refs::letters_to_col(col_str)
        .ok_or_else(|| PyValueError::new_err(format!("Invalid column letter: {col_str}")))?;
    let width = payload
        .get_item("width")?
        .and_then(|value| value.extract::<f64>().ok());
    let hidden = payload
        .get_item("hidden")?
        .and_then(|value| value.extract::<bool>().ok())
        .unwrap_or(false);
    let outline_level = payload
        .get_item("outline_level")?
        .and_then(|value| value.extract::<u8>().ok())
        .unwrap_or(0);

    ws.set_column(
        col,
        Column {
            width,
            hidden,
            outline_level,
            style_id: None,
        },
    );
    Ok(())
}

/// Add a merged-cell range after normalizing absolute markers.
pub(crate) fn apply_merged_range(ws: &mut Worksheet, range_str: &str) -> PyResult<()> {
    let cleaned = range_str.replace('$', "");
    ws.merge_cells(&cleaned).map_err(PyValueError::new_err)
}

/// Apply oracle-shaped freeze/split pane settings to a worksheet.
pub(crate) fn apply_freeze_panes(ws: &mut Worksheet, settings: &Bound<'_, PyAny>) -> PyResult<()> {
    let dict = settings
        .cast::<PyDict>()
        .map_err(|_| PyValueError::new_err("settings must be a dict"))?;

    let inner: Option<Bound<'_, PyAny>> = dict.get_item("freeze")?;
    let cfg: &Bound<'_, PyDict> = match &inner {
        Some(v) => v.cast::<PyDict>().unwrap_or(dict),
        None => dict,
    };

    let mode: String = cfg
        .get_item("mode")?
        .and_then(|v| v.extract::<String>().ok())
        .unwrap_or_else(|| "freeze".to_string());

    if mode == "freeze" {
        let top_left: Option<String> = cfg
            .get_item("top_left_cell")?
            .and_then(|v| v.extract::<String>().ok());
        if let Some(cell) = top_left {
            let (row, col) = parse_a1_to_row_col(&cell)?;
            // freeze_row/col semantics in the model: rows above `freeze_row`
            // and columns left of `freeze_col` stay pinned; the top-left
            // cell's (row, col) is the freeze split point.
            ws.set_freeze(row, col, Some((row, col)));
        }
    } else if mode == "split" {
        let x_split: f64 = cfg
            .get_item("x_split")?
            .and_then(|v| v.extract::<f64>().ok())
            .unwrap_or(0.0);
        let y_split: f64 = cfg
            .get_item("y_split")?
            .and_then(|v| v.extract::<f64>().ok())
            .unwrap_or(0.0);
        ws.set_split(x_split, y_split, None);
    }

    Ok(())
}

/// Apply print area metadata to a worksheet.
pub(crate) fn apply_print_area(ws: &mut Worksheet, range_str: &str) {
    ws.print_area = Some(range_str.to_string());
}

/// Apply parsed sheet setup blocks to a worksheet.
pub(crate) fn apply_sheet_setup(ws: &mut Worksheet, payload: &Bound<'_, PyDict>) -> PyResult<()> {
    let specs = crate::wolfxl::sheet_setup::parse_sheet_setup_payload(payload)?;
    ws.views = specs.sheet_view;
    ws.protection = specs.sheet_protection;
    ws.print_options = specs.print_options;
    ws.page_margins = specs.page_margins;
    ws.page_setup = specs.page_setup;
    ws.header_footer = specs.header_footer;
    // print_titles is workbook-scope; routed via definedNames queue on the
    // Python side, not here.
    Ok(())
}

/// Apply parsed page-break and sheet-format blocks to a worksheet.
pub(crate) fn apply_page_breaks(ws: &mut Worksheet, payload: &Bound<'_, PyDict>) -> PyResult<()> {
    let queued = crate::wolfxl::page_breaks::parse_page_breaks_payload(payload)?;
    ws.row_breaks = queued.row_breaks;
    ws.col_breaks = queued.col_breaks;
    ws.sheet_format = queued.sheet_format;
    Ok(())
}

fn parse_a1_to_row_col(a1: &str) -> PyResult<(u32, u32)> {
    let cleaned = a1.replace('$', "");
    refs::parse_a1(&cleaned)
        .ok_or_else(|| PyValueError::new_err(format!("Invalid A1 reference: {a1}")))
}
