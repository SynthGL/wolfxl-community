//! Drawing anchor payload parsing shared by native writer images and charts.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use wolfxl_writer::model::image::ImageAnchor;

pub(crate) fn parse_image_anchor(d: &Bound<'_, PyDict>) -> PyResult<ImageAnchor> {
    let kind: String = d
        .get_item("type")?
        .ok_or_else(|| PyValueError::new_err("anchor dict missing 'type'"))?
        .extract()?;
    match kind.as_str() {
        "one_cell" => {
            let from_col: u32 = anchor_int(d, "from_col", 0)?;
            let from_row: u32 = anchor_int(d, "from_row", 0)?;
            let from_col_off: i64 = anchor_int_i64(d, "from_col_off", 0)?;
            let from_row_off: i64 = anchor_int_i64(d, "from_row_off", 0)?;
            Ok(ImageAnchor::OneCell {
                from_col,
                from_row,
                from_col_off,
                from_row_off,
            })
        }
        "two_cell" => {
            let from_col: u32 = anchor_int(d, "from_col", 0)?;
            let from_row: u32 = anchor_int(d, "from_row", 0)?;
            let from_col_off: i64 = anchor_int_i64(d, "from_col_off", 0)?;
            let from_row_off: i64 = anchor_int_i64(d, "from_row_off", 0)?;
            let to_col: u32 = anchor_int(d, "to_col", 0)?;
            let to_row: u32 = anchor_int(d, "to_row", 0)?;
            let to_col_off: i64 = anchor_int_i64(d, "to_col_off", 0)?;
            let to_row_off: i64 = anchor_int_i64(d, "to_row_off", 0)?;
            let edit_as: String = d
                .get_item("edit_as")?
                .and_then(|v| v.extract().ok())
                .unwrap_or_else(|| "oneCell".to_string());
            Ok(ImageAnchor::TwoCell {
                from_col,
                from_row,
                from_col_off,
                from_row_off,
                to_col,
                to_row,
                to_col_off,
                to_row_off,
                edit_as,
            })
        }
        "absolute" => {
            let x_emu: i64 = anchor_int_i64(d, "x_emu", 0)?;
            let y_emu: i64 = anchor_int_i64(d, "y_emu", 0)?;
            let cx_emu: i64 = anchor_int_i64(d, "cx_emu", 0)?;
            let cy_emu: i64 = anchor_int_i64(d, "cy_emu", 0)?;
            Ok(ImageAnchor::Absolute {
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            })
        }
        other => Err(PyValueError::new_err(format!(
            "unknown anchor type: {other:?} (expected one_cell, two_cell, or absolute)"
        ))),
    }
}

fn anchor_int(d: &Bound<'_, PyDict>, key: &str, default: u32) -> PyResult<u32> {
    Ok(d.get_item(key)?
        .and_then(|v| v.extract().ok())
        .unwrap_or(default))
}

fn anchor_int_i64(d: &Bound<'_, PyDict>, key: &str, default: i64) -> PyResult<i64> {
    Ok(d.get_item(key)?
        .and_then(|v| v.extract().ok())
        .unwrap_or(default))
}
