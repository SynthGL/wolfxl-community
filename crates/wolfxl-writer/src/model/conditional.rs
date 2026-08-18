//! Conditional formatting data. Wave 3 module — types only here.

/// A single conditional-formatting block applied to a range.
#[derive(Debug, Clone, PartialEq)]
pub struct ConditionalFormat {
    /// The A1 range this block applies to. Can be a single cell or
    /// multi-area (space-separated).
    pub sqref: String,
    pub rules: Vec<ConditionalRule>,
}

/// One rule within a conditional-formatting block. Priority defaults to the
/// rule's positional index inside the parent `Vec` (earlier rules win),
/// but a user can override it explicitly via [`Self::priority`].
#[derive(Debug, Clone, PartialEq)]
pub struct ConditionalRule {
    pub kind: ConditionalKind,
    /// Index into `xl/styles.xml`'s `<dxfs>` (differential formats) table.
    /// `None` for rule types like icon sets that don't use dxf styling.
    pub dxf_id: Option<u32>,
    pub stop_if_true: bool,
    /// User-supplied priority (openpyxl: ``rule.priority = N``). When `Some`
    /// the emitter writes this value verbatim instead of using the
    /// positional fallback. This matters for multi-rule blocks where the
    /// author wants explicit ordering rather than insertion-order.
    /// Added in G14 (Sprint 3).
    pub priority: Option<u32>,
}

impl ConditionalRule {
    /// Convenience constructor preserving the pre-G14 default of "no
    /// explicit priority, no dxf, don't stop". Existing callers that built
    /// the struct field-by-field continue to work because the new field is
    /// `Option<u32>` and old code paths populate it with `None` here.
    pub fn new(kind: ConditionalKind) -> Self {
        Self {
            kind,
            dxf_id: None,
            stop_if_true: false,
            priority: None,
        }
    }
}

/// The large sum type covering every CF rule Excel recognizes.
///
/// Kept explicit rather than string-based so the emitter can lean on
/// the Rust match-exhaustiveness check when adding new kinds.
#[derive(Debug, Clone, PartialEq)]
pub enum ConditionalKind {
    CellIs {
        operator: CellIsOperator,
        formula_a: String,
        formula_b: Option<String>,
    },
    Expression {
        formula: String,
    },
    ContainsText {
        text: String,
    },
    NotContainsText {
        text: String,
    },
    BeginsWith {
        text: String,
    },
    EndsWith {
        text: String,
    },
    Duplicate,
    Unique,
    Top10 {
        count: u32,
        bottom: bool,
        percent: bool,
    },
    AboveAverage {
        above: bool,
        /// 0 means "exactly average"; 1 = "one std dev", etc.
        std_dev: u32,
    },
    Generic {
        /// Openpyxl/OOXML cfRule type name (for example "containsText",
        /// "top10", "duplicateValues", or "timePeriod").
        type_name: String,
        /// Additional cfRule attributes beyond type / priority / dxfId /
        /// stopIfTrue. Values are already stringified for OOXML.
        attrs: Vec<(String, String)>,
        /// Optional `<formula>` children in wire order.
        formulas: Vec<String>,
    },
    /// Gradient color scale (2-stop or 3-stop).
    ColorScale {
        stops: Vec<ColorScaleStop>,
    },
    DataBar {
        color_rgb: String,
        min: ConditionalThreshold,
        max: ConditionalThreshold,
        /// Whether to render the cell value next to the bar.
        /// OOXML default is `true`; when `false` we emit `showValue="0"` on
        /// the `<dataBar>` element. Added in G12 (Sprint 3).
        show_value: bool,
        /// Optional OOXML minLength / maxLength display bounds.
        min_length: Option<u32>,
        max_length: Option<u32>,
    },
    IconSet {
        /// e.g. `"3TrafficLights1"`, `"5Arrows"`, `"4Rating"`.
        set_name: String,
        /// One entry per icon band; length must match the set.
        thresholds: Vec<ConditionalThreshold>,
        /// OOXML `showValue` attribute. Default is `true` (matches the
        /// OOXML spec default), so emit `showValue="0"` only when this
        /// is explicitly `false`.
        show_value: bool,
        /// Optional OOXML flags for absolute/percent threshold semantics and
        /// reversed icon ordering.
        percent: Option<bool>,
        reverse: Option<bool>,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CellIsOperator {
    Equal,
    NotEqual,
    GreaterThan,
    GreaterThanOrEqual,
    LessThan,
    LessThanOrEqual,
    Between,
    NotBetween,
}

/// One stop on a color-scale gradient.
#[derive(Debug, Clone, PartialEq)]
pub struct ColorScaleStop {
    pub threshold: ConditionalThreshold,
    /// ARGB like `"FFRRGGBB"`.
    pub color_rgb: String,
}

/// A threshold value for gradient / bar / icon rules.
#[derive(Debug, Clone, PartialEq)]
pub enum ConditionalThreshold {
    Min,
    Max,
    /// Literal number.
    Number(f64),
    /// Percentage 0-100.
    Percent(f64),
    /// Percentile 0-100.
    Percentile(f64),
    /// Formula that evaluates to a threshold.
    Formula(String),
}
