//! Sheet-feature payload parsing for the native writer backend.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use wolfxl_writer::model::{
    CellIsOperator, ColorScaleStop, Comment, CommentAuthorTable, ConditionalFormat,
    ConditionalKind, ConditionalRule, ConditionalThreshold, DataValidation, DxfRecord, ErrorStyle,
    FillSpec, Hyperlink, Person, StylesBuilder, Table, TableColumn, TableStyle, ThreadedComment,
    ValidationOperator, ValidationType,
};

use crate::native_writer_formats::parse_hex_color;

/// Unwrap an optional wrapper key, or return the original dict unchanged.
pub(crate) fn unwrap_optional_wrapper<'py>(
    dict: &'py Bound<'py, PyDict>,
    wrapper_key: &str,
) -> PyResult<Bound<'py, PyDict>> {
    if let Some(v) = dict.get_item(wrapper_key)? {
        if let Ok(inner) = v.cast::<PyDict>() {
            return Ok(inner.clone());
        }
    }
    Ok(dict.clone())
}

/// Build a `(a1_ref, Hyperlink)` pair from a cfg dict, or `None` for no-op.
pub(crate) fn dict_to_hyperlink(cfg: &Bound<'_, PyDict>) -> PyResult<Option<(String, Hyperlink)>> {
    let cell: Option<String> = cfg
        .get_item("cell")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let target: Option<String> = cfg
        .get_item("target")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });

    let (Some(cell), Some(raw_target)) = (cell, target) else {
        return Ok(None);
    };

    let display: Option<String> = cfg
        .get_item("display")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let tooltip: Option<String> = cfg
        .get_item("tooltip")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let location: Option<String> = cfg
        .get_item("location")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let is_internal: bool = cfg
        .get_item("internal")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);

    let target = if is_internal {
        raw_target.trim_start_matches('#').to_string()
    } else {
        raw_target
    };

    Ok(Some((
        cell,
        Hyperlink {
            target,
            location,
            is_internal,
            display,
            tooltip,
        },
    )))
}

/// Build a `(a1_ref, Comment)` pair from a cfg dict, or `None` for no-op.
pub(crate) fn dict_to_comment(
    cfg: &Bound<'_, PyDict>,
    authors: &mut CommentAuthorTable,
) -> PyResult<Option<(String, Comment)>> {
    let cell: Option<String> = cfg
        .get_item("cell")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let text: Option<String> = cfg
        .get_item("text")?
        .and_then(|v| v.extract::<String>().ok());

    let (Some(cell), Some(text)) = (cell, text) else {
        return Ok(None);
    };

    let author_name: String = cfg
        .get_item("author")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) })
        .unwrap_or_default();

    let author_id = authors.intern(author_name);

    Ok(Some((
        cell,
        Comment {
            text,
            author_id,
            width_pt: None,
            height_pt: None,
            visible: false,
        },
    )))
}

/// Build a `Person` from a cfg dict, or `None` for no-op.
///
/// RFC-068 / G08. The Python `PersonRegistry` allocates GUIDs eagerly so this
/// always sees an `id`; the dict-based contract keeps the Rust side
/// agnostic to Python's `Person` class shape.
pub(crate) fn dict_to_person(cfg: &Bound<'_, PyDict>) -> PyResult<Option<Person>> {
    let id: Option<String> = cfg
        .get_item("id")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let display_name: Option<String> = cfg
        .get_item("name")?
        .and_then(|v| v.extract::<String>().ok());

    let (Some(id), Some(display_name)) = (id, display_name) else {
        return Ok(None);
    };

    let user_id: String = cfg
        .get_item("user_id")?
        .and_then(|v| v.extract::<String>().ok())
        .unwrap_or_default();
    let provider_id: String = cfg
        .get_item("provider_id")?
        .and_then(|v| v.extract::<String>().ok())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "None".to_string());

    Ok(Some(Person {
        display_name,
        id,
        user_id,
        provider_id,
    }))
}

/// Build a `ThreadedComment` from a cfg dict, or `None` for no-op.
///
/// RFC-068 / G08. Required keys: `id`, `cell`, `person_id`, `created`, `text`.
/// Optional: `parent_id`, `done`. The Python flush layer is responsible for
/// resolving Python `Person`/`ThreadedComment` references to their GUID
/// strings before calling.
pub(crate) fn dict_to_threaded_comment(
    cfg: &Bound<'_, PyDict>,
) -> PyResult<Option<ThreadedComment>> {
    let id: Option<String> = cfg
        .get_item("id")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let cell_ref: Option<String> = cfg
        .get_item("cell")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let person_id: Option<String> = cfg
        .get_item("person_id")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let created: Option<String> = cfg
        .get_item("created")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let text: Option<String> = cfg
        .get_item("text")?
        .and_then(|v| v.extract::<String>().ok());

    let (Some(id), Some(cell_ref), Some(person_id), Some(created), Some(text)) =
        (id, cell_ref, person_id, created, text)
    else {
        return Ok(None);
    };

    let parent_id: Option<String> = cfg
        .get_item("parent_id")?
        .and_then(|v| v.extract::<String>().ok())
        .filter(|s| !s.is_empty());
    let done: bool = cfg
        .get_item("done")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);

    Ok(Some(ThreadedComment {
        id,
        cell_ref,
        person_id,
        created,
        parent_id,
        text,
        done,
    }))
}

/// Resolve a cfvo (`start_type` / `end_type` + value) into a
/// `ConditionalThreshold`. Falls back to `default_threshold` when the type
/// is missing or unrecognised — this preserves the original write-mode
/// behaviour (Min/Max) for callers that don't supply explicit thresholds.
///
/// Numeric thresholds (`num`, `percent`, `percentile`) coerce the value into
/// `f64`: ints, floats, and decimal strings all work; anything else falls
/// back to `0.0`. Formula thresholds always stringify the value.
fn build_threshold(
    cfvo_type: Option<&str>,
    value: Option<&Bound<'_, PyAny>>,
    default_threshold: ConditionalThreshold,
) -> PyResult<ConditionalThreshold> {
    let Some(t) = cfvo_type else {
        return Ok(default_threshold);
    };
    fn coerce_f64(v: Option<&Bound<'_, PyAny>>) -> f64 {
        let Some(v) = v else {
            return 0.0;
        };
        if let Ok(f) = v.extract::<f64>() {
            return f;
        }
        if let Ok(i) = v.extract::<i64>() {
            return i as f64;
        }
        if let Ok(s) = v.extract::<String>() {
            if let Ok(f) = s.parse::<f64>() {
                return f;
            }
        }
        0.0
    }
    fn coerce_string(v: Option<&Bound<'_, PyAny>>) -> String {
        let Some(v) = v else {
            return String::new();
        };
        if let Ok(s) = v.extract::<String>() {
            return s;
        }
        if let Ok(f) = v.extract::<f64>() {
            return f.to_string();
        }
        if let Ok(i) = v.extract::<i64>() {
            return i.to_string();
        }
        String::new()
    }
    let threshold = match t {
        "min" => ConditionalThreshold::Min,
        "max" => ConditionalThreshold::Max,
        "num" | "number" => ConditionalThreshold::Number(coerce_f64(value)),
        "percent" => ConditionalThreshold::Percent(coerce_f64(value)),
        "percentile" => ConditionalThreshold::Percentile(coerce_f64(value)),
        "formula" => ConditionalThreshold::Formula(coerce_string(value)),
        _ => default_threshold,
    };
    Ok(threshold)
}

/// Build a `ConditionalFormat` from a cfg dict, or `None` for no-op.
pub(crate) fn dict_to_conditional_format(
    cfg: &Bound<'_, PyDict>,
    styles: &mut StylesBuilder,
) -> PyResult<Option<ConditionalFormat>> {
    let range: Option<String> = cfg.get_item("range")?.and_then(|v| v.extract().ok());
    let rule_type: Option<String> = cfg.get_item("rule_type")?.and_then(|v| v.extract().ok());

    let (Some(range), Some(rule_type)) = (range, rule_type) else {
        return Ok(None);
    };

    let operator: Option<String> = cfg.get_item("operator")?.and_then(|v| v.extract().ok());
    let formula: Option<String> = cfg.get_item("formula")?.and_then(|v| v.extract().ok());
    let formula_a: Option<String> = cfg.get_item("formula_a")?.and_then(|v| v.extract().ok());
    let formula_b: Option<String> = cfg.get_item("formula_b")?.and_then(|v| v.extract().ok());
    let stop_if_true: bool = cfg
        .get_item("stop_if_true")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);

    let mut bg_color: Option<String> = None;
    if let Some(v) = cfg.get_item("format")? {
        if let Ok(fd) = v.cast::<PyDict>() {
            bg_color = fd.get_item("bg_color")?.and_then(|x| x.extract().ok());
        }
    }
    let dxf_id: Option<u32> = if let Some(ref hex) = bg_color {
        parse_hex_color(hex).map(|rgb| {
            let dxf = DxfRecord {
                font: None,
                fill: Some(FillSpec {
                    pattern_type: "solid".to_string(),
                    fg_color_rgb: Some(rgb.clone()),
                    bg_color_rgb: Some(rgb),
                    gradient: None,
                }),
                border: None,
            };
            styles.intern_dxf(&dxf)
        })
    } else {
        None
    };

    let kind = match rule_type.as_str() {
        "cellIs" | "cell_is" => {
            let op_str = operator.as_deref().unwrap_or("equal");
            let op = match op_str {
                "equal" | "==" => CellIsOperator::Equal,
                "notEqual" | "!=" => CellIsOperator::NotEqual,
                "greaterThan" | ">" => CellIsOperator::GreaterThan,
                "greaterThanOrEqual" | ">=" => CellIsOperator::GreaterThanOrEqual,
                "lessThan" | "<" => CellIsOperator::LessThan,
                "lessThanOrEqual" | "<=" => CellIsOperator::LessThanOrEqual,
                "between" => CellIsOperator::Between,
                "notBetween" => CellIsOperator::NotBetween,
                _ => CellIsOperator::Equal,
            };

            let formula_a = formula_a.or(formula);
            let fstr = formula_a.as_deref().unwrap_or("").trim_start_matches('=');
            let (formula_a, formula_b) = if let Some(formula_b) = formula_b {
                (
                    fstr.to_string(),
                    Some(formula_b.trim_start_matches('=').to_string()),
                )
            } else if matches!(op, CellIsOperator::Between | CellIsOperator::NotBetween) {
                if let Some(idx) = fstr.find(',') {
                    (
                        fstr[..idx].trim().to_string(),
                        Some(fstr[idx + 1..].trim().to_string()),
                    )
                } else {
                    (fstr.to_string(), None)
                }
            } else {
                (fstr.to_string(), None)
            };

            ConditionalKind::CellIs {
                operator: op,
                formula_a,
                formula_b,
            }
        }
        "expression" | "formula" => {
            let fstr = formula
                .as_deref()
                .unwrap_or("")
                .trim_start_matches('=')
                .to_string();
            ConditionalKind::Expression { formula: fstr }
        }
        "dataBar" | "data_bar" => {
            let color = cfg
                .get_item("color")?
                .and_then(|v| v.extract::<String>().ok())
                .and_then(|s| parse_hex_color(&s))
                .unwrap_or_else(|| "FF638EC6".to_string());
            let start_type: Option<String> =
                cfg.get_item("start_type")?.and_then(|v| v.extract().ok());
            let end_type: Option<String> = cfg.get_item("end_type")?.and_then(|v| v.extract().ok());
            let start_value = cfg.get_item("start_value")?;
            let end_value = cfg.get_item("end_value")?;
            let show_value: bool = cfg
                .get_item("show_value")?
                .and_then(|v| v.extract::<bool>().ok())
                .unwrap_or(true);
            let min_length: Option<u32> =
                cfg.get_item("min_length")?.and_then(|v| v.extract().ok());
            let max_length: Option<u32> =
                cfg.get_item("max_length")?.and_then(|v| v.extract().ok());
            ConditionalKind::DataBar {
                color_rgb: color,
                min: build_threshold(
                    start_type.as_deref(),
                    start_value.as_ref(),
                    ConditionalThreshold::Min,
                )?,
                max: build_threshold(
                    end_type.as_deref(),
                    end_value.as_ref(),
                    ConditionalThreshold::Max,
                )?,
                show_value,
                min_length,
                max_length,
            }
        }
        "colorScale" | "color_scale" => ConditionalKind::ColorScale {
            stops: build_color_scale_stops(cfg)?,
        },
        "iconSet" | "icon_set" => {
            let set_name: String = cfg
                .get_item("icon_style")?
                .and_then(|v| v.extract::<String>().ok())
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| "3TrafficLights1".to_string());
            let value_type: String = cfg
                .get_item("value_type")?
                .and_then(|v| v.extract::<String>().ok())
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| "percent".to_string());
            let raw_values: Vec<String> = if let Some(v) = cfg.get_item("values")? {
                if let Ok(nums) = v.extract::<Vec<f64>>() {
                    nums.into_iter()
                        .map(|n| {
                            if n == (n as i64) as f64 && n.abs() < 1e15 {
                                format!("{}", n as i64)
                            } else {
                                format!("{}", n)
                            }
                        })
                        .collect()
                } else if let Ok(strs) = v.extract::<Vec<String>>() {
                    strs
                } else {
                    Vec::new()
                }
            } else {
                Vec::new()
            };
            let thresholds: Vec<ConditionalThreshold> = raw_values
                .into_iter()
                .map(|val| match value_type.as_str() {
                    "percent" => val
                        .parse::<f64>()
                        .map(ConditionalThreshold::Percent)
                        .unwrap_or(ConditionalThreshold::Percent(0.0)),
                    "percentile" => val
                        .parse::<f64>()
                        .map(ConditionalThreshold::Percentile)
                        .unwrap_or(ConditionalThreshold::Percentile(0.0)),
                    "num" | "number" => val
                        .parse::<f64>()
                        .map(ConditionalThreshold::Number)
                        .unwrap_or(ConditionalThreshold::Number(0.0)),
                    "formula" => ConditionalThreshold::Formula(val),
                    _ => val
                        .parse::<f64>()
                        .map(ConditionalThreshold::Percent)
                        .unwrap_or(ConditionalThreshold::Percent(0.0)),
                })
                .collect();
            let show_value: bool = cfg
                .get_item("show_value")?
                .and_then(|v| v.extract::<bool>().ok())
                .unwrap_or(true);
            let percent: Option<bool> = cfg.get_item("percent")?.and_then(|v| v.extract().ok());
            let reverse: Option<bool> = cfg.get_item("reverse")?.and_then(|v| v.extract().ok());
            ConditionalKind::IconSet {
                set_name,
                thresholds,
                show_value,
                percent,
                reverse,
            }
        }
        "containsText" | "notContainsText" | "beginsWith" | "endsWith" | "duplicateValues"
        | "uniqueValues" | "top10" | "aboveAverage" | "containsBlanks" | "notContainsBlanks"
        | "containsErrors" | "notContainsErrors" | "timePeriod" => ConditionalKind::Generic {
            type_name: rule_type.clone(),
            attrs: generic_cf_attrs(cfg, &rule_type)?,
            formulas: generic_cf_formulas(cfg)?,
        },
        _ => ConditionalKind::Generic {
            type_name: rule_type.clone(),
            attrs: generic_cf_attrs(cfg, &rule_type)?,
            formulas: generic_cf_formulas(cfg)?,
        },
    };

    // G14: forward an explicit user-set priority; emitter prefers this
    // over the positional fallback so authored ordering survives round-trip.
    let priority: Option<u32> = cfg
        .get_item("priority")?
        .and_then(|v| v.extract::<u32>().ok());

    let rule = ConditionalRule {
        kind,
        dxf_id,
        stop_if_true,
        priority,
    };

    Ok(Some(ConditionalFormat {
        sqref: range,
        rules: vec![rule],
    }))
}

fn generic_cf_attrs(cfg: &Bound<'_, PyDict>, rule_type: &str) -> PyResult<Vec<(String, String)>> {
    let mut attrs: Vec<(String, String)> = Vec::new();
    if let Some(operator) = dict_get_string(cfg, "operator")? {
        attrs.push(("operator".to_string(), operator));
    }
    if let Some(text) = dict_get_string(cfg, "text")? {
        attrs.push(("text".to_string(), text));
    }
    if let Some(time_period) =
        dict_get_string(cfg, "time_period")?.or(dict_get_string(cfg, "timePeriod")?)
    {
        attrs.push(("timePeriod".to_string(), time_period));
    }
    if let Some(rank) = dict_get_string(cfg, "rank")? {
        attrs.push(("rank".to_string(), rank));
    }
    if let Some(std_dev) = dict_get_string(cfg, "std_dev")?.or(dict_get_string(cfg, "stdDev")?) {
        attrs.push(("stdDev".to_string(), std_dev));
    }
    if let Some(value) = extract_bool(cfg, "above_average")?.or(extract_bool(cfg, "aboveAverage")?)
    {
        attrs.push(("aboveAverage".to_string(), bool_attr(value)));
    } else if rule_type == "aboveAverage" {
        attrs.push(("aboveAverage".to_string(), "1".to_string()));
    }
    if let Some(value) = extract_bool(cfg, "equal_average")?.or(extract_bool(cfg, "equalAverage")?)
    {
        attrs.push(("equalAverage".to_string(), bool_attr(value)));
    }
    if let Some(value) = extract_bool(cfg, "percent")? {
        attrs.push(("percent".to_string(), bool_attr(value)));
    }
    if let Some(value) = extract_bool(cfg, "bottom")? {
        attrs.push(("bottom".to_string(), bool_attr(value)));
    }
    Ok(attrs)
}

fn generic_cf_formulas(cfg: &Bound<'_, PyDict>) -> PyResult<Vec<String>> {
    if let Some(v) = cfg.get_item("formulas")? {
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
        if let Some(value) = dict_get_string(cfg, key)? {
            formulas.push(value.trim_start_matches('=').to_string());
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

fn extract_bool(cfg: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<bool>> {
    Ok(cfg.get_item(key)?.and_then(|v| v.extract::<bool>().ok()))
}

/// Map a cfvo type string + optional value into a `ConditionalThreshold`.
///
/// Mirrors the openpyxl naming surface: ``min`` / ``max`` / ``num`` /
/// ``percent`` / ``percentile`` / ``formula``. Unknown types fall back to
/// ``Min``/``Max`` based on the position-implied ``fallback`` argument so
/// the Vec we return still has the right shape.
fn cfvo_to_threshold(
    cfvo_type: Option<&str>,
    value: Option<&str>,
    fallback: ConditionalThreshold,
) -> ConditionalThreshold {
    let Some(cfvo_type) = cfvo_type else {
        return fallback;
    };
    match cfvo_type {
        "min" => ConditionalThreshold::Min,
        "max" => ConditionalThreshold::Max,
        "num" | "number" => value
            .and_then(|s| s.parse::<f64>().ok())
            .map(ConditionalThreshold::Number)
            .unwrap_or(fallback),
        "percent" => value
            .and_then(|s| s.parse::<f64>().ok())
            .map(ConditionalThreshold::Percent)
            .unwrap_or(fallback),
        "percentile" => value
            .and_then(|s| s.parse::<f64>().ok())
            .map(ConditionalThreshold::Percentile)
            .unwrap_or(fallback),
        "formula" => value
            .map(|s| ConditionalThreshold::Formula(s.to_string()))
            .unwrap_or(fallback),
        _ => fallback,
    }
}

/// Pull a string out of the cfg dict, treating empty strings as absent.
fn dict_get_string(cfg: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
    let value: Option<String> = cfg.get_item(key)?.and_then(|v| {
        // Accept str directly or coerce numeric values via PyAny.
        if let Ok(s) = v.extract::<String>() {
            Some(s)
        } else if let Ok(f) = v.extract::<f64>() {
            // Drop trailing ``.0`` for whole numbers so ``50`` round-trips
            // instead of becoming ``50.0`` in the OOXML attribute.
            if f.fract() == 0.0 && f.abs() < 1e15 {
                Some(format!("{}", f as i64))
            } else {
                Some(format!("{}", f))
            }
        } else if let Ok(i) = v.extract::<i64>() {
            Some(format!("{}", i))
        } else {
            None
        }
    });
    Ok(value.filter(|s| !s.is_empty()))
}

/// Build the `Vec<ColorScaleStop>` for a colorScale rule from cfg keys.
///
/// Honours up to nine user-supplied keys (``start_type`` / ``start_value`` /
/// ``start_color`` and the ``mid_*`` / ``end_*`` siblings). A 2-stop scale is
/// emitted when no ``mid_*`` keys are present; otherwise a 3-stop. Missing
/// colors fall back to Excel's defaults (`F8696B` red, `FFEB84` yellow,
/// `63BE7B` green) so partial input still produces a valid gradient.
fn build_color_scale_stops(cfg: &Bound<'_, PyDict>) -> PyResult<Vec<ColorScaleStop>> {
    // Defaults match Excel's "Red - Yellow - Green" 3-color scale preset so
    // a bare ``ColorScaleRule()`` round-trips without surprising the user.
    const DEFAULT_START_COLOR: &str = "FFF8696B";
    const DEFAULT_MID_COLOR: &str = "FFFFEB84";
    const DEFAULT_END_COLOR: &str = "FF63BE7B";

    let start_type = dict_get_string(cfg, "start_type")?;
    let start_value = dict_get_string(cfg, "start_value")?;
    let start_color = dict_get_string(cfg, "start_color")?;
    let mid_type = dict_get_string(cfg, "mid_type")?;
    let mid_value = dict_get_string(cfg, "mid_value")?;
    let mid_color = dict_get_string(cfg, "mid_color")?;
    let end_type = dict_get_string(cfg, "end_type")?;
    let end_value = dict_get_string(cfg, "end_value")?;
    let end_color = dict_get_string(cfg, "end_color")?;

    // 3-stop iff any mid_* key is non-None; otherwise 2-stop. This mirrors
    // openpyxl's ColorScaleRule semantics where omitting mid_* gives a 2-stop.
    let has_mid = mid_type.is_some() || mid_value.is_some() || mid_color.is_some();

    // Backwards-compat default: a bare ``ColorScaleRule()`` with no kwargs
    // forwards no start/mid/end keys at all, so produce the hardcoded
    // 3-stop "Red - Yellow - Green" gradient that older callers relied on.
    let any_user_input = start_type.is_some()
        || start_value.is_some()
        || start_color.is_some()
        || has_mid
        || end_type.is_some()
        || end_value.is_some()
        || end_color.is_some();
    let has_mid = has_mid || !any_user_input;

    let normalize = |c: Option<String>, fallback: &str| -> String {
        c.as_deref()
            .and_then(parse_hex_color)
            .unwrap_or_else(|| fallback.to_string())
    };

    let mut stops: Vec<ColorScaleStop> = Vec::with_capacity(if has_mid { 3 } else { 2 });

    stops.push(ColorScaleStop {
        threshold: cfvo_to_threshold(
            start_type.as_deref(),
            start_value.as_deref(),
            ConditionalThreshold::Min,
        ),
        color_rgb: normalize(start_color, DEFAULT_START_COLOR),
    });

    if has_mid {
        stops.push(ColorScaleStop {
            threshold: cfvo_to_threshold(
                mid_type.as_deref(),
                mid_value.as_deref(),
                ConditionalThreshold::Percentile(50.0),
            ),
            color_rgb: normalize(mid_color, DEFAULT_MID_COLOR),
        });
    }

    stops.push(ColorScaleStop {
        threshold: cfvo_to_threshold(
            end_type.as_deref(),
            end_value.as_deref(),
            ConditionalThreshold::Max,
        ),
        color_rgb: normalize(end_color, DEFAULT_END_COLOR),
    });

    Ok(stops)
}

/// Build a `DataValidation` from a cfg dict, or `None` for no-op.
pub(crate) fn dict_to_data_validation(cfg: &Bound<'_, PyDict>) -> PyResult<Option<DataValidation>> {
    let range: Option<String> = cfg.get_item("range")?.and_then(|v| v.extract().ok());
    let validation_type: Option<String> = cfg
        .get_item("validation_type")?
        .and_then(|v| v.extract().ok());

    let (Some(range), Some(vtype_str)) = (range, validation_type) else {
        return Ok(None);
    };

    let validation_type = match vtype_str.as_str() {
        "whole" | "Whole" => ValidationType::Whole,
        "decimal" | "Decimal" => ValidationType::Decimal,
        "list" | "List" => ValidationType::List,
        "date" | "Date" => ValidationType::Date,
        "time" | "Time" => ValidationType::Time,
        "textLength" | "TextLength" | "text_length" => ValidationType::TextLength,
        "custom" | "Custom" => ValidationType::Custom,
        _ => ValidationType::Any,
    };

    let operator: Option<String> = cfg.get_item("operator")?.and_then(|v| v.extract().ok());
    let operator = match operator.as_deref().unwrap_or("between") {
        "between" | "Between" => ValidationOperator::Between,
        "notBetween" | "NotBetween" | "not_between" => ValidationOperator::NotBetween,
        "equal" | "Equal" | "==" => ValidationOperator::Equal,
        "notEqual" | "NotEqual" | "not_equal" | "!=" => ValidationOperator::NotEqual,
        "greaterThan" | "GreaterThan" | "greater_than" | ">" => ValidationOperator::GreaterThan,
        "lessThan" | "LessThan" | "less_than" | "<" => ValidationOperator::LessThan,
        "greaterThanOrEqual" | "GreaterThanOrEqual" | ">=" => {
            ValidationOperator::GreaterThanOrEqual
        }
        "lessThanOrEqual" | "LessThanOrEqual" | "<=" => ValidationOperator::LessThanOrEqual,
        _ => ValidationOperator::Between,
    };

    let formula_a: Option<String> = cfg.get_item("formula1")?.and_then(|v| v.extract().ok());
    let formula_b: Option<String> = cfg.get_item("formula2")?.and_then(|v| v.extract().ok());
    let allow_blank: bool = cfg
        .get_item("allow_blank")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(true);

    let error_title: Option<String> = cfg
        .get_item("error_title")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let error_message: Option<String> = cfg
        .get_item("error")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let input_title: Option<String> = cfg
        .get_item("prompt_title")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let input_message: Option<String> = cfg
        .get_item("prompt")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let show_dropdown: bool = cfg
        .get_item("show_dropdown")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);
    let show_input_message: bool = cfg
        .get_item("show_input_message")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);
    let show_error_message: bool = cfg
        .get_item("show_error_message")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(true);
    let error_style_raw: Option<String> = cfg
        .get_item("error_style")?
        .and_then(|v| v.extract::<String>().ok());
    let error_style = match error_style_raw.as_deref() {
        Some("warning" | "Warning") => ErrorStyle::Warning,
        Some("information" | "Information") => ErrorStyle::Information,
        _ => ErrorStyle::Stop,
    };

    Ok(Some(DataValidation {
        sqref: range,
        validation_type,
        operator,
        formula_a,
        formula_b,
        allow_blank,
        show_dropdown,
        show_error_message,
        error_style,
        error_title,
        error_message,
        show_input_message,
        input_title,
        input_message,
    }))
}

/// Build a `Table` from a cfg dict, or `None` for no-op.
pub(crate) fn dict_to_table(cfg: &Bound<'_, PyDict>) -> PyResult<Option<Table>> {
    let name: Option<String> = cfg.get_item("name")?.and_then(|v| v.extract().ok());
    let ref_range: Option<String> = cfg.get_item("ref")?.and_then(|v| v.extract().ok());

    let (Some(name), Some(ref_range)) = (name, ref_range) else {
        return Ok(None);
    };

    let style: Option<String> = cfg
        .get_item("style")?
        .and_then(|v| v.extract::<String>().ok())
        .and_then(|s| if s.is_empty() { None } else { Some(s) });
    let header_row: bool = cfg
        .get_item("header_row")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(true);
    let totals_row: bool = cfg
        .get_item("totals_row")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);
    let autofilter: bool = cfg
        .get_item("autofilter")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(true);

    let mut columns: Vec<TableColumn> = Vec::new();
    if let Some(v) = cfg.get_item("columns")? {
        if let Ok(list) = v.extract::<Vec<String>>() {
            for col_name in list {
                columns.push(TableColumn {
                    name: col_name,
                    totals_function: None,
                    totals_label: None,
                });
            }
        }
    }

    let table_style: Option<TableStyle> = style.map(|s| TableStyle {
        name: s,
        show_first_column: false,
        show_last_column: false,
        show_row_stripes: true,
        show_column_stripes: false,
    });

    Ok(Some(Table {
        name,
        display_name: None,
        range: ref_range,
        columns,
        header_row,
        totals_row,
        style: table_style,
        autofilter,
    }))
}
