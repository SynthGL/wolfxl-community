//! Dict-shape parser. RFC-056 §10.
//!
//! PyO3-free: the cdylib boundary in `src/wolfxl/autofilter.rs`
//! lifts each PyDict into a `DictValue` tree, then calls into here
//! for the typed-model construction. This means the §10 contract
//! is enforced by exactly one body of code regardless of caller.

use crate::model::{
    AutoFilter, BlankFilter, ColorFilter, CustomFilter, CustomFilterOp, CustomFilters,
    DateGroupItem, DateTimeGrouping, DynamicFilter, DynamicFilterType, FilterColumn, FilterKind,
    IconFilter, NumberFilter, SortBy, SortCondition, SortState, StringFilter, Top10,
};
use std::collections::BTreeMap;

/// Plain Rust mirror of a §10 dict value. Keeps this crate PyO3-free.
#[derive(Debug, Clone, PartialEq)]
pub enum DictValue {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Str(String),
    List(Vec<DictValue>),
    Dict(BTreeMap<String, DictValue>),
}

impl DictValue {
    pub fn as_str(&self) -> Option<&str> {
        match self {
            DictValue::Str(s) => Some(s),
            _ => None,
        }
    }
    pub fn as_bool(&self) -> Option<bool> {
        match self {
            DictValue::Bool(b) => Some(*b),
            DictValue::Int(i) => Some(*i != 0),
            _ => None,
        }
    }
    pub fn as_f64(&self) -> Option<f64> {
        match self {
            DictValue::Float(f) => Some(*f),
            DictValue::Int(i) => Some(*i as f64),
            DictValue::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
            _ => None,
        }
    }
    pub fn as_u32(&self) -> Option<u32> {
        match self {
            DictValue::Int(i) => Some(*i as u32),
            DictValue::Float(f) => Some(*f as u32),
            _ => None,
        }
    }
    pub fn as_i32(&self) -> Option<i32> {
        match self {
            DictValue::Int(i) => Some(*i as i32),
            DictValue::Float(f) => Some(*f as i32),
            _ => None,
        }
    }
    pub fn as_dict(&self) -> Option<&BTreeMap<String, DictValue>> {
        match self {
            DictValue::Dict(d) => Some(d),
            _ => None,
        }
    }
    pub fn as_list(&self) -> Option<&[DictValue]> {
        match self {
            DictValue::List(l) => Some(l),
            _ => None,
        }
    }
    pub fn is_null(&self) -> bool {
        matches!(self, DictValue::Null)
    }
}

/// Parse the top-level §10 dict into a typed `AutoFilter`.
pub fn parse_autofilter(d: &DictValue) -> Result<AutoFilter, String> {
    let dict = d
        .as_dict()
        .ok_or_else(|| "autofilter: expected dict".to_string())?;

    let ref_ = match dict.get("ref") {
        Some(DictValue::Null) | None => None,
        Some(v) => Some(
            v.as_str()
                .ok_or_else(|| "autofilter.ref: expected string".to_string())?
                .to_string(),
        ),
    };

    let filter_columns = match dict.get("filter_columns") {
        None | Some(DictValue::Null) => Vec::new(),
        Some(DictValue::List(l)) => {
            let mut out = Vec::with_capacity(l.len());
            for v in l {
                out.push(parse_filter_column(v)?);
            }
            out
        }
        _ => return Err("autofilter.filter_columns: expected list".into()),
    };

    let sort_state = match dict.get("sort_state") {
        None | Some(DictValue::Null) => None,
        Some(v) => Some(parse_sort_state(v)?),
    };

    Ok(AutoFilter {
        ref_,
        filter_columns,
        sort_state,
    })
}

fn parse_filter_column(d: &DictValue) -> Result<FilterColumn, String> {
    let dict = d
        .as_dict()
        .ok_or_else(|| "filter_column: expected dict".to_string())?;
    let col_id = dict
        .get("col_id")
        .and_then(|v| v.as_u32())
        .ok_or_else(|| "filter_column.col_id: required u32".to_string())?;
    let hidden_button = dict
        .get("hidden_button")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let show_button = dict
        .get("show_button")
        .and_then(|v| v.as_bool())
        .unwrap_or(true);
    let filter = match dict.get("filter") {
        None | Some(DictValue::Null) => None,
        Some(v) => Some(parse_filter(v)?),
    };
    let date_group_items = match dict.get("date_group_items") {
        None | Some(DictValue::Null) => Vec::new(),
        Some(DictValue::List(l)) => {
            let mut out = Vec::with_capacity(l.len());
            for v in l {
                out.push(parse_date_group_item(v)?);
            }
            out
        }
        _ => return Err("filter_column.date_group_items: expected list".into()),
    };
    Ok(FilterColumn {
        col_id,
        hidden_button,
        show_button,
        filter,
        date_group_items,
    })
}

fn parse_filter(d: &DictValue) -> Result<FilterKind, String> {
    let dict = d
        .as_dict()
        .ok_or_else(|| "filter: expected dict".to_string())?;
    let kind = dict
        .get("kind")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "filter.kind: required string".to_string())?;
    match kind {
        "blank" => Ok(FilterKind::Blank(BlankFilter)),
        "color" => {
            let dxf_id = dict
                .get("dxf_id")
                .and_then(|v| v.as_u32())
                .ok_or_else(|| "color filter requires dxf_id".to_string())?;
            let cell_color = dict
                .get("cell_color")
                .and_then(|v| v.as_bool())
                .unwrap_or(true);
            Ok(FilterKind::Color(ColorFilter { dxf_id, cell_color }))
        }
        "custom" => {
            let and_ = dict.get("and_").and_then(|v| v.as_bool()).unwrap_or(false);
            let filters = match dict.get("filters") {
                None | Some(DictValue::Null) => Vec::new(),
                Some(DictValue::List(l)) => {
                    let mut out = Vec::with_capacity(l.len());
                    for v in l {
                        out.push(parse_custom_filter(v)?);
                    }
                    out
                }
                _ => return Err("custom filter.filters: expected list".into()),
            };
            Ok(FilterKind::Custom(CustomFilters { filters, and_ }))
        }
        "dynamic" => {
            let type_str = dict
                .get("type")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "dynamic filter requires type".to_string())?;
            let type_ = DynamicFilterType::parse(type_str)
                .ok_or_else(|| format!("unknown DynamicFilterType {type_str:?}"))?;
            let val = dict.get("val").and_then(|v| v.as_f64());
            let val_iso = dict
                .get("val_iso")
                .and_then(|v| v.as_str())
                .map(str::to_string);
            let max_val_iso = dict
                .get("max_val_iso")
                .and_then(|v| v.as_str())
                .map(str::to_string);
            Ok(FilterKind::Dynamic(DynamicFilter {
                type_,
                val,
                val_iso,
                max_val_iso,
            }))
        }
        "icon" => {
            let icon_set = dict
                .get("icon_set")
                .and_then(|v| v.as_str())
                .ok_or_else(|| "icon filter requires icon_set".to_string())?
                .to_string();
            let icon_id = dict
                .get("icon_id")
                .and_then(|v| v.as_u32())
                .ok_or_else(|| "icon filter requires icon_id".to_string())?;
            Ok(FilterKind::Icon(IconFilter { icon_set, icon_id }))
        }
        "number" => {
            let filters =
                match dict.get("filters") {
                    None | Some(DictValue::Null) => Vec::new(),
                    Some(DictValue::List(l)) => {
                        let mut out = Vec::with_capacity(l.len());
                        for v in l {
                            out.push(v.as_f64().ok_or_else(|| {
                                "number filter values must be numeric".to_string()
                            })?);
                        }
                        out
                    }
                    _ => return Err("number filter.filters: expected list".into()),
                };
            let blank = dict.get("blank").and_then(|v| v.as_bool()).unwrap_or(false);
            let calendar_type = dict
                .get("calendar_type")
                .and_then(|v| v.as_str())
                .map(str::to_string);
            Ok(FilterKind::Number(NumberFilter {
                filters,
                blank,
                calendar_type,
            }))
        }
        "string" => {
            let values = match dict.get("values") {
                None | Some(DictValue::Null) => Vec::new(),
                Some(DictValue::List(l)) => {
                    let mut out = Vec::with_capacity(l.len());
                    for v in l {
                        out.push(
                            v.as_str()
                                .ok_or_else(|| "string filter values must be strings".to_string())?
                                .to_string(),
                        );
                    }
                    out
                }
                _ => return Err("string filter.values: expected list".into()),
            };
            Ok(FilterKind::String(StringFilter { values }))
        }
        "top10" => {
            let top = dict.get("top").and_then(|v| v.as_bool()).unwrap_or(true);
            let percent = dict
                .get("percent")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            let val = dict
                .get("val")
                .and_then(|v| v.as_f64())
                .ok_or_else(|| "top10 requires val".to_string())?;
            let filter_val = dict.get("filter_val").and_then(|v| v.as_f64());
            Ok(FilterKind::Top10(Top10 {
                top,
                percent,
                val,
                filter_val,
            }))
        }
        other => Err(format!("unknown filter kind {other:?}")),
    }
}

fn parse_custom_filter(d: &DictValue) -> Result<CustomFilter, String> {
    let dict = d
        .as_dict()
        .ok_or_else(|| "custom_filter: expected dict".to_string())?;
    let op_str = dict
        .get("operator")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "custom_filter.operator: required".to_string())?;
    let operator = CustomFilterOp::parse(op_str)
        .ok_or_else(|| format!("unknown custom_filter operator {op_str:?}"))?;
    let val = dict
        .get("val")
        .and_then(|v| match v {
            DictValue::Str(s) => Some(s.clone()),
            DictValue::Int(i) => Some(i.to_string()),
            DictValue::Float(f) => Some(crate::emit::format_number(*f)),
            DictValue::Bool(b) => Some(if *b { "TRUE".into() } else { "FALSE".into() }),
            _ => None,
        })
        .ok_or_else(|| "custom_filter.val: required".to_string())?;
    Ok(CustomFilter { operator, val })
}

fn parse_date_group_item(d: &DictValue) -> Result<DateGroupItem, String> {
    let dict = d
        .as_dict()
        .ok_or_else(|| "date_group_item: expected dict".to_string())?;
    let year = dict
        .get("year")
        .and_then(|v| v.as_i32())
        .ok_or_else(|| "date_group_item.year: required".to_string())?;
    let month = dict.get("month").and_then(|v| v.as_u32()).map(|n| n as u8);
    let day = dict.get("day").and_then(|v| v.as_u32()).map(|n| n as u8);
    let hour = dict.get("hour").and_then(|v| v.as_u32()).map(|n| n as u8);
    let minute = dict.get("minute").and_then(|v| v.as_u32()).map(|n| n as u8);
    let second = dict.get("second").and_then(|v| v.as_u32()).map(|n| n as u8);
    let dtg_str = dict
        .get("date_time_grouping")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "date_group_item.date_time_grouping: required".to_string())?;
    let date_time_grouping = DateTimeGrouping::parse(dtg_str)
        .ok_or_else(|| format!("unknown date_time_grouping {dtg_str:?}"))?;
    Ok(DateGroupItem {
        year,
        month,
        day,
        hour,
        minute,
        second,
        date_time_grouping,
    })
}

fn parse_sort_state(d: &DictValue) -> Result<SortState, String> {
    let dict = d
        .as_dict()
        .ok_or_else(|| "sort_state: expected dict".to_string())?;
    let conditions = match dict.get("sort_conditions") {
        None | Some(DictValue::Null) => Vec::new(),
        Some(DictValue::List(l)) => {
            let mut out = Vec::with_capacity(l.len());
            for v in l {
                out.push(parse_sort_condition(v)?);
            }
            out
        }
        _ => return Err("sort_state.sort_conditions: expected list".into()),
    };
    let column_sort = dict
        .get("column_sort")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let case_sensitive = dict
        .get("case_sensitive")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let ref_ = dict.get("ref").and_then(|v| v.as_str()).map(str::to_string);
    Ok(SortState {
        sort_conditions: conditions,
        column_sort,
        case_sensitive,
        ref_,
    })
}

fn parse_sort_condition(d: &DictValue) -> Result<SortCondition, String> {
    let dict = d
        .as_dict()
        .ok_or_else(|| "sort_condition: expected dict".to_string())?;
    let ref_ = dict
        .get("ref")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "sort_condition.ref: required".to_string())?
        .to_string();
    let descending = dict
        .get("descending")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let sort_by_str = dict
        .get("sort_by")
        .and_then(|v| v.as_str())
        .unwrap_or("value");
    let sort_by =
        SortBy::parse(sort_by_str).ok_or_else(|| format!("unknown sort_by {sort_by_str:?}"))?;
    let custom_list = dict
        .get("custom_list")
        .and_then(|v| v.as_str())
        .map(str::to_string);
    let dxf_id = dict.get("dxf_id").and_then(|v| v.as_u32());
    let icon_set = dict
        .get("icon_set")
        .and_then(|v| v.as_str())
        .map(str::to_string);
    let icon_id = dict.get("icon_id").and_then(|v| v.as_u32());
    Ok(SortCondition {
        ref_,
        descending,
        sort_by,
        custom_list,
        dxf_id,
        icon_set,
        icon_id,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dict(pairs: Vec<(&str, DictValue)>) -> DictValue {
        let mut m = BTreeMap::new();
        for (k, v) in pairs {
            m.insert(k.to_string(), v);
        }
        DictValue::Dict(m)
    }

    #[test]
    fn empty_autofilter() {
        let d = dict(vec![("ref", DictValue::Null)]);
        let af = parse_autofilter(&d).unwrap();
        assert!(af.ref_.is_none());
        assert!(af.filter_columns.is_empty());
        assert!(af.sort_state.is_none());
    }

    #[test]
    fn ref_only() {
        let d = dict(vec![("ref", DictValue::Str("A1:D10".into()))]);
        let af = parse_autofilter(&d).unwrap();
        assert_eq!(af.ref_.as_deref(), Some("A1:D10"));
    }

    #[test]
    fn parse_number_filter_column() {
        let d = dict(vec![
            ("ref", DictValue::Str("A1:D10".into())),
            (
                "filter_columns",
                DictValue::List(vec![dict(vec![
                    ("col_id", DictValue::Int(0)),
                    (
                        "filter",
                        dict(vec![
                            ("kind", DictValue::Str("number".into())),
                            (
                                "filters",
                                DictValue::List(vec![DictValue::Float(1.0), DictValue::Float(2.5)]),
                            ),
                        ]),
                    ),
                ])]),
            ),
        ]);
        let af = parse_autofilter(&d).unwrap();
        assert_eq!(af.filter_columns.len(), 1);
        let fc = &af.filter_columns[0];
        assert_eq!(fc.col_id, 0);
        match &fc.filter {
            Some(FilterKind::Number(n)) => assert_eq!(n.filters, vec![1.0, 2.5]),
            _ => panic!("expected NumberFilter"),
        }
    }

    #[test]
    fn parse_string_filter_column() {
        let d = dict(vec![(
            "filter_columns",
            DictValue::List(vec![dict(vec![
                ("col_id", DictValue::Int(2)),
                (
                    "filter",
                    dict(vec![
                        ("kind", DictValue::Str("string".into())),
                        (
                            "values",
                            DictValue::List(vec![
                                DictValue::Str("red".into()),
                                DictValue::Str("blue".into()),
                            ]),
                        ),
                    ]),
                ),
            ])]),
        )]);
        let af = parse_autofilter(&d).unwrap();
        match &af.filter_columns[0].filter {
            Some(FilterKind::String(s)) => assert_eq!(s.values, vec!["red", "blue"]),
            _ => panic!("expected StringFilter"),
        }
    }

    #[test]
    fn parse_sort_state() {
        let d = dict(vec![(
            "sort_state",
            dict(vec![
                ("ref", DictValue::Str("A2:A100".into())),
                (
                    "sort_conditions",
                    DictValue::List(vec![dict(vec![
                        ("ref", DictValue::Str("A2:A100".into())),
                        ("descending", DictValue::Bool(true)),
                    ])]),
                ),
            ]),
        )]);
        let af = parse_autofilter(&d).unwrap();
        let s = af.sort_state.unwrap();
        assert_eq!(s.ref_.as_deref(), Some("A2:A100"));
        assert_eq!(s.sort_conditions.len(), 1);
        assert!(s.sort_conditions[0].descending);
    }

    #[test]
    fn parse_top10_defaults() {
        let d = dict(vec![(
            "filter_columns",
            DictValue::List(vec![dict(vec![
                ("col_id", DictValue::Int(0)),
                (
                    "filter",
                    dict(vec![
                        ("kind", DictValue::Str("top10".into())),
                        ("val", DictValue::Float(5.0)),
                    ]),
                ),
            ])]),
        )]);
        let af = parse_autofilter(&d).unwrap();
        match &af.filter_columns[0].filter {
            Some(FilterKind::Top10(t)) => {
                assert!(t.top);
                assert!(!t.percent);
                assert_eq!(t.val, 5.0);
            }
            _ => panic!("expected Top10"),
        }
    }

    #[test]
    fn parse_dynamic_today() {
        let d = dict(vec![(
            "filter_columns",
            DictValue::List(vec![dict(vec![
                ("col_id", DictValue::Int(0)),
                (
                    "filter",
                    dict(vec![
                        ("kind", DictValue::Str("dynamic".into())),
                        ("type", DictValue::Str("today".into())),
                    ]),
                ),
            ])]),
        )]);
        let af = parse_autofilter(&d).unwrap();
        match &af.filter_columns[0].filter {
            Some(FilterKind::Dynamic(d)) => {
                assert_eq!(d.type_, DynamicFilterType::Today);
            }
            _ => panic!("expected Dynamic"),
        }
    }

    #[test]
    fn parse_unknown_kind_errors() {
        let d = dict(vec![(
            "filter_columns",
            DictValue::List(vec![dict(vec![
                ("col_id", DictValue::Int(0)),
                ("filter", dict(vec![("kind", DictValue::Str("xyz".into()))])),
            ])]),
        )]);
        let err = parse_autofilter(&d).unwrap_err();
        assert!(err.contains("unknown filter kind"));
    }
}
