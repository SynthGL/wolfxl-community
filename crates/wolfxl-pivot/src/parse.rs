//! Parser-side helpers for the §10 dict shape (RFC-047 / RFC-048).
//!
//! This module is **PyO3-free**. PyDict access lives in the
//! `src/wolfxl/pivot.rs` boundary inside the cdylib crate; that
//! boundary calls into these helpers (or constructs the typed
//! models directly) after extracting plain Rust values from the
//! Python side.
//!
//! The helpers below are split out because the dict-shape mapping
//! to enum variants (data_type, axis, function, cache_value kinds)
//! is identical in modify-mode and write-mode; centralising the
//! string→enum logic prevents drift between callers.

use crate::model::cache::{CacheValue, DataType};
use crate::model::records::RecordCell;
use crate::model::table::{AxisItemType, AxisType, DataFunction, PivotItemType, ShowDataAs};

/// RFC-047 §10.3 — `data_type` string → typed enum.
pub fn parse_data_type(s: &str) -> Result<DataType, String> {
    match s {
        "string" => Ok(DataType::String),
        "number" => Ok(DataType::Number),
        "date" => Ok(DataType::Date),
        "bool" => Ok(DataType::Bool),
        "mixed" => Ok(DataType::Mixed),
        other => Err(format!(
            "unknown data_type {other:?} (expected string/number/date/bool/mixed)"
        )),
    }
}

/// RFC-047 §10.5 — `shared_value.kind` → constructor.
pub fn parse_shared_value(kind: &str, value: Option<ParsedValue>) -> Result<CacheValue, String> {
    match (kind, value) {
        ("string", Some(ParsedValue::Str(s))) => Ok(CacheValue::String(s)),
        ("number", Some(ParsedValue::Num(n))) => Ok(CacheValue::Number(n)),
        ("boolean", Some(ParsedValue::Bool(b))) => Ok(CacheValue::Boolean(b)),
        ("date", Some(ParsedValue::Str(s))) => Ok(CacheValue::Date(s)),
        ("missing", _) => Ok(CacheValue::Missing),
        ("error", Some(ParsedValue::Str(s))) => Ok(CacheValue::Error(s)),
        (k, _) => Err(format!(
            "unknown/invalid shared_value kind {k:?} or value mismatch"
        )),
    }
}

/// RFC-047 §10.7 — `record_cell.kind` → typed `RecordCell`.
pub fn parse_record_cell(kind: &str, value: Option<ParsedValue>) -> Result<RecordCell, String> {
    match (kind, value) {
        ("index", Some(ParsedValue::Num(n))) => Ok(RecordCell::Index(n as u32)),
        ("number", Some(ParsedValue::Num(n))) => Ok(RecordCell::Number(n)),
        ("string", Some(ParsedValue::Str(s))) => Ok(RecordCell::String(s)),
        ("boolean", Some(ParsedValue::Bool(b))) => Ok(RecordCell::Boolean(b)),
        ("date", Some(ParsedValue::Str(s))) => Ok(RecordCell::Date(s)),
        ("missing", _) => Ok(RecordCell::Missing),
        ("error", Some(ParsedValue::Str(s))) => Ok(RecordCell::Error(s)),
        (k, _) => Err(format!(
            "unknown/invalid record_cell kind {k:?} or value mismatch"
        )),
    }
}

/// RFC-048 §10.3 — `axis` string → typed enum.
pub fn parse_axis(s: &str) -> Result<AxisType, String> {
    match s {
        "axisRow" => Ok(AxisType::Row),
        "axisCol" => Ok(AxisType::Col),
        "axisPage" => Ok(AxisType::Page),
        "axisValues" => Ok(AxisType::Values),
        other => Err(format!(
            "unknown axis {other:?} (expected axisRow/axisCol/axisPage/axisValues)"
        )),
    }
}

/// RFC-048 §10.4 — `pivot_item.t` string → typed enum.
pub fn parse_pivot_item_type(s: &str) -> Result<PivotItemType, String> {
    match s {
        "default" => Ok(PivotItemType::Default),
        "sum" => Ok(PivotItemType::Sum),
        "count" => Ok(PivotItemType::Count),
        "avg" => Ok(PivotItemType::Avg),
        "max" => Ok(PivotItemType::Max),
        "min" => Ok(PivotItemType::Min),
        "blank" => Ok(PivotItemType::Blank),
        "grand" => Ok(PivotItemType::Grand),
        other => Err(format!("unknown pivot_item.t {other:?}")),
    }
}

/// RFC-048 §10.5 — `function` string → typed enum.
pub fn parse_data_function(s: &str) -> Result<DataFunction, String> {
    match s {
        "sum" => Ok(DataFunction::Sum),
        "count" => Ok(DataFunction::Count),
        "average" => Ok(DataFunction::Average),
        "max" => Ok(DataFunction::Max),
        "min" => Ok(DataFunction::Min),
        "product" => Ok(DataFunction::Product),
        "countNums" => Ok(DataFunction::CountNums),
        "stdDev" => Ok(DataFunction::StdDev),
        "stdDevp" => Ok(DataFunction::StdDevp),
        "var" => Ok(DataFunction::Var),
        "varp" => Ok(DataFunction::Varp),
        other => Err(format!("unknown DataFunction {other:?}")),
    }
}

/// RFC-048 §10.5 — `show_data_as` string → typed enum.
pub fn parse_show_data_as(s: &str) -> Result<ShowDataAs, String> {
    match s {
        "normal" => Ok(ShowDataAs::Normal),
        "difference" => Ok(ShowDataAs::Difference),
        "percent" => Ok(ShowDataAs::Percent),
        "percentDiff" => Ok(ShowDataAs::PercentDiff),
        "runTotal" => Ok(ShowDataAs::RunTotal),
        "percentOfRow" => Ok(ShowDataAs::PercentOfRow),
        "percentOfCol" => Ok(ShowDataAs::PercentOfCol),
        "percentOfTotal" => Ok(ShowDataAs::PercentOfTotal),
        "index" => Ok(ShowDataAs::Index),
        other => Err(format!("unknown show_data_as {other:?}")),
    }
}

/// RFC-048 §10.6 — `axis_item.t` string → typed enum.
pub fn parse_axis_item_type(s: &str) -> Result<AxisItemType, String> {
    match s {
        "data" => Ok(AxisItemType::Data),
        "default" => Ok(AxisItemType::Default),
        "sum" => Ok(AxisItemType::Sum),
        "count" => Ok(AxisItemType::Count),
        "avg" => Ok(AxisItemType::Avg),
        "max" => Ok(AxisItemType::Max),
        "min" => Ok(AxisItemType::Min),
        "product" => Ok(AxisItemType::Product),
        "countNums" => Ok(AxisItemType::CountNums),
        "stdDev" => Ok(AxisItemType::StdDev),
        "stdDevp" => Ok(AxisItemType::StdDevp),
        "var" => Ok(AxisItemType::Var),
        "varp" => Ok(AxisItemType::Varp),
        "grand" => Ok(AxisItemType::Grand),
        "blank" => Ok(AxisItemType::Blank),
        other => Err(format!("unknown axis_item.t {other:?}")),
    }
}

/// Plain Rust value extracted from a §10 dict at the PyO3 boundary.
/// Used by the dispatch helpers above so this crate stays PyO3-free.
#[derive(Debug, Clone, PartialEq)]
pub enum ParsedValue {
    Str(String),
    Num(f64),
    Bool(bool),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_data_type_known() {
        assert_eq!(parse_data_type("number").unwrap(), DataType::Number);
        assert_eq!(parse_data_type("string").unwrap(), DataType::String);
        assert!(parse_data_type("xyz").is_err());
    }

    #[test]
    fn parse_axis_known() {
        assert_eq!(parse_axis("axisRow").unwrap(), AxisType::Row);
        assert!(parse_axis("axisOther").is_err());
    }

    #[test]
    fn parse_function_known() {
        assert_eq!(parse_data_function("sum").unwrap(), DataFunction::Sum);
        assert_eq!(
            parse_data_function("countNums").unwrap(),
            DataFunction::CountNums
        );
    }

    #[test]
    fn parse_record_cell_index() {
        assert_eq!(
            parse_record_cell("index", Some(ParsedValue::Num(3.0))).unwrap(),
            RecordCell::Index(3)
        );
        assert_eq!(
            parse_record_cell("missing", None).unwrap(),
            RecordCell::Missing
        );
    }

    #[test]
    fn parse_shared_value_kinds() {
        assert_eq!(
            parse_shared_value("string", Some(ParsedValue::Str("x".into()))).unwrap(),
            CacheValue::String("x".into())
        );
        assert_eq!(
            parse_shared_value("number", Some(ParsedValue::Num(1.5))).unwrap(),
            CacheValue::Number(1.5)
        );
        assert_eq!(
            parse_shared_value("missing", None).unwrap(),
            CacheValue::Missing
        );
    }
}
