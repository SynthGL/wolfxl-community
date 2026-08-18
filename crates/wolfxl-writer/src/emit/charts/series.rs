//! Chart series and series-level option emission.

use crate::model::chart::{
    ChartKind, DataLabels, DataPoint, ErrorBars, Marker, Reference, Series, Trendline,
    TrendlineKind,
};
use crate::xml_escape;

use super::primitives::{bool_str, fmt_f64};
use super::style::emit_graphical_props;
use super::text::emit_series_title;

pub(super) fn emit_series(
    out: &mut String,
    ser: &Series,
    kind: ChartKind,
    pivot_fmt_id: Option<u32>,
) {
    out.push_str("<c:ser>");
    out.push_str(&format!("<c:idx val=\"{}\"/>", ser.idx));
    out.push_str(&format!("<c:order val=\"{}\"/>", ser.order));

    if let Some(fmt_id) = pivot_fmt_id {
        out.push_str(&format!("<c:fmtId val=\"{fmt_id}\"/>"));
    }

    if let Some(t) = &ser.title {
        emit_series_title(out, t);
    }

    if let Some(g) = &ser.graphical_properties {
        emit_graphical_props(out, g);
    }

    if let Some(m) = &ser.marker {
        emit_marker(out, m);
    }

    if let Some(b) = ser.invert_if_negative {
        out.push_str(&format!("<c:invertIfNegative val=\"{}\"/>", bool_str(b)));
    }

    for dp in &ser.data_points {
        emit_data_point(out, dp);
    }

    if let Some(d) = &ser.data_labels {
        emit_data_labels(out, d);
    }

    for eb in &ser.error_bars {
        emit_error_bars(out, eb);
    }

    for tl in &ser.trendlines {
        emit_trendline(out, tl);
    }

    match kind {
        ChartKind::Scatter => {
            if let Some(x) = &ser.x_values {
                out.push_str("<c:xVal>");
                emit_num_ref(out, x);
                out.push_str("</c:xVal>");
            }
            if let Some(y) = &ser.values {
                out.push_str("<c:yVal>");
                emit_num_ref(out, y);
                out.push_str("</c:yVal>");
            }
            if let Some(s) = ser.smooth {
                out.push_str(&format!("<c:smooth val=\"{}\"/>", bool_str(s)));
            }
        }
        ChartKind::Bubble => {
            if let Some(x) = &ser.x_values {
                out.push_str("<c:xVal>");
                emit_num_ref(out, x);
                out.push_str("</c:xVal>");
            }
            if let Some(y) = &ser.values {
                out.push_str("<c:yVal>");
                emit_num_ref(out, y);
                out.push_str("</c:yVal>");
            }
            if let Some(b) = &ser.bubble_size {
                out.push_str("<c:bubbleSize>");
                emit_num_ref(out, b);
                out.push_str("</c:bubbleSize>");
            }
        }
        _ => {
            if let Some(c) = &ser.categories {
                out.push_str("<c:cat>");
                emit_num_ref(out, c);
                out.push_str("</c:cat>");
            }
            if let Some(v) = &ser.values {
                out.push_str("<c:val>");
                emit_num_ref(out, v);
                out.push_str("</c:val>");
            }
            if matches!(kind, ChartKind::Line | ChartKind::Radar | ChartKind::Line3D) {
                if let Some(s) = ser.smooth {
                    out.push_str(&format!("<c:smooth val=\"{}\"/>", bool_str(s)));
                }
            }
        }
    }

    out.push_str("</c:ser>");
}

fn emit_num_ref(out: &mut String, r: &Reference) {
    out.push_str("<c:numRef>");
    out.push_str(&format!(
        "<c:f>{}</c:f>",
        xml_escape::text(&r.to_formula_string())
    ));
    out.push_str("</c:numRef>");
}

pub(super) fn emit_data_labels(out: &mut String, d: &DataLabels) {
    out.push_str("<c:dLbls>");
    if let Some(nf) = &d.number_format {
        out.push_str(&format!(
            "<c:numFmt formatCode=\"{}\" sourceLinked=\"0\"/>",
            xml_escape::attr(nf)
        ));
    }
    if !d.tx_pr_runs.is_empty() {
        super::text::emit_tx_pr(out, &d.tx_pr_runs);
    }
    if let Some(p) = &d.position {
        out.push_str(&format!("<c:dLblPos val=\"{}\"/>", xml_escape::attr(p)));
    }
    if let Some(b) = d.show_legend_key {
        out.push_str(&format!("<c:showLegendKey val=\"{}\"/>", bool_str(b)));
    }
    if let Some(b) = d.show_val {
        out.push_str(&format!("<c:showVal val=\"{}\"/>", bool_str(b)));
    }
    if let Some(b) = d.show_cat_name {
        out.push_str(&format!("<c:showCatName val=\"{}\"/>", bool_str(b)));
    }
    if let Some(b) = d.show_ser_name {
        out.push_str(&format!("<c:showSerName val=\"{}\"/>", bool_str(b)));
    }
    if let Some(b) = d.show_percent {
        out.push_str(&format!("<c:showPercent val=\"{}\"/>", bool_str(b)));
    }
    if let Some(b) = d.show_bubble_size {
        out.push_str(&format!("<c:showBubbleSize val=\"{}\"/>", bool_str(b)));
    }
    if let Some(s) = &d.separator {
        out.push_str(&format!(
            "<c:separator>{}</c:separator>",
            xml_escape::text(s)
        ));
    }
    out.push_str("</c:dLbls>");
}

fn emit_error_bars(out: &mut String, eb: &ErrorBars) {
    out.push_str("<c:errBars>");
    out.push_str(&format!("<c:errBarType val=\"{}\"/>", eb.bar_type.as_str()));
    out.push_str(&format!("<c:errValType val=\"{}\"/>", eb.val_type.as_str()));
    if let Some(b) = eb.no_end_cap {
        out.push_str(&format!("<c:noEndCap val=\"{}\"/>", bool_str(b)));
    }
    if let Some(v) = eb.value {
        out.push_str(&format!("<c:val val=\"{}\"/>", fmt_f64(v)));
    }
    out.push_str("</c:errBars>");
}

fn emit_trendline(out: &mut String, tl: &Trendline) {
    out.push_str("<c:trendline>");
    if let Some(name) = &tl.name {
        out.push_str(&format!("<c:name>{}</c:name>", xml_escape::text(name)));
    }
    out.push_str(&format!("<c:trendlineType val=\"{}\"/>", tl.kind.as_str()));
    if let Some(o) = tl.order {
        if matches!(tl.kind, TrendlineKind::Polynomial) {
            out.push_str(&format!("<c:order val=\"{o}\"/>"));
        }
    }
    if let Some(p) = tl.period {
        if matches!(tl.kind, TrendlineKind::MovingAvg) {
            out.push_str(&format!("<c:period val=\"{p}\"/>"));
        }
    }
    if let Some(f) = tl.forward {
        out.push_str(&format!("<c:forward val=\"{}\"/>", fmt_f64(f)));
    }
    if let Some(b) = tl.backward {
        out.push_str(&format!("<c:backward val=\"{}\"/>", fmt_f64(b)));
    }
    if let Some(b) = tl.display_equation {
        out.push_str(&format!("<c:dispEq val=\"{}\"/>", bool_str(b)));
    }
    if let Some(b) = tl.display_r_squared {
        out.push_str(&format!("<c:dispRSqr val=\"{}\"/>", bool_str(b)));
    }
    out.push_str("</c:trendline>");
}

fn emit_marker(out: &mut String, m: &Marker) {
    out.push_str("<c:marker>");
    out.push_str(&format!("<c:symbol val=\"{}\"/>", m.symbol.as_str()));
    if let Some(s) = m.size {
        out.push_str(&format!("<c:size val=\"{s}\"/>"));
    }
    if let Some(g) = &m.graphical_properties {
        emit_graphical_props(out, g);
    }
    out.push_str("</c:marker>");
}

fn emit_data_point(out: &mut String, d: &DataPoint) {
    out.push_str("<c:dPt>");
    out.push_str(&format!("<c:idx val=\"{}\"/>", d.idx));
    if let Some(b) = d.invert_if_negative {
        out.push_str(&format!("<c:invertIfNegative val=\"{}\"/>", bool_str(b)));
    }
    if let Some(m) = &d.marker {
        emit_marker(out, m);
    }
    if let Some(b) = d.bubble_3d {
        out.push_str(&format!("<c:bubble3D val=\"{}\"/>", bool_str(b)));
    }
    if let Some(n) = d.explosion {
        out.push_str(&format!("<c:explosion val=\"{n}\"/>"));
    }
    if let Some(g) = &d.graphical_properties {
        emit_graphical_props(out, g);
    }
    out.push_str("</c:dPt>");
}
