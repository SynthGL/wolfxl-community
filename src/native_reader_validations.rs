//! Data validation reader logic for native XLSX/XLSB books.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use wolfxl_reader::DataValidation;

use crate::native_reader_backend::{NativeXlsbBook, NativeXlsxBook};

type PyObject = Py<PyAny>;

pub(crate) fn read_data_validations_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let validations = book.ensure_sheet(sheet)?.data_validations.clone();
    serialize(py, &validations)
}

pub(crate) fn read_data_validations_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let validations = book.ensure_sheet(sheet)?.data_validations.clone();
    serialize(py, &validations)
}

fn serialize(py: Python<'_>, validations: &[DataValidation]) -> PyResult<PyObject> {
    let result = PyList::empty(py);
    for validation in validations {
        let d = PyDict::new(py);
        d.set_item("range", &validation.range)?;
        d.set_item("validation_type", &validation.validation_type)?;
        if let Some(operator) = &validation.operator {
            d.set_item("operator", operator)?;
        }
        if let Some(formula1) = &validation.formula1 {
            d.set_item("formula1", formula1)?;
        }
        if let Some(formula2) = &validation.formula2 {
            d.set_item("formula2", formula2)?;
        }
        d.set_item("allow_blank", validation.allow_blank)?;
        d.set_item("show_input_message", validation.show_input_message)?;
        d.set_item("show_error_message", validation.show_error_message)?;
        if let Some(error_title) = &validation.error_title {
            d.set_item("error_title", error_title)?;
        }
        if let Some(error) = &validation.error {
            d.set_item("error", error)?;
        }
        if let Some(prompt_title) = &validation.prompt_title {
            d.set_item("prompt_title", prompt_title)?;
        }
        if let Some(prompt) = &validation.prompt {
            d.set_item("prompt", prompt)?;
        }
        result.append(d)?;
    }
    Ok(result.into())
}
