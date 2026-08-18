//! Structured tables (`xl/tables/tableN.xml`).
//!
//! Excel tables add header styling, auto-filter, and structured references
//! (`=myTable[Col]`) to a plain cell range. One table = one `<table>` part
//! plus a worksheet-level `<tablePart>` back-reference.

/// A structured table attached to a range of cells.
#[derive(Debug, Clone, PartialEq)]
pub struct Table {
    /// The display name — what `=myTable[Col]` references. Must be unique
    /// workbook-wide.
    pub name: String,

    /// The visible caption. Often equal to `name` but can differ.
    pub display_name: Option<String>,

    /// The range the table covers, in A1 form (e.g. `"A1:D20"`).
    pub range: String,

    /// Column definitions. Length must equal the column span of `range`.
    pub columns: Vec<TableColumn>,

    /// If `true`, the first row of the range is the header strip.
    pub header_row: bool,

    /// If `true`, the last row of the range is a totals row.
    pub totals_row: bool,

    /// Built-in style name, e.g. `"TableStyleMedium2"`, or `None` for
    /// default.
    pub style: Option<TableStyle>,

    /// Auto-filter behavior.
    pub autofilter: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub struct TableColumn {
    pub name: String,
    /// Totals-row aggregation function, if set.
    pub totals_function: Option<String>,
    pub totals_label: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableStyle {
    /// e.g. `"TableStyleMedium2"`, `"TableStyleLight1"`, `"TableStyleDark4"`.
    pub name: String,
    pub show_first_column: bool,
    pub show_last_column: bool,
    pub show_row_stripes: bool,
    pub show_column_stripes: bool,
}
