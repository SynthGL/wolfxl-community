//! Hyperlinks reader logic for native XLSX/XLSB books.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use wolfxl_reader::Hyperlink;

use crate::native_reader_backend::{NativeXlsbBook, NativeXlsxBook};

type PyObject = Py<PyAny>;

pub(crate) fn read_hyperlinks_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let links = book.ensure_sheet(sheet)?.hyperlinks.clone();
    serialize(py, &links)
}

pub(crate) fn read_hyperlinks_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let links = book.ensure_sheet(sheet)?.hyperlinks.clone();
    serialize(py, &links)
}

fn serialize(py: Python<'_>, links: &[Hyperlink]) -> PyResult<PyObject> {
    let result = PyList::empty(py);
    for link in links {
        let d = PyDict::new(py);
        d.set_item("cell", &link.cell)?;
        d.set_item("target", &link.target)?;
        match &link.location {
            Some(location) => d.set_item("location", location)?,
            None => d.set_item("location", py.None())?,
        }
        d.set_item("display", &link.display)?;
        match &link.tooltip {
            Some(tooltip) => d.set_item("tooltip", tooltip)?,
            None => d.set_item("tooltip", py.None())?,
        }
        d.set_item("internal", link.internal)?;
        result.append(d)?;
    }
    Ok(result.into())
}
