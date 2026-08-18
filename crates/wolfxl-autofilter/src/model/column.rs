//! `FilterColumn`, `DateGroupItem`, and the top-level `AutoFilter`.

use super::filter::FilterKind;
use super::sort::SortState;

/// Date-component matcher used by `<dateGroupItem>`. ECMA-376
/// §18.18.16 `ST_DateTimeGrouping`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DateTimeGrouping {
    Year,
    Month,
    Day,
    Hour,
    Minute,
    Second,
}

impl DateTimeGrouping {
    pub fn as_xml(&self) -> &'static str {
        match self {
            DateTimeGrouping::Year => "year",
            DateTimeGrouping::Month => "month",
            DateTimeGrouping::Day => "day",
            DateTimeGrouping::Hour => "hour",
            DateTimeGrouping::Minute => "minute",
            DateTimeGrouping::Second => "second",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "year" => Some(DateTimeGrouping::Year),
            "month" => Some(DateTimeGrouping::Month),
            "day" => Some(DateTimeGrouping::Day),
            "hour" => Some(DateTimeGrouping::Hour),
            "minute" => Some(DateTimeGrouping::Minute),
            "second" => Some(DateTimeGrouping::Second),
            _ => None,
        }
    }
}

/// `<dateGroupItem>` — a single date-component matcher inside a
/// `<filters>` group. Components below the grouping precision are
/// `None` and are not emitted.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DateGroupItem {
    pub year: i32,
    pub month: Option<u8>,
    pub day: Option<u8>,
    pub hour: Option<u8>,
    pub minute: Option<u8>,
    pub second: Option<u8>,
    pub date_time_grouping: DateTimeGrouping,
}

/// One `<filterColumn colId="…">…</filterColumn>` entry.
///
/// `col_id` is **0-based** relative to `auto_filter.ref`'s left edge;
/// the XML emits it verbatim (Excel uses 0-based here even though
/// every other column index in OOXML is 1-based).
#[derive(Debug, Clone, PartialEq)]
pub struct FilterColumn {
    pub col_id: u32,
    pub hidden_button: bool,
    pub show_button: bool,
    pub filter: Option<FilterKind>,
    pub date_group_items: Vec<DateGroupItem>,
}

impl FilterColumn {
    pub fn new(col_id: u32) -> Self {
        Self {
            col_id,
            hidden_button: false,
            show_button: true,
            filter: None,
            date_group_items: Vec::new(),
        }
    }
}

/// `<autoFilter ref="…">…</autoFilter>` — the worksheet-level entry.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct AutoFilter {
    pub ref_: Option<String>,
    pub filter_columns: Vec<FilterColumn>,
    pub sort_state: Option<SortState>,
}
