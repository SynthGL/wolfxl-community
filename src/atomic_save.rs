//! Atomic output helpers for workbook save paths.

use std::fs::File;
use std::path::Path;

use pyo3::exceptions::PyIOError;
use pyo3::prelude::*;

pub(crate) fn write_zip_atomically<F>(target: &str, write_fn: F) -> PyResult<()>
where
    F: FnOnce(&mut File) -> PyResult<()>,
{
    write_zip_atomically_impl(target, write_fn, SaveChecks::ValidateAndSync)
}

pub(crate) fn write_zip_atomically_fast<F>(target: &str, write_fn: F) -> PyResult<()>
where
    F: FnOnce(&mut File) -> PyResult<()>,
{
    write_zip_atomically_impl(target, write_fn, SaveChecks::RenameOnly)
}

enum SaveChecks {
    ValidateAndSync,
    RenameOnly,
}

fn write_zip_atomically_impl<F>(target: &str, write_fn: F, checks: SaveChecks) -> PyResult<()>
where
    F: FnOnce(&mut File) -> PyResult<()>,
{
    let target_path = Path::new(target);
    let dir = target_path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    let file_name = target_path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("workbook.xlsx");
    let prefix = format!(".{file_name}.wolfxl-");
    let mut tmp = tempfile::Builder::new()
        .prefix(&prefix)
        .suffix(".tmp")
        .tempfile_in(dir)
        .map_err(|e| PyIOError::new_err(format!("failed to create temp file for {target}: {e}")))?;

    let write_result = write_fn(tmp.as_file_mut());
    if let Err(e) = write_result {
        return Err(e);
    }

    let should_validate = matches!(checks, SaveChecks::ValidateAndSync) || zip_safety_env_is_set();
    if should_validate {
        if matches!(checks, SaveChecks::ValidateAndSync) {
            tmp.as_file_mut().sync_all().map_err(|e| {
                PyIOError::new_err(format!("failed to sync temp file for {target}: {e}"))
            })?;
        }

        validate_zip_file(tmp.path(), target)?;
    }

    tmp.persist(target_path).map_err(|e| {
        PyIOError::new_err(format!(
            "failed to atomically replace {target}: {}",
            e.error
        ))
    })?;
    if matches!(checks, SaveChecks::ValidateAndSync) {
        let _ = sync_parent_dir(dir);
    }
    Ok(())
}

fn validate_zip_file(path: &Path, target: &str) -> PyResult<()> {
    let file = File::open(path)
        .map_err(|e| PyIOError::new_err(format!("failed to validate {target}: {e}")))?;
    let mut zip = zip::ZipArchive::new(file)
        .map_err(|e| PyIOError::new_err(format!("failed to validate {target} as ZIP: {e}")))?;
    crate::ooxml_util::validate_zip_archive(&mut zip)?;
    Ok(())
}

fn zip_safety_env_is_set() -> bool {
    [
        "WOLFXL_MAX_ZIP_ENTRIES",
        "WOLFXL_MAX_ZIP_ENTRY_BYTES",
        "WOLFXL_MAX_ZIP_TOTAL_BYTES",
        "WOLFXL_MAX_ZIP_COMPRESSION_RATIO",
    ]
    .iter()
    .any(|name| std::env::var_os(name).is_some())
}

fn sync_parent_dir(dir: &Path) -> std::io::Result<()> {
    File::open(dir)?.sync_all()
}
