//! The 11 filter classes — RFC-056 §2.1.
//!
//! Every variant maps 1:1 to an openpyxl class of the same name. The
//! Python side ships dataclasses; the Rust side mirrors them as plain
//! structs/enums. The coordinator (`AutoFilter.to_rust_dict()`) flattens
//! everything into the §10 PyDict shape and `parse::parse_filter` (in
//! this crate) lifts that back into typed values.

/// `<blank/>` / `<filter blank=true/>` — pass iff cell is empty.
/// openpyxl parity: `BlankFilter`.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct BlankFilter;

/// `<colorFilter dxfId="N" cellColor="1"/>` — RFC-056 §2.1.
///
/// `cell_color = true` → match against the cell fill (default).
/// `cell_color = false` → match against the font colour.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ColorFilter {
    pub dxf_id: u32,
    pub cell_color: bool,
}

impl Default for ColorFilter {
    fn default() -> Self {
        Self {
            dxf_id: 0,
            cell_color: true,
        }
    }
}

/// `<customFilter operator="…" val="…"/>` — six binary operators.
/// ECMA-376 §18.18.13 `ST_FilterOperator`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CustomFilterOp {
    Equal,
    LessThan,
    LessThanOrEqual,
    NotEqual,
    GreaterThanOrEqual,
    GreaterThan,
}

impl CustomFilterOp {
    pub fn as_xml(&self) -> &'static str {
        match self {
            CustomFilterOp::Equal => "equal",
            CustomFilterOp::LessThan => "lessThan",
            CustomFilterOp::LessThanOrEqual => "lessThanOrEqual",
            CustomFilterOp::NotEqual => "notEqual",
            CustomFilterOp::GreaterThanOrEqual => "greaterThanOrEqual",
            CustomFilterOp::GreaterThan => "greaterThan",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "equal" => Some(CustomFilterOp::Equal),
            "lessThan" => Some(CustomFilterOp::LessThan),
            "lessThanOrEqual" => Some(CustomFilterOp::LessThanOrEqual),
            "notEqual" => Some(CustomFilterOp::NotEqual),
            "greaterThanOrEqual" => Some(CustomFilterOp::GreaterThanOrEqual),
            "greaterThan" => Some(CustomFilterOp::GreaterThan),
            _ => None,
        }
    }
}

/// One `<customFilter>` row — operator + RHS literal.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CustomFilter {
    pub operator: CustomFilterOp,
    pub val: String,
}

/// `<customFilters and="0|1">…</customFilters>` — group of `CustomFilter`.
///
/// `and_ = false` → logical OR (the openpyxl + ECMA default).
/// `and_ = true`  → logical AND.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CustomFilters {
    pub filters: Vec<CustomFilter>,
    pub and_: bool,
}

/// `<dynamicFilter type="…" val="…" valIso="…" maxValIso="…"/>`.
/// ECMA-376 §18.18.36 `ST_DynamicFilterType`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DynamicFilterType {
    Null,
    AboveAverage,
    BelowAverage,
    Tomorrow,
    Today,
    Yesterday,
    NextWeek,
    ThisWeek,
    LastWeek,
    NextMonth,
    ThisMonth,
    LastMonth,
    NextQuarter,
    ThisQuarter,
    LastQuarter,
    NextYear,
    ThisYear,
    LastYear,
    YearToDate,
    Q1,
    Q2,
    Q3,
    Q4,
    /// Month constants `M1..=M12`.
    Month(u8),
}

impl DynamicFilterType {
    pub fn as_xml(&self) -> String {
        match self {
            DynamicFilterType::Null => "null".to_string(),
            DynamicFilterType::AboveAverage => "aboveAverage".to_string(),
            DynamicFilterType::BelowAverage => "belowAverage".to_string(),
            DynamicFilterType::Tomorrow => "tomorrow".to_string(),
            DynamicFilterType::Today => "today".to_string(),
            DynamicFilterType::Yesterday => "yesterday".to_string(),
            DynamicFilterType::NextWeek => "nextWeek".to_string(),
            DynamicFilterType::ThisWeek => "thisWeek".to_string(),
            DynamicFilterType::LastWeek => "lastWeek".to_string(),
            DynamicFilterType::NextMonth => "nextMonth".to_string(),
            DynamicFilterType::ThisMonth => "thisMonth".to_string(),
            DynamicFilterType::LastMonth => "lastMonth".to_string(),
            DynamicFilterType::NextQuarter => "nextQuarter".to_string(),
            DynamicFilterType::ThisQuarter => "thisQuarter".to_string(),
            DynamicFilterType::LastQuarter => "lastQuarter".to_string(),
            DynamicFilterType::NextYear => "nextYear".to_string(),
            DynamicFilterType::ThisYear => "thisYear".to_string(),
            DynamicFilterType::LastYear => "lastYear".to_string(),
            DynamicFilterType::YearToDate => "yearToDate".to_string(),
            DynamicFilterType::Q1 => "Q1".to_string(),
            DynamicFilterType::Q2 => "Q2".to_string(),
            DynamicFilterType::Q3 => "Q3".to_string(),
            DynamicFilterType::Q4 => "Q4".to_string(),
            DynamicFilterType::Month(m) => format!("M{m}"),
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "null" => Some(DynamicFilterType::Null),
            "aboveAverage" => Some(DynamicFilterType::AboveAverage),
            "belowAverage" => Some(DynamicFilterType::BelowAverage),
            "tomorrow" => Some(DynamicFilterType::Tomorrow),
            "today" => Some(DynamicFilterType::Today),
            "yesterday" => Some(DynamicFilterType::Yesterday),
            "nextWeek" => Some(DynamicFilterType::NextWeek),
            "thisWeek" => Some(DynamicFilterType::ThisWeek),
            "lastWeek" => Some(DynamicFilterType::LastWeek),
            "nextMonth" => Some(DynamicFilterType::NextMonth),
            "thisMonth" => Some(DynamicFilterType::ThisMonth),
            "lastMonth" => Some(DynamicFilterType::LastMonth),
            "nextQuarter" => Some(DynamicFilterType::NextQuarter),
            "thisQuarter" => Some(DynamicFilterType::ThisQuarter),
            "lastQuarter" => Some(DynamicFilterType::LastQuarter),
            "nextYear" => Some(DynamicFilterType::NextYear),
            "thisYear" => Some(DynamicFilterType::ThisYear),
            "lastYear" => Some(DynamicFilterType::LastYear),
            "yearToDate" => Some(DynamicFilterType::YearToDate),
            "Q1" => Some(DynamicFilterType::Q1),
            "Q2" => Some(DynamicFilterType::Q2),
            "Q3" => Some(DynamicFilterType::Q3),
            "Q4" => Some(DynamicFilterType::Q4),
            other if other.starts_with('M') => {
                let n: u8 = other[1..].parse().ok()?;
                if (1..=12).contains(&n) {
                    Some(DynamicFilterType::Month(n))
                } else {
                    None
                }
            }
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct DynamicFilter {
    pub type_: DynamicFilterType,
    pub val: Option<f64>,
    pub val_iso: Option<String>,
    pub max_val_iso: Option<String>,
}

/// `<iconFilter iconSet="…" iconId="…"/>`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IconFilter {
    pub icon_set: String,
    pub icon_id: u32,
}

/// `<filters blank="0|1">…</filters>` containing `<filter val="…"/>`
/// children — numeric whitelist.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct NumberFilter {
    pub filters: Vec<f64>,
    pub blank: bool,
    pub calendar_type: Option<String>,
}

/// String whitelist (case-insensitive per Excel).
/// Same XML shape as `NumberFilter` but the values are strings.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct StringFilter {
    pub values: Vec<String>,
}

/// `<top10 top="0|1" percent="0|1" val="…" filterVal="…"/>`.
#[derive(Debug, Clone, PartialEq)]
pub struct Top10 {
    pub top: bool,
    pub percent: bool,
    pub val: f64,
    pub filter_val: Option<f64>,
}

impl Default for Top10 {
    fn default() -> Self {
        Self {
            top: true,
            percent: false,
            val: 10.0,
            filter_val: None,
        }
    }
}

/// Discriminated union of every filter kind a `FilterColumn` may carry.
#[derive(Debug, Clone, PartialEq)]
pub enum FilterKind {
    Blank(BlankFilter),
    Color(ColorFilter),
    /// `CustomFilters` — group; the single-`CustomFilter` form is
    /// represented as a one-element `CustomFilters`.
    Custom(CustomFilters),
    Dynamic(DynamicFilter),
    Icon(IconFilter),
    Number(NumberFilter),
    /// String list (subset of NumberFilter shape with text values).
    String(StringFilter),
    Top10(Top10),
}
