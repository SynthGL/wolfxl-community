//! RFC-055 Phase 2.5n — sheet-setup queue parser + drain helpers.
//!
//! Consumes the §10 dict shape produced by
//! `Worksheet.to_rust_setup_dict()` on the Python side and turns it
//! into a [`SheetSetupBlocks`] of typed Rust specs ready to feed the
//! emitters in `wolfxl_writer::parse::sheet_setup`. The patcher's
//! Phase 2.5n then turns those specs into bytes and emits one
//! [`wolfxl_merger::SheetBlock`] per non-empty block for splice via
//! `merge_blocks`.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use wolfxl_writer::parse::sheet_setup::{
    HeaderFooterItemSpec, HeaderFooterSpec, PageMarginsSpec, PageSetupSpec, PaneSpec,
    PrintOptionsSpec, PrintTitlesSpec, SelectionSpec, SheetProtectionSpec, SheetSetupBlocks,
    SheetViewSpec,
};

// ---------------------------------------------------------------------------
// QueuedSheetSetup — the patcher's per-sheet queue entry.
// ---------------------------------------------------------------------------

/// One queued sheet-setup mutation, keyed in
/// [`crate::XlsxPatcher::queued_sheet_setup`] by sheet title. Stores
/// the §10 dict verbatim so the drain phase can re-parse it without
/// holding the GIL while running the splice.
#[derive(Debug, Clone)]
pub struct QueuedSheetSetup {
    /// Already-parsed typed specs. Drain phase consumes these directly.
    pub specs: SheetSetupBlocks,
}

// ---------------------------------------------------------------------------
// Parser — Python dict → SheetSetupBlocks
// ---------------------------------------------------------------------------

/// Parse a Python dict matching RFC-055 §10 into a typed
/// [`SheetSetupBlocks`].
///
/// `None` / missing keys are tolerated — the corresponding slot stays
/// `None` in the returned struct. Type errors raise `ValueError` on the
/// Python side.
pub fn parse_sheet_setup_payload(payload: &Bound<'_, PyDict>) -> PyResult<SheetSetupBlocks> {
    let page_setup = match payload.get_item("page_setup")? {
        Some(v) if !v.is_none() => Some(parse_page_setup(v.cast::<PyDict>().map_err(|_| {
            PyValueError::new_err("queue_sheet_setup_update: 'page_setup' must be a dict or None")
        })?)?),
        _ => None,
    };
    let page_margins = match payload.get_item("page_margins")? {
        Some(v) if !v.is_none() => Some(parse_page_margins(v.cast::<PyDict>().map_err(|_| {
            PyValueError::new_err("queue_sheet_setup_update: 'page_margins' must be a dict or None")
        })?)?),
        _ => None,
    };
    let print_options = match payload.get_item("print_options")? {
        Some(v) if !v.is_none() => {
            Some(parse_print_options(v.cast::<PyDict>().map_err(|_| {
                PyValueError::new_err(
                    "queue_sheet_setup_update: 'print_options' must be a dict or None",
                )
            })?)?)
        }
        _ => None,
    };
    let header_footer = match payload.get_item("header_footer")? {
        Some(v) if !v.is_none() => {
            Some(parse_header_footer(v.cast::<PyDict>().map_err(|_| {
                PyValueError::new_err(
                    "queue_sheet_setup_update: 'header_footer' must be a dict or None",
                )
            })?)?)
        }
        _ => None,
    };
    let sheet_view = match payload.get_item("sheet_view")? {
        Some(v) if !v.is_none() => Some(parse_sheet_view(v.cast::<PyDict>().map_err(|_| {
            PyValueError::new_err("queue_sheet_setup_update: 'sheet_view' must be a dict or None")
        })?)?),
        _ => None,
    };
    let sheet_protection = match payload.get_item("sheet_protection")? {
        Some(v) if !v.is_none() => Some(parse_sheet_protection(v.cast::<PyDict>().map_err(
            |_| {
                PyValueError::new_err(
                    "queue_sheet_setup_update: 'sheet_protection' must be a dict or None",
                )
            },
        )?)?),
        _ => None,
    };
    let print_titles = match payload.get_item("print_titles")? {
        Some(v) if !v.is_none() => Some(parse_print_titles(v.cast::<PyDict>().map_err(|_| {
            PyValueError::new_err("queue_sheet_setup_update: 'print_titles' must be a dict or None")
        })?)?),
        _ => None,
    };
    Ok(SheetSetupBlocks {
        sheet_view,
        sheet_protection,
        print_options,
        page_margins,
        page_setup,
        header_footer,
        print_titles,
    })
}

fn extract_str(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract::<String>()?)),
        _ => Ok(None),
    }
}

fn extract_bool(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<bool>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract::<bool>()?)),
        _ => Ok(None),
    }
}

fn extract_u32(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<u32>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.extract::<u32>()?)),
        _ => Ok(None),
    }
}

fn extract_f64(d: &Bound<'_, PyDict>, key: &str, default: f64) -> PyResult<f64> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => Ok(v.extract::<f64>()?),
        _ => Ok(default),
    }
}

fn extract_bool_default(d: &Bound<'_, PyDict>, key: &str, default: bool) -> PyResult<bool> {
    Ok(extract_bool(d, key)?.unwrap_or(default))
}

fn parse_page_setup(d: &Bound<'_, PyDict>) -> PyResult<PageSetupSpec> {
    Ok(PageSetupSpec {
        orientation: extract_str(d, "orientation")?,
        paper_size: extract_u32(d, "paper_size")?,
        fit_to_width: extract_u32(d, "fit_to_width")?,
        fit_to_height: extract_u32(d, "fit_to_height")?,
        scale: extract_u32(d, "scale")?,
        first_page_number: extract_u32(d, "first_page_number")?,
        horizontal_dpi: extract_u32(d, "horizontal_dpi")?,
        vertical_dpi: extract_u32(d, "vertical_dpi")?,
        cell_comments: extract_str(d, "cell_comments")?,
        errors: extract_str(d, "errors")?,
        use_first_page_number: extract_bool(d, "use_first_page_number")?,
        paper_height: extract_str(d, "paper_height")?,
        paper_width: extract_str(d, "paper_width")?,
        page_order: extract_str(d, "page_order")?,
        use_printer_defaults: extract_bool(d, "use_printer_defaults")?,
        black_and_white: extract_bool(d, "black_and_white")?,
        draft: extract_bool(d, "draft")?,
        copies: extract_u32(d, "copies")?,
    })
}

fn parse_print_options(d: &Bound<'_, PyDict>) -> PyResult<PrintOptionsSpec> {
    Ok(PrintOptionsSpec {
        horizontal_centered: extract_bool(d, "horizontal_centered")?,
        vertical_centered: extract_bool(d, "vertical_centered")?,
        headings: extract_bool(d, "headings")?,
        grid_lines: extract_bool(d, "grid_lines")?,
        grid_lines_set: extract_bool(d, "grid_lines_set")?,
    })
}

fn parse_page_margins(d: &Bound<'_, PyDict>) -> PyResult<PageMarginsSpec> {
    Ok(PageMarginsSpec {
        left: extract_f64(d, "left", 0.7)?,
        right: extract_f64(d, "right", 0.7)?,
        top: extract_f64(d, "top", 0.75)?,
        bottom: extract_f64(d, "bottom", 0.75)?,
        header: extract_f64(d, "header", 0.3)?,
        footer: extract_f64(d, "footer", 0.3)?,
    })
}

fn parse_header_footer_item(
    d: Option<&Bound<'_, PyDict>>,
) -> PyResult<Option<HeaderFooterItemSpec>> {
    match d {
        None => Ok(None),
        Some(d) => Ok(Some(HeaderFooterItemSpec {
            left: extract_str(d, "left")?,
            center: extract_str(d, "center")?,
            right: extract_str(d, "right")?,
        })),
    }
}

fn extract_dict<'py>(d: &Bound<'py, PyDict>, key: &str) -> PyResult<Option<Bound<'py, PyDict>>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => Ok(Some(v.cast_into::<PyDict>().map_err(|_| {
            PyValueError::new_err(format!(
                "queue_sheet_setup_update: {key:?} must be a dict or None"
            ))
        })?)),
        _ => Ok(None),
    }
}

fn parse_header_footer(d: &Bound<'_, PyDict>) -> PyResult<HeaderFooterSpec> {
    let odd_header = extract_dict(d, "odd_header")?;
    let odd_footer = extract_dict(d, "odd_footer")?;
    let even_header = extract_dict(d, "even_header")?;
    let even_footer = extract_dict(d, "even_footer")?;
    let first_header = extract_dict(d, "first_header")?;
    let first_footer = extract_dict(d, "first_footer")?;
    Ok(HeaderFooterSpec {
        odd_header: parse_header_footer_item(odd_header.as_ref())?,
        odd_footer: parse_header_footer_item(odd_footer.as_ref())?,
        even_header: parse_header_footer_item(even_header.as_ref())?,
        even_footer: parse_header_footer_item(even_footer.as_ref())?,
        first_header: parse_header_footer_item(first_header.as_ref())?,
        first_footer: parse_header_footer_item(first_footer.as_ref())?,
        different_odd_even: extract_bool_default(d, "different_odd_even", false)?,
        different_first: extract_bool_default(d, "different_first", false)?,
        scale_with_doc: extract_bool_default(d, "scale_with_doc", true)?,
        align_with_margins: extract_bool_default(d, "align_with_margins", true)?,
    })
}

fn parse_pane(d: &Bound<'_, PyDict>) -> PyResult<PaneSpec> {
    Ok(PaneSpec {
        x_split: extract_f64(d, "x_split", 0.0)?,
        y_split: extract_f64(d, "y_split", 0.0)?,
        top_left_cell: extract_str(d, "top_left_cell")?.unwrap_or_else(|| "A1".into()),
        active_pane: extract_str(d, "active_pane")?.unwrap_or_else(|| "topLeft".into()),
        state: extract_str(d, "state")?.unwrap_or_else(|| "frozen".into()),
    })
}

fn parse_selection(d: &Bound<'_, PyDict>) -> PyResult<SelectionSpec> {
    Ok(SelectionSpec {
        active_cell: extract_str(d, "active_cell")?,
        sqref: extract_str(d, "sqref")?,
        pane: extract_str(d, "pane")?,
    })
}

fn parse_sheet_view(d: &Bound<'_, PyDict>) -> PyResult<SheetViewSpec> {
    let pane = match extract_dict(d, "pane")? {
        Some(p) => Some(parse_pane(&p)?),
        None => None,
    };
    let selection: Vec<SelectionSpec> = match d.get_item("selection")? {
        Some(v) if !v.is_none() => {
            let list = v.cast::<PyList>().map_err(|_| {
                PyValueError::new_err(
                    "queue_sheet_setup_update: 'selection' must be a list or None",
                )
            })?;
            let mut out = Vec::with_capacity(list.len());
            for item in list.iter() {
                let sd = item.cast::<PyDict>().map_err(|_| {
                    PyValueError::new_err(
                        "queue_sheet_setup_update: 'selection' items must be dicts",
                    )
                })?;
                out.push(parse_selection(sd)?);
            }
            out
        }
        _ => Vec::new(),
    };
    Ok(SheetViewSpec {
        workbook_view_id: extract_u32(d, "workbook_view_id")?.unwrap_or(0),
        zoom_scale: extract_u32(d, "zoom_scale")?.unwrap_or(100),
        zoom_scale_normal: extract_u32(d, "zoom_scale_normal")?.unwrap_or(100),
        view: extract_str(d, "view")?,
        show_grid_lines: extract_bool(d, "show_grid_lines")?,
        show_row_col_headers: extract_bool(d, "show_row_col_headers")?,
        show_outline_symbols: extract_bool(d, "show_outline_symbols")?,
        show_zeros: extract_bool(d, "show_zeros")?,
        right_to_left: extract_bool(d, "right_to_left")?,
        tab_selected: extract_bool(d, "tab_selected")?,
        top_left_cell: extract_str(d, "top_left_cell")?,
        pane,
        selection,
    })
}

fn parse_sheet_protection(d: &Bound<'_, PyDict>) -> PyResult<SheetProtectionSpec> {
    Ok(SheetProtectionSpec {
        sheet: extract_bool_default(d, "sheet", false)?,
        objects: extract_bool_default(d, "objects", false)?,
        scenarios: extract_bool_default(d, "scenarios", false)?,
        format_cells: extract_bool_default(d, "format_cells", true)?,
        format_columns: extract_bool_default(d, "format_columns", true)?,
        format_rows: extract_bool_default(d, "format_rows", true)?,
        insert_columns: extract_bool_default(d, "insert_columns", true)?,
        insert_rows: extract_bool_default(d, "insert_rows", true)?,
        insert_hyperlinks: extract_bool_default(d, "insert_hyperlinks", true)?,
        delete_columns: extract_bool_default(d, "delete_columns", true)?,
        delete_rows: extract_bool_default(d, "delete_rows", true)?,
        select_locked_cells: extract_bool_default(d, "select_locked_cells", false)?,
        sort: extract_bool_default(d, "sort", true)?,
        auto_filter: extract_bool_default(d, "auto_filter", true)?,
        pivot_tables: extract_bool_default(d, "pivot_tables", true)?,
        select_unlocked_cells: extract_bool_default(d, "select_unlocked_cells", false)?,
        password_hash: extract_str(d, "password_hash")?,
        algorithm_name: extract_str(d, "algorithm_name")?,
        hash_value: extract_str(d, "hash_value")?,
        salt_value: extract_str(d, "salt_value")?,
        spin_count: extract_u32(d, "spin_count")?,
    })
}

fn parse_print_titles(d: &Bound<'_, PyDict>) -> PyResult<PrintTitlesSpec> {
    Ok(PrintTitlesSpec {
        rows: extract_str(d, "rows")?,
        cols: extract_str(d, "cols")?,
    })
}
