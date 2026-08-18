//! Pure-Rust serializers for the 5 sheet-setup child elements of
//! CT_Worksheet — `<sheetView>`, `<sheetProtection>`, `<printOptions>`,
//! `<pageMargins>`, `<pageSetup>`, `<headerFooter>`. (RFC-055 §3 / §10.)
//!
//! The structs in this module mirror the §10 dict shape produced by
//! `Worksheet.to_rust_setup_dict()` on the Python side. Each emitter
//! returns the canonical XML bytes for splice into a sheet via
//! `wolfxl_merger::merge_blocks`. Empty / default specs round-trip to
//! empty `Vec<u8>` so the patcher knows to skip the `SheetBlock`.
//!
//! Both the native writer (`emit::sheet_xml`) and the patcher
//! (`src/wolfxl/sheet_setup.rs`) consume these.

use crate::xml_escape;

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/// `<pageSetup>` attribute group (CT_PageSetup, ECMA-376 §18.3.1.51).
#[derive(Debug, Clone, Default, PartialEq)]
pub struct PageSetupSpec {
    pub orientation: Option<String>,
    pub paper_size: Option<u32>,
    pub fit_to_width: Option<u32>,
    pub fit_to_height: Option<u32>,
    pub scale: Option<u32>,
    pub first_page_number: Option<u32>,
    pub horizontal_dpi: Option<u32>,
    pub vertical_dpi: Option<u32>,
    pub cell_comments: Option<String>,
    pub errors: Option<String>,
    pub use_first_page_number: Option<bool>,
    pub paper_height: Option<String>,
    pub paper_width: Option<String>,
    pub page_order: Option<String>,
    pub use_printer_defaults: Option<bool>,
    pub black_and_white: Option<bool>,
    pub draft: Option<bool>,
    pub copies: Option<u32>,
}

/// `<printOptions>` toggles (CT_PrintOptions, ECMA-376 §18.3.1.70).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct PrintOptionsSpec {
    pub horizontal_centered: Option<bool>,
    pub vertical_centered: Option<bool>,
    pub headings: Option<bool>,
    pub grid_lines: Option<bool>,
    pub grid_lines_set: Option<bool>,
}

/// `<pageMargins>` (CT_PageMargins, ECMA-376 §18.3.1.49). All values
/// in inches per OOXML.
#[derive(Debug, Clone, PartialEq)]
pub struct PageMarginsSpec {
    pub left: f64,
    pub right: f64,
    pub top: f64,
    pub bottom: f64,
    pub header: f64,
    pub footer: f64,
}

impl Default for PageMarginsSpec {
    fn default() -> Self {
        Self {
            left: 0.7,
            right: 0.7,
            top: 0.75,
            bottom: 0.75,
            header: 0.3,
            footer: 0.3,
        }
    }
}

/// One header/footer segment block (left / center / right).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct HeaderFooterItemSpec {
    pub left: Option<String>,
    pub center: Option<String>,
    pub right: Option<String>,
}

impl HeaderFooterItemSpec {
    fn is_empty(&self) -> bool {
        self.left.is_none() && self.center.is_none() && self.right.is_none()
    }

    /// Compose the segments back into the OOXML text form
    /// (`&Lleft&Ccenter&Rright`).
    fn compose(&self) -> String {
        let mut out = String::new();
        if let Some(ref s) = self.left {
            out.push_str("&L");
            out.push_str(s);
        }
        if let Some(ref s) = self.center {
            out.push_str("&C");
            out.push_str(s);
        }
        if let Some(ref s) = self.right {
            out.push_str("&R");
            out.push_str(s);
        }
        out
    }
}

/// `<headerFooter>` (CT_HeaderFooter, ECMA-376 §18.3.1.36).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HeaderFooterSpec {
    pub odd_header: Option<HeaderFooterItemSpec>,
    pub odd_footer: Option<HeaderFooterItemSpec>,
    pub even_header: Option<HeaderFooterItemSpec>,
    pub even_footer: Option<HeaderFooterItemSpec>,
    pub first_header: Option<HeaderFooterItemSpec>,
    pub first_footer: Option<HeaderFooterItemSpec>,
    pub different_odd_even: bool,
    pub different_first: bool,
    pub scale_with_doc: bool,
    pub align_with_margins: bool,
}

impl Default for HeaderFooterSpec {
    fn default() -> Self {
        Self {
            odd_header: None,
            odd_footer: None,
            even_header: None,
            even_footer: None,
            first_header: None,
            first_footer: None,
            different_odd_even: false,
            different_first: false,
            scale_with_doc: true,
            align_with_margins: true,
        }
    }
}

/// `<pane>` child of `<sheetView>` (CT_Pane).
#[derive(Debug, Clone, PartialEq)]
pub struct PaneSpec {
    pub x_split: f64,
    pub y_split: f64,
    pub top_left_cell: String,
    pub active_pane: String,
    pub state: String,
}

impl Default for PaneSpec {
    fn default() -> Self {
        Self {
            x_split: 0.0,
            y_split: 0.0,
            top_left_cell: "A1".into(),
            active_pane: "topLeft".into(),
            state: "frozen".into(),
        }
    }
}

/// `<selection>` child of `<sheetView>` (CT_Selection).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SelectionSpec {
    pub active_cell: Option<String>,
    pub sqref: Option<String>,
    pub pane: Option<String>,
}

/// `<sheetView>` (CT_SheetView, ECMA-376 §18.3.1.85).
#[derive(Debug, Clone, PartialEq)]
pub struct SheetViewSpec {
    pub workbook_view_id: u32,
    pub zoom_scale: u32,
    pub zoom_scale_normal: u32,
    pub view: Option<String>,
    pub show_grid_lines: Option<bool>,
    pub show_row_col_headers: Option<bool>,
    pub show_outline_symbols: Option<bool>,
    pub show_zeros: Option<bool>,
    pub right_to_left: Option<bool>,
    pub tab_selected: Option<bool>,
    pub top_left_cell: Option<String>,
    pub pane: Option<PaneSpec>,
    pub selection: Vec<SelectionSpec>,
}

impl Default for SheetViewSpec {
    fn default() -> Self {
        Self {
            workbook_view_id: 0,
            zoom_scale: 100,
            zoom_scale_normal: 100,
            view: None,
            show_grid_lines: None,
            show_row_col_headers: None,
            show_outline_symbols: None,
            show_zeros: None,
            right_to_left: None,
            tab_selected: None,
            top_left_cell: None,
            pane: None,
            selection: Vec::new(),
        }
    }
}

/// `<sheetProtection>` (CT_SheetProtection, ECMA-376 §18.3.1.85).
///
/// `password_hash` is already-hashed by the Python side
/// (`wolfxl.utils.protection.hash_password`); the writer emits it
/// verbatim into the legacy `password=` attribute. Modern hash
/// fields (`algorithm_name` / `hash_value` / `salt_value` /
/// `spin_count`) live alongside the legacy hex string per
/// ECMA-376 spec rules.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SheetProtectionSpec {
    pub sheet: bool,
    pub objects: bool,
    pub scenarios: bool,
    pub format_cells: bool,
    pub format_columns: bool,
    pub format_rows: bool,
    pub insert_columns: bool,
    pub insert_rows: bool,
    pub insert_hyperlinks: bool,
    pub delete_columns: bool,
    pub delete_rows: bool,
    pub select_locked_cells: bool,
    pub sort: bool,
    pub auto_filter: bool,
    pub pivot_tables: bool,
    pub select_unlocked_cells: bool,
    pub password_hash: Option<String>,
    pub algorithm_name: Option<String>,
    pub hash_value: Option<String>,
    pub salt_value: Option<String>,
    pub spin_count: Option<u32>,
}

impl Default for SheetProtectionSpec {
    fn default() -> Self {
        // Excel UX defaults: when ws.protection is enabled, the
        // "allow these actions" toggles default to allowed. The
        // toggles only affect the *protected* operation set when
        // `sheet == true`.
        Self {
            sheet: false,
            objects: false,
            scenarios: false,
            format_cells: true,
            format_columns: true,
            format_rows: true,
            insert_columns: true,
            insert_rows: true,
            insert_hyperlinks: true,
            delete_columns: true,
            delete_rows: true,
            select_locked_cells: false,
            sort: true,
            auto_filter: true,
            pivot_tables: true,
            select_unlocked_cells: false,
            password_hash: None,
            algorithm_name: None,
            hash_value: None,
            salt_value: None,
            spin_count: None,
        }
    }
}

/// `print_titles` payload — workbook-scope `_xlnm.Print_Titles`
/// definedName composer input. Not emitted as a sheet XML block;
/// the workbook `<definedNames>` queue consumes it.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct PrintTitlesSpec {
    pub rows: Option<String>,
    pub cols: Option<String>,
}

/// Bundle of the 5 sheet-setup blocks for one worksheet. Either
/// field may be `None` — the corresponding element is suppressed
/// from the splice set.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct SheetSetupBlocks {
    pub sheet_view: Option<SheetViewSpec>,
    pub sheet_protection: Option<SheetProtectionSpec>,
    pub print_options: Option<PrintOptionsSpec>,
    pub page_margins: Option<PageMarginsSpec>,
    pub page_setup: Option<PageSetupSpec>,
    pub header_footer: Option<HeaderFooterSpec>,
    pub print_titles: Option<PrintTitlesSpec>,
}

impl SheetSetupBlocks {
    /// `True` iff every slot is `None`. Patcher uses this to short-circuit.
    pub fn is_empty(&self) -> bool {
        self.sheet_view.is_none()
            && self.sheet_protection.is_none()
            && self.print_options.is_none()
            && self.page_margins.is_none()
            && self.page_setup.is_none()
            && self.header_footer.is_none()
            && self.print_titles.is_none()
    }
}

// ---------------------------------------------------------------------------
// Emitters
// ---------------------------------------------------------------------------

fn push_attr(out: &mut String, key: &str, value: &str) {
    out.push(' ');
    out.push_str(key);
    out.push_str("=\"");
    out.push_str(&xml_escape::attr(value));
    out.push('"');
}

fn fmt_float(value: f64) -> String {
    // Excel-style: print integer values with no decimals, fractional
    // values with the natural representation. We use Rust's default
    // `{}` since OOXML accepts any valid `xsd:double`.
    if value == value.trunc() {
        format!("{}", value as i64)
    } else {
        format!("{value}")
    }
}

/// Emit `<pageMargins .../>`. Always emits all 6 attributes — Excel
/// expects them present even at default values for round-trip parity.
pub fn emit_page_margins(spec: &PageMarginsSpec) -> Vec<u8> {
    let mut out = String::with_capacity(96);
    out.push_str("<pageMargins");
    out.push_str(&format!(" left=\"{}\"", fmt_float(spec.left)));
    out.push_str(&format!(" right=\"{}\"", fmt_float(spec.right)));
    out.push_str(&format!(" top=\"{}\"", fmt_float(spec.top)));
    out.push_str(&format!(" bottom=\"{}\"", fmt_float(spec.bottom)));
    out.push_str(&format!(" header=\"{}\"", fmt_float(spec.header)));
    out.push_str(&format!(" footer=\"{}\"", fmt_float(spec.footer)));
    out.push_str("/>");
    out.into_bytes()
}

/// Emit `<printOptions .../>`. Returns empty bytes when every attribute
/// is unspecified.
pub fn emit_print_options(spec: &PrintOptionsSpec) -> Vec<u8> {
    let any_set = spec.horizontal_centered.is_some()
        || spec.vertical_centered.is_some()
        || spec.headings.is_some()
        || spec.grid_lines.is_some()
        || spec.grid_lines_set.is_some();
    if !any_set {
        return Vec::new();
    }

    let mut out = String::with_capacity(96);
    out.push_str("<printOptions");
    push_opt_bool(&mut out, "horizontalCentered", spec.horizontal_centered);
    push_opt_bool(&mut out, "verticalCentered", spec.vertical_centered);
    push_opt_bool(&mut out, "headings", spec.headings);
    push_opt_bool(&mut out, "gridLines", spec.grid_lines);
    push_opt_bool(&mut out, "gridLinesSet", spec.grid_lines_set);
    out.push_str("/>");
    out.into_bytes()
}

/// Emit `<pageSetup .../>`. Returns empty bytes when every attribute
/// is at its default (`None`) — Excel treats absence as "use defaults".
pub fn emit_page_setup(spec: &PageSetupSpec) -> Vec<u8> {
    let any_set = spec.orientation.is_some()
        || spec.paper_size.is_some()
        || spec.fit_to_width.is_some()
        || spec.fit_to_height.is_some()
        || spec.scale.is_some()
        || spec.first_page_number.is_some()
        || spec.horizontal_dpi.is_some()
        || spec.vertical_dpi.is_some()
        || spec.cell_comments.is_some()
        || spec.errors.is_some()
        || spec.use_first_page_number.is_some()
        || spec.paper_height.is_some()
        || spec.paper_width.is_some()
        || spec.page_order.is_some()
        || spec.use_printer_defaults.is_some()
        || spec.black_and_white.is_some()
        || spec.draft.is_some()
        || spec.copies.is_some();
    if !any_set {
        return Vec::new();
    }

    let mut out = String::with_capacity(192);
    out.push_str("<pageSetup");
    if let Some(n) = spec.paper_size {
        out.push_str(&format!(" paperSize=\"{n}\""));
    }
    if let Some(n) = spec.scale {
        out.push_str(&format!(" scale=\"{n}\""));
    }
    if let Some(n) = spec.first_page_number {
        out.push_str(&format!(" firstPageNumber=\"{n}\""));
    }
    if let Some(n) = spec.fit_to_width {
        out.push_str(&format!(" fitToWidth=\"{n}\""));
    }
    if let Some(n) = spec.fit_to_height {
        out.push_str(&format!(" fitToHeight=\"{n}\""));
    }
    if let Some(ref s) = spec.orientation {
        push_attr(&mut out, "orientation", s);
    }
    if let Some(b) = spec.use_printer_defaults {
        out.push_str(&format!(
            " usePrinterDefaults=\"{}\"",
            if b { "1" } else { "0" }
        ));
    }
    if let Some(b) = spec.black_and_white {
        out.push_str(&format!(" blackAndWhite=\"{}\"", if b { "1" } else { "0" }));
    }
    if let Some(b) = spec.draft {
        out.push_str(&format!(" draft=\"{}\"", if b { "1" } else { "0" }));
    }
    if let Some(ref s) = spec.cell_comments {
        push_attr(&mut out, "cellComments", s);
    }
    if let Some(b) = spec.use_first_page_number {
        out.push_str(&format!(
            " useFirstPageNumber=\"{}\"",
            if b { "1" } else { "0" }
        ));
    }
    if let Some(ref s) = spec.paper_height {
        push_attr(&mut out, "paperHeight", s);
    }
    if let Some(ref s) = spec.paper_width {
        push_attr(&mut out, "paperWidth", s);
    }
    if let Some(ref s) = spec.page_order {
        push_attr(&mut out, "pageOrder", s);
    }
    if let Some(ref s) = spec.errors {
        push_attr(&mut out, "errors", s);
    }
    if let Some(n) = spec.horizontal_dpi {
        out.push_str(&format!(" horizontalDpi=\"{n}\""));
    }
    if let Some(n) = spec.vertical_dpi {
        out.push_str(&format!(" verticalDpi=\"{n}\""));
    }
    if let Some(n) = spec.copies {
        out.push_str(&format!(" copies=\"{n}\""));
    }
    out.push_str("/>");
    out.into_bytes()
}

fn push_opt_bool(out: &mut String, key: &str, value: Option<bool>) {
    if let Some(b) = value {
        out.push_str(&format!(" {key}=\"{}\"", if b { "1" } else { "0" }));
    }
}

/// Emit `<headerFooter>`. Returns empty bytes when the spec is at
/// construction defaults (no segments + standard flags).
pub fn emit_header_footer(spec: &HeaderFooterSpec) -> Vec<u8> {
    let any_text = spec.odd_header.as_ref().map_or(false, |i| !i.is_empty())
        || spec.odd_footer.as_ref().map_or(false, |i| !i.is_empty())
        || spec.even_header.as_ref().map_or(false, |i| !i.is_empty())
        || spec.even_footer.as_ref().map_or(false, |i| !i.is_empty())
        || spec.first_header.as_ref().map_or(false, |i| !i.is_empty())
        || spec.first_footer.as_ref().map_or(false, |i| !i.is_empty());
    let any_flags_non_default = spec.different_odd_even
        || spec.different_first
        || !spec.scale_with_doc
        || !spec.align_with_margins;
    if !any_text && !any_flags_non_default {
        return Vec::new();
    }

    let mut out = String::with_capacity(256);
    out.push_str("<headerFooter");
    if spec.different_odd_even {
        out.push_str(" differentOddEven=\"1\"");
    }
    if spec.different_first {
        out.push_str(" differentFirst=\"1\"");
    }
    if !spec.scale_with_doc {
        out.push_str(" scaleWithDoc=\"0\"");
    }
    if !spec.align_with_margins {
        out.push_str(" alignWithMargins=\"0\"");
    }
    if !any_text {
        out.push_str("/>");
        return out.into_bytes();
    }
    out.push('>');

    fn emit_segment(out: &mut String, tag: &str, item: &Option<HeaderFooterItemSpec>) {
        if let Some(i) = item {
            if !i.is_empty() {
                out.push('<');
                out.push_str(tag);
                out.push('>');
                out.push_str(&xml_escape::text(&i.compose()));
                out.push_str("</");
                out.push_str(tag);
                out.push('>');
            }
        }
    }
    emit_segment(&mut out, "oddHeader", &spec.odd_header);
    emit_segment(&mut out, "oddFooter", &spec.odd_footer);
    emit_segment(&mut out, "evenHeader", &spec.even_header);
    emit_segment(&mut out, "evenFooter", &spec.even_footer);
    emit_segment(&mut out, "firstHeader", &spec.first_header);
    emit_segment(&mut out, "firstFooter", &spec.first_footer);
    out.push_str("</headerFooter>");
    out.into_bytes()
}

/// Emit `<sheetViews><sheetView .../></sheetViews>`. The wrapping
/// element is always present so the `SheetBlock::SheetViews` payload
/// matches the canonical CT_Worksheet child element. Returns empty
/// bytes when the spec is at construction defaults.
pub fn emit_sheet_views(spec: &SheetViewSpec) -> Vec<u8> {
    if is_default_sheet_view(spec) {
        return Vec::new();
    }
    let mut out = String::with_capacity(192);
    out.push_str("<sheetViews>");
    out.push_str("<sheetView");
    out.push_str(&format!(" workbookViewId=\"{}\"", spec.workbook_view_id));
    if let Some(show_grid_lines) = spec.show_grid_lines {
        out.push_str(if show_grid_lines {
            " showGridLines=\"1\""
        } else {
            " showGridLines=\"0\""
        });
    }
    if let Some(show_row_col_headers) = spec.show_row_col_headers {
        out.push_str(if show_row_col_headers {
            " showRowColHeaders=\"1\""
        } else {
            " showRowColHeaders=\"0\""
        });
    }
    if let Some(show_outline_symbols) = spec.show_outline_symbols {
        out.push_str(if show_outline_symbols {
            " showOutlineSymbols=\"1\""
        } else {
            " showOutlineSymbols=\"0\""
        });
    }
    if let Some(show_zeros) = spec.show_zeros {
        out.push_str(if show_zeros {
            " showZeros=\"1\""
        } else {
            " showZeros=\"0\""
        });
    }
    if let Some(right_to_left) = spec.right_to_left {
        out.push_str(if right_to_left {
            " rightToLeft=\"1\""
        } else {
            " rightToLeft=\"0\""
        });
    }
    if let Some(tab_selected) = spec.tab_selected {
        out.push_str(if tab_selected {
            " tabSelected=\"1\""
        } else {
            " tabSelected=\"0\""
        });
    }
    if let Some(ref v) = spec.view {
        if v != "normal" {
            push_attr(&mut out, "view", v);
        }
    }
    if spec.zoom_scale != 100 {
        out.push_str(&format!(" zoomScale=\"{}\"", spec.zoom_scale));
    }
    if spec.zoom_scale_normal != 100 {
        out.push_str(&format!(" zoomScaleNormal=\"{}\"", spec.zoom_scale_normal));
    }
    if let Some(ref s) = spec.top_left_cell {
        push_attr(&mut out, "topLeftCell", s);
    }

    // Children: <pane>, then <selection>...
    let has_children = spec.pane.is_some() || !spec.selection.is_empty();
    if !has_children {
        out.push_str("/>");
    } else {
        out.push('>');
        if let Some(p) = &spec.pane {
            out.push_str("<pane");
            if p.x_split != 0.0 {
                out.push_str(&format!(" xSplit=\"{}\"", fmt_float(p.x_split)));
            }
            if p.y_split != 0.0 {
                out.push_str(&format!(" ySplit=\"{}\"", fmt_float(p.y_split)));
            }
            push_attr(&mut out, "topLeftCell", &p.top_left_cell);
            push_attr(&mut out, "activePane", &p.active_pane);
            push_attr(&mut out, "state", &p.state);
            out.push_str("/>");
        }
        for sel in &spec.selection {
            out.push_str("<selection");
            if let Some(ref s) = sel.pane {
                push_attr(&mut out, "pane", s);
            }
            if let Some(ref s) = sel.active_cell {
                push_attr(&mut out, "activeCell", s);
            }
            if let Some(ref s) = sel.sqref {
                push_attr(&mut out, "sqref", s);
            }
            out.push_str("/>");
        }
        out.push_str("</sheetView>");
    }
    out.push_str("</sheetViews>");
    out.into_bytes()
}

fn is_default_sheet_view(s: &SheetViewSpec) -> bool {
    s.workbook_view_id == 0
        && s.zoom_scale == 100
        && s.zoom_scale_normal == 100
        && s.view.as_deref().map_or(true, |v| v == "normal")
        && s.show_grid_lines.is_none()
        && s.show_row_col_headers.is_none()
        && s.show_outline_symbols.is_none()
        && s.show_zeros.is_none()
        && s.right_to_left.is_none()
        && s.tab_selected.is_none()
        && s.top_left_cell.is_none()
        && s.pane.is_none()
        && s.selection.is_empty()
}

/// Emit `<sheetProtection .../>`. Returns empty bytes when the spec
/// is at its construction defaults (no protection requested).
pub fn emit_sheet_protection(spec: &SheetProtectionSpec) -> Vec<u8> {
    if !spec.sheet
        && spec.password_hash.is_none()
        && spec.algorithm_name.is_none()
        && spec.hash_value.is_none()
        && spec.salt_value.is_none()
        && spec.spin_count.is_none()
    {
        // Per RFC-055 §2.6, `sheet=False` with no password / hash
        // material means "no protection"; suppress the element entirely.
        return Vec::new();
    }

    let mut out = String::with_capacity(256);
    out.push_str("<sheetProtection");
    if let Some(ref s) = spec.algorithm_name {
        push_attr(&mut out, "algorithmName", s);
    }
    if let Some(ref s) = spec.hash_value {
        push_attr(&mut out, "hashValue", s);
    }
    if let Some(ref s) = spec.salt_value {
        push_attr(&mut out, "saltValue", s);
    }
    if let Some(n) = spec.spin_count {
        out.push_str(&format!(" spinCount=\"{n}\""));
    }
    if let Some(ref pw) = spec.password_hash {
        // Empty password hash ("") should NOT be emitted — the
        // Python side returns "" for "no password set". Skip.
        if !pw.is_empty() {
            push_attr(&mut out, "password", pw);
        }
    }
    if spec.sheet {
        out.push_str(" sheet=\"1\"");
    }
    if spec.objects {
        out.push_str(" objects=\"1\"");
    }
    if spec.scenarios {
        out.push_str(" scenarios=\"1\"");
    }
    // The "format/insert/delete/sort/etc." flags default to True
    // (allowed); only emit when False (forbidden).
    bool_attr(&mut out, "formatCells", spec.format_cells, true);
    bool_attr(&mut out, "formatColumns", spec.format_columns, true);
    bool_attr(&mut out, "formatRows", spec.format_rows, true);
    bool_attr(&mut out, "insertColumns", spec.insert_columns, true);
    bool_attr(&mut out, "insertRows", spec.insert_rows, true);
    bool_attr(&mut out, "insertHyperlinks", spec.insert_hyperlinks, true);
    bool_attr(&mut out, "deleteColumns", spec.delete_columns, true);
    bool_attr(&mut out, "deleteRows", spec.delete_rows, true);
    if spec.select_locked_cells {
        // Default is False (allowed); emit only when True (forbidden).
        out.push_str(" selectLockedCells=\"1\"");
    }
    bool_attr(&mut out, "sort", spec.sort, true);
    bool_attr(&mut out, "autoFilter", spec.auto_filter, true);
    bool_attr(&mut out, "pivotTables", spec.pivot_tables, true);
    if spec.select_unlocked_cells {
        out.push_str(" selectUnlockedCells=\"1\"");
    }
    out.push_str("/>");
    out.into_bytes()
}

/// Emit `attr="0"` when `value != default_value`, where default is
/// True. Used for `<sheetProtection>` "allow" toggles.
fn bool_attr(out: &mut String, key: &str, value: bool, default_true: bool) {
    if value == default_true {
        return;
    }
    out.push(' ');
    out.push_str(key);
    out.push_str(if value { "=\"1\"" } else { "=\"0\"" });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // ---- pageMargins -----------------------------------------------------
    #[test]
    fn page_margins_default_emits_all_six_attrs() {
        let bytes = emit_page_margins(&PageMarginsSpec::default());
        let text = String::from_utf8(bytes).unwrap();
        assert_eq!(
            text,
            "<pageMargins left=\"0.7\" right=\"0.7\" top=\"0.75\" \
             bottom=\"0.75\" header=\"0.3\" footer=\"0.3\"/>"
        );
    }

    #[test]
    fn page_margins_custom_values() {
        let spec = PageMarginsSpec {
            left: 1.0,
            right: 1.5,
            top: 2.0,
            bottom: 2.0,
            header: 0.5,
            footer: 0.5,
        };
        let text = String::from_utf8(emit_page_margins(&spec)).unwrap();
        assert!(text.contains("left=\"1\""));
        assert!(text.contains("right=\"1.5\""));
        assert!(text.contains("top=\"2\""));
        assert!(text.contains("header=\"0.5\""));
    }

    // ---- pageSetup -------------------------------------------------------
    #[test]
    fn page_setup_empty_yields_empty() {
        assert!(emit_page_setup(&PageSetupSpec::default()).is_empty());
    }

    #[test]
    fn page_setup_orientation_only() {
        let spec = PageSetupSpec {
            orientation: Some("landscape".into()),
            ..Default::default()
        };
        let text = String::from_utf8(emit_page_setup(&spec)).unwrap();
        assert!(text.contains("orientation=\"landscape\""));
    }

    #[test]
    fn page_setup_paper_and_scale() {
        let spec = PageSetupSpec {
            paper_size: Some(9),
            scale: Some(75),
            orientation: Some("portrait".into()),
            fit_to_width: Some(1),
            fit_to_height: Some(0),
            ..Default::default()
        };
        let text = String::from_utf8(emit_page_setup(&spec)).unwrap();
        assert!(text.contains("paperSize=\"9\""));
        assert!(text.contains("scale=\"75\""));
        assert!(text.contains("fitToWidth=\"1\""));
        assert!(text.contains("fitToHeight=\"0\""));
        assert!(text.contains("orientation=\"portrait\""));
    }

    // ---- headerFooter ----------------------------------------------------
    #[test]
    fn header_footer_default_yields_empty() {
        assert!(emit_header_footer(&HeaderFooterSpec::default()).is_empty());
    }

    #[test]
    fn header_footer_odd_header_left_only() {
        let spec = HeaderFooterSpec {
            odd_header: Some(HeaderFooterItemSpec {
                left: Some("Title".into()),
                ..Default::default()
            }),
            ..Default::default()
        };
        let text = String::from_utf8(emit_header_footer(&spec)).unwrap();
        assert!(text.contains("<oddHeader>&amp;LTitle</oddHeader>"));
    }

    #[test]
    fn header_footer_full_lcr() {
        let spec = HeaderFooterSpec {
            odd_header: Some(HeaderFooterItemSpec {
                left: Some("L".into()),
                center: Some("C".into()),
                right: Some("R".into()),
            }),
            ..Default::default()
        };
        let text = String::from_utf8(emit_header_footer(&spec)).unwrap();
        assert!(text.contains("&amp;LL&amp;CC&amp;RR"));
    }

    #[test]
    fn header_footer_different_first_flag_only() {
        let spec = HeaderFooterSpec {
            different_first: true,
            ..Default::default()
        };
        let text = String::from_utf8(emit_header_footer(&spec)).unwrap();
        assert_eq!(text, "<headerFooter differentFirst=\"1\"/>");
    }

    // ---- sheetViews ------------------------------------------------------
    #[test]
    fn sheet_view_default_yields_empty() {
        assert!(emit_sheet_views(&SheetViewSpec::default()).is_empty());
    }

    #[test]
    fn sheet_view_grid_off() {
        let spec = SheetViewSpec {
            show_grid_lines: Some(false),
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_views(&spec)).unwrap();
        assert!(text.starts_with("<sheetViews>"));
        assert!(text.contains("showGridLines=\"0\""));
        assert!(text.ends_with("</sheetViews>"));
    }

    #[test]
    fn sheet_view_with_pane_freeze() {
        let spec = SheetViewSpec {
            pane: Some(PaneSpec {
                x_split: 0.0,
                y_split: 1.0,
                top_left_cell: "A2".into(),
                active_pane: "bottomLeft".into(),
                state: "frozen".into(),
            }),
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_views(&spec)).unwrap();
        assert!(text.contains("<pane "));
        assert!(text.contains("ySplit=\"1\""));
        assert!(text.contains("topLeftCell=\"A2\""));
        assert!(text.contains("activePane=\"bottomLeft\""));
        assert!(text.contains("state=\"frozen\""));
    }

    #[test]
    fn sheet_view_with_selection() {
        let spec = SheetViewSpec {
            selection: vec![SelectionSpec {
                active_cell: Some("B5".into()),
                sqref: Some("B5".into()),
                pane: None,
            }],
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_views(&spec)).unwrap();
        assert!(text.contains("<selection "));
        assert!(text.contains("activeCell=\"B5\""));
        assert!(text.contains("sqref=\"B5\""));
    }

    #[test]
    fn sheet_view_tab_selected_preserves_explicit_bool() {
        let selected = String::from_utf8(emit_sheet_views(&SheetViewSpec {
            tab_selected: Some(true),
            ..Default::default()
        }))
        .unwrap();
        assert!(selected.contains("tabSelected=\"1\""));

        let unselected = String::from_utf8(emit_sheet_views(&SheetViewSpec {
            tab_selected: Some(false),
            ..Default::default()
        }))
        .unwrap();
        assert!(unselected.contains("tabSelected=\"0\""));
    }

    #[test]
    fn sheet_view_zoom_non_default() {
        let spec = SheetViewSpec {
            zoom_scale: 150,
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_views(&spec)).unwrap();
        assert!(text.contains("zoomScale=\"150\""));
    }

    // ---- sheetProtection -------------------------------------------------
    #[test]
    fn sheet_protection_default_yields_empty() {
        assert!(emit_sheet_protection(&SheetProtectionSpec::default()).is_empty());
    }

    #[test]
    fn sheet_protection_with_sheet_only() {
        let spec = SheetProtectionSpec {
            sheet: true,
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_protection(&spec)).unwrap();
        assert!(text.starts_with("<sheetProtection"));
        assert!(text.contains("sheet=\"1\""));
        // No "allow" overrides at default values.
        assert!(!text.contains("formatCells="));
        assert!(text.ends_with("/>"));
    }

    #[test]
    fn sheet_protection_with_password_hash() {
        let spec = SheetProtectionSpec {
            sheet: true,
            password_hash: Some("C258".into()),
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_protection(&spec)).unwrap();
        assert!(text.contains("password=\"C258\""));
        assert!(text.contains("sheet=\"1\""));
    }

    #[test]
    fn sheet_protection_disable_sort() {
        let spec = SheetProtectionSpec {
            sheet: true,
            sort: false,
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_protection(&spec)).unwrap();
        assert!(text.contains("sort=\"0\""));
    }

    #[test]
    fn sheet_protection_select_locked_cells_default_false() {
        // selectLockedCells defaults to False (allowed) — only emit when True.
        let spec = SheetProtectionSpec {
            sheet: true,
            select_locked_cells: true,
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_protection(&spec)).unwrap();
        assert!(text.contains("selectLockedCells=\"1\""));
    }

    #[test]
    fn sheet_protection_modern_hash_attrs() {
        let spec = SheetProtectionSpec {
            sheet: true,
            algorithm_name: Some("SHA-512".into()),
            hash_value: Some("HASH==".into()),
            salt_value: Some("SALT==".into()),
            spin_count: Some(100_000),
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_protection(&spec)).unwrap();
        assert!(text.contains("algorithmName=\"SHA-512\""));
        assert!(text.contains("hashValue=\"HASH==\""));
        assert!(text.contains("saltValue=\"SALT==\""));
        assert!(text.contains("spinCount=\"100000\""));
    }

    #[test]
    fn sheet_protection_password_xml_special() {
        let spec = SheetProtectionSpec {
            sheet: true,
            password_hash: Some("ab&c".into()),
            ..Default::default()
        };
        let text = String::from_utf8(emit_sheet_protection(&spec)).unwrap();
        assert!(text.contains("password=\"ab&amp;c\""));
    }

    // ---- SheetSetupBlocks ------------------------------------------------
    #[test]
    fn empty_bundle_is_empty() {
        assert!(SheetSetupBlocks::default().is_empty());
    }

    #[test]
    fn bundle_with_one_block_is_not_empty() {
        let b = SheetSetupBlocks {
            page_margins: Some(PageMarginsSpec::default()),
            ..Default::default()
        };
        assert!(!b.is_empty());
    }
}
