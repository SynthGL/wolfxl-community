//! Pure data model for a workbook awaiting serialization.
//!
//! No I/O, no XML. Everything in here is a plain struct / enum. The emitter
//! modules in [`crate::emit`] consume this data; the ZIP packager in
//! [`crate::zip`] assembles their output.

pub mod cell;
pub mod chart;
pub mod comment;
pub mod conditional;
pub mod date;
pub mod defined_name;
pub mod format;
pub mod image;
pub mod table;
pub mod threaded_comment;
pub mod validation;
pub mod workbook;
pub mod worksheet;

pub use cell::{WriteCell, WriteCellValue};
pub use chart::{
    Axis, AxisCommon, AxisOrientation, AxisPos, BarDir, BarGrouping, CategoryAxis, Chart,
    ChartKind, DataLabels, DataPoint, DateAxis, DisplayBlanksAs, DisplayUnits, ErrorBarType,
    ErrorBarValType, ErrorBars, GraphicalProperties, Layout, LayoutTarget, Legend, LegendPosition,
    Marker, MarkerSymbol, PivotSource, RadarStyle, Reference, ScatterStyle, Series, SeriesAxis,
    SeriesTitle, TickMark, Title, TitleRun, Trendline, TrendlineKind, ValueAxis,
};
pub use comment::{Comment, CommentAuthor, CommentAuthorTable};
pub use conditional::{
    CellIsOperator, ColorScaleStop, ConditionalFormat, ConditionalKind, ConditionalRule,
    ConditionalThreshold,
};
pub use date::to_excel_serial;
pub use defined_name::{BuiltinName, DefinedName};
pub use format::{
    AlignmentSpec, BorderSideSpec, BorderSpec, DxfRecord, FillSpec, FontSpec, FormatSpec,
    GradientFillSpec, GradientStopSpec, ProtectionSpec, StylesBuilder,
};
pub use image::{ImageAnchor, SheetImage};
pub use table::{Table, TableColumn, TableStyle};
pub use threaded_comment::{Person, PersonTable, ThreadedComment};
pub use validation::{DataValidation, ErrorStyle, ValidationOperator, ValidationType};
pub use workbook::{DocProperties, Workbook};
pub use worksheet::{Column, FreezePane, Hyperlink, Row, SheetVisibility, SplitPane, Worksheet};
