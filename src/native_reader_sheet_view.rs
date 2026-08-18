//! Sheet view, sheet format, sheet properties, and freeze panes serializers.
//! Split out of `native_reader_page_setup` so each module stays under the
//! 500-LOC cap.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use wolfxl_reader::{
    FreezePane, PaneMode, SelectionInfo, SheetFormatInfo, SheetPropertiesInfo, SheetViewInfo,
};

use crate::native_reader_backend::{NativeXlsbBook, NativeXlsxBook};

type PyObject = Py<PyAny>;

// ---------- Sheet format ----------

pub(crate) fn read_sheet_format_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.sheet_format {
        Some(format) => sheet_format_to_py(py, format),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_sheet_format_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.sheet_format {
        Some(format) => sheet_format_to_py(py, format),
        None => Ok(py.None()),
    }
}

pub(crate) fn sheet_format_to_py(py: Python<'_>, format: &SheetFormatInfo) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("base_col_width", format.base_col_width)?;
    d.set_item("default_col_width", format.default_col_width)?;
    d.set_item("default_row_height", format.default_row_height)?;
    d.set_item("custom_height", format.custom_height)?;
    d.set_item("zero_height", format.zero_height)?;
    d.set_item("thick_top", format.thick_top)?;
    d.set_item("thick_bottom", format.thick_bottom)?;
    d.set_item("outline_level_row", format.outline_level_row)?;
    d.set_item("outline_level_col", format.outline_level_col)?;
    Ok(d.into())
}

// ---------- Sheet properties ----------

pub(crate) fn read_sheet_properties_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.sheet_properties {
        Some(properties) => sheet_properties_to_py(py, properties),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_sheet_properties_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.sheet_properties {
        Some(properties) => sheet_properties_to_py(py, properties),
        None => Ok(py.None()),
    }
}

pub(crate) fn sheet_properties_to_py(
    py: Python<'_>,
    properties: &SheetPropertiesInfo,
) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("code_name", properties.code_name.as_deref())?;
    d.set_item(
        "enable_format_conditions_calculation",
        properties.enable_format_conditions_calculation,
    )?;
    d.set_item("filter_mode", properties.filter_mode)?;
    d.set_item("published", properties.published)?;
    d.set_item("sync_horizontal", properties.sync_horizontal)?;
    d.set_item("sync_ref", properties.sync_ref.as_deref())?;
    d.set_item("sync_vertical", properties.sync_vertical)?;
    d.set_item("transition_evaluation", properties.transition_evaluation)?;
    d.set_item("transition_entry", properties.transition_entry)?;
    d.set_item("tab_color", properties.tab_color.as_deref())?;

    let outline = PyDict::new(py);
    outline.set_item("summary_below", properties.outline.summary_below)?;
    outline.set_item("summary_right", properties.outline.summary_right)?;
    outline.set_item("apply_styles", properties.outline.apply_styles)?;
    outline.set_item(
        "show_outline_symbols",
        properties.outline.show_outline_symbols,
    )?;
    d.set_item("outline", outline)?;

    let page_setup = PyDict::new(py);
    page_setup.set_item("auto_page_breaks", properties.page_setup.auto_page_breaks)?;
    page_setup.set_item("fit_to_page", properties.page_setup.fit_to_page)?;
    d.set_item("page_setup", page_setup)?;
    Ok(d.into())
}

// ---------- Sheet view ----------

pub(crate) fn read_sheet_view_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.sheet_view {
        Some(sheet_view) => sheet_view_to_py(py, sheet_view),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_sheet_view_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.sheet_view {
        Some(sheet_view) => sheet_view_to_py(py, sheet_view),
        None => Ok(py.None()),
    }
}

pub(crate) fn sheet_view_to_py(py: Python<'_>, sheet_view: &SheetViewInfo) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("zoom_scale", sheet_view.zoom_scale)?;
    d.set_item("zoom_scale_normal", sheet_view.zoom_scale_normal)?;
    d.set_item("view", &sheet_view.view)?;
    d.set_item("show_grid_lines", sheet_view.show_grid_lines)?;
    d.set_item("show_row_col_headers", sheet_view.show_row_col_headers)?;
    d.set_item("show_outline_symbols", sheet_view.show_outline_symbols)?;
    d.set_item("show_zeros", sheet_view.show_zeros)?;
    d.set_item("right_to_left", sheet_view.right_to_left)?;
    d.set_item("tab_selected", sheet_view.tab_selected)?;
    d.set_item("top_left_cell", sheet_view.top_left_cell.as_deref())?;
    d.set_item("workbook_view_id", sheet_view.workbook_view_id)?;
    match &sheet_view.pane {
        Some(pane) => d.set_item("pane", pane_to_py(py, pane)?)?,
        None => d.set_item("pane", py.None())?,
    }
    let selections = PyList::empty(py);
    for selection in &sheet_view.selections {
        selections.append(selection_to_py(py, selection)?)?;
    }
    d.set_item("selection", selections)?;
    Ok(d.into())
}

pub(crate) fn pane_to_py(py: Python<'_>, pane: &FreezePane) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("x_split", pane.x_split.unwrap_or_default())?;
    d.set_item("y_split", pane.y_split.unwrap_or_default())?;
    d.set_item(
        "top_left_cell",
        pane.top_left_cell.as_deref().unwrap_or("A1"),
    )?;
    d.set_item(
        "active_pane",
        pane.active_pane.as_deref().unwrap_or("topLeft"),
    )?;
    d.set_item(
        "state",
        match pane.mode {
            PaneMode::Freeze => "frozen",
            PaneMode::Split => "split",
        },
    )?;
    Ok(d.into())
}

pub(crate) fn selection_to_py(py: Python<'_>, selection: &SelectionInfo) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("active_cell", selection.active_cell.as_deref())?;
    d.set_item("sqref", selection.sqref.as_deref())?;
    d.set_item("pane", selection.pane.as_deref())?;
    d.set_item("active_cell_id", selection.active_cell_id)?;
    Ok(d.into())
}

// ---------- Freeze panes (top-level method) ----------

pub(crate) fn read_freeze_panes_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    serialize_freeze_panes(py, book.ensure_sheet(sheet)?.freeze_panes.clone())
}

pub(crate) fn read_freeze_panes_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    serialize_freeze_panes(py, book.ensure_sheet(sheet)?.freeze_panes.clone())
}

fn serialize_freeze_panes(py: Python<'_>, info: Option<FreezePane>) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    let Some(info) = info else {
        return Ok(d.into());
    };
    d.set_item(
        "mode",
        match info.mode {
            PaneMode::Freeze => "freeze",
            PaneMode::Split => "split",
        },
    )?;
    if let Some(top_left_cell) = info.top_left_cell {
        d.set_item("top_left_cell", top_left_cell)?;
    }
    if let Some(x_split) = info.x_split {
        d.set_item("x_split", x_split)?;
    }
    if let Some(y_split) = info.y_split {
        d.set_item("y_split", y_split)?;
    }
    if let Some(active_pane) = info.active_pane {
        d.set_item("active_pane", active_pane)?;
    }
    Ok(d.into())
}
