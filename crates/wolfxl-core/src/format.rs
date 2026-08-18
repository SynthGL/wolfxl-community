//! Number-format detection and cell-value rendering.
//!
//! Mirrors the format-category logic that the PyO3 backend in `wolfxl` carries
//! internally. Kept duplicated for now so wolfxl-core stays free of PyO3; the
//! plan is to converge the two once the CLI is shipping.

use crate::cell::{Cell, CellValue};

/// Coarse classification of an Excel number format - what an agent needs to
/// know to render a value sensibly.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FormatCategory {
    General,
    Integer,
    Float,
    Percentage,
    Currency,
    Date,
    Time,
    DateTime,
    Scientific,
    Text,
}

impl FormatCategory {
    pub fn as_str(self) -> &'static str {
        match self {
            FormatCategory::General => "general",
            FormatCategory::Integer => "integer",
            FormatCategory::Float => "float",
            FormatCategory::Percentage => "percentage",
            FormatCategory::Currency => "currency",
            FormatCategory::Date => "date",
            FormatCategory::Time => "time",
            FormatCategory::DateTime => "datetime",
            FormatCategory::Scientific => "scientific",
            FormatCategory::Text => "text",
        }
    }
}

/// Classify an Excel number-format string. Best-effort heuristic; matches the
/// categories the agent-facing tools care about (`peek`, `schema`).
pub fn classify_format(fmt: &str) -> FormatCategory {
    if fmt.is_empty() || fmt.eq_ignore_ascii_case("general") {
        return FormatCategory::General;
    }
    if fmt == "@" {
        return FormatCategory::Text;
    }
    // Currency markers (check raw fmt — `[$-409]` carries the locale tag).
    if fmt.contains('$')
        || fmt.contains('€')
        || fmt.contains('£')
        || fmt.contains('¥')
        || fmt.contains("[$")
    {
        return FormatCategory::Currency;
    }
    // Strip `[...]` segments before the date/time substring scan: tags like
    // `[Red]` or `[h]` contain `d` and `h` which would otherwise trigger the
    // date / time heuristics on a plain numeric format such as
    // `#,##0_);[Red](#,##0)`.
    let stripped = strip_bracketed_tags(fmt);
    if stripped.contains('%') {
        return FormatCategory::Percentage;
    }
    if stripped.contains('E') && (stripped.contains("E+") || stripped.contains("E-")) {
        return FormatCategory::Scientific;
    }
    let lower = stripped.to_ascii_lowercase();
    let has_date = lower.contains('y') || lower.contains('d') || lower.contains("mmm");
    let has_time = lower.contains('h') || lower.contains(":mm") || lower.contains(':');
    match (has_date, has_time) {
        (true, true) => FormatCategory::DateTime,
        (true, false) => FormatCategory::Date,
        (false, true) => FormatCategory::Time,
        _ => {
            if stripped.contains('.') {
                FormatCategory::Float
            } else if stripped.chars().any(|c| c == '0' || c == '#') {
                FormatCategory::Integer
            } else {
                FormatCategory::General
            }
        }
    }
}

/// Remove `[...]` segments from an Excel format code so substring-based
/// scans don't get tripped up by characters inside color/locale tags.
fn strip_bracketed_tags(fmt: &str) -> String {
    let mut out = String::with_capacity(fmt.len());
    let mut depth = 0usize;
    for ch in fmt.chars() {
        match ch {
            '[' => depth += 1,
            ']' if depth > 0 => depth -= 1,
            _ if depth == 0 => out.push(ch),
            _ => {}
        }
    }
    out
}

/// Render a [`Cell`] for human/agent display, respecting its number format.
///
/// This is intentionally lossy in places where Excel's full format string is
/// richer than what an agent needs. The goal: a sensible default that beats
/// raw `Display` of the underlying value.
pub fn format_cell(cell: &Cell) -> String {
    let number_format = cell.number_format.as_deref();
    let category = cell
        .number_format
        .as_deref()
        .map(classify_format)
        .unwrap_or(FormatCategory::General);

    match (&cell.value, category) {
        (CellValue::Empty, _) => String::new(),
        (CellValue::String(s), _) => s.clone(),
        (CellValue::Bool(b), _) => if *b { "TRUE" } else { "FALSE" }.to_string(),
        (CellValue::Error(e), _) => e.clone(),
        (CellValue::Date(d), _) => d.format("%Y-%m-%d").to_string(),
        (CellValue::DateTime(dt), _) => dt.format("%Y-%m-%d %H:%M:%S").to_string(),
        (CellValue::Time(t), _) => t.format("%H:%M:%S").to_string(),

        (CellValue::Int(n), FormatCategory::Currency) => {
            format_currency(*n as f64, 2, currency_symbol(number_format))
        }
        (CellValue::Float(n), FormatCategory::Currency) => {
            format_currency(*n, 2, currency_symbol(number_format))
        }

        (CellValue::Int(n), FormatCategory::Percentage) => format_percentage(*n as f64, 1),
        (CellValue::Float(n), FormatCategory::Percentage) => format_percentage(*n, 1),

        (CellValue::Int(n), _) => format_with_grouping(*n),
        (CellValue::Float(n), FormatCategory::Integer) => format_with_grouping(n.round() as i64),
        (CellValue::Float(n), FormatCategory::Scientific) => format!("{:.4E}", n),
        (CellValue::Float(n), _) => trim_float(*n),
    }
}

fn currency_symbol(fmt: Option<&str>) -> &'static str {
    let Some(fmt) = fmt else {
        return "$";
    };
    if fmt.contains('€') {
        "€"
    } else if fmt.contains('£') {
        "£"
    } else if fmt.contains('¥') {
        "¥"
    } else {
        "$"
    }
}

fn format_currency(value: f64, decimals: usize, symbol: &str) -> String {
    // Round once on a single scaled integer so 1.995 carries to 2.00, not 1.100.
    // Splitting `trunc()` and `fract()` separately drops the carry.
    let sign = if value < 0.0 { "-" } else { "" };
    let scale = 10u64.pow(decimals as u32);
    let scaled = (value.abs() * scale as f64).round() as u64;
    let whole = scaled / scale;
    let frac = scaled % scale;
    format!(
        "{}{}{}.{:0width$}",
        sign,
        symbol,
        group_thousands(whole),
        frac,
        width = decimals
    )
}

fn format_percentage(value: f64, decimals: usize) -> String {
    format!("{:.*}%", decimals, value * 100.0)
}

fn format_with_grouping(value: i64) -> String {
    if value < 0 {
        format!("-{}", group_thousands(value.unsigned_abs()))
    } else {
        group_thousands(value as u64)
    }
}

fn group_thousands(mut n: u64) -> String {
    if n == 0 {
        return "0".to_string();
    }
    let mut parts: Vec<String> = Vec::new();
    while n > 0 {
        let chunk = n % 1000;
        n /= 1000;
        if n > 0 {
            parts.push(format!("{:03}", chunk));
        } else {
            parts.push(chunk.to_string());
        }
    }
    parts.reverse();
    parts.join(",")
}

fn trim_float(n: f64) -> String {
    if n.fract() == 0.0 && n.abs() < 1e15 {
        format!("{:.1}", n)
    } else {
        let s = format!("{:.6}", n);
        s.trim_end_matches('0').trim_end_matches('.').to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classify_known_formats() {
        assert_eq!(classify_format(""), FormatCategory::General);
        assert_eq!(classify_format("General"), FormatCategory::General);
        assert_eq!(classify_format("@"), FormatCategory::Text);
        assert_eq!(classify_format("0%"), FormatCategory::Percentage);
        assert_eq!(classify_format("0.00%"), FormatCategory::Percentage);
        assert_eq!(classify_format("$#,##0.00"), FormatCategory::Currency);
        assert_eq!(classify_format("[$-409]#,##0.00"), FormatCategory::Currency);
        assert_eq!(classify_format("yyyy-mm-dd"), FormatCategory::Date);
        assert_eq!(classify_format("h:mm:ss"), FormatCategory::Time);
        assert_eq!(classify_format("yyyy-mm-dd h:mm"), FormatCategory::DateTime);
        assert_eq!(classify_format("0.00E+00"), FormatCategory::Scientific);
        assert_eq!(classify_format("0.00"), FormatCategory::Float);
        assert_eq!(classify_format("#,##0"), FormatCategory::Integer);
    }

    #[test]
    fn bracketed_tags_dont_trigger_date_or_time_heuristic() {
        // `[Red]` contains `d`, which previously misclassified the format
        // as Date. `[h]:mm:ss` legitimately encodes elapsed-hour time and
        // should still classify as Time, but any non-time `[...]` tag
        // should be ignored by the date/time scan.
        assert_eq!(
            classify_format("#,##0_);[Red](#,##0)"),
            FormatCategory::Integer
        );
        assert_eq!(classify_format("0.00;[Red]-0.00"), FormatCategory::Float);
        assert_eq!(classify_format("[h]:mm:ss"), FormatCategory::Time);
    }

    #[test]
    fn currency_render() {
        let cell = Cell {
            value: CellValue::Float(1234567.5),
            number_format: Some("$#,##0.00".into()),
        };
        assert_eq!(format_cell(&cell), "$1,234,567.50");

        let neg = Cell {
            value: CellValue::Float(-42.0),
            number_format: Some("$#,##0.00".into()),
        };
        assert_eq!(format_cell(&neg), "-$42.00");
    }

    #[test]
    fn currency_render_preserves_common_symbols() {
        let euro = Cell {
            value: CellValue::Float(1234.5),
            number_format: Some("€#,##0.00".into()),
        };
        assert_eq!(format_cell(&euro), "€1,234.50");

        let pound = Cell {
            value: CellValue::Float(-42.0),
            number_format: Some("[$£-809]#,##0.00".into()),
        };
        assert_eq!(format_cell(&pound), "-£42.00");

        let yen = Cell {
            value: CellValue::Int(5000),
            number_format: Some("¥#,##0".into()),
        };
        assert_eq!(format_cell(&yen), "¥5,000.00");
    }

    #[test]
    fn currency_handles_carry_on_rounding() {
        // Pre-fix: 1.995 → "$1.100" because frac rounded to 100 without carrying.
        let cell = Cell {
            value: CellValue::Float(1.995),
            number_format: Some("$#,##0.00".into()),
        };
        assert_eq!(format_cell(&cell), "$2.00");

        // Carry across the thousands boundary too.
        let cell = Cell {
            value: CellValue::Float(999.999),
            number_format: Some("$#,##0.00".into()),
        };
        assert_eq!(format_cell(&cell), "$1,000.00");
    }

    #[test]
    fn percentage_render() {
        let cell = Cell {
            value: CellValue::Float(0.234),
            number_format: Some("0.0%".into()),
        };
        assert_eq!(format_cell(&cell), "23.4%");
    }

    #[test]
    fn integer_grouping() {
        let cell = Cell {
            value: CellValue::Int(1234567),
            number_format: None,
        };
        assert_eq!(format_cell(&cell), "1,234,567");
    }

    #[test]
    fn empty_cell_renders_blank() {
        assert_eq!(format_cell(&Cell::empty()), "");
    }
}
