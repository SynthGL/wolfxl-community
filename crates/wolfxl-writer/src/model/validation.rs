//! Data validation rules (Data → Data Validation in Excel).

/// A single validation rule applied to one or more ranges.
#[derive(Debug, Clone, PartialEq)]
pub struct DataValidation {
    /// Space-separated A1 ranges the rule applies to.
    pub sqref: String,

    pub validation_type: ValidationType,
    pub operator: ValidationOperator,

    /// Primary formula/value. Meaning depends on `validation_type`.
    /// e.g. for `List`, a comma-separated values string or a range ref.
    pub formula_a: Option<String>,
    /// Secondary formula, used by `Between`/`NotBetween` operators.
    pub formula_b: Option<String>,

    pub allow_blank: bool,
    pub show_dropdown: bool,

    /// If `false`, Excel still highlights the bad value but doesn't stop entry.
    pub show_error_message: bool,
    pub error_style: ErrorStyle,
    pub error_title: Option<String>,
    pub error_message: Option<String>,

    pub show_input_message: bool,
    pub input_title: Option<String>,
    pub input_message: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ValidationType {
    #[default]
    Any,
    Whole,
    Decimal,
    List,
    Date,
    Time,
    TextLength,
    /// "Custom" → free-form formula.
    Custom,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ValidationOperator {
    #[default]
    Between,
    NotBetween,
    Equal,
    NotEqual,
    GreaterThan,
    LessThan,
    GreaterThanOrEqual,
    LessThanOrEqual,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ErrorStyle {
    #[default]
    Stop,
    Warning,
    Information,
}
