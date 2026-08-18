//! Workbook metadata payload parsing for the native writer backend.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use wolfxl_writer::model::{DefinedName, DocProperties};
use wolfxl_writer::parse::workbook_security::{
    emit_file_sharing, emit_workbook_protection, FileSharingSpec, WorkbookProtectionSpec,
    WorkbookSecurity,
};
use wolfxl_writer::Workbook;

use crate::util::{parse_iso_date, parse_iso_datetime};

/// Build a `DefinedName` from a cfg dict, or `None` for a silent no-op.
pub(crate) fn dict_to_defined_name(
    wb: &Workbook,
    sheet_name: &str,
    cfg: &Bound<'_, PyDict>,
) -> PyResult<Option<DefinedName>> {
    let name: Option<String> = cfg.get_item("name")?.and_then(|v| v.extract().ok());
    let refers_to: Option<String> = cfg.get_item("refers_to")?.and_then(|v| v.extract().ok());

    let (Some(name), Some(refers_to)) = (name, refers_to) else {
        return Ok(None);
    };

    let scope: String = cfg
        .get_item("scope")?
        .and_then(|v| v.extract::<String>().ok())
        .unwrap_or_else(|| "workbook".to_string());

    let scope_sheet_index: Option<usize> = if scope == "sheet" {
        let idx = wb.sheet_index_by_name(sheet_name).ok_or_else(|| {
            PyValueError::new_err(format!(
                "add_named_range: sheet {sheet_name:?} not found (scope=sheet requires the sheet to exist)"
            ))
        })?;
        Some(idx)
    } else {
        None
    };

    let hidden: bool = cfg
        .get_item("hidden")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);

    Ok(Some(DefinedName {
        name,
        formula: refers_to,
        scope_sheet_index,
        builtin: None,
        hidden,
        comment: extract_opt_str(cfg, "comment")?,
        custom_menu: extract_opt_str(cfg, "custom_menu")?,
        description: extract_opt_str(cfg, "description")?,
        help: extract_opt_str(cfg, "help")?,
        status_bar: extract_opt_str(cfg, "status_bar")?,
        shortcut_key: extract_opt_str(cfg, "shortcut_key")?,
        function: extract_opt_bool(cfg, "function")?,
        function_group_id: extract_opt_u32(cfg, "function_group_id")?,
        vb_procedure: extract_opt_bool(cfg, "vb_procedure")?,
        xlm: extract_opt_bool(cfg, "xlm")?,
        publish_to_server: extract_opt_bool(cfg, "publish_to_server")?,
        workbook_parameter: extract_opt_bool(cfg, "workbook_parameter")?,
    }))
}

fn extract_opt_str(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => v.extract::<String>().map(Some),
        _ => Ok(None),
    }
}

fn extract_opt_bool(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<bool>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => v.extract::<bool>().map(Some),
        _ => Ok(None),
    }
}

fn extract_opt_u32(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<u32>> {
    match d.get_item(key)? {
        Some(v) if !v.is_none() => v.extract::<u32>().map(Some),
        _ => Ok(None),
    }
}

/// Build a `DocProperties` from a flat props dict.
pub(crate) fn dict_to_doc_properties(props: &Bound<'_, PyDict>) -> PyResult<DocProperties> {
    let title: Option<String> = props.get_item("title")?.and_then(|v| v.extract().ok());
    let subject: Option<String> = props.get_item("subject")?.and_then(|v| v.extract().ok());
    let creator: Option<String> = props.get_item("creator")?.and_then(|v| v.extract().ok());
    let keywords: Option<String> = props.get_item("keywords")?.and_then(|v| v.extract().ok());
    let description: Option<String> = props
        .get_item("description")?
        .and_then(|v| v.extract().ok());
    let category: Option<String> = props.get_item("category")?.and_then(|v| v.extract().ok());
    let content_status: Option<String> = props
        .get_item("contentStatus")?
        .and_then(|v| v.extract().ok());

    let created: Option<chrono::NaiveDateTime> = props.get_item("created")?.and_then(|v| {
        v.extract::<String>().ok().and_then(|s| {
            parse_iso_datetime(&s)
                .or_else(|| parse_iso_date(&s).and_then(|d| d.and_hms_opt(0, 0, 0)))
        })
    });

    Ok(DocProperties {
        title,
        subject,
        creator,
        keywords,
        description,
        category,
        created,
        content_status,
        ..Default::default()
    })
}

pub(crate) fn dict_to_workbook_security(payload: &Bound<'_, PyDict>) -> PyResult<WorkbookSecurity> {
    fn extract_str(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
        match d.get_item(key)? {
            Some(v) if !v.is_none() => v.extract::<String>().map(Some),
            _ => Ok(None),
        }
    }
    fn extract_bool(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<bool>> {
        match d.get_item(key)? {
            Some(v) if !v.is_none() => v.extract::<bool>().map(Some),
            _ => Ok(None),
        }
    }
    fn extract_u32(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<u32>> {
        match d.get_item(key)? {
            Some(v) if !v.is_none() => v.extract::<u32>().map(Some),
            _ => Ok(None),
        }
    }

    let workbook_protection = match payload.get_item("workbook_protection")? {
        Some(v) if !v.is_none() => {
            let d = v
                .cast::<PyDict>()
                .map_err(|_| PyValueError::new_err("workbook_protection must be a dict or None"))?;
            Some(WorkbookProtectionSpec {
                lock_structure: extract_bool(d, "lock_structure")?.unwrap_or(false),
                lock_windows: extract_bool(d, "lock_windows")?.unwrap_or(false),
                lock_revision: extract_bool(d, "lock_revision")?.unwrap_or(false),
                workbook_password: extract_str(d, "workbook_password")?,
                workbook_password_character_set: extract_str(d, "workbook_password_character_set")?,
                workbook_algorithm_name: extract_str(d, "workbook_algorithm_name")?,
                workbook_hash_value: extract_str(d, "workbook_hash_value")?,
                workbook_salt_value: extract_str(d, "workbook_salt_value")?,
                workbook_spin_count: extract_u32(d, "workbook_spin_count")?,
                revisions_password: extract_str(d, "revisions_password")?,
                revisions_password_character_set: extract_str(
                    d,
                    "revisions_password_character_set",
                )?,
                revisions_algorithm_name: extract_str(d, "revisions_algorithm_name")?,
                revisions_hash_value: extract_str(d, "revisions_hash_value")?,
                revisions_salt_value: extract_str(d, "revisions_salt_value")?,
                revisions_spin_count: extract_u32(d, "revisions_spin_count")?,
            })
        }
        _ => None,
    };

    let file_sharing = match payload.get_item("file_sharing")? {
        Some(v) if !v.is_none() => {
            let d = v
                .cast::<PyDict>()
                .map_err(|_| PyValueError::new_err("file_sharing must be a dict or None"))?;
            Some(FileSharingSpec {
                read_only_recommended: extract_bool(d, "read_only_recommended")?.unwrap_or(false),
                user_name: extract_str(d, "user_name")?,
                reservation_password: extract_str(d, "reservation_password")?,
                algorithm_name: extract_str(d, "algorithm_name")?,
                hash_value: extract_str(d, "hash_value")?,
                salt_value: extract_str(d, "salt_value")?,
                spin_count: extract_u32(d, "spin_count")?,
            })
        }
        _ => None,
    };

    Ok(WorkbookSecurity {
        workbook_protection,
        file_sharing,
    })
}

/// Render workbook security payloads to `workbookProtection` and `fileSharing`.
#[pyfunction]
pub fn serialize_workbook_security_dict(
    payload: &Bound<'_, PyDict>,
) -> PyResult<(Vec<u8>, Vec<u8>)> {
    let security = dict_to_workbook_security(payload)?;
    let prot_bytes = security
        .workbook_protection
        .as_ref()
        .map(emit_workbook_protection)
        .unwrap_or_default();
    let share_bytes = security
        .file_sharing
        .as_ref()
        .map(emit_file_sharing)
        .unwrap_or_default();
    Ok((prot_bytes, share_bytes))
}
