//! Chart axis id selection and axis XML emission.

use crate::model::chart::{
    Axis, AxisCommon, AxisPos, CategoryAxis, Chart, DateAxis, DisplayUnits, Gridlines, SeriesAxis,
    ValueAxis,
};
use crate::xml_escape;

use super::primitives::{bool_str, fmt_f64};
use super::style::emit_graphical_props;
use super::text::emit_title;

pub(super) fn pick_axis_ids(chart: &Chart) -> (u32, u32) {
    let from_explicit = (
        chart.x_axis.as_ref().map(axis_common).map(|c| c.ax_id),
        chart.y_axis.as_ref().map(axis_common).map(|c| c.ax_id),
    );
    match from_explicit {
        (Some(a), Some(b)) => (a, b),
        _ => (10, 100),
    }
}

pub(super) fn axis_common(a: &Axis) -> &AxisCommon {
    match a {
        Axis::Category(c) => &c.common,
        Axis::Value(c) => &c.common,
        Axis::Date(c) => &c.common,
        Axis::Series(c) => &c.common,
    }
}

pub(super) fn emit_axis(out: &mut String, axis: &Axis) {
    match axis {
        Axis::Category(c) => emit_category_axis(out, c),
        Axis::Value(v) => emit_value_axis(out, v),
        Axis::Date(d) => emit_date_axis(out, d),
        Axis::Series(s) => emit_series_axis(out, s),
    }
}

/// RFC-069 §5.2 — emit a value axis as a *secondary* axis on the right
/// side of the plot. Forces `<c:axPos val="r"/>` and `<c:crosses
/// val="max"/>` (when not explicitly set) to match Excel's convention
/// for the second `<c:valAx>` sibling in a combination chart.
///
/// This is called only for value axes that the secondary chart owns
/// (i.e. the secondary's y_axis ax_id differs from the primary's). When
/// the secondary shares the primary y-axis, no extra axis is emitted.
pub(super) fn emit_axis_as_secondary(out: &mut String, v: &ValueAxis) {
    let mut adjusted = v.clone();
    adjusted.common.ax_pos = AxisPos::Right;
    if adjusted.crosses.is_none() {
        adjusted.crosses = Some("max".to_string());
    }
    emit_value_axis(out, &adjusted);
}

fn emit_gridlines(out: &mut String, tag: &str, flag: bool, obj: Option<&Gridlines>) {
    if let Some(g) = obj {
        if let Some(gp) = &g.graphical_properties {
            out.push_str(&format!("<c:{tag}>"));
            emit_graphical_props(out, gp);
            out.push_str(&format!("</c:{tag}>"));
        } else {
            out.push_str(&format!("<c:{tag}/>"));
        }
        return;
    }
    if flag {
        out.push_str(&format!("<c:{tag}/>"));
    }
}

fn emit_axis_common_pre(out: &mut String, common: &AxisCommon) {
    out.push_str(&format!("<c:axId val=\"{}\"/>", common.ax_id));
    out.push_str("<c:scaling>");
    out.push_str(&format!(
        "<c:orientation val=\"{}\"/>",
        common.orientation.as_str()
    ));
    out.push_str("</c:scaling>");
    if let Some(d) = common.delete {
        out.push_str(&format!("<c:delete val=\"{}\"/>", bool_str(d)));
    }
    out.push_str(&format!("<c:axPos val=\"{}\"/>", common.ax_pos.as_str()));
    emit_gridlines(
        out,
        "majorGridlines",
        common.major_gridlines,
        common.major_gridlines_obj.as_ref(),
    );
    emit_gridlines(
        out,
        "minorGridlines",
        common.minor_gridlines,
        common.minor_gridlines_obj.as_ref(),
    );
    if let Some(t) = &common.title {
        emit_title(out, t);
    }
    if let Some(nf) = &common.number_format {
        out.push_str(&format!(
            "<c:numFmt formatCode=\"{}\" sourceLinked=\"0\"/>",
            xml_escape::attr(nf)
        ));
    }
    if let Some(t) = common.major_tick_mark {
        out.push_str(&format!("<c:majorTickMark val=\"{}\"/>", t.as_str()));
    }
    if let Some(t) = common.minor_tick_mark {
        out.push_str(&format!("<c:minorTickMark val=\"{}\"/>", t.as_str()));
    }
    out.push_str(&format!("<c:crossAx val=\"{}\"/>", common.cross_ax));
}

fn emit_category_axis(out: &mut String, c: &CategoryAxis) {
    out.push_str("<c:catAx>");
    emit_axis_common_pre(out, &c.common);
    if let Some(o) = c.lbl_offset {
        out.push_str(&format!("<c:lblOffset val=\"{o}\"/>"));
    }
    if let Some(a) = &c.lbl_algn {
        out.push_str(&format!("<c:lblAlgn val=\"{}\"/>", xml_escape::attr(a)));
    }
    out.push_str("</c:catAx>");
}

fn emit_value_axis(out: &mut String, v: &ValueAxis) {
    out.push_str("<c:valAx>");
    out.push_str(&format!("<c:axId val=\"{}\"/>", v.common.ax_id));
    out.push_str("<c:scaling>");
    out.push_str(&format!(
        "<c:orientation val=\"{}\"/>",
        v.common.orientation.as_str()
    ));
    if let Some(m) = v.min {
        out.push_str(&format!("<c:min val=\"{}\"/>", fmt_f64(m)));
    }
    if let Some(m) = v.max {
        out.push_str(&format!("<c:max val=\"{}\"/>", fmt_f64(m)));
    }
    out.push_str("</c:scaling>");
    if let Some(d) = v.common.delete {
        out.push_str(&format!("<c:delete val=\"{}\"/>", bool_str(d)));
    }
    out.push_str(&format!("<c:axPos val=\"{}\"/>", v.common.ax_pos.as_str()));
    emit_gridlines(
        out,
        "majorGridlines",
        v.common.major_gridlines,
        v.common.major_gridlines_obj.as_ref(),
    );
    emit_gridlines(
        out,
        "minorGridlines",
        v.common.minor_gridlines,
        v.common.minor_gridlines_obj.as_ref(),
    );
    if let Some(t) = &v.common.title {
        emit_title(out, t);
    }
    if let Some(nf) = &v.common.number_format {
        out.push_str(&format!(
            "<c:numFmt formatCode=\"{}\" sourceLinked=\"0\"/>",
            xml_escape::attr(nf)
        ));
    }
    if let Some(t) = v.common.major_tick_mark {
        out.push_str(&format!("<c:majorTickMark val=\"{}\"/>", t.as_str()));
    }
    if let Some(t) = v.common.minor_tick_mark {
        out.push_str(&format!("<c:minorTickMark val=\"{}\"/>", t.as_str()));
    }
    out.push_str(&format!("<c:crossAx val=\"{}\"/>", v.common.cross_ax));
    if let Some(c) = &v.crosses {
        out.push_str(&format!("<c:crosses val=\"{}\"/>", xml_escape::attr(c)));
    }
    if let Some(u) = v.major_unit {
        out.push_str(&format!("<c:majorUnit val=\"{}\"/>", fmt_f64(u)));
    }
    if let Some(u) = v.minor_unit {
        out.push_str(&format!("<c:minorUnit val=\"{}\"/>", fmt_f64(u)));
    }
    if let Some(d) = &v.display_units {
        emit_display_units(out, d);
    }
    out.push_str("</c:valAx>");
}

fn emit_display_units(out: &mut String, d: &DisplayUnits) {
    out.push_str("<c:dispUnits>");
    if let Some(u) = d.custom_unit {
        out.push_str(&format!("<c:custUnit val=\"{}\"/>", fmt_f64(u)));
    }
    if let Some(u) = &d.built_in_unit {
        out.push_str(&format!("<c:builtInUnit val=\"{}\"/>", xml_escape::attr(u)));
    }
    out.push_str("</c:dispUnits>");
}

fn emit_date_axis(out: &mut String, d: &DateAxis) {
    out.push_str("<c:dateAx>");
    out.push_str(&format!("<c:axId val=\"{}\"/>", d.common.ax_id));
    out.push_str("<c:scaling>");
    out.push_str(&format!(
        "<c:orientation val=\"{}\"/>",
        d.common.orientation.as_str()
    ));
    if let Some(m) = d.min {
        out.push_str(&format!("<c:min val=\"{}\"/>", fmt_f64(m)));
    }
    if let Some(m) = d.max {
        out.push_str(&format!("<c:max val=\"{}\"/>", fmt_f64(m)));
    }
    out.push_str("</c:scaling>");
    if let Some(de) = d.common.delete {
        out.push_str(&format!("<c:delete val=\"{}\"/>", bool_str(de)));
    }
    out.push_str(&format!("<c:axPos val=\"{}\"/>", d.common.ax_pos.as_str()));
    emit_gridlines(
        out,
        "majorGridlines",
        d.common.major_gridlines,
        d.common.major_gridlines_obj.as_ref(),
    );
    emit_gridlines(
        out,
        "minorGridlines",
        d.common.minor_gridlines,
        d.common.minor_gridlines_obj.as_ref(),
    );
    if let Some(t) = &d.common.title {
        emit_title(out, t);
    }
    if let Some(nf) = &d.common.number_format {
        out.push_str(&format!(
            "<c:numFmt formatCode=\"{}\" sourceLinked=\"0\"/>",
            xml_escape::attr(nf)
        ));
    }
    if let Some(t) = d.common.major_tick_mark {
        out.push_str(&format!("<c:majorTickMark val=\"{}\"/>", t.as_str()));
    }
    if let Some(t) = d.common.minor_tick_mark {
        out.push_str(&format!("<c:minorTickMark val=\"{}\"/>", t.as_str()));
    }
    out.push_str(&format!("<c:crossAx val=\"{}\"/>", d.common.cross_ax));
    if let Some(b) = &d.base_time_unit {
        out.push_str(&format!(
            "<c:baseTimeUnit val=\"{}\"/>",
            xml_escape::attr(b)
        ));
    }
    if let Some(u) = d.major_unit {
        out.push_str(&format!("<c:majorUnit val=\"{}\"/>", fmt_f64(u)));
    }
    if let Some(u) = d.minor_unit {
        out.push_str(&format!("<c:minorUnit val=\"{}\"/>", fmt_f64(u)));
    }
    out.push_str("</c:dateAx>");
}

fn emit_series_axis(out: &mut String, s: &SeriesAxis) {
    out.push_str("<c:serAx>");
    emit_axis_common_pre(out, &s.common);
    out.push_str("</c:serAx>");
}
