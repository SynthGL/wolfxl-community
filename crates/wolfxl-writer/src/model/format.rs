//! Style specifications + the deduplicating [`StylesBuilder`].
//!
//! Promoted from `src/wolfxl/styles.rs` (the modify-mode home). The types
//! are the same so modify-mode and write-mode describe the same style
//! primitives. `src/wolfxl/styles.rs` will become a re-export shim during
//! the Wave 2 styles-emitter work so one copy is canonical.
//!
//! # Find-or-create dedup
//!
//! OOXML's `xl/styles.xml` has an implicit dedup requirement: two cells
//! that want the same visual style should point at the same `<xf>` index.
//! If you mint a new `<xf>` per cell, Excel and LibreOffice still render
//! correctly, but the file size explodes and diffs with openpyxl-generated
//! files become noisy. The `StylesBuilder::intern_*` methods handle this.

use std::collections::HashMap;

/// Font specification. `Hash + Eq` so the builder can dedup by value.
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct FontSpec {
    pub bold: bool,
    pub italic: bool,
    /// Underline style, e.g. `"single"` or `"double"`.
    pub underline: Option<String>,
    pub strikethrough: bool,
    pub name: Option<String>,
    /// Stored as integer points (e.g. 11). Excel's schema allows a `Decimal`
    /// but in practice every real file uses whole points or halves
    /// (e.g. 10.5) — and `u32` here matches the modify-mode type.
    pub size: Option<u32>,
    /// ARGB, e.g. `"FFRRGGBB"`. Conversion from `"#RRGGBB"` or `"RRGGBB"`
    /// happens at the Python-Rust boundary (see the pyclass layer).
    pub color_rgb: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct FillSpec {
    /// Typical values: `"solid"`, `"none"`, `"gray125"`, `"darkHorizontal"`,
    /// etc. Default `""` (empty) is equivalent to `"none"`.
    pub pattern_type: String,
    pub fg_color_rgb: Option<String>,
    pub bg_color_rgb: Option<String>,
    /// When `Some`, this fill is a `<gradientFill>` and the pattern
    /// fields above are ignored on emit. OOXML allows exactly one of
    /// `<patternFill>` / `<gradientFill>` per `<fill>`.
    pub gradient: Option<GradientFillSpec>,
}

/// Gradient fill payload mirroring OOXML's `<gradientFill>` element.
///
/// All numeric fields are stored as canonical decimal strings so the
/// builder can dedup via `Hash + Eq`. Two cells with the same gradient
/// share one `<fill>` slot exactly like pattern fills.
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct GradientFillSpec {
    /// `"linear"` (default) or `"path"`. Linear uses `degree`; path uses
    /// `left`/`right`/`top`/`bottom` to position a focus rectangle.
    pub gradient_type: String,
    pub degree: String,
    pub left: String,
    pub right: String,
    pub top: String,
    pub bottom: String,
    pub stops: Vec<GradientStopSpec>,
}

/// One `<stop position="..."><color .../></stop>` inside a `<gradientFill>`.
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct GradientStopSpec {
    pub position: String,
    pub color_rgb: Option<String>,
}

/// One side of a cell border.
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct BorderSideSpec {
    /// `"thin"`, `"medium"`, `"thick"`, `"dashed"`, `"hair"`, etc.
    pub style: Option<String>,
    pub color_rgb: Option<String>,
}

/// Four-side border with optional diagonals (top-left / bottom-right).
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct BorderSpec {
    pub left: BorderSideSpec,
    pub right: BorderSideSpec,
    pub top: BorderSideSpec,
    pub bottom: BorderSideSpec,
    pub diagonal: BorderSideSpec,
    pub diagonal_up: bool,
    pub diagonal_down: bool,
}

/// Alignment (horizontal + vertical + wrap + indent + rotation).
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct AlignmentSpec {
    /// `"left"`, `"center"`, `"right"`, `"justify"`, `"fill"`, `"general"`.
    pub horizontal: Option<String>,
    /// `"top"`, `"center"`, `"bottom"`, `"justify"`.
    pub vertical: Option<String>,
    pub wrap_text: bool,
    pub indent: u32,
    /// Degrees 0-180. `255` is Excel's special "vertical text" marker.
    pub text_rotation: u32,
    pub shrink_to_fit: bool,
}

/// Cell-level protection flags. Lives as a `<protection>` child element of
/// `<xf>` and is gated on `applyProtection="1"`.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct ProtectionSpec {
    pub locked: bool,
    pub hidden: bool,
}

impl Default for ProtectionSpec {
    fn default() -> Self {
        Self {
            locked: true,
            hidden: false,
        }
    }
}

/// Full format description for one cell or named style.
///
/// Every field is optional — a `FormatSpec::default()` means "use the
/// default cell style, don't emit an `s` attribute". The builder maps
/// this onto the five underlying tables (fonts, fills, borders, numFmts,
/// cellXfs) and returns a single xf index.
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct FormatSpec {
    pub font: Option<FontSpec>,
    pub fill: Option<FillSpec>,
    pub border: Option<BorderSpec>,
    pub alignment: Option<AlignmentSpec>,
    /// A format code like `"0.00"`, `"$#,##0"`, `"yyyy-mm-dd"`, or one of
    /// Excel's 164 built-in format IDs referenced by name.
    pub number_format: Option<String>,
    /// Cell-level protection flags. `None` means "inherit the default
    /// (locked=true, hidden=false)" and emit no `<protection>` child.
    pub protection: Option<ProtectionSpec>,
}

/// Deduplicating styles builder.
///
/// # Reserved slots
///
/// - `fills[0]` = pattern `"none"` (required by Excel, always present)
/// - `fills[1]` = pattern `"gray125"` (required by Excel, always present)
/// - User fills start at index 2.
/// - `fonts[0]` is the default (`Calibri 11`).
/// - `borders[0]` is the empty border.
/// - `cellXfs[0]` is the default xf pointing at all zeros.
///
/// The `intern_*` methods insert these reserved entries on first use
/// and return indices relative to the full flat array.
#[derive(Debug, Clone)]
pub struct StylesBuilder {
    pub fonts: Vec<FontSpec>,
    pub fills: Vec<FillSpec>,
    pub borders: Vec<BorderSpec>,
    /// Custom number formats (id ≥ 164). Built-in ids 0-163 are not stored.
    pub num_fmts: Vec<(u32, String)>,
    /// The cellXfs table — one entry per distinct (font,fill,border,numFmt,align) combo.
    pub cell_xfs: Vec<XfRecord>,
    /// Differential-format records referenced by conditional-formatting rules.
    /// Index into this vec is what `<cfRule dxfId="N">` points at.
    pub dxfs: Vec<DxfRecord>,
    /// Workbook-level named cell styles beyond the built-in Normal style.
    pub named_styles: Vec<NamedStyleRecord>,

    // --- Dedup indices (not serialized) ---
    font_index: HashMap<FontSpec, u32>,
    fill_index: HashMap<FillSpec, u32>,
    border_index: HashMap<BorderSpec, u32>,
    num_fmt_index: HashMap<String, u32>,
    xf_index: HashMap<XfRecord, u32>,
    dxf_index: HashMap<DxfRecord, u32>,
    next_custom_num_fmt_id: u32,
}

impl Default for StylesBuilder {
    fn default() -> Self {
        let mut b = Self {
            fonts: Vec::new(),
            fills: Vec::new(),
            borders: Vec::new(),
            num_fmts: Vec::new(),
            cell_xfs: Vec::new(),
            dxfs: Vec::new(),
            named_styles: Vec::new(),
            font_index: HashMap::new(),
            fill_index: HashMap::new(),
            border_index: HashMap::new(),
            num_fmt_index: HashMap::new(),
            xf_index: HashMap::new(),
            dxf_index: HashMap::new(),
            // Excel reserves 0-163 for built-in format codes; custom ids start at 164.
            next_custom_num_fmt_id: 164,
        };

        // Reserved defaults — slot 0.
        b.fonts.push(FontSpec {
            size: Some(11),
            name: Some("Calibri".into()),
            ..Default::default()
        });
        b.font_index.insert(b.fonts[0].clone(), 0);

        // Reserved fills — slots 0 and 1 are mandatory.
        b.fills.push(FillSpec {
            pattern_type: "none".into(),
            ..Default::default()
        });
        b.fill_index.insert(b.fills[0].clone(), 0);
        b.fills.push(FillSpec {
            pattern_type: "gray125".into(),
            ..Default::default()
        });
        b.fill_index.insert(b.fills[1].clone(), 1);

        // Reserved border — slot 0.
        b.borders.push(BorderSpec::default());
        b.border_index.insert(b.borders[0].clone(), 0);

        // Reserved xf — slot 0 (all zeros, the default style).
        let default_xf = XfRecord::default();
        b.cell_xfs.push(default_xf.clone());
        b.xf_index.insert(default_xf, 0);

        b
    }
}

impl StylesBuilder {
    /// Intern a full `FormatSpec` and return its cellXfs index.
    ///
    /// The default `FormatSpec` always returns 0 (the "no style" sentinel),
    /// letting cells emit without the `s` attribute.
    pub fn intern_format(&mut self, spec: &FormatSpec) -> u32 {
        self.intern_format_with_xf_id(spec, 0)
    }

    /// Like [`intern_format`], but stamps the resulting XfRecord with a
    /// non-zero `xfId` so it points to a `<cellStyleXfs>` slot. Used by
    /// `cell.style = "Highlight"` to bind a cell's xf to a registered
    /// named style; the resulting `<xf>` element gets `xfId="N"` and
    /// the reader resurfaces the style's name from `<cellStyles>`.
    pub fn intern_format_with_xf_id(&mut self, spec: &FormatSpec, xf_id: u32) -> u32 {
        if xf_id == 0 && spec == &FormatSpec::default() {
            return 0;
        }
        let font_id = spec.font.as_ref().map(|f| self.intern_font(f)).unwrap_or(0);
        let fill_id = spec.fill.as_ref().map(|f| self.intern_fill(f)).unwrap_or(0);
        let border_id = spec
            .border
            .as_ref()
            .map(|b| self.intern_border(b))
            .unwrap_or(0);
        let num_fmt_id = spec
            .number_format
            .as_ref()
            .map(|n| self.intern_num_fmt(n))
            .unwrap_or(0);

        let record = XfRecord {
            font_id,
            fill_id,
            border_id,
            num_fmt_id,
            xf_id,
            alignment: spec.alignment.clone(),
            protection: spec.protection.clone(),
            apply_font: spec.font.is_some(),
            apply_fill: spec.fill.is_some(),
            apply_border: spec.border.is_some(),
            apply_number_format: spec.number_format.is_some(),
            apply_alignment: spec.alignment.is_some(),
            apply_protection: spec.protection.is_some(),
        };
        self.intern_xf(record)
    }

    pub fn intern_font(&mut self, font: &FontSpec) -> u32 {
        if let Some(&idx) = self.font_index.get(font) {
            return idx;
        }
        let idx = self.fonts.len() as u32;
        self.fonts.push(font.clone());
        self.font_index.insert(font.clone(), idx);
        idx
    }

    pub fn intern_fill(&mut self, fill: &FillSpec) -> u32 {
        if let Some(&idx) = self.fill_index.get(fill) {
            return idx;
        }
        let idx = self.fills.len() as u32;
        self.fills.push(fill.clone());
        self.fill_index.insert(fill.clone(), idx);
        idx
    }

    pub fn intern_border(&mut self, border: &BorderSpec) -> u32 {
        if let Some(&idx) = self.border_index.get(border) {
            return idx;
        }
        let idx = self.borders.len() as u32;
        self.borders.push(border.clone());
        self.border_index.insert(border.clone(), idx);
        idx
    }

    /// Intern a number format string. Returns a built-in id (0-163) for
    /// codes that match Excel's built-in set, otherwise mints a new
    /// custom id starting at 164.
    pub fn intern_num_fmt(&mut self, code: &str) -> u32 {
        if let Some(builtin) = builtin_num_fmt_id(code) {
            return builtin;
        }
        if let Some(&idx) = self.num_fmt_index.get(code) {
            return idx;
        }
        let id = self.next_custom_num_fmt_id;
        self.next_custom_num_fmt_id += 1;
        self.num_fmts.push((id, code.to_string()));
        self.num_fmt_index.insert(code.to_string(), id);
        id
    }

    fn intern_xf(&mut self, record: XfRecord) -> u32 {
        if let Some(&idx) = self.xf_index.get(&record) {
            return idx;
        }
        let idx = self.cell_xfs.len() as u32;
        self.cell_xfs.push(record.clone());
        self.xf_index.insert(record, idx);
        idx
    }

    /// Intern a differential-format record and return its index into
    /// `<dxfs>`. Two rules pointing at the same `DxfRecord` share an
    /// index, same dedup story as `intern_font` / `intern_fill` / …
    pub fn intern_dxf(&mut self, dxf: &DxfRecord) -> u32 {
        if let Some(&idx) = self.dxf_index.get(dxf) {
            return idx;
        }
        let idx = self.dxfs.len() as u32;
        self.dxfs.push(dxf.clone());
        self.dxf_index.insert(dxf.clone(), idx);
        idx
    }

    /// Register a workbook-level named style by name.
    pub fn add_named_style(&mut self, name: &str) {
        if name.is_empty() || name == "Normal" {
            return;
        }
        if self.named_styles.iter().any(|style| style.name == name) {
            return;
        }
        self.named_styles.push(NamedStyleRecord {
            name: name.to_string(),
        });
    }

    /// Resolve a named-style name to its `<cellStyleXfs>` slot.
    ///
    /// `"Normal"` always resolves to slot 0 (Excel's reserved default).
    /// User-registered styles map to slot `1 + position`. Returns `None`
    /// for unknown names so callers can decide whether to skip the xfId
    /// stamp or auto-register first.
    pub fn xf_id_for_named_style(&self, name: &str) -> Option<u32> {
        if name == "Normal" {
            return Some(0);
        }
        self.named_styles
            .iter()
            .position(|style| style.name == name)
            .map(|idx| 1 + idx as u32)
    }
}

/// One workbook-level named cell style.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct NamedStyleRecord {
    pub name: String,
}

/// One row of the `<cellXfs>` table. Two cells with the same `XfRecord`
/// share an index (that's the whole point of interning).
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct XfRecord {
    pub font_id: u32,
    pub fill_id: u32,
    pub border_id: u32,
    pub num_fmt_id: u32,
    /// `xfId` attr on the `<xf>` element. Points to a `<cellStyleXfs>`
    /// entry; 0 means the default Normal style. Cells that opt into a
    /// user-defined named style (via `cell.style = "Highlight"`) carry
    /// a non-zero `xf_id`, which is what `cell.style` resurfaces on
    /// load via the reader's `<cellStyles>` lookup.
    pub xf_id: u32,
    pub alignment: Option<AlignmentSpec>,
    pub protection: Option<ProtectionSpec>,
    pub apply_font: bool,
    pub apply_fill: bool,
    pub apply_border: bool,
    pub apply_number_format: bool,
    pub apply_alignment: bool,
    pub apply_protection: bool,
}

/// One entry in `<dxfs>` — differential formatting for conditional
/// formatting rules. Unlike [`XfRecord`], a dxf does NOT carry an
/// alignment or number-format override (those aren't valid in OOXML's
/// dxf schema), just the visual overrides — font / fill / border.
/// Fields are `Option` so a CF rule can say "make it bold" without
/// touching the fill or border.
#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct DxfRecord {
    pub font: Option<FontSpec>,
    pub fill: Option<FillSpec>,
    pub border: Option<BorderSpec>,
}

/// Excel's 164 built-in number-format slots. Returns `Some(id)` if `code`
/// matches one (and thus needs no custom `<numFmt>` entry).
///
/// The subset covered here is the "always-present" set Excel hard-codes —
/// the full list (Excel/OOXML spec Annex A.2) is fine to extend later.
/// Codes not on this list get a custom id 164+.
pub fn builtin_num_fmt_id(code: &str) -> Option<u32> {
    match code {
        "General" => Some(0),
        "0" => Some(1),
        "0.00" => Some(2),
        "#,##0" => Some(3),
        "#,##0.00" => Some(4),
        "\"$\"#,##0_);(\"$\"#,##0)" => Some(5),
        "\"$\"#,##0_);[Red](\"$\"#,##0)" => Some(6),
        "\"$\"#,##0.00_);(\"$\"#,##0.00)" => Some(7),
        "\"$\"#,##0.00_);[Red](\"$\"#,##0.00)" => Some(8),
        "0%" => Some(9),
        "0.00%" => Some(10),
        "0.00E+00" => Some(11),
        "# ?/?" => Some(12),
        "# ??/??" => Some(13),
        "mm-dd-yy" | "m/d/yy" | "m/d/yyyy" => Some(14),
        "d-mmm-yy" => Some(15),
        "d-mmm" => Some(16),
        "mmm-yy" => Some(17),
        "h:mm AM/PM" => Some(18),
        "h:mm:ss AM/PM" => Some(19),
        "h:mm" => Some(20),
        "h:mm:ss" => Some(21),
        "m/d/yy h:mm" => Some(22),
        "#,##0_);(#,##0)" => Some(37),
        "#,##0_);[Red](#,##0)" => Some(38),
        "#,##0.00_);(#,##0.00)" => Some(39),
        "#,##0.00_);[Red](#,##0.00)" => Some(40),
        r#"_(* #,##0_);_(* \(#,##0\);_(* "-"_);_(@_)"# => Some(41),
        r#"_("$"* #,##0_);_("$"* \(#,##0\);_("$"* "-"_);_(@_)"# => Some(42),
        r#"_(* #,##0.00_);_(* \(#,##0.00\);_(* "-"??_);_(@_)"# => Some(43),
        r#"_("$"* #,##0.00_)_("$"* \(#,##0.00\)_("$"* "-"??_)_(@_)"# => Some(44),
        "mm:ss" => Some(45),
        "[h]:mm:ss" => Some(46),
        "mmss.0" => Some(47),
        "##0.0E+0" => Some(48),
        "@" => Some(49),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_format_returns_zero() {
        let mut b = StylesBuilder::default();
        assert_eq!(b.intern_format(&FormatSpec::default()), 0);
    }

    #[test]
    fn identical_format_specs_share_an_index() {
        let mut b = StylesBuilder::default();
        let spec = FormatSpec {
            font: Some(FontSpec {
                bold: true,
                ..Default::default()
            }),
            ..Default::default()
        };
        let a = b.intern_format(&spec);
        let b_idx = b.intern_format(&spec);
        assert_eq!(a, b_idx);
        assert!(a >= 1, "non-default spec should get non-zero xf id");
    }

    #[test]
    fn fills_reserve_slots_zero_and_one() {
        let b = StylesBuilder::default();
        assert_eq!(b.fills[0].pattern_type, "none");
        assert_eq!(b.fills[1].pattern_type, "gray125");
    }

    #[test]
    fn custom_num_fmt_gets_id_164_plus() {
        let mut b = StylesBuilder::default();
        let id = b.intern_num_fmt("0.0000");
        assert!(id >= 164);
    }

    #[test]
    fn builtin_num_fmt_shortcircuits() {
        let mut b = StylesBuilder::default();
        let id = b.intern_num_fmt("0.00");
        assert_eq!(id, 2);
        // Also should not add a custom entry.
        assert!(b.num_fmts.is_empty());
    }

    #[test]
    fn xf_id_for_named_style_resolves_normal_and_custom() {
        let mut b = StylesBuilder::default();
        // Normal always maps to slot 0 (Excel's reserved default).
        assert_eq!(b.xf_id_for_named_style("Normal"), Some(0));
        // Unknown names return None.
        assert_eq!(b.xf_id_for_named_style("Highlight"), None);
        // Registered styles map to 1 + position.
        b.add_named_style("Highlight");
        b.add_named_style("Total");
        assert_eq!(b.xf_id_for_named_style("Highlight"), Some(1));
        assert_eq!(b.xf_id_for_named_style("Total"), Some(2));
    }

    #[test]
    fn intern_format_with_xf_id_threads_xf_id_into_record() {
        let mut b = StylesBuilder::default();
        b.add_named_style("Highlight");
        let spec = FormatSpec {
            font: Some(FontSpec {
                bold: true,
                ..Default::default()
            }),
            ..Default::default()
        };
        let xf_idx = b.intern_format_with_xf_id(&spec, 1);
        assert!(
            xf_idx >= 1,
            "non-default spec should not collide with slot 0"
        );
        assert_eq!(b.cell_xfs[xf_idx as usize].xf_id, 1);
    }
}
