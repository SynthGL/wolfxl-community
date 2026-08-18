//! Centralized allocator for part-suffix indices in OOXML packages.
//!
//! Excel does not allow two parts of the same kind to share a numeric suffix
//! (`xl/tables/table1.xml`, `xl/comments3.xml`, `xl/drawings/vmlDrawing4.vml`,
//! …). Several modify-mode subsystems (RFC-024 tables, RFC-023 comments, the
//! upcoming RFC-035 sheet-copy planner) need to mint fresh suffixes for new
//! parts, and they MUST share a single allocator so two callers in the same
//! save can never pick the same suffix.
//!
//! See `Plans/rfcs/035-copy-worksheet.md` §5.2 + §8 risk #1 for the design
//! rationale. This struct lives in `wolfxl-rels` so every patcher subsystem
//! can depend on it without pulling a heavier dependency.
//!
//! # Behavior
//!
//! - Each part-type has an independent monotonic counter starting at 1.
//! - [`PartIdAllocator::from_zip_parts`] scans a list of part paths and
//!   seeds each counter to `(max_seen_for_that_kind) + 1`. Paths it does
//!   not recognize are silently ignored.
//! - `alloc_*` returns the next free suffix and post-increments. Counters
//!   never decrease.
//! - Allocators for different part-types are independent — `alloc_table`
//!   and `alloc_comments` live in separate counters and cannot collide.
//!
//! # Recognized path patterns
//!
//! | Pattern                              | Counter         |
//! |--------------------------------------|-----------------|
//! | `xl/tables/table<N>.xml`             | `next_table`    |
//! | `xl/comments<N>.xml`                 | `next_comments` |
//! | `xl/drawings/vmlDrawing<N>.vml`      | `next_vml`      |
//! | `xl/drawings/drawing<N>.xml`         | `next_drawing`  |
//! | `xl/worksheets/sheet<N>.xml`         | `next_sheet`    |
//! | `xl/charts/chart<N>.xml`             | `next_chart`    |
//! | `xl/charts/style<N>.xml`             | `next_chart_style` |
//! | `xl/charts/colors<N>.xml`            | `next_chart_color` |
//! | `xl/ctrlProps/ctrlProp<N>.xml`       | `next_ctrl_prop` |
//!
//! Any path with a non-numeric or missing suffix (e.g. `xl/tables/foo.xml`)
//! is skipped — it does not contribute to any counter and does not panic.

/// Strip `prefix` and `suffix`, parse the middle as a `u32`. Returns `None`
/// if either bracket fails or the middle is empty / non-numeric.
fn parse_n(path: &str, prefix: &str, suffix: &str) -> Option<u32> {
    let mid = path.strip_prefix(prefix)?.strip_suffix(suffix)?;
    if mid.is_empty() {
        return None;
    }
    if !mid.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    mid.parse::<u32>().ok()
}

/// Workbook-scoped part-suffix allocator. One instance per save.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PartIdAllocator {
    next_table: u32,
    next_comments: u32,
    next_vml_drawing: u32,
    next_drawing: u32,
    next_sheet: u32,
    next_chart: u32,
    next_chart_style: u32,
    next_chart_color: u32,
    next_image: u32,
    // Sprint Ν Pod-γ (RFC-035 §10) — pivot deep-clone counters.
    next_pivot_table: u32,
    next_pivot_cache: u32,
    // Sprint Ο Pod 3.5 (RFC-061 §3.1) — slicer deep-clone counters.
    next_slicer: u32,
    next_slicer_cache: u32,
    // Real Excel fidelity — timeline presentations/caches are separate
    // workbook-scoped part families from slicers.
    next_timeline: u32,
    next_timeline_cache: u32,
    // Sprint Σ G08 (RFC-068 §5) — threaded-comment counter.
    next_threaded_comments: u32,
    // Real Excel form-control property parts.
    next_ctrl_prop: u32,
    // Real Excel form-control VML shape IDs. The first authored form-control
    // shape is conventionally `_x0000_s1025`.
    next_vml_shape_id: u32,
}

impl Default for PartIdAllocator {
    fn default() -> Self {
        Self::new()
    }
}

impl PartIdAllocator {
    /// Empty allocator: every counter starts at 1.
    pub fn new() -> Self {
        Self {
            next_table: 1,
            next_comments: 1,
            next_vml_drawing: 1,
            next_drawing: 1,
            next_sheet: 1,
            next_chart: 1,
            next_chart_style: 1,
            next_chart_color: 1,
            next_image: 1,
            next_pivot_table: 1,
            next_pivot_cache: 1,
            next_slicer: 1,
            next_slicer_cache: 1,
            next_timeline: 1,
            next_timeline_cache: 1,
            next_threaded_comments: 1,
            next_ctrl_prop: 1,
            next_vml_shape_id: 1025,
        }
    }

    /// Pre-populate counters by scanning a sequence of part paths (typically
    /// the names returned by the source ZIP archive).
    ///
    /// Unknown / unparseable paths are silently skipped. Never panics.
    /// After the scan, each counter is `(max_seen + 1)`, or `1` if no path
    /// of that kind was observed.
    pub fn from_zip_parts<'a, I>(part_paths: I) -> Self
    where
        I: IntoIterator<Item = &'a str>,
    {
        let mut alloc = Self::new();
        for path in part_paths {
            alloc.observe(path);
        }
        alloc
    }

    /// Bump the relevant counter if `path` matches a known pattern. Used by
    /// [`PartIdAllocator::from_zip_parts`] and exposed publicly so callers
    /// that mutate the patcher's `file_adds` mid-save can keep the
    /// allocator in sync.
    pub fn observe(&mut self, path: &str) {
        if let Some(n) = parse_n(path, "xl/tables/table", ".xml") {
            self.bump(Counter::Table, n);
        } else if let Some(n) = parse_n(path, "xl/comments", ".xml") {
            self.bump(Counter::Comments, n);
        } else if let Some(n) = parse_n(path, "xl/drawings/vmlDrawing", ".vml") {
            self.bump(Counter::VmlDrawing, n);
        } else if let Some(n) = parse_n(path, "xl/drawings/drawing", ".xml") {
            self.bump(Counter::Drawing, n);
        } else if let Some(n) = parse_n(path, "xl/worksheets/sheet", ".xml") {
            self.bump(Counter::Sheet, n);
        } else if let Some(n) = parse_n(path, "xl/charts/chart", ".xml") {
            self.bump(Counter::Chart, n);
        } else if let Some(n) = parse_n(path, "xl/charts/style", ".xml") {
            self.bump(Counter::ChartStyle, n);
        } else if let Some(n) = parse_n(path, "xl/charts/colors", ".xml") {
            self.bump(Counter::ChartColor, n);
        } else if let Some(n) = parse_n(path, "xl/pivotTables/pivotTable", ".xml") {
            self.bump(Counter::PivotTable, n);
        } else if let Some(n) = parse_n(path, "xl/pivotCache/pivotCacheDefinition", ".xml") {
            self.bump(Counter::PivotCache, n);
        } else if let Some(n) = parse_n(path, "xl/pivotCache/pivotCacheRecords", ".xml") {
            // Records share the cache counter (cache N = records N).
            self.bump(Counter::PivotCache, n);
        } else if let Some(n) = parse_n(path, "xl/slicers/slicer", ".xml") {
            self.bump(Counter::Slicer, n);
        } else if let Some(n) = parse_n(path, "xl/slicerCaches/slicerCache", ".xml") {
            self.bump(Counter::SlicerCache, n);
        } else if let Some(n) = parse_n(path, "xl/timelines/timeline", ".xml") {
            self.bump(Counter::Timeline, n);
        } else if let Some(n) = parse_n(path, "xl/timelineCaches/timelineCache", ".xml") {
            self.bump(Counter::TimelineCache, n);
        } else if let Some(n) = parse_n(path, "xl/threadedComments/threadedComments", ".xml") {
            self.bump(Counter::ThreadedComments, n);
        } else if let Some(n) = parse_n(path, "xl/ctrlProps/ctrlProp", ".xml") {
            self.bump(Counter::CtrlProp, n);
        } else if path.starts_with("xl/media/image") {
            // Images use heterogeneous extensions (png/jpeg/gif/...) so a
            // generic strip+parse covers all of them.
            if let Some(stem) = path.strip_prefix("xl/media/image") {
                let mid: String = stem.chars().take_while(|c| c.is_ascii_digit()).collect();
                if let Ok(n) = mid.parse::<u32>() {
                    self.bump(Counter::Image, n);
                }
            }
        }
    }

    fn bump(&mut self, c: Counter, n: u32) {
        let slot = match c {
            Counter::Table => &mut self.next_table,
            Counter::Comments => &mut self.next_comments,
            Counter::VmlDrawing => &mut self.next_vml_drawing,
            Counter::Drawing => &mut self.next_drawing,
            Counter::Sheet => &mut self.next_sheet,
            Counter::Chart => &mut self.next_chart,
            Counter::ChartStyle => &mut self.next_chart_style,
            Counter::ChartColor => &mut self.next_chart_color,
            Counter::Image => &mut self.next_image,
            Counter::PivotTable => &mut self.next_pivot_table,
            Counter::PivotCache => &mut self.next_pivot_cache,
            Counter::Slicer => &mut self.next_slicer,
            Counter::SlicerCache => &mut self.next_slicer_cache,
            Counter::Timeline => &mut self.next_timeline,
            Counter::TimelineCache => &mut self.next_timeline_cache,
            Counter::ThreadedComments => &mut self.next_threaded_comments,
            Counter::CtrlProp => &mut self.next_ctrl_prop,
        };
        if n + 1 > *slot {
            *slot = n + 1;
        }
    }

    /// Allocate a fresh `tableN` suffix; returns `N` (≥1).
    pub fn alloc_table(&mut self) -> u32 {
        let n = self.next_table;
        self.next_table += 1;
        n
    }

    /// Allocate a fresh `commentsN` suffix; returns `N` (≥1).
    pub fn alloc_comments(&mut self) -> u32 {
        let n = self.next_comments;
        self.next_comments += 1;
        n
    }

    /// Allocate a fresh `vmlDrawingN` suffix; returns `N` (≥1).
    pub fn alloc_vml_drawing(&mut self) -> u32 {
        let n = self.next_vml_drawing;
        self.next_vml_drawing += 1;
        n
    }

    /// Allocate a fresh `drawingN` suffix; returns `N` (≥1).
    pub fn alloc_drawing(&mut self) -> u32 {
        let n = self.next_drawing;
        self.next_drawing += 1;
        n
    }

    /// Allocate a fresh `sheetN` suffix; returns `N` (≥1).
    pub fn alloc_sheet(&mut self) -> u32 {
        let n = self.next_sheet;
        self.next_sheet += 1;
        n
    }

    /// Allocate a fresh `chartN` suffix; returns `N` (≥1).
    pub fn alloc_chart(&mut self) -> u32 {
        let n = self.next_chart;
        self.next_chart += 1;
        n
    }

    /// Allocate a fresh `styleN` suffix for `xl/charts/styleN.xml`;
    /// returns `N` (>=1).
    pub fn alloc_chart_style(&mut self) -> u32 {
        let n = self.next_chart_style;
        self.next_chart_style += 1;
        n
    }

    /// Allocate a fresh `colorsN` suffix for `xl/charts/colorsN.xml`;
    /// returns `N` (>=1).
    pub fn alloc_chart_color(&mut self) -> u32 {
        let n = self.next_chart_color;
        self.next_chart_color += 1;
        n
    }

    /// Allocate a fresh `imageN` suffix for `xl/media/imageN.<ext>`;
    /// returns `N` (≥1). Used by RFC-035 §5.3 deep-copy mode (Sprint Θ
    /// Pod-C2). Extensions vary (png/jpeg/gif/…) so callers append the
    /// extension themselves.
    pub fn alloc_image(&mut self) -> u32 {
        let n = self.next_image;
        self.next_image += 1;
        n
    }

    /// Allocate a fresh `pivotTableN` suffix; returns `N` (≥1).
    /// Used by Sprint Ν Pod-γ (RFC-035 §10) deep-clone in sheet copy.
    pub fn alloc_pivot_table(&mut self) -> u32 {
        let n = self.next_pivot_table;
        self.next_pivot_table += 1;
        n
    }

    /// Allocate a fresh `pivotCacheN` suffix; returns `N` (≥1). Both
    /// `pivotCacheDefinitionN.xml` and `pivotCacheRecordsN.xml` share
    /// the same `N`. Used by Sprint Ν Pod-γ (RFC-035 §10) when
    /// deep-cloning a self-cache (cache whose source range lives on
    /// the sheet being copied).
    pub fn alloc_pivot_cache(&mut self) -> u32 {
        let n = self.next_pivot_cache;
        self.next_pivot_cache += 1;
        n
    }

    /// Allocate a fresh `slicer{N}` suffix; returns `N` (≥1). Used by
    /// Sprint Ο Pod 3.5 (RFC-061) deep-clone in sheet copy.
    pub fn alloc_slicer(&mut self) -> u32 {
        let n = self.next_slicer;
        self.next_slicer += 1;
        n
    }

    /// Allocate a fresh `slicerCache{N}` suffix; returns `N` (≥1).
    /// Used only when a slicer cache also needs deep-cloning (rare —
    /// default is share, see RFC-061 §6).
    pub fn alloc_slicer_cache(&mut self) -> u32 {
        let n = self.next_slicer_cache;
        self.next_slicer_cache += 1;
        n
    }

    /// Allocate a fresh `timeline{N}` suffix; returns `N` (≥1).
    pub fn alloc_timeline(&mut self) -> u32 {
        let n = self.next_timeline;
        self.next_timeline += 1;
        n
    }

    /// Allocate a fresh `timelineCache{N}` suffix; returns `N` (≥1).
    pub fn alloc_timeline_cache(&mut self) -> u32 {
        let n = self.next_timeline_cache;
        self.next_timeline_cache += 1;
        n
    }

    /// Allocate a fresh `threadedComments{N}` suffix; returns `N` (≥1).
    /// Used by RFC-068 G08 step 5 in modify mode for sheets that gain
    /// their first threaded-comment part.
    pub fn alloc_threaded_comments(&mut self) -> u32 {
        let n = self.next_threaded_comments;
        self.next_threaded_comments += 1;
        n
    }

    /// Allocate a fresh `ctrlPropN` suffix; returns `N` (>=1).
    pub fn alloc_ctrl_prop(&mut self) -> u32 {
        let n = self.next_ctrl_prop;
        self.next_ctrl_prop += 1;
        n
    }

    /// Seed the form-control VML shape-ID counter from the maximum existing
    /// shape ID in the workbook package. Excel starts copied control shapes in
    /// the next 1024-ID block (1025 -> 2049), while subsequent in-flight copies
    /// keep consuming from the same allocator so IDs stay workbook-unique.
    pub fn observe_vml_shape_id_max(&mut self, max_shape_id: u32) {
        let next = next_vml_shape_id_block_start(max_shape_id);
        if next > self.next_vml_shape_id {
            self.next_vml_shape_id = next;
        }
    }

    /// Allocate a fresh workbook-unique VML shape ID for copied form controls.
    pub fn alloc_vml_shape_id(&mut self) -> u32 {
        let n = self.next_vml_shape_id;
        self.next_vml_shape_id = self.next_vml_shape_id.saturating_add(1);
        n
    }

    /// Peek at each counter without consuming. Test-only.
    #[cfg(test)]
    fn peek(&self) -> [u32; 7] {
        [
            self.next_table,
            self.next_comments,
            self.next_vml_drawing,
            self.next_drawing,
            self.next_sheet,
            self.next_chart,
            self.next_image,
        ]
    }
}

fn next_vml_shape_id_block_start(max_shape_id: u32) -> u32 {
    let block = max_shape_id
        .saturating_sub(1)
        .checked_div(1024)
        .unwrap_or(0)
        .saturating_add(1)
        .max(1);
    block.saturating_mul(1024).saturating_add(1)
}

enum Counter {
    Table,
    Comments,
    VmlDrawing,
    Slicer,
    SlicerCache,
    Timeline,
    TimelineCache,
    Drawing,
    Sheet,
    Chart,
    ChartStyle,
    ChartColor,
    Image,
    PivotTable,
    PivotCache,
    ThreadedComments,
    CtrlProp,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_allocator_starts_at_one() {
        let mut a = PartIdAllocator::new();
        assert_eq!(a.alloc_table(), 1);
        assert_eq!(a.alloc_comments(), 1);
        assert_eq!(a.alloc_vml_drawing(), 1);
        assert_eq!(a.alloc_drawing(), 1);
        assert_eq!(a.alloc_sheet(), 1);
        assert_eq!(a.alloc_chart(), 1);
        assert_eq!(a.alloc_ctrl_prop(), 1);
    }

    #[test]
    fn empty_seed_returns_one_on_first_alloc() {
        let mut a = PartIdAllocator::from_zip_parts(std::iter::empty::<&str>());
        assert_eq!(a.alloc_table(), 1);
    }

    #[test]
    fn from_zip_parts_seeds_table_counter() {
        // table1 + table5 means next alloc must be table6.
        let parts = ["xl/tables/table1.xml", "xl/tables/table5.xml"];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        assert_eq!(a.alloc_table(), 6);
        assert_eq!(a.alloc_table(), 7);
    }

    #[test]
    fn consecutive_alloc_table_calls_are_monotonic_and_distinct() {
        let mut a = PartIdAllocator::new();
        let n1 = a.alloc_table();
        let n2 = a.alloc_table();
        let n3 = a.alloc_table();
        assert!(n1 < n2 && n2 < n3, "monotonic: {n1} < {n2} < {n3}");
        assert_ne!(n1, n2);
        assert_ne!(n2, n3);
    }

    #[test]
    fn allocators_are_independent_across_part_types() {
        // Seed only tables; comments must still start at 1.
        let mut a = PartIdAllocator::from_zip_parts(["xl/tables/table7.xml"].iter().copied());
        assert_eq!(a.alloc_table(), 8);
        assert_eq!(a.alloc_comments(), 1);
        assert_eq!(a.alloc_vml_drawing(), 1);
        assert_eq!(a.alloc_drawing(), 1);
        assert_eq!(a.alloc_sheet(), 1);
        assert_eq!(a.alloc_chart(), 1);
        assert_eq!(a.alloc_ctrl_prop(), 1);
    }

    #[test]
    fn from_zip_parts_seeds_ctrl_prop_counter() {
        let parts = ["xl/ctrlProps/ctrlProp1.xml", "xl/ctrlProps/ctrlProp4.xml"];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        assert_eq!(a.alloc_ctrl_prop(), 5);
        assert_eq!(a.alloc_ctrl_prop(), 6);
    }

    #[test]
    fn vml_shape_id_counter_starts_at_next_excel_block() {
        let mut a = PartIdAllocator::new();
        a.observe_vml_shape_id_max(1025);
        assert_eq!(a.alloc_vml_shape_id(), 2049);
        assert_eq!(a.alloc_vml_shape_id(), 2050);
        a.observe_vml_shape_id_max(1025);
        assert_eq!(a.alloc_vml_shape_id(), 2051);
    }

    #[test]
    fn vml_shape_id_observe_never_moves_backwards() {
        let mut a = PartIdAllocator::new();
        a.observe_vml_shape_id_max(2049);
        assert_eq!(a.alloc_vml_shape_id(), 3073);
        a.observe_vml_shape_id_max(1025);
        assert_eq!(a.alloc_vml_shape_id(), 3074);
    }

    #[test]
    fn non_numeric_suffix_is_silently_skipped() {
        let parts = [
            "xl/tables/foo.xml",
            "xl/tables/table_x.xml",
            "xl/tables/table.xml",
            "xl/tables/table12abc.xml",
        ];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        // None of these contributed; counter stays at 1.
        assert_eq!(a.alloc_table(), 1);
    }

    #[test]
    fn unrelated_paths_are_ignored() {
        let parts = [
            "[Content_Types].xml",
            "xl/workbook.xml",
            "xl/styles.xml",
            "xl/_rels/workbook.xml.rels",
            "xl/worksheets/_rels/sheet1.xml.rels",
            "docProps/core.xml",
        ];
        let a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        // Layout: [table, comments, vml, drawing, sheet, chart, image].
        assert_eq!(a.peek(), [1, 1, 1, 1, 1, 1, 1]);
    }

    #[test]
    fn image_seed_from_xl_media_image_n_ext() {
        let parts = [
            "xl/media/image1.png",
            "xl/media/image2.jpeg",
            "xl/media/image5.gif",
        ];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        // Highest seen is 5 → next free is 6.
        assert_eq!(a.alloc_image(), 6);
    }

    #[test]
    fn comments_seed_from_xl_comments_n_xml() {
        let parts = ["xl/comments1.xml", "xl/comments3.xml", "xl/comments7.xml"];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        assert_eq!(a.alloc_comments(), 8);
    }

    #[test]
    fn vml_drawing_seed_from_xl_drawings_path() {
        let parts = [
            "xl/drawings/vmlDrawing1.vml",
            "xl/drawings/vmlDrawing2.vml",
            "xl/drawings/vmlDrawing4.vml",
        ];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        assert_eq!(a.alloc_vml_drawing(), 5);
    }

    #[test]
    fn drawing_seed_from_xl_drawings_drawing_xml() {
        let parts = [
            "xl/drawings/drawing1.xml",
            "xl/drawings/drawing2.xml",
            "xl/drawings/drawing9.xml",
            // vmlDrawing must NOT contribute to drawing counter:
            "xl/drawings/vmlDrawing20.vml",
        ];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        assert_eq!(a.alloc_drawing(), 10);
        // vmlDrawing counter sees the 20.
        assert_eq!(a.alloc_vml_drawing(), 21);
    }

    #[test]
    fn sheet_and_chart_seeds() {
        let parts = [
            "xl/worksheets/sheet1.xml",
            "xl/worksheets/sheet2.xml",
            "xl/worksheets/sheet11.xml",
            "xl/charts/chart1.xml",
            "xl/charts/chart3.xml",
            "xl/charts/style1.xml",
            "xl/charts/colors4.xml",
        ];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        assert_eq!(a.alloc_sheet(), 12);
        assert_eq!(a.alloc_chart(), 4);
        assert_eq!(a.alloc_chart_style(), 2);
        assert_eq!(a.alloc_chart_color(), 5);
    }

    #[test]
    fn observe_respects_existing_max() {
        // Seed with table5; observing a smaller value (table2) must NOT
        // reset the counter.
        let mut a = PartIdAllocator::from_zip_parts(["xl/tables/table5.xml"].iter().copied());
        a.observe("xl/tables/table2.xml");
        assert_eq!(a.alloc_table(), 6);
    }

    #[test]
    fn observe_advances_counter_for_runtime_additions() {
        // Simulates: scan sources at start of save, then mid-save the
        // patcher emits xl/tables/table8.xml; observing it keeps the
        // allocator from re-issuing 8.
        let mut a = PartIdAllocator::new();
        a.observe("xl/tables/table8.xml");
        assert_eq!(a.alloc_table(), 9);
    }

    #[test]
    fn from_zip_parts_with_gaps_uses_max_plus_one() {
        // Spec: the seed is "max + 1", not "count + 1". So gaps are
        // preserved (caller may want to fill them later but the allocator
        // never reuses a slot it has not been told about).
        let parts = [
            "xl/tables/table1.xml",
            "xl/tables/table10.xml",
            // No table 2..9 present.
        ];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        assert_eq!(a.alloc_table(), 11);
    }

    #[test]
    fn counters_independent_for_drawing_kinds() {
        // drawingN.xml and vmlDrawingN.vml are different kinds — make sure
        // a vmlDrawing path does not bump the drawing counter.
        let parts = ["xl/drawings/vmlDrawing7.vml"];
        let mut a = PartIdAllocator::from_zip_parts(parts.iter().copied());
        assert_eq!(a.alloc_drawing(), 1);
        assert_eq!(a.alloc_vml_drawing(), 8);
    }

    #[test]
    fn many_allocations_stay_distinct() {
        let mut a = PartIdAllocator::new();
        let mut seen = std::collections::HashSet::new();
        for _ in 0..50 {
            assert!(seen.insert(a.alloc_table()));
        }
        // After 50 allocations from empty seed, next is 51.
        assert_eq!(a.alloc_table(), 51);
    }

    #[test]
    fn does_not_panic_on_missing_or_strange_inputs() {
        // Extreme: empty path, root path, paths with only a slash.
        let parts = ["", "/", "xl/", "xl/tables/", "xl/tables/.xml"];
        let _ = PartIdAllocator::from_zip_parts(parts.iter().copied());
        // No assertion needed beyond "did not panic".
    }
}
