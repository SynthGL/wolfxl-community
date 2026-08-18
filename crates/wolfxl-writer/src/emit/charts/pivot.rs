//! Pivot-chart source emission.

use crate::model::chart::PivotSource;
use crate::xml_escape;

/// Emit the chart-level `<c:pivotSource>` block.
///
/// `name` is XML-escaped as text content rather than as an attribute.
pub(super) fn emit_pivot_source(out: &mut String, ps: &PivotSource) {
    out.push_str("<c:pivotSource>");
    out.push_str("<c:name>");
    out.push_str(&xml_escape::text(&ps.name));
    out.push_str("</c:name>");
    out.push_str(&format!("<c:fmtId val=\"{}\"/>", ps.fmt_id));
    out.push_str("</c:pivotSource>");
}
