//! Page setup: margins, setup, print options, header/footer, breaks,
//! sheet protection. Sheet view, format, properties, and freeze panes live in
//! `native_reader_sheet_view`.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use wolfxl_reader::{
    BreakInfo, HeaderFooterInfo, HeaderFooterItemInfo, PageBreakListInfo, PageMarginsInfo,
    PageSetupInfo, PrintOptionsInfo, SheetProtection,
};

use crate::native_reader_backend::{NativeXlsbBook, NativeXlsxBook};

type PyObject = Py<PyAny>;

// ---------- Sheet protection ----------

pub(crate) fn read_sheet_protection_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let protection = book.ensure_sheet(sheet)?.sheet_protection.clone();
    match protection {
        Some(protection) => sheet_protection_to_py(py, &protection),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_sheet_protection_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let protection = book.ensure_sheet(sheet)?.sheet_protection.clone();
    match protection {
        Some(protection) => sheet_protection_to_py(py, &protection),
        None => Ok(py.None()),
    }
}

pub(crate) fn sheet_protection_to_py(
    py: Python<'_>,
    protection: &SheetProtection,
) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("sheet", protection.sheet)?;
    d.set_item("objects", protection.objects)?;
    d.set_item("scenarios", protection.scenarios)?;
    d.set_item("format_cells", protection.format_cells)?;
    d.set_item("format_columns", protection.format_columns)?;
    d.set_item("format_rows", protection.format_rows)?;
    d.set_item("insert_columns", protection.insert_columns)?;
    d.set_item("insert_rows", protection.insert_rows)?;
    d.set_item("insert_hyperlinks", protection.insert_hyperlinks)?;
    d.set_item("delete_columns", protection.delete_columns)?;
    d.set_item("delete_rows", protection.delete_rows)?;
    d.set_item("select_locked_cells", protection.select_locked_cells)?;
    d.set_item("sort", protection.sort)?;
    d.set_item("auto_filter", protection.auto_filter)?;
    d.set_item("pivot_tables", protection.pivot_tables)?;
    d.set_item("select_unlocked_cells", protection.select_unlocked_cells)?;
    if let Some(password_hash) = &protection.password_hash {
        d.set_item("password_hash", password_hash)?;
    }
    Ok(d.into())
}

// ---------- Page margins / setup / print options / header / footer / breaks ----------

pub(crate) fn read_page_margins_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match book.ensure_sheet(sheet)?.page_margins {
        Some(margins) => page_margins_to_py(py, &margins),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_page_margins_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match book.ensure_sheet(sheet)?.page_margins {
        Some(margins) => page_margins_to_py(py, &margins),
        None => Ok(py.None()),
    }
}

pub(crate) fn page_margins_to_py(py: Python<'_>, margins: &PageMarginsInfo) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("left", margins.left)?;
    d.set_item("right", margins.right)?;
    d.set_item("top", margins.top)?;
    d.set_item("bottom", margins.bottom)?;
    d.set_item("header", margins.header)?;
    d.set_item("footer", margins.footer)?;
    Ok(d.into())
}

pub(crate) fn read_page_setup_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.page_setup {
        Some(setup) => page_setup_to_py(py, setup),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_page_setup_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.page_setup {
        Some(setup) => page_setup_to_py(py, setup),
        None => Ok(py.None()),
    }
}

pub(crate) fn page_setup_to_py(py: Python<'_>, setup: &PageSetupInfo) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("orientation", setup.orientation.as_deref())?;
    d.set_item("paper_size", setup.paper_size)?;
    d.set_item("fit_to_width", setup.fit_to_width)?;
    d.set_item("fit_to_height", setup.fit_to_height)?;
    d.set_item("scale", setup.scale)?;
    d.set_item("first_page_number", setup.first_page_number)?;
    d.set_item("horizontal_dpi", setup.horizontal_dpi)?;
    d.set_item("vertical_dpi", setup.vertical_dpi)?;
    d.set_item("cell_comments", setup.cell_comments.as_deref())?;
    d.set_item("errors", setup.errors.as_deref())?;
    d.set_item("use_first_page_number", setup.use_first_page_number)?;
    d.set_item("paper_height", setup.paper_height.as_deref())?;
    d.set_item("paper_width", setup.paper_width.as_deref())?;
    d.set_item("page_order", setup.page_order.as_deref())?;
    d.set_item("use_printer_defaults", setup.use_printer_defaults)?;
    d.set_item("black_and_white", setup.black_and_white)?;
    d.set_item("draft", setup.draft)?;
    d.set_item("copies", setup.copies)?;
    Ok(d.into())
}

pub(crate) fn read_print_options_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.print_options {
        Some(options) => print_options_to_py(py, options),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_print_options_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.print_options {
        Some(options) => print_options_to_py(py, options),
        None => Ok(py.None()),
    }
}

pub(crate) fn print_options_to_py(
    py: Python<'_>,
    options: &PrintOptionsInfo,
) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("horizontal_centered", options.horizontal_centered)?;
    d.set_item("vertical_centered", options.vertical_centered)?;
    d.set_item("headings", options.headings)?;
    d.set_item("grid_lines", options.grid_lines)?;
    d.set_item("grid_lines_set", options.grid_lines_set)?;
    Ok(d.into())
}

pub(crate) fn read_header_footer_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.header_footer {
        Some(header_footer) => header_footer_to_py(py, header_footer),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_header_footer_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.header_footer {
        Some(header_footer) => header_footer_to_py(py, header_footer),
        None => Ok(py.None()),
    }
}

pub(crate) fn header_footer_to_py(
    py: Python<'_>,
    header_footer: &HeaderFooterInfo,
) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item(
        "odd_header",
        header_footer_item_to_py(py, &header_footer.odd_header)?,
    )?;
    d.set_item(
        "odd_footer",
        header_footer_item_to_py(py, &header_footer.odd_footer)?,
    )?;
    d.set_item(
        "even_header",
        header_footer_item_to_py(py, &header_footer.even_header)?,
    )?;
    d.set_item(
        "even_footer",
        header_footer_item_to_py(py, &header_footer.even_footer)?,
    )?;
    d.set_item(
        "first_header",
        header_footer_item_to_py(py, &header_footer.first_header)?,
    )?;
    d.set_item(
        "first_footer",
        header_footer_item_to_py(py, &header_footer.first_footer)?,
    )?;
    d.set_item("different_odd_even", header_footer.different_odd_even)?;
    d.set_item("different_first", header_footer.different_first)?;
    d.set_item("scale_with_doc", header_footer.scale_with_doc)?;
    d.set_item("align_with_margins", header_footer.align_with_margins)?;
    Ok(d.into())
}

pub(crate) fn header_footer_item_to_py(
    py: Python<'_>,
    item: &HeaderFooterItemInfo,
) -> PyResult<PyObject> {
    if item.left.is_none() && item.center.is_none() && item.right.is_none() {
        return Ok(py.None());
    }
    let d = PyDict::new(py);
    d.set_item("left", item.left.as_deref())?;
    d.set_item("center", item.center.as_deref())?;
    d.set_item("right", item.right.as_deref())?;
    Ok(d.into())
}

pub(crate) fn read_row_breaks_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.row_breaks {
        Some(breaks) => page_breaks_to_py(py, breaks),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_row_breaks_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.row_breaks {
        Some(breaks) => page_breaks_to_py(py, breaks),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_column_breaks_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.column_breaks {
        Some(breaks) => page_breaks_to_py(py, breaks),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_column_breaks_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    match &book.ensure_sheet(sheet)?.column_breaks {
        Some(breaks) => page_breaks_to_py(py, breaks),
        None => Ok(py.None()),
    }
}

pub(crate) fn page_breaks_to_py(py: Python<'_>, breaks: &PageBreakListInfo) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("count", breaks.count)?;
    d.set_item("manual_break_count", breaks.manual_break_count)?;
    let items = PyList::empty(py);
    for item in &breaks.breaks {
        items.append(break_to_py(py, item)?)?;
    }
    d.set_item("breaks", items)?;
    Ok(d.into())
}

pub(crate) fn break_to_py(py: Python<'_>, item: &BreakInfo) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("id", item.id)?;
    d.set_item("min", item.min)?;
    d.set_item("max", item.max)?;
    d.set_item("man", item.man)?;
    d.set_item("pt", item.pt)?;
    Ok(d.into())
}
