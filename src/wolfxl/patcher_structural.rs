//! Structural worksheet mutation phases for the surgical xlsx patcher.

use std::collections::{BTreeMap, HashMap};
use std::fs::File;

use pyo3::prelude::*;
use zip::ZipArchive;

use super::patcher_workbook::patched_or_source_part_bytes;
use super::shared_strings;
use super::XlsxPatcher;

pub(super) fn apply_axis_shifts_phase(
    patcher: &mut XlsxPatcher,
    file_patches: &mut HashMap<String, Vec<u8>>,
    zip: &mut ZipArchive<File>,
) -> PyResult<()> {
    let sheet_positions: BTreeMap<String, u32> = patcher
        .sheet_order
        .iter()
        .enumerate()
        .map(|(i, name)| (name.clone(), i as u32))
        .collect();

    for op in patcher.queued_axis_shifts.clone() {
        let sheet_path = match patcher.sheet_paths.get(&op.sheet) {
            Some(p) => p.clone(),
            None => continue,
        };

        let axis = match op.axis.as_str() {
            "row" => wolfxl_structural::Axis::Row,
            "col" => wolfxl_structural::Axis::Col,
            _ => continue,
        };

        let sheet_xml = match patched_or_source_part_bytes(file_patches, zip, &sheet_path) {
            Some(b) => b,
            None => continue,
        };
        let wb_xml = patched_or_source_part_bytes(file_patches, zip, "xl/workbook.xml");
        let shared_strings_xml =
            patched_or_source_part_bytes(file_patches, zip, "xl/sharedStrings.xml");
        let parsed_shared_strings = shared_strings_xml
            .as_ref()
            .map(|bytes| shared_strings::parse_shared_strings(&String::from_utf8_lossy(bytes)));

        let _ = patcher
            .ancillary
            .populate_for_sheet(zip, &op.sheet, &sheet_path);

        let (comments_part, vml_part, table_paths, drawing_part, ctrl_prop_paths) = {
            let anc = patcher
                .ancillary
                .get(&op.sheet)
                .cloned()
                .unwrap_or_default();
            (
                anc.comments_part,
                anc.vml_drawing_part,
                anc.table_parts.clone(),
                anc.drawing_part,
                anc.ctrl_prop_parts.clone(),
            )
        };

        let comments_bytes: Option<(String, Vec<u8>)> = comments_part.as_ref().and_then(|p| {
            patched_or_source_part_bytes(file_patches, zip, p).map(|b| (p.clone(), b))
        });
        let vml_bytes: Option<(String, Vec<u8>)> = vml_part.as_ref().and_then(|p| {
            patched_or_source_part_bytes(file_patches, zip, p).map(|b| (p.clone(), b))
        });
        let drawing_bytes: Option<(String, Vec<u8>)> = drawing_part.as_ref().and_then(|p| {
            patched_or_source_part_bytes(file_patches, zip, p).map(|b| (p.clone(), b))
        });
        let mut table_bytes: Vec<(String, Vec<u8>)> = Vec::new();
        for tp in &table_paths {
            if let Some(b) = patched_or_source_part_bytes(file_patches, zip, tp) {
                table_bytes.push((tp.clone(), b));
            }
        }
        let mut ctrl_prop_bytes: Vec<(String, Vec<u8>)> = Vec::new();
        for cp in &ctrl_prop_paths {
            if let Some(b) = patched_or_source_part_bytes(file_patches, zip, cp) {
                ctrl_prop_bytes.push((cp.clone(), b));
            }
        }

        let mut inputs = wolfxl_structural::SheetXmlInputs::empty();
        inputs.sheets.insert(op.sheet.clone(), sheet_xml.as_slice());
        inputs
            .sheet_paths
            .insert(op.sheet.clone(), sheet_path.clone());
        if let Some(ref wb) = wb_xml {
            inputs.workbook_xml = Some(wb.as_slice());
        }
        if let Some(ref strings) = parsed_shared_strings {
            inputs.shared_strings = Some(strings.as_slice());
        }
        if !table_bytes.is_empty() {
            let parts: Vec<(String, &[u8])> = table_bytes
                .iter()
                .map(|(p, b)| (p.clone(), b.as_slice()))
                .collect();
            inputs.tables.insert(op.sheet.clone(), parts);
        }
        if let Some((ref p, ref b)) = comments_bytes {
            inputs
                .comments
                .insert(op.sheet.clone(), (p.clone(), b.as_slice()));
        }
        if let Some((ref p, ref b)) = vml_bytes {
            inputs
                .vml
                .insert(op.sheet.clone(), (p.clone(), b.as_slice()));
        }
        if let Some((ref p, ref b)) = drawing_bytes {
            inputs
                .drawings
                .insert(op.sheet.clone(), (p.clone(), b.as_slice()));
        }
        if !ctrl_prop_bytes.is_empty() {
            let parts: Vec<(String, &[u8])> = ctrl_prop_bytes
                .iter()
                .map(|(p, b)| (p.clone(), b.as_slice()))
                .collect();
            inputs.control_props.insert(op.sheet.clone(), parts);
        }
        inputs.sheet_positions = sheet_positions.clone();

        let ops_one = vec![wolfxl_structural::AxisShiftOp {
            sheet: op.sheet.clone(),
            axis,
            idx: op.idx,
            n: op.n,
        }];
        let mutations = wolfxl_structural::apply_workbook_shift(inputs, &ops_one);
        for (path, bytes) in mutations.file_patches {
            file_patches.insert(path, bytes);
        }
    }

    Ok(())
}

pub(super) fn apply_range_moves_phase(
    patcher: &mut XlsxPatcher,
    file_patches: &mut HashMap<String, Vec<u8>>,
    zip: &mut ZipArchive<File>,
) -> PyResult<()> {
    for op in patcher.queued_range_moves.clone() {
        let sheet_path = match patcher.sheet_paths.get(&op.sheet) {
            Some(p) => p.clone(),
            None => continue,
        };

        let sheet_xml = match patched_or_source_part_bytes(file_patches, zip, &sheet_path) {
            Some(b) => b,
            None => continue,
        };

        let plan = wolfxl_structural::RangeMovePlan {
            src_lo: (op.src_min_row, op.src_min_col),
            src_hi: (op.src_max_row, op.src_max_col),
            d_row: op.d_row,
            d_col: op.d_col,
            translate: op.translate,
        };
        let new_bytes = wolfxl_structural::apply_range_move(&sheet_xml, &plan);
        if new_bytes != sheet_xml {
            file_patches.insert(sheet_path, new_bytes);
        }
    }

    Ok(())
}
