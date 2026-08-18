//! Python dictionary payload parsers for patcher queues.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PySequence};

use super::conditional_formatting::{CfRuleKind, CfRulePatch, CfvoPatch, ColorScaleStop, DxfPatch};
use super::styles;
use super::styles::FormatSpec;
use wolfxl_writer::parse::workbook_security::{
    FileSharingSpec, WorkbookProtectionSpec, WorkbookSecurity,
};
use wolfxl_writer::rich_text::{InlineFontProps, RichTextRun};

pub(crate) fn dict_to_format_spec(d: &Bound<'_, PyDict>) -> PyResult<FormatSpec> {
    let mut spec = FormatSpec::default();

    let bold = extract_bool(d, "bold")?;
    let italic = extract_bool(d, "italic")?;
    let underline = extract_bool(d, "underline")?;
    let strikethrough = extract_bool(d, "strikethrough")?;
    let font_name = extract_str(d, "font_name")?;
    let font_size = extract_u32(d, "font_size")?;
    let font_color = extract_str(d, "font_color")?;

    if bold.is_some()
        || italic.is_some()
        || underline.is_some()
        || strikethrough.is_some()
        || font_name.is_some()
        || font_size.is_some()
        || font_color.is_some()
    {
        spec.font = Some(styles::FontSpec {
            bold: bold.unwrap_or(false),
            italic: italic.unwrap_or(false),
            underline: underline.unwrap_or(false),
            strikethrough: strikethrough.unwrap_or(false),
            name: font_name,
            size: font_size,
            color_rgb: font_color.map(|c| normalize_color(&c)),
        });
    }

    if let Some(color) = extract_str(d, "bg_color")? {
        spec.fill = Some(styles::FillSpec {
            pattern_type: "solid".to_string(),
            fg_color_rgb: Some(normalize_color(&color)),
        });
    }

    spec.number_format = extract_str(d, "number_format")?;

    let horizontal = extract_str(d, "horizontal")?.or(extract_str(d, "h_align")?);
    let vertical = extract_str(d, "vertical")?.or(extract_str(d, "v_align")?);
    let wrap_text = extract_bool(d, "wrap_text")?.or(extract_bool(d, "wrap")?);
    let indent = extract_u32(d, "indent")?;
    let text_rotation = extract_u32(d, "text_rotation")?.or(extract_u32(d, "rotation")?);

    if horizontal.is_some()
        || vertical.is_some()
        || wrap_text.is_some()
        || indent.is_some()
        || text_rotation.is_some()
    {
        spec.alignment = Some(styles::AlignmentSpec {
            horizontal,
            vertical,
            wrap_text: wrap_text.unwrap_or(false),
            indent: indent.unwrap_or(0),
            text_rotation: text_rotation.unwrap_or(0),
        });
    }

    Ok(spec)
}

pub(crate) fn dict_to_border_spec(d: &Bound<'_, PyDict>) -> PyResult<styles::BorderSpec> {
    fn extract_side(d: &Bound<'_, PyDict>, key: &str) -> PyResult<(styles::BorderSideSpec, bool)> {
        if let Some(side) = d.get_item(key)? {
            if let Ok(sd) = side.cast::<PyDict>() {
                let style = extract_str(sd, "style")?;
                let color = extract_str(sd, "color")?.map(|c| normalize_color(&c));
                return Ok((
                    styles::BorderSideSpec {
                        style,
                        color_rgb: color,
                    },
                    true,
                ));
            }
        }
        Ok((styles::BorderSideSpec::default(), false))
    }

    let (left, _) = extract_side(d, "left")?;
    let (right, _) = extract_side(d, "right")?;
    let (top, _) = extract_side(d, "top")?;
    let (bottom, _) = extract_side(d, "bottom")?;
    let (diag_up, has_up) = extract_side(d, "diagonal_up")?;
    let (diag_down, has_down) = extract_side(d, "diagonal_down")?;

    let (diagonal, diagonal_up, diagonal_down) = if has_down {
        (diag_down, has_up, true)
    } else if has_up {
        (diag_up, true, false)
    } else {
        (styles::BorderSideSpec::default(), false, false)
    };

    Ok(styles::BorderSpec {
        left,
        right,
        top,
        bottom,
        diagonal,
        diagonal_up,
        diagonal_down,
    })
}

pub(crate) fn extract_cf_rule(d: &Bound<'_, PyDict>) -> PyResult<CfRulePatch> {
    let kind_tag =
        extract_str(d, "kind")?.ok_or_else(|| PyValueError::new_err("CF rule requires 'kind'"))?;

    let kind = match kind_tag.as_str() {
        "cellIs" => CfRuleKind::CellIs {
            operator: extract_str(d, "operator")?.unwrap_or_else(|| "equal".to_string()),
            formula_a: extract_str(d, "formula_a")?.unwrap_or_default(),
            formula_b: extract_str(d, "formula_b")?,
        },
        "expression" => CfRuleKind::Expression {
            formula: extract_str(d, "formula")?.unwrap_or_default(),
        },
        "colorScale" => {
            let stops_obj = d
                .get_item("stops")?
                .ok_or_else(|| PyValueError::new_err("colorScale rule requires 'stops'"))?;
            let stops_list = stops_obj
                .cast::<PyList>()
                .map_err(|_| PyValueError::new_err("'stops' must be a list of dicts"))?;
            let mut stops: Vec<ColorScaleStop> = Vec::with_capacity(stops_list.len());
            for s in stops_list.iter() {
                let sd = s
                    .cast::<PyDict>()
                    .map_err(|_| PyValueError::new_err("each stop must be a dict"))?;
                stops.push(ColorScaleStop {
                    cfvo: CfvoPatch {
                        cfvo_type: extract_str(sd, "cfvo_type")?
                            .unwrap_or_else(|| "min".to_string()),
                        val: extract_str(sd, "val")?,
                    },
                    color_rgb: extract_str(sd, "color_rgb")?.unwrap_or_default(),
                });
            }
            CfRuleKind::ColorScale { stops }
        }
        "dataBar" => CfRuleKind::DataBar {
            min: CfvoPatch {
                cfvo_type: extract_str(d, "min_cfvo_type")?.unwrap_or_else(|| "min".to_string()),
                val: extract_str(d, "min_val")?,
            },
            max: CfvoPatch {
                cfvo_type: extract_str(d, "max_cfvo_type")?.unwrap_or_else(|| "max".to_string()),
                val: extract_str(d, "max_val")?,
            },
            color_rgb: extract_str(d, "color_rgb")?.unwrap_or_default(),
            show_value: extract_bool(d, "show_value")?.unwrap_or(true),
            min_length: extract_u32(d, "min_length")?,
            max_length: extract_u32(d, "max_length")?,
        },
        "iconSet" => {
            let set_name = extract_str(d, "icon_style")?
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| "3TrafficLights1".to_string());
            let value_type = extract_str(d, "value_type")?
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| "percent".to_string());
            let values_obj = d.get_item("values")?;
            let mut thresholds = Vec::new();
            if let Some(values) = values_obj {
                let values_list = values
                    .cast::<PyList>()
                    .map_err(|_| PyValueError::new_err("'values' must be a list"))?;
                for value in values_list.iter() {
                    thresholds.push(CfvoPatch {
                        cfvo_type: value_type.clone(),
                        val: Some(value.str()?.to_string()),
                    });
                }
            }
            CfRuleKind::IconSet {
                set_name,
                thresholds,
                show_value: extract_bool(d, "show_value")?.unwrap_or(true),
                percent: extract_bool(d, "percent")?,
                reverse: extract_bool(d, "reverse")?,
            }
        }
        "containsText" | "notContainsText" | "beginsWith" | "endsWith" | "duplicateValues"
        | "uniqueValues" | "top10" | "aboveAverage" | "containsBlanks" | "notContainsBlanks"
        | "containsErrors" | "notContainsErrors" | "timePeriod" => CfRuleKind::Generic {
            type_name: kind_tag.clone(),
            attrs: generic_cf_attrs(d, &kind_tag)?,
            formulas: generic_cf_formulas(d)?,
        },
        _ => CfRuleKind::Generic {
            type_name: kind_tag.clone(),
            attrs: generic_cf_attrs(d, &kind_tag)?,
            formulas: generic_cf_formulas(d)?,
        },
    };

    let dxf = match d.get_item("dxf")? {
        Some(v) if !v.is_none() => {
            let dd = v
                .cast::<PyDict>()
                .map_err(|_| PyValueError::new_err("'dxf' must be a dict or None"))?;
            Some(extract_dxf_patch(dd)?)
        }
        _ => None,
    };

    Ok(CfRulePatch {
        kind,
        dxf,
        stop_if_true: extract_bool(d, "stop_if_true")?.unwrap_or(false),
    })
}

fn generic_cf_attrs(d: &Bound<'_, PyDict>, rule_type: &str) -> PyResult<Vec<(String, String)>> {
    let mut attrs: Vec<(String, String)> = Vec::new();
    if let Some(operator) = extract_str(d, "operator")? {
        attrs.push(("operator".to_string(), operator));
    }
    if let Some(text) = extract_str(d, "text")? {
        attrs.push(("text".to_string(), text));
    }
    if let Some(time_period) = extract_str(d, "time_period")?.or(extract_str(d, "timePeriod")?) {
        attrs.push(("timePeriod".to_string(), time_period));
    }
    if let Some(rank) = extract_attr_string(d, "rank")? {
        attrs.push(("rank".to_string(), rank));
    }
    if let Some(std_dev) = extract_attr_string(d, "std_dev")?.or(extract_attr_string(d, "stdDev")?)
    {
        attrs.push(("stdDev".to_string(), std_dev));
    }
    if let Some(value) = extract_bool(d, "above_average")?.or(extract_bool(d, "aboveAverage")?) {
        attrs.push(("aboveAverage".to_string(), bool_attr(value)));
    } else if rule_type == "aboveAverage" {
        attrs.push(("aboveAverage".to_string(), "1".to_string()));
    }
    if let Some(value) = extract_bool(d, "equal_average")?.or(extract_bool(d, "equalAverage")?) {
        attrs.push(("equalAverage".to_string(), bool_attr(value)));
    }
    if let Some(value) = extract_bool(d, "percent")? {
        attrs.push(("percent".to_string(), bool_attr(value)));
    }
    if let Some(value) = extract_bool(d, "bottom")? {
        attrs.push(("bottom".to_string(), bool_attr(value)));
    }
    Ok(attrs)
}

fn extract_attr_string(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
    let Some(value) = d.get_item(key)? else {
        return Ok(None);
    };
    if let Ok(s) = value.extract::<String>() {
        return Ok(Some(s));
    }
    if let Ok(i) = value.extract::<i64>() {
        return Ok(Some(i.to_string()));
    }
    if let Ok(f) = value.extract::<f64>() {
        if f.fract() == 0.0 && f.abs() < 1e15 {
            return Ok(Some((f as i64).to_string()));
        }
        return Ok(Some(f.to_string()));
    }
    Ok(None)
}

fn generic_cf_formulas(d: &Bound<'_, PyDict>) -> PyResult<Vec<String>> {
    if let Some(v) = d.get_item("formulas")? {
        if let Ok(items) = v.extract::<Vec<String>>() {
            return Ok(items
                .into_iter()
                .map(|s| s.trim_start_matches('=').to_string())
                .filter(|s| !s.is_empty())
                .collect());
        }
    }
    let mut formulas = Vec::new();
    for key in ["formula_a", "formula_b", "formula"] {
        if let Some(value) = extract_str(d, key)? {
            let value = value.trim_start_matches('=').to_string();
            if !value.is_empty() {
                formulas.push(value);
            }
        }
    }
    Ok(formulas)
}

fn bool_attr(value: bool) -> String {
    if value {
        "1".to_string()
    } else {
        "0".to_string()
    }
}

/// Converts a Python RFC-058 workbook-security payload into writer state.
pub(crate) fn parse_workbook_security_payload(
    payload: &Bound<'_, PyDict>,
) -> PyResult<WorkbookSecurity> {
    let workbook_protection = match payload.get_item("workbook_protection")? {
        Some(v) if !v.is_none() => {
            let d = v.cast::<PyDict>().map_err(|_| {
                PyValueError::new_err(
                    "queue_workbook_security: 'workbook_protection' must be a dict or None",
                )
            })?;
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
            let d = v.cast::<PyDict>().map_err(|_| {
                PyValueError::new_err(
                    "queue_workbook_security: 'file_sharing' must be a dict or None",
                )
            })?;
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

/// Converts Python rich-text runs into writer-compatible run structs.
pub(crate) fn py_runs_to_rust(runs: &Bound<'_, PyList>) -> PyResult<Vec<RichTextRun>> {
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
            if let Some(v) = d.get_item("b")? {
                if !v.is_none() {
                    props.bold = Some(v.extract::<bool>()?);
                }
            }
            if let Some(v) = d.get_item("i")? {
                if !v.is_none() {
                    props.italic = Some(v.extract::<bool>()?);
                }
            }
            if let Some(v) = d.get_item("strike")? {
                if !v.is_none() {
                    props.strike = Some(v.extract::<bool>()?);
                }
            }
            if let Some(v) = d.get_item("u")? {
                if !v.is_none() {
                    let s: String = v.extract()?;
                    props.underline = Some(s);
                }
            }
            if let Some(v) = d.get_item("sz")? {
                if !v.is_none() {
                    props.size = Some(v.extract::<f64>()?);
                }
            }
            if let Some(v) = d.get_item("color")? {
                if !v.is_none() {
                    let s: String = v.extract()?;
                    props.color = Some(s);
                }
            }
            if let Some(v) = d.get_item("rFont")? {
                if !v.is_none() {
                    let s: String = v.extract()?;
                    props.name = Some(s);
                }
            }
            if let Some(v) = d.get_item("family")? {
                if !v.is_none() {
                    props.family = Some(v.extract::<i32>()?);
                }
            }
            if let Some(v) = d.get_item("charset")? {
                if !v.is_none() {
                    props.charset = Some(v.extract::<i32>()?);
                }
            }
            if let Some(v) = d.get_item("vertAlign")? {
                if !v.is_none() {
                    let s: String = v.extract()?;
                    props.vert_align = Some(s);
                }
            }
            if let Some(v) = d.get_item("scheme")? {
                if !v.is_none() {
                    let s: String = v.extract()?;
                    props.scheme = Some(s);
                }
            }
            Some(props)
        };
        out.push(RichTextRun { text, font });
    }
    Ok(out)
}

fn extract_dxf_patch(d: &Bound<'_, PyDict>) -> PyResult<DxfPatch> {
    Ok(DxfPatch {
        font_bold: extract_bool(d, "font_bold")?,
        font_italic: extract_bool(d, "font_italic")?,
        font_color_rgb: extract_str(d, "font_color_rgb")?.map(|c| normalize_color(&c)),
        fill_pattern_type: extract_str(d, "fill_pattern_type")?,
        fill_fg_color_rgb: extract_str(d, "fill_fg_color_rgb")?.map(|c| normalize_color(&c)),
        border_top_style: extract_str(d, "border_top_style")?,
        border_bottom_style: extract_str(d, "border_bottom_style")?,
        border_left_style: extract_str(d, "border_left_style")?,
        border_right_style: extract_str(d, "border_right_style")?,
    })
}

pub(crate) fn extract_str(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
    d.get_item(key)?.map(|v| v.extract::<String>()).transpose()
}

pub(crate) fn extract_bool(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<bool>> {
    d.get_item(key)?.map(|v| v.extract::<bool>()).transpose()
}

pub(crate) fn extract_u32(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<u32>> {
    d.get_item(key)?.map(|v| v.extract::<u32>()).transpose()
}

pub(crate) fn extract_f64(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<f64>> {
    d.get_item(key)?.map(|v| v.extract::<f64>()).transpose()
}

/// Build one [`super::threaded_comments::ThreadedCommentEntry`] from a
/// Python dict (RFC-068 G08 step 5). Required keys: `id`, `cell`,
/// `person_id`, `created`, `text`. Optional: `parent_id`, `done`.
pub(crate) fn dict_to_threaded_entry(
    d: &Bound<'_, PyDict>,
) -> PyResult<super::threaded_comments::ThreadedCommentEntry> {
    use super::threaded_comments::ThreadedCommentEntry;
    let id = extract_str(d, "id")?
        .ok_or_else(|| PyValueError::new_err("threaded entry: 'id' required"))?;
    let cell_ref = extract_str(d, "cell")?
        .ok_or_else(|| PyValueError::new_err("threaded entry: 'cell' required"))?;
    let person_id = extract_str(d, "person_id")?
        .ok_or_else(|| PyValueError::new_err("threaded entry: 'person_id' required"))?;
    let created = extract_str(d, "created")?
        .ok_or_else(|| PyValueError::new_err("threaded entry: 'created' required"))?;
    let text = extract_str(d, "text")?.unwrap_or_default();
    // parent_id is `None` for top-level threads — treat the Python literal
    // `None` as absence rather than letting `extract::<String>` reject it.
    let parent_id = match d.get_item("parent_id")? {
        Some(v) if !v.is_none() => Some(v.extract::<String>()?),
        _ => None,
    };
    let done = extract_bool(d, "done")?.unwrap_or(false);
    Ok(ThreadedCommentEntry {
        id,
        cell_ref,
        person_id,
        created,
        parent_id,
        text,
        done,
    })
}

fn normalize_color(color: &str) -> String {
    let hex = color.trim_start_matches('#');
    if hex.len() == 6 {
        format!("FF{}", hex.to_uppercase())
    } else if hex.len() == 8 {
        hex.to_uppercase()
    } else {
        format!("FF{hex}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_color_adds_alpha() {
        assert_eq!(normalize_color("#c00000"), "FFC00000");
        assert_eq!(normalize_color("FFC00000"), "FFC00000");
    }
}
