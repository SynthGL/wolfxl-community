//! Rich-text run payload parsing for the native writer backend.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PySequence};
use wolfxl_writer::rich_text::{InlineFontProps, RichTextRun};

/// Convert Python rich-text run tuples into writer rich-text runs.
pub(crate) fn py_runs_to_rust_writer(runs: &Bound<'_, PyList>) -> PyResult<Vec<RichTextRun>> {
    let mut out: Vec<RichTextRun> = Vec::with_capacity(runs.len());
    for entry in runs.iter() {
        let seq: &Bound<'_, PySequence> = entry.cast()?;
        if seq.len()? < 2 {
            return Err(PyValueError::new_err(
                "rich-text run must be a (text, font_or_none) pair",
            ));
        }
        let text: String = seq.get_item(0)?.extract()?;
        let font_obj = seq.get_item(1)?;
        let font = if font_obj.is_none() {
            None
        } else {
            let d: &Bound<'_, PyDict> = font_obj.cast()?;
            let mut props = InlineFontProps::default();
            macro_rules! pull_bool {
                ($k:literal, $field:ident) => {
                    if let Some(v) = d.get_item($k)? {
                        if !v.is_none() {
                            props.$field = Some(v.extract::<bool>()?);
                        }
                    }
                };
            }
            macro_rules! pull_str {
                ($k:literal, $field:ident) => {
                    if let Some(v) = d.get_item($k)? {
                        if !v.is_none() {
                            let s: String = v.extract()?;
                            props.$field = Some(s);
                        }
                    }
                };
            }
            macro_rules! pull_i32 {
                ($k:literal, $field:ident) => {
                    if let Some(v) = d.get_item($k)? {
                        if !v.is_none() {
                            let val = if let Ok(i) = v.extract::<i32>() {
                                i
                            } else if let Ok(f) = v.extract::<f64>() {
                                if !f.is_finite() {
                                    return Err(PyValueError::new_err(format!(
                                        "{}: non-finite number",
                                        $k,
                                    )));
                                }
                                f as i32
                            } else {
                                return Err(PyValueError::new_err(format!(
                                    "{}: expected integer",
                                    $k,
                                )));
                            };
                            props.$field = Some(val);
                        }
                    }
                };
            }
            pull_bool!("b", bold);
            pull_bool!("i", italic);
            pull_bool!("strike", strike);
            pull_str!("u", underline);
            if let Some(v) = d.get_item("sz")? {
                if !v.is_none() {
                    props.size = Some(v.extract::<f64>()?);
                }
            }
            pull_str!("color", color);
            pull_str!("rFont", name);
            pull_i32!("family", family);
            pull_i32!("charset", charset);
            pull_str!("vertAlign", vert_align);
            pull_str!("scheme", scheme);
            Some(props)
        };
        out.push(RichTextRun { text, font });
    }
    Ok(out)
}
