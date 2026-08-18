//! Filter evaluation engine. RFC-056 §4.
//!
//! Inputs: a row matrix (one entry per row, each row a Vec of cell
//! values within `auto_filter.ref`'s columns), the typed
//! `FilterColumn`s, and an optional `SortState`.
//!
//! Outputs: indices of rows to hide + an optional permutation of row
//! indices encoding the sort order. Per RFC-056 §8 / Pod 1B
//! constraint: the patcher applies the hide list directly via
//! `<row hidden="1">` markers; the sort permutation is **XML-only**
//! in v2.0 (returned to the caller for inspection) — physical row
//! reordering is deferred to v2.1.

use crate::model::{
    AutoFilter, ColorFilter, CustomFilter, CustomFilterOp, CustomFilters, DynamicFilter,
    DynamicFilterType, FilterColumn, FilterKind, IconFilter, NumberFilter, SortState, StringFilter,
    Top10,
};

/// Cell value as seen by the evaluator. The patcher reads cell text/
/// numeric/bool from the existing read-back path and converts to one
/// of these variants before calling `evaluate`. Empty cells use
/// `Cell::Empty`.
#[derive(Debug, Clone, PartialEq)]
pub enum Cell {
    Empty,
    Number(f64),
    String(String),
    Bool(bool),
    /// Date as serial number (Excel epoch). The evaluator coerces
    /// dates the same way it coerces numbers; the dynamic-date filters
    /// do their own arithmetic on the f64 serial.
    Date(f64),
}

impl Cell {
    pub fn is_empty(&self) -> bool {
        matches!(self, Cell::Empty)
    }

    pub fn as_number(&self) -> Option<f64> {
        match self {
            Cell::Number(n) | Cell::Date(n) => Some(*n),
            Cell::Bool(true) => Some(1.0),
            Cell::Bool(false) => Some(0.0),
            Cell::String(s) => s.parse::<f64>().ok(),
            Cell::Empty => None,
        }
    }

    pub fn as_string(&self) -> Option<String> {
        match self {
            Cell::String(s) => Some(s.clone()),
            Cell::Number(n) => Some(crate::emit::format_number(*n)),
            Cell::Date(n) => Some(crate::emit::format_number(*n)),
            Cell::Bool(true) => Some("TRUE".to_string()),
            Cell::Bool(false) => Some("FALSE".to_string()),
            Cell::Empty => None,
        }
    }
}

/// Result of `evaluate`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct EvaluationResult {
    /// Row indices (0-based, relative to `rows`) that the filter set
    /// excludes. Sorted ascending, deduped.
    pub hidden_row_indices: Vec<u32>,
    /// Permutation: if non-`None`, `sort_order[k]` gives the row
    /// index (0-based, into `rows`) that should appear at position
    /// `k` after sorting. Hidden rows are NOT removed from the
    /// permutation.
    pub sort_order: Option<Vec<u32>>,
}

/// Public entry point. RFC-056 §4.
pub fn evaluate(
    rows: &[Vec<Cell>],
    filter_columns: &[FilterColumn],
    sort_state: Option<&SortState>,
    ref_date_serial: Option<f64>,
) -> EvaluationResult {
    // ------------------- Hidden indices -------------------
    let mut hidden = Vec::<u32>::new();
    if !filter_columns.is_empty() {
        // Pre-compute Top10 thresholds + above/below-average reference.
        // For multi-column filters Excel evaluates each column over the
        // full column (not over the in-progress filtered set), so we
        // pre-compute per-column once.
        for (row_idx, row) in rows.iter().enumerate() {
            let mut keep = true;
            for fc in filter_columns {
                if !column_accepts_row(row, fc.col_id, &fc.filter, rows, ref_date_serial) {
                    keep = false;
                    break;
                }
            }
            if !keep {
                hidden.push(row_idx as u32);
            }
        }
    }

    // ------------------- Sort permutation -------------------
    let sort_order = sort_state.and_then(|s| compute_sort_order(rows, s));

    EvaluationResult {
        hidden_row_indices: hidden,
        sort_order,
    }
}

fn column_accepts_row(
    row: &[Cell],
    col_id: u32,
    filter: &Option<FilterKind>,
    all_rows: &[Vec<Cell>],
    ref_date_serial: Option<f64>,
) -> bool {
    // No filter on this column → accept.
    let Some(filter) = filter else {
        return true;
    };
    let cell = row.get(col_id as usize).cloned().unwrap_or(Cell::Empty);
    match filter {
        FilterKind::Blank(_) => cell.is_empty(),
        FilterKind::Color(c) => eval_color_filter(&cell, c),
        FilterKind::Custom(c) => eval_custom_filters(&cell, c),
        FilterKind::Dynamic(d) => eval_dynamic_filter(&cell, d, all_rows, col_id, ref_date_serial),
        FilterKind::Icon(i) => eval_icon_filter(&cell, i),
        FilterKind::Number(n) => eval_number_filter(&cell, n),
        FilterKind::String(s) => eval_string_filter(&cell, s),
        FilterKind::Top10(t) => eval_top10(&cell, t, all_rows, col_id),
    }
}

fn eval_color_filter(_cell: &Cell, _c: &ColorFilter) -> bool {
    // ColorFilter requires per-cell dxf metadata that the patcher
    // doesn't pass through this evaluator (the filter's intended
    // semantics is "Excel re-evaluates the dxfId match on open").
    // Per RFC-056 §4.1: Wolfxl evaluation of color is best-effort —
    // we accept all rows so the filter survives in XML and Excel
    // applies it on open. KNOWN_GAP entry in the test for this.
    true
}

fn eval_custom_filters(cell: &Cell, c: &CustomFilters) -> bool {
    if c.filters.is_empty() {
        return true;
    }
    if c.and_ {
        c.filters.iter().all(|f| eval_custom_filter(cell, f))
    } else {
        c.filters.iter().any(|f| eval_custom_filter(cell, f))
    }
}

fn eval_custom_filter(cell: &Cell, cf: &CustomFilter) -> bool {
    // Numeric path if both sides parse as numbers.
    let lhs_num = cell.as_number();
    let rhs_num: Option<f64> = cf.val.parse::<f64>().ok();
    if let (Some(l), Some(r)) = (lhs_num, rhs_num) {
        return match cf.operator {
            CustomFilterOp::Equal => l == r,
            CustomFilterOp::LessThan => l < r,
            CustomFilterOp::LessThanOrEqual => l <= r,
            CustomFilterOp::NotEqual => l != r,
            CustomFilterOp::GreaterThanOrEqual => l >= r,
            CustomFilterOp::GreaterThan => l > r,
        };
    }
    // String path (case-insensitive, Excel parity).
    let l = cell.as_string().unwrap_or_default().to_lowercase();
    let r = cf.val.to_lowercase();
    match cf.operator {
        CustomFilterOp::Equal => match_glob(&r, &l),
        CustomFilterOp::NotEqual => !match_glob(&r, &l),
        CustomFilterOp::LessThan => l < r,
        CustomFilterOp::LessThanOrEqual => l <= r,
        CustomFilterOp::GreaterThanOrEqual => l >= r,
        CustomFilterOp::GreaterThan => l > r,
    }
}

/// Excel custom filter glob: `*` matches any chars, `?` matches one.
/// Used only for `Equal`/`NotEqual` on string operands.
fn match_glob(pattern: &str, text: &str) -> bool {
    if !pattern.contains('*') && !pattern.contains('?') {
        return pattern == text;
    }
    let pchars: Vec<char> = pattern.chars().collect();
    let tchars: Vec<char> = text.chars().collect();
    glob_recurse(&pchars, &tchars, 0, 0)
}

fn glob_recurse(p: &[char], t: &[char], pi: usize, ti: usize) -> bool {
    if pi == p.len() {
        return ti == t.len();
    }
    match p[pi] {
        '*' => {
            // Match zero or more chars.
            if glob_recurse(p, t, pi + 1, ti) {
                return true;
            }
            if ti < t.len() {
                return glob_recurse(p, t, pi, ti + 1);
            }
            false
        }
        '?' => {
            if ti < t.len() {
                glob_recurse(p, t, pi + 1, ti + 1)
            } else {
                false
            }
        }
        c => {
            if ti < t.len() && t[ti] == c {
                glob_recurse(p, t, pi + 1, ti + 1)
            } else {
                false
            }
        }
    }
}

fn eval_dynamic_filter(
    cell: &Cell,
    d: &DynamicFilter,
    all_rows: &[Vec<Cell>],
    col_id: u32,
    ref_date_serial: Option<f64>,
) -> bool {
    match &d.type_ {
        DynamicFilterType::Null => true,
        DynamicFilterType::AboveAverage => {
            let avg = column_average(all_rows, col_id).unwrap_or(0.0);
            cell.as_number().map(|n| n > avg).unwrap_or(false)
        }
        DynamicFilterType::BelowAverage => {
            let avg = column_average(all_rows, col_id).unwrap_or(0.0);
            cell.as_number().map(|n| n < avg).unwrap_or(false)
        }
        DynamicFilterType::YearToDate => {
            let today = today_serial(ref_date_serial);
            let year = year_from_serial(today);
            let jan1 = serial_for_jan1(year);
            cell.as_number()
                .map(|n| n >= jan1 && n <= today)
                .unwrap_or(false)
        }
        DynamicFilterType::Today | DynamicFilterType::Tomorrow | DynamicFilterType::Yesterday => {
            let target = match d.type_ {
                DynamicFilterType::Today => today_serial(ref_date_serial),
                DynamicFilterType::Tomorrow => today_serial(ref_date_serial) + 1.0,
                DynamicFilterType::Yesterday => today_serial(ref_date_serial) - 1.0,
                _ => unreachable!(),
            };
            cell.as_number()
                .map(|n| n.floor() == target.floor())
                .unwrap_or(false)
        }
        DynamicFilterType::ThisWeek | DynamicFilterType::LastWeek | DynamicFilterType::NextWeek => {
            let today = today_serial(ref_date_serial);
            let dow = (today.floor() as i64 + 6).rem_euclid(7);
            let week_start = today.floor() - dow as f64;
            let (lo, hi) = match d.type_ {
                DynamicFilterType::ThisWeek => (week_start, week_start + 7.0),
                DynamicFilterType::LastWeek => (week_start - 7.0, week_start),
                DynamicFilterType::NextWeek => (week_start + 7.0, week_start + 14.0),
                _ => unreachable!(),
            };
            cell.as_number().map(|n| n >= lo && n < hi).unwrap_or(false)
        }
        DynamicFilterType::ThisMonth
        | DynamicFilterType::LastMonth
        | DynamicFilterType::NextMonth => {
            let today = today_serial(ref_date_serial);
            let (year, month, _) = ymd_from_serial(today);
            let (target_year, target_month) = match d.type_ {
                DynamicFilterType::ThisMonth => (year, month),
                DynamicFilterType::LastMonth => {
                    if month == 1 {
                        (year - 1, 12)
                    } else {
                        (year, month - 1)
                    }
                }
                DynamicFilterType::NextMonth => {
                    if month == 12 {
                        (year + 1, 1)
                    } else {
                        (year, month + 1)
                    }
                }
                _ => unreachable!(),
            };
            cell.as_number()
                .map(|n| {
                    let (y, m, _) = ymd_from_serial(n);
                    y == target_year && m == target_month
                })
                .unwrap_or(false)
        }
        DynamicFilterType::ThisQuarter
        | DynamicFilterType::LastQuarter
        | DynamicFilterType::NextQuarter => {
            let today = today_serial(ref_date_serial);
            let (year, month, _) = ymd_from_serial(today);
            let q = (month - 1) / 3 + 1;
            let (target_year, target_q) = match d.type_ {
                DynamicFilterType::ThisQuarter => (year, q),
                DynamicFilterType::LastQuarter => {
                    if q == 1 {
                        (year - 1, 4)
                    } else {
                        (year, q - 1)
                    }
                }
                DynamicFilterType::NextQuarter => {
                    if q == 4 {
                        (year + 1, 1)
                    } else {
                        (year, q + 1)
                    }
                }
                _ => unreachable!(),
            };
            cell.as_number()
                .map(|n| {
                    let (y, m, _) = ymd_from_serial(n);
                    let cell_q = (m - 1) / 3 + 1;
                    y == target_year && cell_q == target_q
                })
                .unwrap_or(false)
        }
        DynamicFilterType::ThisYear | DynamicFilterType::LastYear | DynamicFilterType::NextYear => {
            let today = today_serial(ref_date_serial);
            let year = year_from_serial(today);
            let target_year = match d.type_ {
                DynamicFilterType::ThisYear => year,
                DynamicFilterType::LastYear => year - 1,
                DynamicFilterType::NextYear => year + 1,
                _ => unreachable!(),
            };
            cell.as_number()
                .map(|n| year_from_serial(n) == target_year)
                .unwrap_or(false)
        }
        DynamicFilterType::Q1
        | DynamicFilterType::Q2
        | DynamicFilterType::Q3
        | DynamicFilterType::Q4 => {
            let target_q = match d.type_ {
                DynamicFilterType::Q1 => 1,
                DynamicFilterType::Q2 => 2,
                DynamicFilterType::Q3 => 3,
                DynamicFilterType::Q4 => 4,
                _ => unreachable!(),
            };
            cell.as_number()
                .map(|n| {
                    let (_y, m, _) = ymd_from_serial(n);
                    let cell_q = (m - 1) / 3 + 1;
                    cell_q == target_q
                })
                .unwrap_or(false)
        }
        DynamicFilterType::Month(target_month) => cell
            .as_number()
            .map(|n| {
                let (_y, m, _) = ymd_from_serial(n);
                m == *target_month as u32
            })
            .unwrap_or(false),
    }
}

fn eval_icon_filter(_cell: &Cell, _i: &IconFilter) -> bool {
    // Like ColorFilter, requires CF iconSet metadata that this
    // evaluator does not see. Accept all → defer to Excel.
    true
}

fn eval_number_filter(cell: &Cell, n: &NumberFilter) -> bool {
    if cell.is_empty() {
        return n.blank;
    }
    let v = match cell.as_number() {
        Some(x) => x,
        None => return false,
    };
    n.filters.iter().any(|f| (*f - v).abs() < 1e-9)
}

fn eval_string_filter(cell: &Cell, s: &StringFilter) -> bool {
    let val = match cell.as_string() {
        Some(v) => v,
        None => return false,
    };
    let val_lower = val.to_lowercase();
    s.values.iter().any(|v| v.to_lowercase() == val_lower)
}

fn eval_top10(cell: &Cell, t: &Top10, all_rows: &[Vec<Cell>], col_id: u32) -> bool {
    let cell_v = match cell.as_number() {
        Some(v) => v,
        None => return false,
    };
    // Build numeric column.
    let mut col_vals: Vec<f64> = all_rows
        .iter()
        .filter_map(|r| r.get(col_id as usize).and_then(|c| c.as_number()))
        .collect();
    if col_vals.is_empty() {
        return false;
    }
    let n_total = col_vals.len() as f64;
    let n_keep = if t.percent {
        ((t.val / 100.0) * n_total).ceil() as usize
    } else {
        t.val as usize
    };
    if n_keep == 0 {
        return false;
    }
    if t.top {
        col_vals.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
    } else {
        col_vals.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    }
    let threshold = col_vals[n_keep.min(col_vals.len()) - 1];
    if t.top {
        cell_v >= threshold
    } else {
        cell_v <= threshold
    }
}

fn column_average(rows: &[Vec<Cell>], col_id: u32) -> Option<f64> {
    let nums: Vec<f64> = rows
        .iter()
        .filter_map(|r| r.get(col_id as usize).and_then(|c| c.as_number()))
        .collect();
    if nums.is_empty() {
        None
    } else {
        Some(nums.iter().sum::<f64>() / nums.len() as f64)
    }
}

// ---------------------------------------------------------------------------
// Sort permutation
// ---------------------------------------------------------------------------

fn compute_sort_order(rows: &[Vec<Cell>], state: &SortState) -> Option<Vec<u32>> {
    if state.sort_conditions.is_empty() || rows.is_empty() {
        return None;
    }
    let mut idx: Vec<u32> = (0..rows.len() as u32).collect();
    let conds = state.sort_conditions.clone();
    let case_sensitive = state.case_sensitive;
    idx.sort_by(|&a, &b| {
        for sc in &conds {
            let col = parse_first_col_of_ref(&sc.ref_).unwrap_or(0);
            let ca = rows.get(a as usize).and_then(|r| r.get(col as usize));
            let cb = rows.get(b as usize).and_then(|r| r.get(col as usize));
            let ord = compare_cells(ca, cb, case_sensitive);
            let ord = if sc.descending { ord.reverse() } else { ord };
            if ord != std::cmp::Ordering::Equal {
                return ord;
            }
        }
        std::cmp::Ordering::Equal
    });
    Some(idx)
}

fn compare_cells(a: Option<&Cell>, b: Option<&Cell>, case_sensitive: bool) -> std::cmp::Ordering {
    use std::cmp::Ordering;
    let a = a.unwrap_or(&Cell::Empty);
    let b = b.unwrap_or(&Cell::Empty);
    // Empty sorts last in Excel ascending.
    match (a.is_empty(), b.is_empty()) {
        (true, true) => return Ordering::Equal,
        (true, false) => return Ordering::Greater,
        (false, true) => return Ordering::Less,
        _ => {}
    }
    // Both numeric → numeric compare.
    if let (Some(na), Some(nb)) = (a.as_number(), b.as_number()) {
        return na.partial_cmp(&nb).unwrap_or(Ordering::Equal);
    }
    // String compare.
    let sa = a.as_string().unwrap_or_default();
    let sb = b.as_string().unwrap_or_default();
    if case_sensitive {
        sa.cmp(&sb)
    } else {
        sa.to_lowercase().cmp(&sb.to_lowercase())
    }
}

/// Parse the first column of a ref like "A2:A100" → 0, "C5:E20" → 2.
/// 0-based.
fn parse_first_col_of_ref(r: &str) -> Option<u32> {
    let head = r.split([':', '!']).next()?;
    let head = head.trim_start_matches('$');
    let mut col: u32 = 0;
    let mut found = false;
    for c in head.chars() {
        if c.is_ascii_alphabetic() {
            col = col * 26 + (c.to_ascii_uppercase() as u32 - b'A' as u32 + 1);
            found = true;
        } else {
            break;
        }
    }
    if found {
        Some(col - 1)
    } else {
        None
    }
}

// ---------------------------------------------------------------------------
// Date helpers — Excel 1900-based serials. The patcher is responsible
// for converting actual dates into the f64 serials this code expects.
// ---------------------------------------------------------------------------

/// Returns today's date as an Excel serial. If `WOLFXL_TEST_EPOCH`
/// is set and parses as an i64, uses (UNIX_EPOCH + that value) for
/// determinism. Otherwise reads the system clock.
pub fn today_serial(override_serial: Option<f64>) -> f64 {
    if let Some(s) = override_serial {
        return s;
    }
    if let Ok(s) = std::env::var("WOLFXL_TEST_EPOCH") {
        if let Ok(secs) = s.parse::<i64>() {
            // Excel serial for 1970-01-01 is 25569.
            let days = secs as f64 / 86400.0;
            return (25569.0 + days).floor();
        }
    }
    // System clock: secs since unix epoch.
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as f64)
        .unwrap_or(0.0);
    (25569.0 + now / 86400.0).floor()
}

/// Convert an Excel 1900-system serial date to (year, month, day).
/// Handles the 1900-leap-year quirk by treating serials < 60 as
/// "garbage but predictable" — for filter purposes nobody cares
/// about pre-1900-03-01 dates.
pub fn ymd_from_serial(serial: f64) -> (i32, u32, u32) {
    let serial = serial.floor() as i64;
    // Excel epoch: 1900-01-01 = 1, but Excel includes the fictional
    // 1900-02-29 → adjust by subtracting 1 for any serial > 60.
    let days_since_1900 = if serial > 60 { serial - 2 } else { serial - 1 };
    // Compute Gregorian date from days since 1900-01-01.
    // 1900-01-01 corresponds to chrono day = 730486 in proleptic
    // Gregorian; we compute by hand to avoid the chrono dep.
    let (y, m, d) = days_to_ymd(days_since_1900);
    (y, m, d)
}

/// Days since 1900-01-01 → (year, month, day).
fn days_to_ymd(days: i64) -> (i32, u32, u32) {
    // Use Howard Hinnant's date algorithms (chrono convert: civil_from_days).
    // Days from 1970-01-01 = days - 25567 (since 1900-01-01 is 25567 days
    // before 1970-01-01? Actually it's exactly 25567 days). Let me adjust
    // via the standard "days from civil 0000-03-01" calc.
    let days_from_1970 = days - 25567;
    // civil_from_days reference impl
    let z = days_from_1970 + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe: u64 = (z - era * 146097) as u64; // [0, 146097)
    let yoe: u64 = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365; // [0, 400)
    let y: i64 = yoe as i64 + era * 400;
    let doy: u64 = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp: u64 = (5 * doy + 2) / 153;
    let d: u64 = doy - (153 * mp + 2) / 5 + 1;
    let m: u64 = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = if m <= 2 { y + 1 } else { y };
    (year as i32, m as u32, d as u32)
}

pub fn year_from_serial(serial: f64) -> i32 {
    ymd_from_serial(serial).0
}

pub fn serial_for_jan1(year: i32) -> f64 {
    // Reverse of ymd_from_serial: compute serial of (year, 1, 1).
    let m: i64 = 1;
    let d: i64 = 1;
    let y_civ = if m <= 2 { year as i64 - 1 } else { year as i64 };
    let era = if y_civ >= 0 { y_civ } else { y_civ - 399 } / 400;
    let yoe: i64 = y_civ - era * 400;
    let mp: i64 = if m > 2 { m - 3 } else { m + 9 };
    let doy: i64 = (153 * mp + 2) / 5 + d - 1;
    let doe: i64 = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days_from_1970: i64 = era * 146097 + doe - 719468;
    let days_from_1900 = days_from_1970 + 25567;
    let serial = if days_from_1900 >= 60 {
        days_from_1900 + 2
    } else {
        days_from_1900 + 1
    };
    serial as f64
}

/// Wrapper that converts the public `evaluate` to operate on an
/// `AutoFilter`. Convenience for callers that have the model already.
pub fn evaluate_autofilter(
    rows: &[Vec<Cell>],
    af: &AutoFilter,
    ref_date_serial: Option<f64>,
) -> EvaluationResult {
    evaluate(
        rows,
        &af.filter_columns,
        af.sort_state.as_ref(),
        ref_date_serial,
    )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{
        BlankFilter, ColorFilter, CustomFilter, CustomFilterOp, CustomFilters, DynamicFilter,
        DynamicFilterType, FilterColumn, FilterKind, IconFilter, NumberFilter, SortBy,
        SortCondition, SortState, StringFilter, Top10,
    };

    fn rows_of(specs: Vec<Vec<Cell>>) -> Vec<Vec<Cell>> {
        specs
    }

    #[test]
    fn no_filters_no_hidden() {
        let rows = rows_of(vec![vec![Cell::Number(1.0)], vec![Cell::Number(2.0)]]);
        let r = evaluate(&rows, &[], None, None);
        assert!(r.hidden_row_indices.is_empty());
        assert!(r.sort_order.is_none());
    }

    #[test]
    fn number_filter_keeps_listed() {
        let rows = vec![
            vec![Cell::Number(1.0)],
            vec![Cell::Number(2.0)],
            vec![Cell::Number(3.0)],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Number(NumberFilter {
                filters: vec![1.0, 3.0],
                blank: false,
                calendar_type: None,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        assert_eq!(r.hidden_row_indices, vec![1]);
    }

    #[test]
    fn number_filter_with_blank() {
        let rows = vec![
            vec![Cell::Number(1.0)],
            vec![Cell::Empty],
            vec![Cell::Number(2.0)],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Number(NumberFilter {
                filters: vec![1.0],
                blank: true,
                calendar_type: None,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        assert_eq!(r.hidden_row_indices, vec![2]);
    }

    #[test]
    fn string_filter_case_insensitive() {
        let rows = vec![
            vec![Cell::String("RED".into())],
            vec![Cell::String("blue".into())],
            vec![Cell::String("Green".into())],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::String(StringFilter {
                values: vec!["red".into(), "GREEN".into()],
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        assert_eq!(r.hidden_row_indices, vec![1]);
    }

    #[test]
    fn blank_filter_hides_non_empty() {
        let rows = vec![
            vec![Cell::Empty],
            vec![Cell::Number(1.0)],
            vec![Cell::Empty],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Blank(BlankFilter)),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        assert_eq!(r.hidden_row_indices, vec![1]);
    }

    #[test]
    fn custom_filter_greater_than() {
        let rows = vec![
            vec![Cell::Number(5.0)],
            vec![Cell::Number(15.0)],
            vec![Cell::Number(25.0)],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Custom(CustomFilters {
                filters: vec![CustomFilter {
                    operator: CustomFilterOp::GreaterThan,
                    val: "10".into(),
                }],
                and_: false,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        assert_eq!(r.hidden_row_indices, vec![0]);
    }

    #[test]
    fn custom_filter_and_range() {
        let rows = vec![
            vec![Cell::Number(5.0)],
            vec![Cell::Number(15.0)],
            vec![Cell::Number(25.0)],
            vec![Cell::Number(50.0)],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Custom(CustomFilters {
                filters: vec![
                    CustomFilter {
                        operator: CustomFilterOp::GreaterThan,
                        val: "10".into(),
                    },
                    CustomFilter {
                        operator: CustomFilterOp::LessThan,
                        val: "30".into(),
                    },
                ],
                and_: true,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        assert_eq!(r.hidden_row_indices, vec![0, 3]);
    }

    #[test]
    fn custom_filter_glob_equal() {
        let rows = vec![
            vec![Cell::String("apple".into())],
            vec![Cell::String("banana".into())],
            vec![Cell::String("apricot".into())],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Custom(CustomFilters {
                filters: vec![CustomFilter {
                    operator: CustomFilterOp::Equal,
                    val: "ap*".into(),
                }],
                and_: false,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        assert_eq!(r.hidden_row_indices, vec![1]);
    }

    #[test]
    fn top10_top_2() {
        let rows = vec![
            vec![Cell::Number(10.0)],
            vec![Cell::Number(50.0)],
            vec![Cell::Number(20.0)],
            vec![Cell::Number(40.0)],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Top10(Top10 {
                top: true,
                percent: false,
                val: 2.0,
                filter_val: None,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        // top 2 → 50 and 40 keep; 10 and 20 hide.
        assert_eq!(r.hidden_row_indices, vec![0, 2]);
    }

    #[test]
    fn top10_bottom_50_percent() {
        let rows = vec![
            vec![Cell::Number(1.0)],
            vec![Cell::Number(2.0)],
            vec![Cell::Number(3.0)],
            vec![Cell::Number(4.0)],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Top10(Top10 {
                top: false,
                percent: true,
                val: 50.0,
                filter_val: None,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        // bottom 50% of 4 → 2 lowest (1, 2) keep; (3, 4) hide.
        assert_eq!(r.hidden_row_indices, vec![2, 3]);
    }

    #[test]
    fn dynamic_above_average() {
        let rows = vec![
            vec![Cell::Number(10.0)],
            vec![Cell::Number(20.0)],
            vec![Cell::Number(30.0)],
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Dynamic(DynamicFilter {
                type_: DynamicFilterType::AboveAverage,
                val: None,
                val_iso: None,
                max_val_iso: None,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        // avg=20; >20 → only row 2 kept.
        assert_eq!(r.hidden_row_indices, vec![0, 1]);
    }

    #[test]
    fn dynamic_today_with_test_epoch() {
        // Use ref_date_serial directly to avoid env var coupling.
        // Excel serial 45000 = 2023-03-15.
        let today = 45000.0;
        let rows = vec![vec![Cell::Date(45000.0)], vec![Cell::Date(45001.0)]];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Dynamic(DynamicFilter {
                type_: DynamicFilterType::Today,
                val: None,
                val_iso: None,
                max_val_iso: None,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, Some(today));
        assert_eq!(r.hidden_row_indices, vec![1]);
    }

    #[test]
    fn dynamic_q1() {
        let rows = vec![
            vec![Cell::Date(serial_for_jan1(2024))], // 2024-01-01 Q1
            vec![Cell::Date(serial_for_jan1(2024) + 100.0)], // ~April Q2
        ];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Dynamic(DynamicFilter {
                type_: DynamicFilterType::Q1,
                val: None,
                val_iso: None,
                max_val_iso: None,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        assert_eq!(r.hidden_row_indices, vec![1]);
    }

    #[test]
    fn multi_column_logical_and() {
        let rows = vec![
            vec![Cell::Number(1.0), Cell::String("a".into())],
            vec![Cell::Number(2.0), Cell::String("b".into())],
            vec![Cell::Number(2.0), Cell::String("a".into())],
        ];
        let fc1 = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Number(NumberFilter {
                filters: vec![2.0],
                blank: false,
                calendar_type: None,
            })),
            date_group_items: Vec::new(),
        };
        let fc2 = FilterColumn {
            col_id: 1,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::String(StringFilter {
                values: vec!["a".into()],
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc1, fc2], None, None);
        // Only row 2 satisfies both (num=2 AND string=a).
        assert_eq!(r.hidden_row_indices, vec![0, 1]);
    }

    #[test]
    fn color_and_icon_accept_all() {
        let rows = vec![vec![Cell::Number(1.0)], vec![Cell::Number(2.0)]];
        let fc = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Color(ColorFilter::default())),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc], None, None);
        assert!(r.hidden_row_indices.is_empty());

        let fc2 = FilterColumn {
            col_id: 0,
            hidden_button: false,
            show_button: true,
            filter: Some(FilterKind::Icon(IconFilter {
                icon_set: "3Arrows".into(),
                icon_id: 0,
            })),
            date_group_items: Vec::new(),
        };
        let r = evaluate(&rows, &[fc2], None, None);
        assert!(r.hidden_row_indices.is_empty());
    }

    #[test]
    fn sort_ascending_string() {
        let rows = vec![
            vec![Cell::String("banana".into())],
            vec![Cell::String("apple".into())],
            vec![Cell::String("cherry".into())],
        ];
        let state = SortState {
            sort_conditions: vec![SortCondition {
                ref_: "A2:A4".into(),
                descending: false,
                sort_by: SortBy::Value,
                custom_list: None,
                dxf_id: None,
                icon_set: None,
                icon_id: None,
            }],
            column_sort: false,
            case_sensitive: false,
            ref_: None,
        };
        let r = evaluate(&rows, &[], Some(&state), None);
        assert_eq!(r.sort_order, Some(vec![1, 0, 2]));
    }

    #[test]
    fn sort_descending_numeric() {
        let rows = vec![
            vec![Cell::Number(10.0)],
            vec![Cell::Number(50.0)],
            vec![Cell::Number(20.0)],
        ];
        let state = SortState {
            sort_conditions: vec![SortCondition {
                ref_: "A2:A100".into(),
                descending: true,
                sort_by: SortBy::Value,
                custom_list: None,
                dxf_id: None,
                icon_set: None,
                icon_id: None,
            }],
            column_sort: false,
            case_sensitive: false,
            ref_: None,
        };
        let r = evaluate(&rows, &[], Some(&state), None);
        assert_eq!(r.sort_order, Some(vec![1, 2, 0]));
    }

    #[test]
    fn parse_first_col_works() {
        assert_eq!(parse_first_col_of_ref("A2:A100"), Some(0));
        assert_eq!(parse_first_col_of_ref("C5:E20"), Some(2));
        assert_eq!(parse_first_col_of_ref("$AB$1:$AB$10"), Some(27));
    }

    #[test]
    fn ymd_serial_roundtrip() {
        // Excel serial 1 = 1900-01-01.
        // Excel serial 60 = the nonexistent 1900-02-29 (Excel quirk).
        // Excel serial 61 = 1900-03-01.
        // Modern check: serial 44197 = 2021-01-01.
        let (y, m, d) = ymd_from_serial(44197.0);
        assert_eq!((y, m, d), (2021, 1, 1));
        // serial 25569 = 1970-01-01
        assert_eq!(ymd_from_serial(25569.0), (1970, 1, 1));
    }

    #[test]
    fn jan1_serial_roundtrip() {
        for year in [1990, 2000, 2010, 2024] {
            let s = serial_for_jan1(year);
            assert_eq!(ymd_from_serial(s), (year, 1, 1));
        }
    }
}
