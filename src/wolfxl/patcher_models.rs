//! Pure Rust queue models for the surgical XLSX patcher.

/// Sprint Μ Pod-gamma (RFC-046) — one chart queued for emit on a sheet.
///
/// The chart XML is pre-serialized by the caller; the patcher only routes
/// bytes through the OOXML rels graph, content-types, and drawing layer.
#[derive(Debug, Clone)]
pub struct QueuedChartAdd {
    /// Chart XML body written into `xl/charts/chartN.xml`.
    pub chart_xml: Vec<u8>,
    /// A1-style anchor cell, for example `"D2"`.
    pub anchor_a1: String,
    /// Fixed chart extent for modify mode.
    pub width_emu: i64,
    pub height_emu: i64,
}

#[derive(Debug, Clone)]
pub struct QueuedChartRemove {
    pub drawing_path: String,
    pub chart_rid: String,
    pub chart_path: String,
}

/// Sprint Lambda Pod-beta (RFC-045) — one image queued for emit on a sheet.
#[derive(Debug, Clone)]
pub struct QueuedImageAdd {
    /// Raw image bytes written into `xl/media/imageN.<ext>`.
    pub data: Vec<u8>,
    /// Lowercase extension such as `"png"`, `"jpeg"`, `"gif"`, or `"bmp"`.
    pub ext: String,
    /// Pixel dimensions used when computing drawing extents.
    pub width_px: u32,
    pub height_px: u32,
    /// Anchor flavor in the Python-facing queue shape.
    pub anchor: QueuedImageAnchor,
}

#[derive(Debug, Clone)]
pub enum QueuedImageAnchor {
    OneCell {
        from_col: u32,
        from_row: u32,
        from_col_off: i64,
        from_row_off: i64,
    },
    TwoCell {
        from_col: u32,
        from_row: u32,
        from_col_off: i64,
        from_row_off: i64,
        to_col: u32,
        to_row: u32,
        to_col_off: i64,
        to_row_off: i64,
        edit_as: String,
    },
    Absolute {
        x_emu: i64,
        y_emu: i64,
        cx_emu: i64,
        cy_emu: i64,
    },
}

/// One queued sheet-copy op (RFC-035).
#[derive(Debug, Clone)]
pub struct SheetCopyOp {
    /// Source sheet title.
    pub src_title: String,
    /// Destination sheet title.
    pub dst_title: String,
    /// Workbook-level `wb.copy_options.deep_copy_images` snapshot at queue time.
    pub deep_copy_images: bool,
}

/// One queued blank worksheet creation in modify mode.
#[derive(Debug, Clone)]
pub struct SheetCreateOp {
    /// Destination sheet title.
    pub title: String,
}

/// One queued axis-shift op (RFC-030/031).
#[derive(Debug, Clone)]
pub struct AxisShift {
    /// Sheet name, not worksheet part path.
    pub sheet: String,
    /// `"row"` or `"col"`.
    pub axis: String,
    /// 1-based index where shifting begins.
    pub idx: u32,
    /// Signed shift count. Positive means insert; negative means delete.
    pub n: i32,
}

/// One queued range-move op (RFC-034).
#[derive(Debug, Clone)]
pub struct RangeMove {
    /// Sheet name, not worksheet part path.
    pub sheet: String,
    /// 1-based inclusive source rectangle corners.
    pub src_min_col: u32,
    pub src_min_row: u32,
    pub src_max_col: u32,
    pub src_max_row: u32,
    /// Signed delta. Positive shifts down/right; negative shifts up/left.
    pub d_row: i32,
    pub d_col: i32,
    /// Whether external formulas pointing into the moved range also re-anchor.
    pub translate: bool,
}
