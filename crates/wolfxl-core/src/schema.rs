//! Per-column schema inference: type, null count, cardinality, format.
//!
//! Built for the `wolfxl schema` subcommand. Returns enough per-column detail
//! for an LLM or agent to plan a query strategy without round-tripping the
//! actual data: pick lookup columns by `cardinality`, choose dimension vs
//! measure by `inferred_type` + `format_category`, decide whether `unique_count`
//! is exact or capped before treating it as a primary key.
//!
//! All inference is single-pass O(rows × cols). Unique-count tracking caps
//! at 10 000 distinct rendered values per column so a million-row sheet
//! doesn't blow memory; the cap is reported via `unique_capped`.

use std::collections::HashSet;

use crate::cell::{Cell, CellValue};
use crate::format::{classify_format, FormatCategory};
use crate::sheet::Sheet;

/// Inferred logical type for a column. `Mixed` means "no clear majority";
/// `Empty` means "no non-null cells were observed".
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InferredType {
    String,
    Int,
    Float,
    Bool,
    Date,
    DateTime,
    Time,
    Mixed,
    Empty,
}

impl InferredType {
    pub fn as_str(self) -> &'static str {
        match self {
            InferredType::String => "string",
            InferredType::Int => "int",
            InferredType::Float => "float",
            InferredType::Bool => "bool",
            InferredType::Date => "date",
            InferredType::DateTime => "datetime",
            InferredType::Time => "time",
            InferredType::Mixed => "mixed",
            InferredType::Empty => "empty",
        }
    }
}

/// Coarse cardinality bucket — what an agent needs to decide "is this a
/// dimension or a measure?".
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Cardinality {
    /// Every non-null value is distinct.
    Unique,
    /// Few distinct values (≤20) and at most half of rows. Lookup-friendly.
    Categorical,
    /// Many distinct values, not unique. Typical for measures, IDs, names.
    HighCardinality,
    /// Column has no non-null cells.
    Empty,
}

impl Cardinality {
    pub fn as_str(self) -> &'static str {
        match self {
            Cardinality::Unique => "unique",
            Cardinality::Categorical => "categorical",
            Cardinality::HighCardinality => "high-cardinality",
            Cardinality::Empty => "empty",
        }
    }
}

#[derive(Debug, Clone)]
pub struct ColumnSchema {
    pub name: String,
    pub inferred_type: InferredType,
    /// First-non-empty-cell number-format category. Drives whether the
    /// column is "dollars" vs "percent" vs "plain integer" — orthogonal to
    /// `inferred_type` (a `currency` column is still typed `Float`).
    pub format_category: FormatCategory,
    pub null_count: usize,
    /// Distinct rendered-value count, capped at 10 000.
    pub unique_count: usize,
    pub unique_capped: bool,
    pub cardinality: Cardinality,
    /// Up to 3 distinct rendered values. Order is whatever the column
    /// presented first; not stable across runs if the underlying sheet
    /// changes. Useful for grounding agent queries with concrete values.
    pub sample_values: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct SheetSchema {
    pub sheet: String,
    pub rows: usize,
    pub columns: Vec<ColumnSchema>,
}

/// Hard cap on the per-column unique-value HashSet to keep a million-row
/// sheet from blowing memory. 10 000 is enough to confidently call a
/// column "high-cardinality" without exact counts past that point.
pub const UNIQUE_CAP: usize = 10_000;

const SAMPLE_LIMIT: usize = 3;
/// Categorical bucket upper bound on distinct values. Above this, a column
/// is too varied to be useful as a lookup dimension even if it's still
/// dense.
const CATEGORICAL_MAX_DISTINCT: usize = 20;

/// Infer per-column schema for a sheet. Header is row 0; body starts at
/// row 1. Returns one [`ColumnSchema`] per column reported by `headers()`.
pub fn infer_sheet_schema(sheet: &Sheet) -> SheetSchema {
    let headers = sheet.headers();
    let (total_rows, _) = sheet.dimensions();
    let body_rows = total_rows.saturating_sub(1);
    let cols = headers.len();
    let mut columns = Vec::with_capacity(cols);

    for col_idx in 0..cols {
        columns.push(infer_column(sheet, col_idx, &headers[col_idx], body_rows));
    }

    SheetSchema {
        sheet: sheet.name.clone(),
        rows: body_rows,
        columns,
    }
}

fn infer_column(sheet: &Sheet, col_idx: usize, name: &str, body_rows: usize) -> ColumnSchema {
    let mut counts = TypeCounts::default();
    let mut null_count = 0usize;
    let mut uniques: HashSet<String> = HashSet::new();
    let mut unique_capped = false;
    let mut samples: Vec<String> = Vec::with_capacity(SAMPLE_LIMIT);
    let mut format_category = FormatCategory::General;
    let mut format_locked = false;

    for row in sheet.rows().iter().skip(1) {
        let cell = match row.get(col_idx) {
            Some(c) => c,
            None => {
                null_count += 1;
                continue;
            }
        };

        if matches!(cell.value, CellValue::Empty) {
            null_count += 1;
            continue;
        }

        // Lock the format from the first non-empty cell. Mixed-format
        // columns are rare in practice; if the user wanted that, they'd
        // be looking at a CSV not an xlsx.
        if !format_locked {
            if let Some(fmt) = &cell.number_format {
                format_category = classify_format(fmt);
            }
            format_locked = true;
        }

        counts.observe(&cell.value);

        let rendered = render_for_uniqueness(cell);
        if !unique_capped {
            if uniques.contains(&rendered) {
                // Already-seen value: no cap consideration, no sample
                // update needed.
            } else if uniques.len() < UNIQUE_CAP {
                uniques.insert(rendered.clone());
                if samples.len() < SAMPLE_LIMIT {
                    samples.push(rendered);
                }
            } else {
                // First *new* distinct value past the cap. A column with
                // exactly UNIQUE_CAP distinct values followed by repeats
                // stays uncapped — `unique_count == UNIQUE_CAP` is then an
                // exact, trustworthy figure.
                unique_capped = true;
            }
        }
    }

    let inferred_type = counts.dominant();
    let unique_count = uniques.len();
    let non_null = body_rows.saturating_sub(null_count);
    let cardinality = classify_cardinality(unique_count, non_null, unique_capped);

    ColumnSchema {
        name: name.to_string(),
        inferred_type,
        format_category,
        null_count,
        unique_count,
        unique_capped,
        cardinality,
        sample_values: samples,
    }
}

/// Render a cell's value as a HashSet key for distinct-counting and as a
/// human-readable sample. Date/time/error formats follow the same conventions
/// as `wolfxl peek -e text` (space-separated DateTime, `ERROR: ` error
/// prefix) so a sample dropped into a `peek` filter expression matches what
/// an agent would otherwise see.
///
/// Two intentional divergences from peek's text renderer:
/// - **Floats keep full Rust precision** (`format!("{n}")`) rather than
///   rounding to two decimals: dedup correctness needs `1.234` and `1.236`
///   to count as distinct.
/// - **Ints are not thousand-grouped**: `1000` and `1,000` would otherwise
///   key into the HashSet as different strings.
fn render_for_uniqueness(cell: &Cell) -> String {
    match &cell.value {
        CellValue::Empty => String::new(),
        CellValue::String(s) => s.clone(),
        CellValue::Bool(b) => b.to_string(),
        CellValue::Int(n) => n.to_string(),
        CellValue::Float(n) => format!("{n}"),
        CellValue::Date(d) => d.format("%Y-%m-%d").to_string(),
        CellValue::DateTime(dt) => dt.format("%Y-%m-%d %H:%M:%S").to_string(),
        CellValue::Time(t) => t.format("%H:%M:%S").to_string(),
        CellValue::Error(e) => format!("ERROR: {e}"),
    }
}

fn classify_cardinality(unique: usize, non_null: usize, capped: bool) -> Cardinality {
    if non_null == 0 {
        return Cardinality::Empty;
    }
    // If the unique tracker hit its cap we cannot prove uniqueness either
    // way, so default to high-cardinality (the safer bucket — caller won't
    // wrongly treat it as a categorical lookup).
    if capped {
        return Cardinality::HighCardinality;
    }
    if unique == non_null {
        return Cardinality::Unique;
    }
    if unique <= CATEGORICAL_MAX_DISTINCT && unique * 2 <= non_null {
        return Cardinality::Categorical;
    }
    Cardinality::HighCardinality
}

/// How a string-valued cell should be counted for type inference. Used by
/// [`TypeCounts::observe`] so a CSV column of numeric-looking strings lands
/// in the Int/Float bucket instead of the catch-all String bucket.
enum StringShape {
    Int,
    Float,
    Other,
}

/// Classify a string cell's text. Conservative: only classifies as numeric
/// when the trimmed text parses cleanly as i64 / f64 with no stray
/// characters. `"$100"`, `"1,000"`, `"100%"` stay `Other` — a number format
/// is typically inferred from the column's format string, not from the cell
/// text, for those shapes.
fn classify_string_as_type(s: &str) -> StringShape {
    let t = s.trim();
    if t.is_empty() {
        return StringShape::Other;
    }
    if t.parse::<i64>().is_ok() {
        StringShape::Int
    } else if t.parse::<f64>().is_ok_and(f64::is_finite) {
        StringShape::Float
    } else {
        StringShape::Other
    }
}

#[derive(Default)]
struct TypeCounts {
    string: usize,
    int: usize,
    float: usize,
    bool_: usize,
    date: usize,
    datetime: usize,
    time: usize,
    error: usize,
}

impl TypeCounts {
    fn observe(&mut self, v: &CellValue) {
        match v {
            CellValue::Empty => {}
            // CSV cells and openpyxl-stored-as-text workbooks surface as
            // strings here. Per invariant B4, schema inference is the
            // single source of truth for "this column is actually numbers";
            // parse the rendered text so a CSV column of `"100","200",...`
            // classifies as Int, not String.
            CellValue::String(s) => match classify_string_as_type(s) {
                StringShape::Int => self.int += 1,
                StringShape::Float => self.float += 1,
                StringShape::Other => self.string += 1,
            },
            CellValue::Int(_) => self.int += 1,
            CellValue::Float(_) => self.float += 1,
            CellValue::Bool(_) => self.bool_ += 1,
            CellValue::Date(_) => self.date += 1,
            CellValue::DateTime(_) => self.datetime += 1,
            CellValue::Time(_) => self.time += 1,
            CellValue::Error(_) => self.error += 1,
        }
    }

    /// Pick the dominant type. Int + Float coexisting in the same column
    /// resolve to Float (numeric supertype). Anything else with two or
    /// more types contributing returns Mixed.
    fn dominant(&self) -> InferredType {
        let total = self.string
            + self.int
            + self.float
            + self.bool_
            + self.date
            + self.datetime
            + self.time
            + self.error;
        if total == 0 {
            return InferredType::Empty;
        }
        // Int+Float merge: if numeric is the only category present, return
        // Float when any cell was Float, else Int.
        let numeric = self.int + self.float;
        if numeric == total {
            return if self.float > 0 {
                InferredType::Float
            } else {
                InferredType::Int
            };
        }

        let pairs: [(usize, InferredType); 7] = [
            (self.string, InferredType::String),
            (self.bool_, InferredType::Bool),
            (self.date, InferredType::Date),
            (self.datetime, InferredType::DateTime),
            (self.time, InferredType::Time),
            // Numeric collapses to a single bucket so a column of 9 floats
            // and 1 string still resolves to Mixed (not Float-wins-because-
            // it's-the-largest); but a column that's pure numeric was
            // already handled above.
            (numeric, InferredType::Float),
            (self.error, InferredType::String),
        ];
        let nonzero = pairs.iter().filter(|(c, _)| *c > 0).count();
        if nonzero > 1 {
            return InferredType::Mixed;
        }
        pairs
            .iter()
            .find(|(c, _)| *c > 0)
            .map(|(_, t)| *t)
            .unwrap_or(InferredType::Empty)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(v: &str) -> Cell {
        Cell {
            value: CellValue::String(v.to_string()),
            number_format: None,
        }
    }
    fn i(n: i64) -> Cell {
        Cell {
            value: CellValue::Int(n),
            number_format: None,
        }
    }
    fn f(n: f64) -> Cell {
        Cell {
            value: CellValue::Float(n),
            number_format: None,
        }
    }
    fn empty() -> Cell {
        Cell::empty()
    }
    fn currency_f(n: f64) -> Cell {
        Cell {
            value: CellValue::Float(n),
            number_format: Some("$#,##0.00".to_string()),
        }
    }

    fn sheet_with(name: &str, rows: Vec<Vec<Cell>>) -> Sheet {
        Sheet::from_rows_for_test(name, rows)
    }

    #[test]
    fn pure_int_column_infers_int_unique_when_distinct() {
        let rows = vec![vec![s("id")], vec![i(1)], vec![i(2)], vec![i(3)]];
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        let col = &schema.columns[0];
        assert_eq!(col.inferred_type, InferredType::Int);
        assert_eq!(col.null_count, 0);
        assert_eq!(col.unique_count, 3);
        assert_eq!(col.cardinality, Cardinality::Unique);
    }

    #[test]
    fn int_plus_float_collapses_to_float() {
        let rows = vec![vec![s("price")], vec![i(1)], vec![f(2.5)], vec![i(3)]];
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        assert_eq!(schema.columns[0].inferred_type, InferredType::Float);
    }

    #[test]
    fn mixed_string_and_numeric_returns_mixed() {
        let rows = vec![vec![s("col")], vec![s("hello")], vec![i(42)]];
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        assert_eq!(schema.columns[0].inferred_type, InferredType::Mixed);
    }

    #[test]
    fn non_finite_numeric_strings_stay_strings() {
        let rows = vec![
            vec![s("value")],
            vec![s("NaN")],
            vec![s("inf")],
            vec![s("-inf")],
        ];
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        assert_eq!(schema.columns[0].inferred_type, InferredType::String);
    }

    #[test]
    fn categorical_bucket_when_few_repeated_values() {
        // 12 rows, 3 distinct values, all repeated → categorical.
        let rows = vec![
            vec![s("region")],
            vec![s("us")],
            vec![s("eu")],
            vec![s("apac")],
            vec![s("us")],
            vec![s("eu")],
            vec![s("apac")],
            vec![s("us")],
            vec![s("eu")],
            vec![s("apac")],
            vec![s("us")],
            vec![s("eu")],
            vec![s("apac")],
        ];
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        let col = &schema.columns[0];
        assert_eq!(col.unique_count, 3);
        assert_eq!(col.cardinality, Cardinality::Categorical);
        assert_eq!(col.sample_values.len(), 3);
    }

    #[test]
    fn high_cardinality_when_distinct_count_too_high_for_categorical() {
        // 21 distinct values exceeds CATEGORICAL_MAX_DISTINCT (20), so
        // even though every value repeats once it still classes as
        // high-cardinality.
        let rows: Vec<Vec<Cell>> = std::iter::once(vec![s("x")])
            .chain((0..21).map(|i| vec![s(&format!("v{i}"))]))
            .chain((0..21).map(|i| vec![s(&format!("v{i}"))]))
            .collect();
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        let col = &schema.columns[0];
        assert_eq!(col.unique_count, 21);
        assert_eq!(col.cardinality, Cardinality::HighCardinality);
    }

    #[test]
    fn null_count_handles_short_rows_and_empty_cells() {
        let rows = vec![
            vec![s("a"), s("b")],
            vec![i(1), empty()],
            vec![i(2)], // short row - col 1 is missing
            vec![i(3), i(4)],
        ];
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        let b = &schema.columns[1];
        assert_eq!(b.null_count, 2);
        assert_eq!(b.unique_count, 1);
    }

    #[test]
    fn currency_format_locked_from_first_non_empty_cell() {
        let rows = vec![
            vec![s("revenue")],
            vec![empty()],
            vec![currency_f(1500.0)],
            vec![currency_f(2500.0)],
        ];
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        let col = &schema.columns[0];
        assert_eq!(col.format_category, FormatCategory::Currency);
        assert_eq!(col.inferred_type, InferredType::Float);
    }

    #[test]
    fn at_cap_then_repeats_stays_uncapped() {
        // A column with exactly UNIQUE_CAP distinct values followed by a
        // long run of repeats should report the exact count and stay
        // uncapped. The earlier flip-on-next-row logic incorrectly set
        // `unique_capped: true` (and forced HighCardinality) on the first
        // duplicate after the cap, misleading downstream callers about
        // whether the cardinality figure was trustworthy.
        let mut rows: Vec<Vec<Cell>> = vec![vec![s("id")]];
        for n in 0..(UNIQUE_CAP as i64) {
            rows.push(vec![i(n)]);
        }
        // Repeats — these must NOT flip `unique_capped`.
        for n in 0..50 {
            rows.push(vec![i(n)]);
        }
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        let col = &schema.columns[0];
        assert_eq!(col.unique_count, UNIQUE_CAP);
        assert!(
            !col.unique_capped,
            "exact-at-cap with only repeats should stay uncapped"
        );
    }

    #[test]
    fn one_past_cap_flips_capped() {
        // The first genuinely new value beyond UNIQUE_CAP correctly flips
        // the capped flag; subsequent classification falls back to
        // HighCardinality (the safer bucket).
        let mut rows: Vec<Vec<Cell>> = vec![vec![s("id")]];
        for n in 0..((UNIQUE_CAP + 1) as i64) {
            rows.push(vec![i(n)]);
        }
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        let col = &schema.columns[0];
        assert!(col.unique_capped);
        assert_eq!(col.cardinality, Cardinality::HighCardinality);
    }

    #[test]
    fn empty_column_classifies_as_empty() {
        let rows = vec![vec![s("a")], vec![empty()], vec![empty()]];
        let schema = infer_sheet_schema(&sheet_with("t", rows));
        let col = &schema.columns[0];
        assert_eq!(col.inferred_type, InferredType::Empty);
        assert_eq!(col.cardinality, Cardinality::Empty);
        assert_eq!(col.null_count, 2);
    }
}
