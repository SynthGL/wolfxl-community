//! Image payload parsing for the native writer backend.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use wolfxl_writer::model::image::SheetImage;

use crate::native_writer_anchors::parse_image_anchor;

pub(crate) fn dict_to_sheet_image(dict: &Bound<'_, PyDict>) -> PyResult<SheetImage> {
    let data: Vec<u8> = dict
        .get_item("data")?
        .ok_or_else(|| PyValueError::new_err("image dict missing 'data'"))?
        .extract()?;
    let ext: String = dict
        .get_item("ext")?
        .ok_or_else(|| PyValueError::new_err("image dict missing 'ext'"))?
        .extract()?;
    let width: u32 = dict
        .get_item("width")?
        .ok_or_else(|| PyValueError::new_err("image dict missing 'width'"))?
        .extract()?;
    let height: u32 = dict
        .get_item("height")?
        .ok_or_else(|| PyValueError::new_err("image dict missing 'height'"))?
        .extract()?;
    let anchor_obj = dict
        .get_item("anchor")?
        .ok_or_else(|| PyValueError::new_err("image dict missing 'anchor'"))?;
    let anchor_dict = anchor_obj
        .cast::<PyDict>()
        .map_err(|_| PyValueError::new_err("anchor must be a dict"))?;

    Ok(SheetImage {
        data,
        ext: ext.to_ascii_lowercase(),
        width_px: width,
        height_px: height,
        anchor: parse_image_anchor(anchor_dict)?,
    })
}
