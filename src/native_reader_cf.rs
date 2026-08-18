//! Conditional-format reader logic for native XLSX/XLSB books.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use wolfxl_reader::ConditionalFormatRule;

use crate::native_reader_backend::{NativeXlsbBook, NativeXlsxBook};

type PyObject = Py<PyAny>;

pub(crate) fn read_conditional_formats_xlsx(
    book: &mut NativeXlsxBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let rules = book.ensure_sheet(sheet)?.conditional_formats.clone();
    serialize(py, &rules)
}

pub(crate) fn read_conditional_formats_xlsb(
    book: &mut NativeXlsbBook,
    py: Python<'_>,
    sheet: &str,
) -> PyResult<PyObject> {
    let rules = book.ensure_sheet(sheet)?.conditional_formats.clone();
    serialize(py, &rules)
}

fn serialize(py: Python<'_>, rules: &[ConditionalFormatRule]) -> PyResult<PyObject> {
    let result = PyList::empty(py);
    for rule in rules {
        let d = PyDict::new(py);
        d.set_item("range", &rule.range)?;
        d.set_item("rule_type", &rule.rule_type)?;
        if let Some(operator) = &rule.operator {
            d.set_item("operator", operator)?;
        }
        if let Some(formula) = &rule.formula {
            d.set_item("formula", formula)?;
        }
        if let Some(dxf_id) = rule.dxf_id {
            d.set_item("dxf_id", dxf_id)?;
        }
        if let Some(priority) = rule.priority {
            d.set_item("priority", priority)?;
        }
        if let Some(stop_if_true) = rule.stop_if_true {
            d.set_item("stop_if_true", stop_if_true)?;
        }
        if let Some(cs) = &rule.color_scale {
            let cs_dict = PyDict::new(py);
            let cfvo_list = PyList::empty(py);
            for cfvo in &cs.cfvo {
                let entry = PyDict::new(py);
                entry.set_item("type", &cfvo.cfvo_type)?;
                if let Some(val) = &cfvo.val {
                    entry.set_item("val", val)?;
                }
                cfvo_list.append(entry)?;
            }
            cs_dict.set_item("cfvo", cfvo_list)?;
            let colors_list = PyList::empty(py);
            for color in &cs.colors {
                colors_list.append(color)?;
            }
            cs_dict.set_item("colors", colors_list)?;
            d.set_item("color_scale", cs_dict)?;
        }
        result.append(d)?;
    }
    Ok(result.into())
}
