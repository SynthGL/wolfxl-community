//! Small formatting helpers for chart XML emission.

pub(super) fn bool_str(b: bool) -> &'static str {
    if b {
        "1"
    } else {
        "0"
    }
}

/// Strip the leading alpha from an 8-char ARGB color, leaving the 6-char
/// RGB. DrawingML's `<a:srgbClr val>` expects RGB, not ARGB.
pub(super) fn strip_alpha(c: &str) -> String {
    if c.len() == 8 {
        c[2..].to_string()
    } else {
        c.to_string()
    }
}

/// Format f64 deterministically for OOXML: drop trailing zeros so `1.0`
/// becomes `"1"`, but keep precision for fractional values.
pub(super) fn fmt_f64(v: f64) -> String {
    if v == v.trunc() && v.abs() < 1e16 {
        format!("{}", v as i64)
    } else {
        // Rust's default display keeps the current chart XML expectations.
        format!("{v}")
    }
}
