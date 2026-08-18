//! Comments and threaded-comments reader logic for native XLSX/XLSB books.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use wolfxl_reader::{Comment, ParsedThreadedComment};

use crate::native_reader_backend::{NativeXlsbBook, NativeXlsxBook};

type PyObject = Py<PyAny>;

pub(crate) fn read_comments_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let comments = book.ensure_sheet(sheet)?.comments.clone();
    serialize_comments(py, &comments)
}

pub(crate) fn read_comments_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let comments = book.ensure_sheet(sheet)?.comments.clone();
    serialize_comments(py, &comments)
}

fn serialize_comments(py: Python<'_>, comments: &[Comment]) -> PyResult<PyObject> {
    let result = PyList::empty(py);
    for comment in comments {
        let d = PyDict::new(py);
        d.set_item("cell", &comment.cell)?;
        d.set_item("text", &comment.text)?;
        d.set_item("author", &comment.author)?;
        d.set_item("threaded", comment.threaded)?;
        result.append(d)?;
    }
    Ok(result.into())
}

/// Threaded comments parsed from `xl/threadedComments/threadedCommentsN.xml`.
/// The Python layer reassembles into a tree by GUID.
pub(crate) fn read_threaded_comments_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let entries = book.ensure_sheet(sheet)?.threaded_comments.clone();
    serialize_threaded(py, &entries)
}

fn serialize_threaded(py: Python<'_>, entries: &[ParsedThreadedComment]) -> PyResult<PyObject> {
    let result = PyList::empty(py);
    for entry in entries {
        let d = PyDict::new(py);
        d.set_item("id", &entry.id)?;
        d.set_item("cell", &entry.cell)?;
        d.set_item("person_id", &entry.person_id)?;
        match &entry.created {
            Some(value) => d.set_item("created", value)?,
            None => d.set_item("created", py.None())?,
        }
        d.set_item("text", &entry.text)?;
        match &entry.parent_id {
            Some(value) => d.set_item("parent_id", value)?,
            None => d.set_item("parent_id", py.None())?,
        }
        d.set_item("done", entry.done)?;
        result.append(d)?;
    }
    Ok(result.into())
}

/// Workbook-scoped person list parsed from `xl/persons/personList.xml`.
pub(crate) fn read_persons_xlsx(book: &NativeXlsxBook, py: Python<'_>) -> PyResult<PyObject> {
    let result = PyList::empty(py);
    for person in book.book.persons() {
        let d = PyDict::new(py);
        d.set_item("id", &person.id)?;
        d.set_item("display_name", &person.display_name)?;
        match &person.user_id {
            Some(value) => d.set_item("user_id", value)?,
            None => d.set_item("user_id", py.None())?,
        }
        match &person.provider_id {
            Some(value) => d.set_item("provider_id", value)?,
            None => d.set_item("provider_id", py.None())?,
        }
        result.append(d)?;
    }
    Ok(result.into())
}
