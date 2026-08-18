//! Cell-level save phase preparation for the surgical xlsx patcher.

use std::collections::HashMap;
use std::fs::File;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use zip::ZipArchive;

use crate::ooxml_util;

use super::patcher_workbook::minimal_styles_xml;
use super::sheet_patcher::CellPatch;
use super::{styles, XlsxPatcher};

pub(super) fn build_sheet_cell_patches_phase(
    patcher: &XlsxPatcher,
    zip: &mut ZipArchive<File>,
) -> PyResult<(Option<String>, HashMap<String, Vec<CellPatch>>)> {
    let mut styles_xml: Option<String> = None;
    let mut style_assignments: HashMap<String, u32> = HashMap::new();

    if !patcher.format_patches.is_empty() {
        let raw = ooxml_util::zip_read_to_string_opt(zip, "xl/styles.xml")?
            .unwrap_or_else(minimal_styles_xml);
        let mut xml = raw;

        for ((sheet, cell), spec) in &patcher.format_patches {
            let (updated, xf_idx) = styles::apply_format_spec(&xml, spec);
            xml = updated;
            style_assignments.insert(format!("{sheet}:{cell}"), xf_idx);
        }
        styles_xml = Some(xml);
    }

    let mut sheet_cell_patches: HashMap<String, Vec<CellPatch>> = HashMap::new();

    for ((sheet, cell), patch) in &patcher.value_patches {
        let sheet_path = match patcher.sheet_paths.get(sheet) {
            Some(path) => path,
            None => continue,
        };
        let mut patch = patch.clone();
        let key = format!("{sheet}:{cell}");
        if let Some(&xf_idx) = style_assignments.get(&key) {
            patch.style_index = Some(xf_idx);
        }
        sheet_cell_patches
            .entry(sheet_path.clone())
            .or_default()
            .push(patch);
    }

    for ((sheet, cell), _) in &patcher.format_patches {
        if patcher
            .value_patches
            .contains_key(&(sheet.clone(), cell.clone()))
        {
            continue;
        }
        let sheet_path = match patcher.sheet_paths.get(sheet) {
            Some(path) => path,
            None => continue,
        };
        let key = format!("{sheet}:{cell}");
        if let Some(&xf_idx) = style_assignments.get(&key) {
            let (row, col) = crate::util::a1_to_row_col(cell).map_err(PyValueError::new_err)?;
            let patch = CellPatch {
                row: row + 1,
                col: col + 1,
                value: None,
                style_index: Some(xf_idx),
            };
            sheet_cell_patches
                .entry(sheet_path.clone())
                .or_default()
                .push(patch);
        }
    }

    Ok((styles_xml, sheet_cell_patches))
}
