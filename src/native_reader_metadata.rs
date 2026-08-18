//! Workbook metadata: doc properties, custom doc properties, workbook
//! security, workbook properties, calc properties, and book views.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use wolfxl_reader::{
    BookViewInfo, CalcPropertiesInfo, CustomPropertyInfo, WorkbookPropertiesInfo, WorkbookSecurity,
};

use crate::native_reader_backend::NativeXlsxBook;

type PyObject = Py<PyAny>;

pub(crate) fn read_doc_properties(book: &NativeXlsxBook, py: Python<'_>) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    for (key, value) in book.book.doc_properties() {
        d.set_item(key, value)?;
    }
    Ok(d.into())
}

pub(crate) fn read_custom_doc_properties(
    book: &NativeXlsxBook,
    py: Python<'_>,
) -> PyResult<PyObject> {
    let result = PyList::empty(py);
    for property in book.book.custom_doc_properties() {
        result.append(custom_property_to_py(py, property)?)?;
    }
    Ok(result.into())
}

pub(crate) fn read_workbook_security(book: &NativeXlsxBook, py: Python<'_>) -> PyResult<PyObject> {
    workbook_security_to_py(py, book.book.workbook_security())
}

pub(crate) fn read_workbook_properties(
    book: &NativeXlsxBook,
    py: Python<'_>,
) -> PyResult<PyObject> {
    match book.book.workbook_properties() {
        Some(properties) => workbook_properties_to_py(py, properties),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_calc_properties(book: &NativeXlsxBook, py: Python<'_>) -> PyResult<PyObject> {
    match book.book.calc_properties() {
        Some(properties) => calc_properties_to_py(py, properties),
        None => Ok(py.None()),
    }
}

pub(crate) fn read_workbook_views(book: &NativeXlsxBook, py: Python<'_>) -> PyResult<PyObject> {
    let result = PyList::empty(py);
    for view in book.book.workbook_views() {
        result.append(book_view_to_py(py, view)?)?;
    }
    Ok(result.into())
}

pub(crate) fn workbook_security_to_py(
    py: Python<'_>,
    security: &WorkbookSecurity,
) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    match &security.workbook_protection {
        Some(protection) => {
            let p = PyDict::new(py);
            p.set_item("lock_structure", protection.lock_structure)?;
            p.set_item("lock_windows", protection.lock_windows)?;
            p.set_item("lock_revision", protection.lock_revision)?;
            p.set_item("workbook_password", protection.workbook_password.as_deref())?;
            p.set_item(
                "workbook_password_character_set",
                protection.workbook_password_character_set.as_deref(),
            )?;
            p.set_item(
                "workbook_algorithm_name",
                protection.workbook_algorithm_name.as_deref(),
            )?;
            p.set_item(
                "workbook_hash_value",
                protection.workbook_hash_value.as_deref(),
            )?;
            p.set_item(
                "workbook_salt_value",
                protection.workbook_salt_value.as_deref(),
            )?;
            p.set_item("workbook_spin_count", protection.workbook_spin_count)?;
            p.set_item(
                "revisions_password",
                protection.revisions_password.as_deref(),
            )?;
            p.set_item(
                "revisions_password_character_set",
                protection.revisions_password_character_set.as_deref(),
            )?;
            p.set_item(
                "revisions_algorithm_name",
                protection.revisions_algorithm_name.as_deref(),
            )?;
            p.set_item(
                "revisions_hash_value",
                protection.revisions_hash_value.as_deref(),
            )?;
            p.set_item(
                "revisions_salt_value",
                protection.revisions_salt_value.as_deref(),
            )?;
            p.set_item("revisions_spin_count", protection.revisions_spin_count)?;
            d.set_item("workbook_protection", p)?;
        }
        None => d.set_item("workbook_protection", py.None())?,
    }
    match &security.file_sharing {
        Some(file_sharing) => {
            let f = PyDict::new(py);
            f.set_item("read_only_recommended", file_sharing.read_only_recommended)?;
            f.set_item("user_name", file_sharing.user_name.as_deref())?;
            f.set_item(
                "reservation_password",
                file_sharing.reservation_password.as_deref(),
            )?;
            f.set_item("algorithm_name", file_sharing.algorithm_name.as_deref())?;
            f.set_item("hash_value", file_sharing.hash_value.as_deref())?;
            f.set_item("salt_value", file_sharing.salt_value.as_deref())?;
            f.set_item("spin_count", file_sharing.spin_count)?;
            d.set_item("file_sharing", f)?;
        }
        None => d.set_item("file_sharing", py.None())?,
    }
    Ok(d.into())
}

pub(crate) fn workbook_properties_to_py(
    py: Python<'_>,
    properties: &WorkbookPropertiesInfo,
) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("date1904", properties.date1904)?;
    d.set_item("date_compatibility", properties.date_compatibility)?;
    d.set_item("show_objects", properties.show_objects.as_deref())?;
    d.set_item(
        "show_border_unselected_tables",
        properties.show_border_unselected_tables,
    )?;
    d.set_item("filter_privacy", properties.filter_privacy)?;
    d.set_item("prompted_solutions", properties.prompted_solutions)?;
    d.set_item("show_ink_annotation", properties.show_ink_annotation)?;
    d.set_item("backup_file", properties.backup_file)?;
    d.set_item(
        "save_external_link_values",
        properties.save_external_link_values,
    )?;
    d.set_item("update_links", properties.update_links.as_deref())?;
    d.set_item("code_name", properties.code_name.as_deref())?;
    d.set_item("hide_pivot_field_list", properties.hide_pivot_field_list)?;
    d.set_item(
        "show_pivot_chart_filter",
        properties.show_pivot_chart_filter,
    )?;
    d.set_item("allow_refresh_query", properties.allow_refresh_query)?;
    d.set_item("publish_items", properties.publish_items)?;
    d.set_item("check_compatibility", properties.check_compatibility)?;
    d.set_item("auto_compress_pictures", properties.auto_compress_pictures)?;
    d.set_item(
        "refresh_all_connections",
        properties.refresh_all_connections,
    )?;
    d.set_item("default_theme_version", properties.default_theme_version)?;
    Ok(d.into())
}

pub(crate) fn calc_properties_to_py(
    py: Python<'_>,
    properties: &CalcPropertiesInfo,
) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("calc_id", properties.calc_id)?;
    d.set_item("calc_mode", properties.calc_mode.as_deref())?;
    d.set_item("full_calc_on_load", properties.full_calc_on_load)?;
    d.set_item("ref_mode", properties.ref_mode.as_deref())?;
    d.set_item("iterate", properties.iterate)?;
    d.set_item("iterate_count", properties.iterate_count)?;
    d.set_item("iterate_delta", properties.iterate_delta)?;
    d.set_item("full_precision", properties.full_precision)?;
    d.set_item("calc_completed", properties.calc_completed)?;
    d.set_item("calc_on_save", properties.calc_on_save)?;
    d.set_item("concurrent_calc", properties.concurrent_calc)?;
    d.set_item(
        "concurrent_manual_count",
        properties.concurrent_manual_count,
    )?;
    d.set_item("force_full_calc", properties.force_full_calc)?;
    Ok(d.into())
}

pub(crate) fn book_view_to_py(py: Python<'_>, view: &BookViewInfo) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("visibility", &view.visibility)?;
    d.set_item("minimized", view.minimized)?;
    d.set_item("show_horizontal_scroll", view.show_horizontal_scroll)?;
    d.set_item("show_vertical_scroll", view.show_vertical_scroll)?;
    d.set_item("show_sheet_tabs", view.show_sheet_tabs)?;
    d.set_item("x_window", view.x_window)?;
    d.set_item("y_window", view.y_window)?;
    d.set_item("window_width", view.window_width)?;
    d.set_item("window_height", view.window_height)?;
    d.set_item("tab_ratio", view.tab_ratio)?;
    d.set_item("first_sheet", view.first_sheet)?;
    d.set_item("active_tab", view.active_tab)?;
    d.set_item("auto_filter_date_grouping", view.auto_filter_date_grouping)?;
    Ok(d.into())
}

pub(crate) fn custom_property_to_py(
    py: Python<'_>,
    property: &CustomPropertyInfo,
) -> PyResult<PyObject> {
    let d = PyDict::new(py);
    d.set_item("name", &property.name)?;
    d.set_item("kind", &property.kind)?;
    d.set_item("value", &property.value)?;
    Ok(d.into())
}
