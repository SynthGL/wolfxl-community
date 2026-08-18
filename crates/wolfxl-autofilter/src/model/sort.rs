//! `<sortState>` model. ECMA-376 §18.3.1.92.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SortBy {
    Value,
    CellColor,
    FontColor,
    Icon,
}

impl SortBy {
    pub fn as_xml(&self) -> &'static str {
        match self {
            SortBy::Value => "value",
            SortBy::CellColor => "cellColor",
            SortBy::FontColor => "fontColor",
            SortBy::Icon => "icon",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "value" => Some(SortBy::Value),
            "cellColor" => Some(SortBy::CellColor),
            "fontColor" => Some(SortBy::FontColor),
            "icon" => Some(SortBy::Icon),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SortCondition {
    pub ref_: String,
    pub descending: bool,
    pub sort_by: SortBy,
    pub custom_list: Option<String>,
    pub dxf_id: Option<u32>,
    pub icon_set: Option<String>,
    pub icon_id: Option<u32>,
}

impl SortCondition {
    pub fn new(ref_: impl Into<String>) -> Self {
        Self {
            ref_: ref_.into(),
            descending: false,
            sort_by: SortBy::Value,
            custom_list: None,
            dxf_id: None,
            icon_set: None,
            icon_id: None,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SortState {
    pub sort_conditions: Vec<SortCondition>,
    pub column_sort: bool,
    pub case_sensitive: bool,
    pub ref_: Option<String>,
}
