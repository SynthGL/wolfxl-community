use chrono::{NaiveDate, NaiveDateTime, NaiveTime};

#[derive(Debug, Clone, PartialEq)]
pub enum CellValue {
    Empty,
    String(String),
    Int(i64),
    Float(f64),
    Bool(bool),
    Date(NaiveDate),
    DateTime(NaiveDateTime),
    Time(NaiveTime),
    Error(String),
}

impl CellValue {
    pub fn is_empty(&self) -> bool {
        matches!(self, CellValue::Empty)
    }

    pub fn type_name(&self) -> &'static str {
        match self {
            CellValue::Empty => "empty",
            CellValue::String(_) => "string",
            CellValue::Int(_) => "int",
            CellValue::Float(_) => "float",
            CellValue::Bool(_) => "bool",
            CellValue::Date(_) => "date",
            CellValue::DateTime(_) => "datetime",
            CellValue::Time(_) => "time",
            CellValue::Error(_) => "error",
        }
    }
}

#[derive(Debug, Clone)]
pub struct Cell {
    pub value: CellValue,
    /// Excel number format string applied to this cell, if any.
    /// Examples: "0.00", "$#,##0.00", "0%", "yyyy-mm-dd".
    pub number_format: Option<String>,
}

impl Cell {
    pub fn empty() -> Self {
        Self {
            value: CellValue::Empty,
            number_format: None,
        }
    }
}
