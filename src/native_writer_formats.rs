//! Format and border payload parsing for the native writer backend.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict};
use wolfxl_writer::model::{
    AlignmentSpec, BorderSideSpec, BorderSpec, FillSpec, FontSpec, FormatSpec, GradientFillSpec,
    GradientStopSpec, ProtectionSpec, Worksheet, WriteCell, WriteCellValue,
};
use wolfxl_writer::Workbook;

/// Normalize a Python-side color string to OOXML's 8-char ARGB form.
pub(crate) fn parse_hex_color(input: &str) -> Option<String> {
    let s = input.strip_prefix('#').unwrap_or(input);
    let upper: String = s.chars().map(|c| c.to_ascii_uppercase()).collect();

    if !upper.chars().all(|c| c.is_ascii_hexdigit()) {
        return None;
    }

    match upper.len() {
        3 => {
            let mut expanded = String::with_capacity(8);
            expanded.push_str("FF");
            for ch in upper.chars() {
                expanded.push(ch);
                expanded.push(ch);
            }
            Some(expanded)
        }
        6 => Some(format!("FF{upper}")),
        8 => Some(upper),
        _ => None,
    }
}

/// Format a finite f64 as a canonical decimal string. We can't store f64s
/// in `GradientFillSpec` directly because the writer's interner needs `Hash
/// + Eq`; storing a canonical string round-trips through dedup correctly.
fn format_grad_number(value: f64) -> String {
    if !value.is_finite() {
        return String::from("0");
    }
    // Trim trailing zeroes so e.g. 0.5 stays "0.5", 90.0 becomes "90".
    let s = format!("{value}");
    if let Some(stripped) = s.strip_suffix(".0") {
        stripped.to_string()
    } else {
        s
    }
}

fn parse_gradient_dict(gd: &Bound<'_, PyDict>) -> PyResult<Option<GradientFillSpec>> {
    let gradient_type: String = gd
        .get_item("type")?
        .and_then(|v| v.extract().ok())
        .unwrap_or_else(|| "linear".to_string());

    let degree = gd
        .get_item("degree")?
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);
    let left = gd
        .get_item("left")?
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);
    let right = gd
        .get_item("right")?
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);
    let top = gd
        .get_item("top")?
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);
    let bottom = gd
        .get_item("bottom")?
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);

    // Stops: accept either "stops" (preferred wolfxl shape) or "stop"
    // (openpyxl-compatible alias). Each entry is a dict {position, color}.
    let stops_any = gd.get_item("stops")?.or(gd.get_item("stop")?);
    let mut stops: Vec<GradientStopSpec> = Vec::new();
    if let Some(seq) = stops_any {
        for item in seq.try_iter()? {
            let item = item?;
            if let Ok(d) = item.cast::<PyDict>() {
                let position = d
                    .get_item("position")?
                    .and_then(|v| v.extract::<f64>().ok())
                    .unwrap_or(0.0);
                let color: Option<String> = d
                    .get_item("color")?
                    .and_then(|v| v.extract::<String>().ok())
                    .and_then(|s| parse_hex_color(&s));
                stops.push(GradientStopSpec {
                    position: format_grad_number(position),
                    color_rgb: color,
                });
            }
        }
    }

    if stops.is_empty() {
        return Ok(None);
    }

    Ok(Some(GradientFillSpec {
        gradient_type,
        degree: format_grad_number(degree),
        left: format_grad_number(left),
        right: format_grad_number(right),
        top: format_grad_number(top),
        bottom: format_grad_number(bottom),
        stops,
    }))
}

fn dict_to_format_spec(dict: &Bound<'_, PyDict>) -> PyResult<FormatSpec> {
    let mut spec = FormatSpec::default();

    let mut font = FontSpec::default();
    let mut font_touched = false;

    if let Some(v) = dict.get_item("bold")? {
        if let Ok(b) = v.extract::<bool>() {
            font.bold = b;
            font_touched |= b;
        }
    }
    if let Some(v) = dict.get_item("italic")? {
        if let Ok(b) = v.extract::<bool>() {
            font.italic = b;
            font_touched |= b;
        }
    }
    if let Some(v) = dict.get_item("underline")? {
        if let Ok(s) = v.extract::<String>() {
            if !s.is_empty() {
                font.underline = Some(s);
                font_touched = true;
            }
        } else if let Ok(b) = v.extract::<bool>() {
            font.underline = if b { Some("single".to_string()) } else { None };
            font_touched |= b;
        }
    }
    if let Some(v) = dict.get_item("strikethrough")? {
        if let Ok(b) = v.extract::<bool>() {
            font.strikethrough = b;
            font_touched |= b;
        }
    }
    if let Some(v) = dict.get_item("font_name")? {
        if let Ok(s) = v.extract::<String>() {
            if !s.is_empty() {
                font.name = Some(s);
                font_touched = true;
            }
        }
    }
    if let Some(v) = dict.get_item("font_size")? {
        if let Ok(f) = v.extract::<f64>() {
            if f.is_finite() && f >= 0.0 {
                font.size = Some(f.round() as u32);
                font_touched = true;
            }
        }
    }
    if let Some(v) = dict.get_item("font_color")? {
        if let Ok(s) = v.extract::<String>() {
            if let Some(rgb) = parse_hex_color(&s) {
                font.color_rgb = Some(rgb);
                font_touched = true;
            }
        }
    }
    if font_touched {
        spec.font = Some(font);
    }

    if let Some(v) = dict.get_item("bg_color")? {
        if let Ok(s) = v.extract::<String>() {
            if let Some(rgb) = parse_hex_color(&s) {
                spec.fill = Some(FillSpec {
                    pattern_type: "solid".to_string(),
                    fg_color_rgb: Some(rgb.clone()),
                    bg_color_rgb: Some(rgb),
                    gradient: None,
                });
            }
        }
    }

    // Gradient fill takes precedence over `bg_color` when both present;
    // OOXML only allows one of <patternFill>/<gradientFill> per <fill>.
    if let Some(v) = dict.get_item("gradient")? {
        if let Ok(gd) = v.cast::<PyDict>() {
            if let Some(grad) = parse_gradient_dict(&gd)? {
                spec.fill = Some(FillSpec {
                    pattern_type: String::new(),
                    fg_color_rgb: None,
                    bg_color_rgb: None,
                    gradient: Some(grad),
                });
            }
        }
    }

    if let Some(v) = dict.get_item("number_format")? {
        if let Ok(s) = v.extract::<String>() {
            if !s.is_empty() {
                spec.number_format = Some(s);
            }
        }
    }

    let mut align = AlignmentSpec::default();
    let mut align_touched = false;
    if let Some(v) = dict.get_item("h_align")? {
        if let Ok(s) = v.extract::<String>() {
            if !s.is_empty() {
                align.horizontal = Some(s);
                align_touched = true;
            }
        }
    }
    if let Some(v) = dict.get_item("v_align")? {
        if let Ok(s) = v.extract::<String>() {
            if !s.is_empty() {
                align.vertical = Some(s);
                align_touched = true;
            }
        }
    }
    if let Some(v) = dict.get_item("wrap")? {
        if let Ok(b) = v.extract::<bool>() {
            align.wrap_text = b;
            align_touched |= b;
        }
    }
    if let Some(v) = dict.get_item("rotation")? {
        if let Ok(i) = v.extract::<i32>() {
            if i >= 0 {
                align.text_rotation = i as u32;
                align_touched = true;
            }
        }
    }
    if let Some(v) = dict.get_item("indent")? {
        if let Ok(i) = v.extract::<i32>() {
            if i >= 0 {
                align.indent = i as u32;
                align_touched = true;
            }
        }
    }
    if align_touched {
        spec.alignment = Some(align);
    }

    let mut prot = ProtectionSpec::default();
    let mut prot_touched = false;
    if let Some(v) = dict.get_item("locked")? {
        if let Ok(b) = v.extract::<bool>() {
            prot.locked = b;
            prot_touched = true;
        }
    }
    if let Some(v) = dict.get_item("hidden")? {
        if let Ok(b) = v.extract::<bool>() {
            prot.hidden = b;
            prot_touched = true;
        }
    }
    if prot_touched {
        spec.protection = Some(prot);
    }

    // Borders may live on the same dict as font / fill / alignment when
    // the Python flush layer merges format + border before dispatch
    // (RFC-064 follow-up: prevents apply_cell_format and apply_cell_border
    // from each minting independent style_ids that overwrite each other).
    let border = dict_to_border_spec(dict)?;
    if border != BorderSpec::default() {
        spec.border = Some(border);
    }

    Ok(spec)
}

fn edge_to_side_spec(dict: &Bound<'_, PyDict>, key: &str) -> PyResult<(BorderSideSpec, bool)> {
    let mut side = BorderSideSpec::default();
    let mut touched = false;

    let Some(sub) = dict.get_item(key)? else {
        return Ok((side, false));
    };
    let Ok(d) = sub.cast::<PyDict>() else {
        return Ok((side, false));
    };

    if let Some(v) = d.get_item("style")? {
        if let Ok(s) = v.extract::<String>() {
            if !s.is_empty() {
                side.style = Some(s);
                touched = true;
            }
        }
    }
    if let Some(v) = d.get_item("color")? {
        if let Ok(s) = v.extract::<String>() {
            if let Some(rgb) = parse_hex_color(&s) {
                side.color_rgb = Some(rgb);
                touched = true;
            }
        }
    }
    Ok((side, touched))
}

fn dict_to_border_spec(dict: &Bound<'_, PyDict>) -> PyResult<BorderSpec> {
    let mut border = BorderSpec::default();

    let (top, t1) = edge_to_side_spec(dict, "top")?;
    let (bottom, t2) = edge_to_side_spec(dict, "bottom")?;
    let (left, t3) = edge_to_side_spec(dict, "left")?;
    let (right, t4) = edge_to_side_spec(dict, "right")?;
    let (diag_up, t5) = edge_to_side_spec(dict, "diagonal_up")?;
    let (diag_down, t6) = edge_to_side_spec(dict, "diagonal_down")?;

    if t1 {
        border.top = top;
    }
    if t2 {
        border.bottom = bottom;
    }
    if t3 {
        border.left = left;
    }
    if t4 {
        border.right = right;
    }
    if t5 || t6 {
        if t6 {
            border.diagonal = diag_down;
        } else {
            border.diagonal = diag_up;
        }
        border.diagonal_up = t5;
        border.diagonal_down = t6;
    }

    Ok(border)
}

pub(crate) fn intern_format_from_dict(
    wb: &mut Workbook,
    dict: &Bound<'_, PyDict>,
) -> PyResult<u32> {
    let spec = dict_to_format_spec(dict)?;
    let xf_id = match dict.get_item("_named_style")? {
        Some(v) => v
            .extract::<String>()
            .ok()
            .and_then(|name| wb.styles.xf_id_for_named_style(&name))
            .unwrap_or(0),
        None => 0,
    };
    Ok(wb.styles.intern_format_with_xf_id(&spec, xf_id))
}

pub(crate) fn intern_border_only(wb: &mut Workbook, dict: &Bound<'_, PyDict>) -> PyResult<u32> {
    let border = dict_to_border_spec(dict)?;
    let spec = FormatSpec {
        border: Some(border),
        ..Default::default()
    };
    Ok(wb.styles.intern_format(&spec))
}

pub(crate) fn apply_cell_format(
    wb: &mut Workbook,
    sheet: &str,
    row: u32,
    col: u32,
    dict: &Bound<'_, PyDict>,
) -> PyResult<()> {
    let style_id = intern_format_from_dict(wb, dict)?;
    let ws = require_sheet(wb, sheet)?;
    set_cell_style_id(ws, row, col, style_id);
    Ok(())
}

pub(crate) fn apply_cell_border(
    wb: &mut Workbook,
    sheet: &str,
    row: u32,
    col: u32,
    dict: &Bound<'_, PyDict>,
) -> PyResult<()> {
    let style_id = intern_border_only(wb, dict)?;
    let ws = require_sheet(wb, sheet)?;
    set_cell_style_id(ws, row, col, style_id);
    Ok(())
}

pub(crate) fn apply_format_grid(
    wb: &mut Workbook,
    sheet: &str,
    base_row: u32,
    base_col: u32,
    grid: &Bound<'_, PyAny>,
) -> PyResult<()> {
    let to_apply = collect_style_grid(wb, base_row, base_col, grid, intern_format_from_dict)?;
    let ws = require_sheet(wb, sheet)?;
    for (row, col, style_id) in to_apply {
        set_cell_style_id(ws, row, col, style_id);
    }
    Ok(())
}

pub(crate) fn apply_style_id_grid(
    wb: &mut Workbook,
    sheet: &str,
    base_row: u32,
    base_col: u32,
    grid: &Bound<'_, PyAny>,
) -> PyResult<()> {
    let rows: Vec<Bound<'_, PyAny>> = grid.extract()?;
    let ws = require_sheet(wb, sheet)?;

    for (ri, row_obj) in rows.iter().enumerate() {
        let cols: Vec<Bound<'_, PyAny>> = row_obj.extract()?;
        for (ci, val) in cols.iter().enumerate() {
            if val.is_none() {
                continue;
            }
            let style_id = val.extract::<u32>()?;
            let row = base_row + ri as u32;
            let col = base_col + ci as u32;
            set_cell_style_id(ws, row, col, style_id);
        }
    }

    Ok(())
}

pub(crate) fn apply_border_grid(
    wb: &mut Workbook,
    sheet: &str,
    base_row: u32,
    base_col: u32,
    grid: &Bound<'_, PyAny>,
) -> PyResult<()> {
    let to_apply = collect_style_grid(wb, base_row, base_col, grid, intern_border_only)?;
    let ws = require_sheet(wb, sheet)?;
    for (row, col, style_id) in to_apply {
        set_cell_style_id(ws, row, col, style_id);
    }
    Ok(())
}

fn collect_style_grid(
    wb: &mut Workbook,
    base_row: u32,
    base_col: u32,
    grid: &Bound<'_, PyAny>,
    intern: fn(&mut Workbook, &Bound<'_, PyDict>) -> PyResult<u32>,
) -> PyResult<Vec<(u32, u32, u32)>> {
    let rows: Vec<Bound<'_, PyAny>> = grid.extract()?;
    let mut to_apply: Vec<(u32, u32, u32)> = Vec::new();

    for (ri, row_obj) in rows.iter().enumerate() {
        let cols: Vec<Bound<'_, PyAny>> = row_obj.extract()?;
        for (ci, val) in cols.iter().enumerate() {
            if val.is_none() {
                continue;
            }
            let dict = val
                .cast::<PyDict>()
                .map_err(|_| PyValueError::new_err("style grid element must be dict or None"))?;
            if dict.is_empty() {
                continue;
            }
            let row = base_row + ri as u32;
            let col = base_col + ci as u32;
            let style_id = intern(wb, dict)?;
            to_apply.push((row, col, style_id));
        }
    }

    Ok(to_apply)
}

fn require_sheet<'wb>(wb: &'wb mut Workbook, name: &str) -> PyResult<&'wb mut Worksheet> {
    wb.sheet_mut_by_name(name)
        .ok_or_else(|| PyValueError::new_err(format!("Unknown sheet: {name}")))
}

fn set_cell_style_id(ws: &mut Worksheet, row: u32, col: u32, style_id: u32) {
    let cell = ws
        .rows
        .entry(row)
        .or_default()
        .cells
        .entry(col)
        .or_insert_with(|| WriteCell {
            value: WriteCellValue::Blank,
            style_id: None,
        });
    cell.style_id = Some(style_id);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_hex_color_normalizes_rgb_and_argb() {
        assert_eq!(parse_hex_color("#abc").as_deref(), Some("FFAABBCC"));
        assert_eq!(parse_hex_color("336699").as_deref(), Some("FF336699"));
        assert_eq!(parse_hex_color("#80336699").as_deref(), Some("80336699"));
    }

    #[test]
    fn parse_hex_color_rejects_invalid_shapes() {
        assert_eq!(parse_hex_color(""), None);
        assert_eq!(parse_hex_color("12345"), None);
        assert_eq!(parse_hex_color("zzzzzz"), None);
    }
}
