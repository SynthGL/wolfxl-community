//! Sprint Π Pod Π-α (RFC-062) — typed specs + emitters for
//! `<rowBreaks>`, `<colBreaks>`, and `<sheetFormatPr>`.
//!
//! Mirrors the §10 dict shape produced by
//! ``Worksheet.to_rust_page_breaks_dict()`` and
//! ``Worksheet.to_rust_sheet_format_dict()`` on the Python side.
//! Each emitter returns the canonical XML bytes for splice via
//! `wolfxl_merger::merge_blocks`. Empty / default specs round-trip
//! to empty `Vec<u8>` so the patcher knows to skip the splice.
//!
//! Both the native writer (`emit::sheet_xml`) and the patcher
//! (`src/wolfxl/page_breaks.rs`) consume these.

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/// One `<brk>` element inside `<rowBreaks>` / `<colBreaks>`
/// (CT_Break, ECMA-376 §18.3.1.1).
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct BreakSpec {
    /// 1-based row or column index above/left of the break.
    pub id: u32,
    /// Optional min cell in the break range. Absence ⇒ Excel default
    /// (`0`, the column-A / row-1 sentinel).
    pub min: Option<u32>,
    /// Optional max cell in the break range. Absence ⇒ Excel default.
    pub max: Option<u32>,
    /// Manual break flag (the default in user-set breaks).
    pub man: bool,
    /// Printer-fitted break flag.
    pub pt: bool,
}

/// `<rowBreaks>` / `<colBreaks>` (CT_PageBreak §18.3.1.69).
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct PageBreakList {
    /// Stored count attribute (`count="…"`).
    pub count: u32,
    /// Stored manual-break-count attribute (`manualBreakCount="…"`).
    pub manual_break_count: u32,
    /// One entry per `<brk/>` child in the order Excel writes them.
    pub breaks: Vec<BreakSpec>,
}

impl PageBreakList {
    /// `True` iff this list carries zero breaks.
    pub fn is_empty(&self) -> bool {
        self.breaks.is_empty()
    }
}

/// `<sheetFormatPr>` (CT_SheetFormatPr §18.3.1.81).
#[derive(Debug, Clone, PartialEq)]
pub struct SheetFormatProperties {
    pub base_col_width: u32,
    pub default_col_width: Option<f64>,
    pub default_row_height: f64,
    pub custom_height: Option<bool>,
    pub zero_height: Option<bool>,
    pub thick_top: Option<bool>,
    pub thick_bottom: Option<bool>,
    pub outline_level_row: u32,
    pub outline_level_col: u32,
}

impl Default for SheetFormatProperties {
    fn default() -> Self {
        Self {
            base_col_width: 8,
            default_col_width: None,
            default_row_height: 15.0,
            custom_height: None,
            zero_height: None,
            thick_top: None,
            thick_bottom: None,
            outline_level_row: 0,
            outline_level_col: 0,
        }
    }
}

impl SheetFormatProperties {
    /// `True` iff every attribute is at its construction default.
    pub fn is_default(&self) -> bool {
        self == &SheetFormatProperties::default()
    }
}

// ---------------------------------------------------------------------------
// Emitters
// ---------------------------------------------------------------------------

fn fmt_float(value: f64) -> String {
    if value == value.trunc() {
        format!("{}", value as i64)
    } else {
        format!("{value}")
    }
}

fn emit_break(out: &mut String, brk: &BreakSpec) {
    out.push_str("<brk");
    out.push_str(&format!(" id=\"{}\"", brk.id));
    if let Some(n) = brk.min {
        out.push_str(&format!(" min=\"{n}\""));
    }
    if let Some(n) = brk.max {
        out.push_str(&format!(" max=\"{n}\""));
    }
    if brk.man {
        out.push_str(" man=\"1\"");
    }
    if brk.pt {
        out.push_str(" pt=\"1\"");
    }
    out.push_str("/>");
}

/// Emit `<rowBreaks count=… manualBreakCount=…>…</rowBreaks>`.
///
/// Returns empty bytes when the list carries zero breaks — Excel
/// expects the element to be absent in that case, not present with
/// no children.
pub fn emit_row_breaks(spec: &PageBreakList) -> Vec<u8> {
    if spec.is_empty() {
        return Vec::new();
    }
    let mut out = String::with_capacity(64 + 32 * spec.breaks.len());
    out.push_str(&format!(
        "<rowBreaks count=\"{}\" manualBreakCount=\"{}\">",
        spec.count, spec.manual_break_count
    ));
    for brk in &spec.breaks {
        emit_break(&mut out, brk);
    }
    out.push_str("</rowBreaks>");
    out.into_bytes()
}

/// Emit `<colBreaks count=… manualBreakCount=…>…</colBreaks>`.
pub fn emit_col_breaks(spec: &PageBreakList) -> Vec<u8> {
    if spec.is_empty() {
        return Vec::new();
    }
    let mut out = String::with_capacity(64 + 32 * spec.breaks.len());
    out.push_str(&format!(
        "<colBreaks count=\"{}\" manualBreakCount=\"{}\">",
        spec.count, spec.manual_break_count
    ));
    for brk in &spec.breaks {
        emit_break(&mut out, brk);
    }
    out.push_str("</colBreaks>");
    out.into_bytes()
}

/// Emit `<sheetFormatPr .../>`. Returns empty bytes when the spec
/// is at all-default — the writer's legacy hardcoded path keeps the
/// minimal `<sheetFormatPr defaultRowHeight="15"/>` form in that case.
pub fn emit_sheet_format_pr(spec: &SheetFormatProperties) -> Vec<u8> {
    if spec.is_default() {
        return Vec::new();
    }
    let mut out = String::with_capacity(96);
    out.push_str("<sheetFormatPr");
    // Excel orders attributes deterministically; we follow CT_SheetFormatPr
    // declaration order so byte-stable diffwriter tests are easy to write.
    if spec.base_col_width != 8 {
        out.push_str(&format!(" baseColWidth=\"{}\"", spec.base_col_width));
    }
    if let Some(w) = spec.default_col_width {
        out.push_str(&format!(" defaultColWidth=\"{}\"", fmt_float(w)));
    }
    out.push_str(&format!(
        " defaultRowHeight=\"{}\"",
        fmt_float(spec.default_row_height)
    ));
    if let Some(custom_height) = spec.custom_height {
        out.push_str(if custom_height {
            " customHeight=\"1\""
        } else {
            " customHeight=\"0\""
        });
    }
    if let Some(zero_height) = spec.zero_height {
        out.push_str(if zero_height {
            " zeroHeight=\"1\""
        } else {
            " zeroHeight=\"0\""
        });
    }
    if let Some(thick_top) = spec.thick_top {
        out.push_str(if thick_top {
            " thickTop=\"1\""
        } else {
            " thickTop=\"0\""
        });
    }
    if let Some(thick_bottom) = spec.thick_bottom {
        out.push_str(if thick_bottom {
            " thickBottom=\"1\""
        } else {
            " thickBottom=\"0\""
        });
    }
    if spec.outline_level_row != 0 {
        out.push_str(&format!(" outlineLevelRow=\"{}\"", spec.outline_level_row));
    }
    if spec.outline_level_col != 0 {
        out.push_str(&format!(" outlineLevelCol=\"{}\"", spec.outline_level_col));
    }
    out.push_str("/>");
    out.into_bytes()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn row_breaks_empty_returns_empty_bytes() {
        let spec = PageBreakList::default();
        assert!(emit_row_breaks(&spec).is_empty());
        assert!(emit_col_breaks(&spec).is_empty());
    }

    #[test]
    fn row_breaks_basic_one_break() {
        let spec = PageBreakList {
            count: 1,
            manual_break_count: 1,
            breaks: vec![BreakSpec {
                id: 5,
                min: Some(0),
                max: Some(16383),
                man: true,
                pt: false,
            }],
        };
        let bytes = emit_row_breaks(&spec);
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(xml.starts_with(r#"<rowBreaks count="1" manualBreakCount="1">"#));
        assert!(xml.contains(r#"<brk id="5" min="0" max="16383" man="1"/>"#));
        assert!(xml.ends_with("</rowBreaks>"));
    }

    #[test]
    fn col_breaks_three_breaks_preserve_order() {
        let spec = PageBreakList {
            count: 3,
            manual_break_count: 2,
            breaks: vec![
                BreakSpec {
                    id: 2,
                    min: None,
                    max: None,
                    man: true,
                    pt: false,
                },
                BreakSpec {
                    id: 5,
                    min: None,
                    max: None,
                    man: false,
                    pt: true,
                },
                BreakSpec {
                    id: 9,
                    min: None,
                    max: None,
                    man: true,
                    pt: false,
                },
            ],
        };
        let bytes = emit_col_breaks(&spec);
        let xml = std::str::from_utf8(&bytes).unwrap();
        // ids appear in the declared order
        let p2 = xml.find(r#"id="2""#).unwrap();
        let p5 = xml.find(r#"id="5""#).unwrap();
        let p9 = xml.find(r#"id="9""#).unwrap();
        assert!(p2 < p5 && p5 < p9);
        // The auto break gets pt="1" and no man attribute.
        assert!(xml.contains(r#"<brk id="5" pt="1"/>"#));
    }

    #[test]
    fn sheet_format_default_returns_empty() {
        let spec = SheetFormatProperties::default();
        assert!(emit_sheet_format_pr(&spec).is_empty());
        assert!(spec.is_default());
    }

    #[test]
    fn sheet_format_custom_row_height_emits() {
        let mut spec = SheetFormatProperties::default();
        spec.default_row_height = 20.0;
        let bytes = emit_sheet_format_pr(&spec);
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(xml.contains(r#"defaultRowHeight="20""#));
        assert!(!spec.is_default());
    }

    #[test]
    fn sheet_format_outline_levels_emit_when_nonzero() {
        let mut spec = SheetFormatProperties::default();
        spec.outline_level_row = 3;
        spec.outline_level_col = 2;
        let bytes = emit_sheet_format_pr(&spec);
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(xml.contains(r#"outlineLevelRow="3""#));
        assert!(xml.contains(r#"outlineLevelCol="2""#));
    }

    #[test]
    fn sheet_format_zero_height_thick_top_bottom_flags() {
        let mut spec = SheetFormatProperties::default();
        spec.zero_height = Some(true);
        spec.thick_top = Some(true);
        spec.thick_bottom = Some(true);
        let bytes = emit_sheet_format_pr(&spec);
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(xml.contains(r#"zeroHeight="1""#));
        assert!(xml.contains(r#"thickTop="1""#));
        assert!(xml.contains(r#"thickBottom="1""#));
    }

    #[test]
    fn sheet_format_default_col_width_emits_when_set() {
        let mut spec = SheetFormatProperties::default();
        spec.default_col_width = Some(12.5);
        let bytes = emit_sheet_format_pr(&spec);
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(xml.contains(r#"defaultColWidth="12.5""#));
    }

    #[test]
    fn breaks_omit_min_max_when_none() {
        let spec = PageBreakList {
            count: 1,
            manual_break_count: 1,
            breaks: vec![BreakSpec {
                id: 4,
                min: None,
                max: None,
                man: true,
                pt: false,
            }],
        };
        let bytes = emit_row_breaks(&spec);
        let xml = std::str::from_utf8(&bytes).unwrap();
        assert!(xml.contains(r#"<brk id="4" man="1"/>"#));
        assert!(!xml.contains("min="));
        assert!(!xml.contains("max="));
    }

    #[test]
    fn breaks_byte_stable_repeated_emits() {
        let spec = PageBreakList {
            count: 2,
            manual_break_count: 2,
            breaks: vec![
                BreakSpec {
                    id: 5,
                    min: Some(0),
                    max: Some(16383),
                    man: true,
                    pt: false,
                },
                BreakSpec {
                    id: 10,
                    min: Some(0),
                    max: Some(16383),
                    man: true,
                    pt: false,
                },
            ],
        };
        let a = emit_row_breaks(&spec);
        let b = emit_row_breaks(&spec);
        assert_eq!(a, b);
    }
}
