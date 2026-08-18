use crate::{Cell, NamedRange};

use super::{error_code, le_f64, le_i32, le_u16, le_u32, utf16_string, XlsbSheet, XtiRef};

pub(super) fn parse_formula_from_cell_record(
    record_type: u16,
    payload: &[u8],
    context: Option<&FormulaContext<'_>>,
    base_row: u32,
    base_col: u32,
) -> Option<String> {
    let formula_payload = match record_type {
        0x0008 => {
            let len = payload.get(8..12).map(le_u32)? as usize;
            payload.get(14 + len * 2..)?
        }
        0x0009 => payload.get(18..)?,
        0x000a | 0x000b => payload.get(11..)?,
        _ => return None,
    };
    parse_cell_parsed_formula(formula_payload, context, base_row, base_col)
}

fn parse_cell_parsed_formula(
    formula_payload: &[u8],
    context: Option<&FormulaContext<'_>>,
    base_row: u32,
    base_col: u32,
) -> Option<String> {
    let rgce_len = formula_payload.get(0..4).map(le_u32)? as usize;
    let rgce = formula_payload.get(4..4 + rgce_len)?;
    parse_formula_rgce_with_base(rgce, context, Some((base_row, base_col)))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct SharedFormulaMasterBin {
    pub(super) master_row: u32,
    pub(super) master_col: u32,
    pub(super) formula: String,
}

pub(super) fn parse_shared_formula_record(
    payload: &[u8],
    context: Option<&FormulaContext<'_>>,
) -> Option<SharedFormulaMasterBin> {
    if payload.len() < 20 {
        return None;
    }
    let master_row = le_u32(&payload[0..4]);
    let master_col = le_u32(&payload[8..12]);
    let formula = parse_cell_parsed_formula(payload.get(16..)?, context, master_row, master_col)?;
    Some(SharedFormulaMasterBin {
        master_row,
        master_col,
        formula,
    })
}

pub(super) fn parse_shared_formula_anchor(record_type: u16, payload: &[u8]) -> Option<(u32, u32)> {
    let formula_payload = match record_type {
        0x0008 => {
            let len = payload.get(8..12).map(le_u32)? as usize;
            payload.get(14 + len * 2..)?
        }
        0x0009 => payload.get(18..)?,
        0x000a | 0x000b => payload.get(11..)?,
        _ => return None,
    };
    let rgce_len = formula_payload.get(0..4).map(le_u32)? as usize;
    let rgce = formula_payload.get(4..4 + rgce_len)?;
    if rgce.len() != 5 || rgce.first().copied()? != 0x01 {
        return None;
    }
    let extra_len_offset = 4 + rgce_len;
    let extra_len = formula_payload
        .get(extra_len_offset..extra_len_offset + 4)
        .map(le_u32)? as usize;
    let extra = formula_payload.get(extra_len_offset + 4..extra_len_offset + 4 + extra_len)?;
    let master_row = le_u32(rgce.get(1..5)?);
    let master_col = extra.get(0..4).map(le_u32)?;
    Some((master_row, master_col))
}

pub(super) fn apply_shared_formula_anchor(cell: &mut Cell, anchor: Option<(u32, u32)>) {
    let Some((row, col)) = anchor else {
        return;
    };
    cell.formula_kind = Some("shared".to_string());
    cell.formula_shared_index = Some(shared_formula_anchor_key(row, col));
}

pub(super) fn resolve_xlsb_shared_formulas(cells: &mut [Cell], masters: &[SharedFormulaMasterBin]) {
    for cell in cells {
        if cell.formula.is_some() || cell.formula_kind.as_deref() != Some("shared") {
            continue;
        }
        let Some(key) = cell.formula_shared_index.as_deref() else {
            continue;
        };
        let Some(master) = masters
            .iter()
            .find(|master| shared_formula_anchor_key(master.master_row, master.master_col) == key)
        else {
            continue;
        };
        let row_delta = cell.row as i32 - (master.master_row + 1) as i32;
        let col_delta = cell.col as i32 - (master.master_col + 1) as i32;
        cell.formula = Some(crate::translate_shared_formula(
            &master.formula,
            row_delta,
            col_delta,
        ));
    }
}

pub(super) fn shared_formula_anchor_key(row: u32, col: u32) -> String {
    format!("{row}:{col}")
}

pub(super) struct FormulaContext<'a> {
    pub(super) sheets: &'a [XlsbSheet],
    pub(super) extern_sheets: &'a [XtiRef],
    pub(super) named_ranges: &'a [NamedRange],
    pub(super) formula_names: &'a [String],
}

#[cfg(test)]
pub(super) fn parse_formula_rgce(rgce: &[u8]) -> Option<String> {
    parse_formula_rgce_with_context(rgce, None)
}

pub(super) fn parse_formula_rgce_with_context(
    rgce: &[u8],
    context: Option<&FormulaContext<'_>>,
) -> Option<String> {
    parse_formula_rgce_with_base(rgce, context, None)
}

fn parse_formula_rgce_with_base(
    mut rgce: &[u8],
    context: Option<&FormulaContext<'_>>,
    base: Option<(u32, u32)>,
) -> Option<String> {
    if rgce.is_empty() {
        return Some(String::new());
    }
    let mut formula = String::with_capacity(rgce.len());
    let mut stack: Vec<usize> = Vec::new();
    while !rgce.is_empty() {
        let ptg = rgce[0];
        rgce = &rgce[1..];
        match ptg {
            0x03..=0x11 => apply_binary_formula_op(ptg, &mut formula, &mut stack)?,
            0x12 => {
                let start = *stack.last()?;
                formula.insert(start, '+');
            }
            0x13 => {
                let start = *stack.last()?;
                formula.insert(start, '-');
            }
            0x14 => formula.push('%'),
            0x15 => {
                let start = *stack.last()?;
                formula.insert(start, '(');
                formula.push(')');
            }
            0x16 => stack.push(formula.len()),
            0x17 => {
                let len = rgce.get(0..2).map(le_u16)? as usize;
                let text = utf16_string(rgce.get(2..2 + len * 2)?);
                stack.push(formula.len());
                formula.push('"');
                formula.push_str(&text);
                formula.push('"');
                rgce = rgce.get(2 + len * 2..)?;
            }
            0x19 => {
                let eptg = *rgce.first()?;
                rgce = rgce.get(1..)?;
                match eptg {
                    0x01 | 0x02 | 0x08 | 0x20 | 0x21 | 0x40 | 0x41 | 0x80 => {
                        rgce = rgce.get(2..)?;
                    }
                    0x04 => rgce = rgce.get(10..)?,
                    0x10 => {
                        let start = *stack.last()?;
                        let args = formula.split_off(start);
                        formula.push_str("SUM(");
                        formula.push_str(&args);
                        formula.push(')');
                        rgce = rgce.get(2..)?;
                    }
                    _ => return None,
                }
            }
            0x1c => {
                let err = error_code(*rgce.first()?);
                stack.push(formula.len());
                formula.push_str(err);
                rgce = rgce.get(1..)?;
            }
            0x1d => {
                stack.push(formula.len());
                formula.push_str(if *rgce.first()? == 0 { "FALSE" } else { "TRUE" });
                rgce = rgce.get(1..)?;
            }
            0x1e => {
                let value = rgce.get(0..2).map(le_u16)?;
                stack.push(formula.len());
                formula.push_str(&value.to_string());
                rgce = rgce.get(2..)?;
            }
            0x1f => {
                let value = rgce.get(0..8).map(le_f64)?;
                stack.push(formula.len());
                formula.push_str(&format_formula_number(value));
                rgce = rgce.get(8..)?;
            }
            0x21 | 0x41 | 0x61 => {
                let iftab = rgce.get(0..2).map(le_u16)? as usize;
                let argc = fixed_formula_arg_count(iftab)?;
                rgce = rgce.get(2..)?;
                apply_formula_function(iftab, argc, &mut formula, &mut stack)?;
            }
            0x22 | 0x42 | 0x62 => {
                let argc = *rgce.first()? as usize;
                let iftab = rgce.get(1..3).map(le_u16)? as usize;
                rgce = rgce.get(3..)?;
                apply_formula_function(iftab, argc, &mut formula, &mut stack)?;
            }
            0x24 | 0x44 | 0x64 => {
                let reference = parse_formula_ref(rgce.get(0..6)?)?;
                stack.push(formula.len());
                formula.push_str(&reference);
                rgce = rgce.get(6..)?;
            }
            0x2c | 0x4c | 0x6c => {
                let reference = parse_formula_ref_relative(rgce.get(0..6)?, base?)?;
                stack.push(formula.len());
                formula.push_str(&reference);
                rgce = rgce.get(6..)?;
            }
            0x25 | 0x45 | 0x65 => {
                let area = parse_formula_area(rgce.get(0..12)?)?;
                stack.push(formula.len());
                formula.push_str(&area);
                rgce = rgce.get(12..)?;
            }
            0x2d | 0x4d | 0x6d => {
                let area = parse_formula_area_relative(rgce.get(0..12)?, base?)?;
                stack.push(formula.len());
                formula.push_str(&area);
                rgce = rgce.get(12..)?;
            }
            0x23 | 0x43 | 0x63 => {
                let name = parse_formula_name(rgce.get(0..4)?, context?)?;
                stack.push(formula.len());
                formula.push_str(&name);
                rgce = rgce.get(4..)?;
            }
            0x3a | 0x5a | 0x7a => {
                let reference = parse_formula_ref3d(rgce.get(0..8)?, context?)?;
                stack.push(formula.len());
                formula.push_str(&reference);
                rgce = rgce.get(8..)?;
            }
            0x3b | 0x5b | 0x7b => {
                let area = parse_formula_area3d(rgce.get(0..14)?, context?)?;
                stack.push(formula.len());
                formula.push_str(&area);
                rgce = rgce.get(14..)?;
            }
            0x2a | 0x4a | 0x6a => {
                stack.push(formula.len());
                formula.push_str("#REF!");
                rgce = rgce.get(6..)?;
            }
            0x2b | 0x4b | 0x6b => {
                stack.push(formula.len());
                formula.push_str("#REF!");
                rgce = rgce.get(12..)?;
            }
            _ => return None,
        }
    }
    (stack.len() == 1).then_some(formula)
}

fn apply_binary_formula_op(ptg: u8, formula: &mut String, stack: &mut Vec<usize>) -> Option<()> {
    let right_start = stack.pop()?;
    let right = formula.split_off(right_start);
    let op = match ptg {
        0x03 => "+",
        0x04 => "-",
        0x05 => "*",
        0x06 => "/",
        0x07 => "^",
        0x08 => "&",
        0x09 => "<",
        0x0a => "<=",
        0x0b => "=",
        0x0c => ">",
        0x0d => ">=",
        0x0e => "<>",
        0x0f => " ",
        0x10 => ",",
        0x11 => ":",
        _ => return None,
    };
    formula.push_str(op);
    formula.push_str(&right);
    Some(())
}

fn apply_formula_function(
    iftab: usize,
    argc: usize,
    formula: &mut String,
    stack: &mut Vec<usize>,
) -> Option<()> {
    let name = formula_function_name(iftab)?;
    if stack.len() < argc {
        return None;
    }
    if argc == 0 {
        stack.push(formula.len());
        formula.push_str(name);
        formula.push_str("()");
        return Some(());
    }
    let args_start = stack.len() - argc;
    let mut arg_offsets = stack.split_off(args_start);
    let start = *arg_offsets.first()?;
    for offset in &mut arg_offsets {
        *offset -= start;
    }
    let args = formula.split_off(start);
    stack.push(formula.len());
    arg_offsets.push(args.len());
    formula.push_str(name);
    formula.push('(');
    for window in arg_offsets.windows(2) {
        formula.push_str(&args[window[0]..window[1]]);
        formula.push(',');
    }
    formula.pop();
    formula.push(')');
    Some(())
}

fn fixed_formula_arg_count(iftab: usize) -> Option<usize> {
    match iftab {
        1 => Some(3), // IF
        2 | 3 | 8 | 9 | 15..=18 | 20..=26 | 32 | 33 | 38 => Some(1),
        10 | 19 | 34 | 35 => Some(0),
        13 | 27 | 30 | 39 | 48 => Some(2),
        14 | 31 | 40..=45 => Some(3),
        29 | 49..=52 => Some(4),
        _ => None,
    }
}

fn formula_function_name(iftab: usize) -> Option<&'static str> {
    match iftab {
        0 => Some("COUNT"),
        1 => Some("IF"),
        2 => Some("ISNA"),
        3 => Some("ISERROR"),
        4 => Some("SUM"),
        5 => Some("AVERAGE"),
        6 => Some("MIN"),
        7 => Some("MAX"),
        8 => Some("ROW"),
        9 => Some("COLUMN"),
        10 => Some("NA"),
        15 => Some("SIN"),
        16 => Some("COS"),
        17 => Some("TAN"),
        19 => Some("PI"),
        20 => Some("SQRT"),
        21 => Some("EXP"),
        22 => Some("LN"),
        23 => Some("LOG10"),
        24 => Some("ABS"),
        25 => Some("INT"),
        26 => Some("SIGN"),
        27 => Some("ROUND"),
        30 => Some("REPT"),
        31 => Some("MID"),
        32 => Some("LEN"),
        33 => Some("VALUE"),
        34 => Some("TRUE"),
        35 => Some("FALSE"),
        36 => Some("AND"),
        37 => Some("OR"),
        38 => Some("NOT"),
        39 => Some("MOD"),
        48 => Some("TEXT"),
        61 => Some("MIRR"),
        63 => Some("RAND"),
        65 => Some("DATE"),
        66 => Some("TIME"),
        67 => Some("DAY"),
        68 => Some("MONTH"),
        69 => Some("YEAR"),
        70 => Some("WEEKDAY"),
        97 => Some("ATAN2"),
        98 => Some("ASIN"),
        99 => Some("ACOS"),
        100 => Some("CHOOSE"),
        101 => Some("HLOOKUP"),
        102 => Some("VLOOKUP"),
        109 => Some("LOG"),
        111 => Some("CHAR"),
        112 => Some("LOWER"),
        113 => Some("UPPER"),
        115 => Some("LEFT"),
        116 => Some("RIGHT"),
        117 => Some("EXACT"),
        118 => Some("TRIM"),
        119 => Some("REPLACE"),
        120 => Some("SUBSTITUTE"),
        124 => Some("FIND"),
        125 => Some("CELL"),
        148 => Some("INDIRECT"),
        162 => Some("CLEAN"),
        163 => Some("MDETERM"),
        164 => Some("MINVERSE"),
        165 => Some("MMULT"),
        167 => Some("IPMT"),
        168 => Some("PPMT"),
        169 => Some("COUNTA"),
        183 => Some("PRODUCT"),
        184 => Some("FACT"),
        193 => Some("DPRODUCT"),
        194 => Some("ISNONTEXT"),
        195 => Some("STDEVP"),
        196 => Some("VARP"),
        197 => Some("DSTDEVP"),
        198 => Some("DVARP"),
        212 => Some("ROUNDUP"),
        213 => Some("ROUNDDOWN"),
        216 => Some("RANK"),
        219 => Some("ADDRESS"),
        220 => Some("DAYS360"),
        221 => Some("TODAY"),
        227 => Some("MEDIAN"),
        228 => Some("SUMPRODUCT"),
        229 => Some("SINH"),
        230 => Some("COSH"),
        231 => Some("TANH"),
        244 => Some("INFO"),
        247 => Some("DB"),
        255 => Some("GETPIVOTDATA"),
        269 => Some("AVEDEV"),
        270 => Some("BETADIST"),
        271 => Some("GAMMALN"),
        276 => Some("COMBIN"),
        279 => Some("CEILING"),
        280 => Some("FLOOR"),
        285 => Some("EVEN"),
        286 => Some("ODD"),
        300 => Some("CEILING"),
        303 => Some("SUMIFS"),
        304 => Some("COUNTIFS"),
        345 => Some("SUMIF"),
        346 => Some("COUNTIF"),
        347 => Some("AVERAGEIF"),
        350 => Some("IFERROR"),
        359 => Some("HYPERLINK"),
        _ => None,
    }
}

fn parse_formula_ref(payload: &[u8]) -> Option<String> {
    let row = le_u32(&payload[0..4]) + 1;
    let col_flags = le_u16(&payload[4..6]);
    let col = (col_flags & 0x3fff) as u32 + 1;
    Some(format_cell_reference(
        row,
        col,
        col_flags & 0x8000 == 0,
        col_flags & 0x4000 == 0,
    ))
}

fn parse_formula_area(payload: &[u8]) -> Option<String> {
    let first_row = le_u32(&payload[0..4]) + 1;
    let last_row = le_u32(&payload[4..8]) + 1;
    let first_col_flags = le_u16(&payload[8..10]);
    let last_col_flags = le_u16(&payload[10..12]);
    let first_col = (first_col_flags & 0x3fff) as u32 + 1;
    let last_col = (last_col_flags & 0x3fff) as u32 + 1;
    Some(format!(
        "{}:{}",
        format_cell_reference(
            first_row,
            first_col,
            first_col_flags & 0x8000 == 0,
            first_col_flags & 0x4000 == 0,
        ),
        format_cell_reference(
            last_row,
            last_col,
            last_col_flags & 0x8000 == 0,
            last_col_flags & 0x4000 == 0,
        )
    ))
}

fn parse_formula_ref_relative(payload: &[u8], base: (u32, u32)) -> Option<String> {
    let row_delta = le_i32(payload.get(0..4)?);
    let col_flags = le_u16(payload.get(4..6)?);
    let row = relative_row_or_absolute(base.0, row_delta, col_flags)? + 1;
    let col = relative_col_or_absolute(base.1, col_flags)? + 1;
    Some(format_cell_reference(
        row,
        col,
        col_flags & 0x8000 == 0,
        col_flags & 0x4000 == 0,
    ))
}

fn parse_formula_area_relative(payload: &[u8], base: (u32, u32)) -> Option<String> {
    let first_col_flags = le_u16(payload.get(8..10)?);
    let last_col_flags = le_u16(payload.get(10..12)?);
    let first_row =
        relative_row_or_absolute(base.0, le_i32(payload.get(0..4)?), first_col_flags)? + 1;
    let last_row =
        relative_row_or_absolute(base.0, le_i32(payload.get(4..8)?), last_col_flags)? + 1;
    let first_col = relative_col_or_absolute(base.1, first_col_flags)? + 1;
    let last_col = relative_col_or_absolute(base.1, last_col_flags)? + 1;
    Some(format!(
        "{}:{}",
        format_cell_reference(
            first_row,
            first_col,
            first_col_flags & 0x8000 == 0,
            first_col_flags & 0x4000 == 0,
        ),
        format_cell_reference(
            last_row,
            last_col,
            last_col_flags & 0x8000 == 0,
            last_col_flags & 0x4000 == 0,
        )
    ))
}

fn relative_row_or_absolute(base: u32, row: i32, col_flags: u16) -> Option<u32> {
    if col_flags & 0x8000 == 0 {
        return (row >= 0).then_some(row as u32);
    }
    relative_axis(base, row)
}

fn relative_col_or_absolute(base: u32, col_flags: u16) -> Option<u32> {
    let col = (col_flags & 0x3fff) as i32;
    if col_flags & 0x4000 == 0 {
        return Some(col as u32);
    }
    let delta = if col & 0x2000 != 0 { col - 0x4000 } else { col };
    relative_axis(base, delta)
}

fn relative_axis(base: u32, delta: i32) -> Option<u32> {
    let value = base as i64 + delta as i64;
    (value >= 0).then_some(value as u32)
}

fn parse_formula_name(payload: &[u8], context: &FormulaContext<'_>) -> Option<String> {
    let name_index = le_u32(payload);
    if name_index == 0 {
        return None;
    }
    context
        .formula_names
        .get(name_index as usize - 1)
        .cloned()
        .or_else(|| {
            context
                .named_ranges
                .get(name_index as usize - 1)
                .map(|range| range.name.clone())
        })
}

fn parse_formula_ref3d(payload: &[u8], context: &FormulaContext<'_>) -> Option<String> {
    let sheet = formula_sheet_prefix(le_u16(&payload[0..2]) as usize, context)?;
    let reference = parse_formula_ref(payload.get(2..8)?)?;
    Some(format!("{sheet}!{reference}"))
}

fn parse_formula_area3d(payload: &[u8], context: &FormulaContext<'_>) -> Option<String> {
    let sheet = formula_sheet_prefix(le_u16(&payload[0..2]) as usize, context)?;
    let area = parse_formula_area(payload.get(2..14)?)?;
    Some(format!("{sheet}!{area}"))
}

fn formula_sheet_prefix(ixti: usize, context: &FormulaContext<'_>) -> Option<String> {
    let xti = context.extern_sheets.get(ixti)?;
    if xti.first_sheet < 0 || xti.last_sheet < 0 {
        return None;
    }
    let first = context.sheets.get(xti.first_sheet as usize)?;
    let last = context.sheets.get(xti.last_sheet as usize)?;
    if xti.first_sheet == xti.last_sheet {
        Some(quote_sheet_name(&first.name))
    } else {
        Some(format!(
            "{}:{}",
            quote_sheet_name(&first.name),
            quote_sheet_name(&last.name)
        ))
    }
}

fn quote_sheet_name(name: &str) -> String {
    if name
        .chars()
        .all(|ch| ch.is_ascii_alphanumeric() || ch == '_')
    {
        return name.to_string();
    }
    let escaped = name.replace('\'', "''");
    format!("'{escaped}'")
}

fn format_cell_reference(row: u32, col: u32, row_abs: bool, col_abs: bool) -> String {
    let mut out = String::new();
    if col_abs {
        out.push('$');
    }
    push_column_label(col, &mut out);
    if row_abs {
        out.push('$');
    }
    out.push_str(&row.to_string());
    out
}

fn push_column_label(mut col: u32, out: &mut String) {
    let mut buf = Vec::new();
    while col > 0 {
        col -= 1;
        buf.push((b'A' + (col % 26) as u8) as char);
        col /= 26;
    }
    for ch in buf.iter().rev() {
        out.push(*ch);
    }
}

fn format_formula_number(value: f64) -> String {
    if value.fract() == 0.0 && value.abs() < (i64::MAX as f64) {
        (value as i64).to_string()
    } else {
        value.to_string()
    }
}
