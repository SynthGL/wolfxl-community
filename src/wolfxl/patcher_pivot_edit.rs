//! G17 / RFC-070 — save-time pivot source-range mutation phase.
//!
//! Sibling pass to `apply_pivot_adds_phase`. Runs AFTER the adds
//! phase so any cache definition queued in the same save (Option A
//! corner case: user adds *and* edits in one session) is touched in
//! the post-adds form held in `file_adds`.
//!
//! For each registered dirty edit:
//!
//! 1. Locate the cache definition bytes — first check `file_patches`
//!    (an earlier pass may have already mutated this part), then
//!    `file_adds` (Option A overlap), then read from the source ZIP.
//! 2. Call `wolfxl_pivot::mutate::rewrite_cache_source` with the new
//!    `ref` / `sheet` / shape-mismatch flag.
//! 3. Write the rewritten bytes back into `file_patches` (or
//!    `file_adds` if that's where they came from).

use std::collections::HashMap;
use std::fs::File;

use pyo3::exceptions::PyIOError;
use pyo3::prelude::*;
use zip::ZipArchive;

use crate::ooxml_util;

use super::XlsxPatcher;

/// One queued source-range edit for an existing on-disk pivot cache.
#[derive(Debug, Clone)]
pub struct QueuedPivotSourceEdit {
    /// ZIP entry path of the cache definition part (e.g.
    /// `xl/pivotCache/pivotCacheDefinition1.xml`).
    pub cache_part_path: String,
    /// New `<worksheetSource ref="...">` value in A1 form.
    pub new_ref: String,
    /// New `<worksheetSource sheet="...">` value. `None` keeps the
    /// existing attribute or omits one when none exists.
    pub new_sheet: Option<String>,
    /// True when the new range's column count differs from the
    /// original — stamps `refreshOnLoad="1"`.
    pub force_refresh_on_load: bool,
}

pub(super) fn apply_pivot_source_edits_phase(
    patcher: &mut XlsxPatcher,
    file_patches: &mut HashMap<String, Vec<u8>>,
    zip: &mut ZipArchive<File>,
) -> PyResult<()> {
    let drained: Vec<QueuedPivotSourceEdit> =
        std::mem::take(&mut patcher.queued_pivot_source_edits);
    if drained.is_empty() {
        return Ok(());
    }

    for edit in drained {
        // Source priority: file_patches → file_adds → ZIP.
        let (xml_bytes, write_to_adds) = if let Some(b) =
            file_patches.get(&edit.cache_part_path).cloned()
        {
            (b, false)
        } else if let Some(b) = patcher.file_adds.get(&edit.cache_part_path).cloned() {
            (b, true)
        } else {
            let s = ooxml_util::zip_read_to_string(zip, &edit.cache_part_path).map_err(|e| {
                PyErr::new::<PyIOError, _>(format!(
                    "pivot source edit: cannot read {}: {}",
                    edit.cache_part_path, e
                ))
            })?;
            (s.into_bytes(), false)
        };

        let new_xml = wolfxl_pivot::mutate::rewrite_cache_source(
            &xml_bytes,
            &edit.new_ref,
            edit.new_sheet.as_deref(),
            edit.force_refresh_on_load,
        )
        .map_err(|e| {
            PyErr::new::<PyIOError, _>(format!(
                "pivot source edit: rewrite failed for {}: {}",
                edit.cache_part_path, e
            ))
        })?;

        if write_to_adds {
            patcher
                .file_adds
                .insert(edit.cache_part_path.clone(), new_xml);
        } else {
            file_patches.insert(edit.cache_part_path.clone(), new_xml);
        }
    }

    Ok(())
}
