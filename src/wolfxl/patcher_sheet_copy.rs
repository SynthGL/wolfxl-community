//! Sheet-copy save phase for the surgical xlsx patcher.

use std::collections::{HashMap, HashSet};
use std::fs::File;

use pyo3::exceptions::{PyIOError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use zip::ZipArchive;

use super::patcher_workbook::{
    current_part_bytes, load_or_empty_rels, sheet_rels_path_for, splice_into_sheets_block,
};
use super::{comments, content_types, defined_names, pivot_slicer, tables, XlsxPatcher};
use wolfxl_rels::RelsGraph;

const RT_TIMELINE_CACHE: &str =
    "http://schemas.microsoft.com/office/2011/relationships/timelineCache";

pub(super) fn apply_sheet_copies_phase(
    patcher: &mut XlsxPatcher,
    file_patches: &mut HashMap<String, Vec<u8>>,
    zip: &mut ZipArchive<File>,
    part_id_allocator: &mut wolfxl_rels::PartIdAllocator,
    cloned_table_names: &mut HashSet<String>,
) -> PyResult<()> {
    let mut existing_table_names: HashSet<String> = HashSet::new();
    let table_inv = tables::scan_existing_tables(zip)
        .map_err(|e| PyIOError::new_err(format!("scan tables: {e}")))?;
    for n in &table_inv.names {
        existing_table_names.insert(n.clone());
    }
    for patches in patcher.queued_tables.values() {
        for p in patches {
            existing_table_names.insert(p.name.clone());
        }
    }

    let workbook_rels_path = "xl/_rels/workbook.xml.rels".to_string();
    if !patcher.rels_patches.contains_key(&workbook_rels_path) {
        let g = load_or_empty_rels(zip, &workbook_rels_path)?;
        patcher.rels_patches.insert(workbook_rels_path.clone(), g);
    }

    let ops = patcher.queued_sheet_copies.clone();
    for op in ops {
        let src_sheet_path = match patcher.sheet_paths.get(&op.src_title).cloned() {
            Some(p) => p,
            None => {
                return Err(PyValueError::new_err(format!(
                    "Phase 2.7: source sheet '{}' missing at flush time",
                    op.src_title
                )));
            }
        };

        let src_rels_path = sheet_rels_path_for(&src_sheet_path);
        let source_rels: RelsGraph = if let Some(g) = patcher.rels_patches.get(&src_rels_path) {
            g.clone()
        } else {
            load_or_empty_rels(zip, &src_rels_path)?
        };

        let subgraph = wolfxl_rels::walk_sheet_subgraph_with_nested(
            &source_rels,
            &src_sheet_path,
            |part_path: &str| {
                let rels_path = wolfxl_rels::rels_path_for(part_path)?;
                let bytes = current_part_bytes(file_patches, &patcher.file_adds, zip, &rels_path)?;
                RelsGraph::parse(&bytes).ok()
            },
        );

        let mut source_zip_parts: HashMap<String, Vec<u8>> = HashMap::new();
        for part_path in &subgraph.reachable_parts {
            if let Some(bytes) =
                current_part_bytes(file_patches, &patcher.file_adds, zip, part_path)
            {
                source_zip_parts.insert(part_path.clone(), bytes);
            }
            if let Some(rp) = wolfxl_rels::rels_path_for(part_path) {
                if let Some(bytes) = current_part_bytes(file_patches, &patcher.file_adds, zip, &rp)
                {
                    source_zip_parts.insert(rp, bytes);
                }
            }
        }
        if let Some(bytes) =
            current_part_bytes(file_patches, &patcher.file_adds, zip, &workbook_rels_path)
        {
            source_zip_parts.insert(workbook_rels_path.clone(), bytes.clone());
            if let Ok(workbook_rels) = RelsGraph::parse(&bytes) {
                for rel in workbook_rels.iter() {
                    if (rel.rel_type == wolfxl_pivot::rt::SLICER_CACHE
                        || rel.rel_type == RT_TIMELINE_CACHE)
                        && rel.mode == wolfxl_rels::TargetMode::Internal
                    {
                        let part_path = if rel.target.starts_with('/') {
                            rel.target.trim_start_matches('/').to_string()
                        } else {
                            format!("xl/{}", rel.target)
                        };
                        if let Some(part_bytes) =
                            current_part_bytes(file_patches, &patcher.file_adds, zip, &part_path)
                        {
                            source_zip_parts.insert(part_path, part_bytes);
                        }
                    }
                }
            }
        }

        let workbook_xml =
            match current_part_bytes(file_patches, &patcher.file_adds, zip, "xl/workbook.xml") {
                Some(b) => b,
                None => {
                    return Err(PyIOError::new_err(
                        "Phase 2.7: xl/workbook.xml missing from source ZIP",
                    ));
                }
            };

        let inputs = wolfxl_structural::sheet_copy::SheetCopyInputs {
            src_title: op.src_title.clone(),
            dst_title: op.dst_title.clone(),
            src_sheet_path: src_sheet_path.clone(),
            source_zip_parts: &source_zip_parts,
            source_rels: &source_rels,
            workbook_xml: &workbook_xml,
            allocator: part_id_allocator,
            existing_table_names: &existing_table_names,
            deep_copy_images: op.deep_copy_images,
        };
        let mutations = wolfxl_structural::sheet_copy::plan_sheet_copy(inputs).map_err(|e| {
            PyRuntimeError::new_err(format!(
                "Phase 2.7: plan_sheet_copy failed for '{}'\u{2192}'{}': {}",
                op.src_title, op.dst_title, e
            ))
        })?;

        let (placeholder, rel_type, target) = mutations
            .workbook_rels_to_add
            .first()
            .cloned()
            .ok_or_else(|| {
                PyRuntimeError::new_err("Phase 2.7: planner returned no workbook_rels_to_add entry")
            })?;
        let new_rid = {
            let g = patcher
                .rels_patches
                .get_mut(&workbook_rels_path)
                .expect("workbook rels graph loaded above");
            g.add(&rel_type, &target, wolfxl_rels::TargetMode::Internal)
        };

        let sheets_append: Vec<u8> = {
            let s = String::from_utf8_lossy(&mutations.workbook_sheets_append);
            s.replace(&placeholder, &new_rid.0).into_bytes()
        };

        let new_workbook_xml = splice_into_sheets_block(&workbook_xml, &sheets_append)?;
        file_patches.insert("xl/workbook.xml".to_string(), new_workbook_xml);

        let mut workbook_slicer_refs: Vec<pivot_slicer::WorkbookSlicerCacheRef> = Vec::new();
        if !mutations.workbook_slicer_cache_rels_to_add.is_empty() {
            let g = patcher
                .rels_patches
                .get_mut(&workbook_rels_path)
                .expect("workbook rels graph loaded above");
            for (cache_name, rel_type, target) in &mutations.workbook_slicer_cache_rels_to_add {
                let rid = g.add(rel_type, target, wolfxl_rels::TargetMode::Internal);
                workbook_slicer_refs.push(pivot_slicer::WorkbookSlicerCacheRef {
                    name: cache_name.clone(),
                    rid: rid.0,
                });
            }
        }
        if !workbook_slicer_refs.is_empty() {
            let wb_xml = file_patches
                .get("xl/workbook.xml")
                .cloned()
                .ok_or_else(|| PyIOError::new_err("Phase 2.7: workbook patch missing"))?;
            let updated =
                pivot_slicer::splice_workbook_slicer_caches(&wb_xml, &workbook_slicer_refs)
                    .map_err(|e| {
                        PyIOError::new_err(format!("Phase 2.7: splice copied slicer caches: {e}"))
                    })?;
            file_patches.insert("xl/workbook.xml".to_string(), updated);
            for cache_ref in &workbook_slicer_refs {
                let already_queued = patcher
                    .queued_defined_names
                    .iter()
                    .any(|q| q.name == cache_ref.name && q.local_sheet_id.is_none());
                if !already_queued {
                    patcher
                        .queued_defined_names
                        .push(defined_names::DefinedNameMut {
                            name: cache_ref.name.clone(),
                            formula: "#N/A".to_string(),
                            local_sheet_id: None,
                            ..Default::default()
                        });
                }
            }
        }

        let mut workbook_timeline_refs: Vec<pivot_slicer::WorkbookTimelineCacheRef> = Vec::new();
        if !mutations.workbook_timeline_cache_rels_to_add.is_empty() {
            let g = patcher
                .rels_patches
                .get_mut(&workbook_rels_path)
                .expect("workbook rels graph loaded above");
            for (cache_name, rel_type, target) in &mutations.workbook_timeline_cache_rels_to_add {
                let rid = g.add(rel_type, target, wolfxl_rels::TargetMode::Internal);
                workbook_timeline_refs.push(pivot_slicer::WorkbookTimelineCacheRef {
                    name: cache_name.clone(),
                    rid: rid.0,
                });
            }
        }
        if !workbook_timeline_refs.is_empty() {
            let wb_xml = file_patches
                .get("xl/workbook.xml")
                .cloned()
                .ok_or_else(|| PyIOError::new_err("Phase 2.7: workbook patch missing"))?;
            let updated =
                pivot_slicer::splice_workbook_timeline_caches(&wb_xml, &workbook_timeline_refs)
                    .map_err(|e| {
                        PyIOError::new_err(format!("Phase 2.7: splice copied timeline caches: {e}"))
                    })?;
            file_patches.insert("xl/workbook.xml".to_string(), updated);
            for cache_ref in &workbook_timeline_refs {
                let already_queued = patcher
                    .queued_defined_names
                    .iter()
                    .any(|q| q.name == cache_ref.name && q.local_sheet_id.is_none());
                if !already_queued {
                    patcher
                        .queued_defined_names
                        .push(defined_names::DefinedNameMut {
                            name: cache_ref.name.clone(),
                            formula: "#N/A".to_string(),
                            local_sheet_id: None,
                            ..Default::default()
                        });
                }
            }
        }

        patcher
            .file_adds
            .insert(mutations.new_sheet_path.clone(), mutations.new_sheet_xml);
        for (path, bytes) in mutations.new_ancillary_parts {
            patcher.file_adds.insert(path, bytes);
        }

        let ct_ops_for_sheet = patcher
            .queued_content_type_ops
            .entry("__rfc035_sheet_copy__".to_string())
            .or_default();
        for (part_path, content_type) in mutations.content_type_overrides_to_add {
            if part_path.ends_with(".vml") {
                ct_ops_for_sheet.push(content_types::ContentTypeOp::EnsureDefault(
                    "vml".to_string(),
                    comments::CT_VML.to_string(),
                ));
            } else {
                ct_ops_for_sheet.push(content_types::ContentTypeOp::AddOverride(
                    part_path,
                    content_type,
                ));
            }
        }

        let needs_vml_default = patcher
            .file_adds
            .keys()
            .any(|k| k.starts_with("xl/drawings/vmlDrawing") && k.ends_with(".vml"));
        if needs_vml_default {
            ct_ops_for_sheet.push(content_types::ContentTypeOp::EnsureDefault(
                "vml".to_string(),
                comments::CT_VML.to_string(),
            ));
        }

        for dn in mutations.defined_names_to_add {
            let key_name = dn.name.as_str();
            let key_lsid = Some(dn.local_sheet_id);
            let already_queued = patcher
                .queued_defined_names
                .iter()
                .any(|q| q.name == key_name && q.local_sheet_id == key_lsid);
            if already_queued {
                continue;
            }
            patcher
                .queued_defined_names
                .push(defined_names::DefinedNameMut {
                    name: dn.name,
                    formula: dn.formula,
                    local_sheet_id: Some(dn.local_sheet_id),
                    ..Default::default()
                });
        }

        for n in &mutations.new_table_names {
            cloned_table_names.insert(n.clone());
            existing_table_names.insert(n.clone());
        }

        patcher.sheet_order.push(op.dst_title.clone());
        patcher
            .sheet_paths
            .insert(op.dst_title.clone(), mutations.new_sheet_path);
    }

    patcher.queued_sheet_copies.clear();
    Ok(())
}
