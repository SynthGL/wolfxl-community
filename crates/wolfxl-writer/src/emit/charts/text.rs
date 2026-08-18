//! Chart title and series-title emission.

use crate::model::chart::{SeriesTitle, Title, TitleRun};
use crate::xml_escape;

use super::layout::emit_layout;
use super::primitives::{bool_str, strip_alpha};

pub(super) fn emit_series_title(out: &mut String, title: &SeriesTitle) {
    out.push_str("<c:tx>");
    match title {
        SeriesTitle::StrRef(r) => {
            out.push_str("<c:strRef>");
            out.push_str(&format!(
                "<c:f>{}</c:f>",
                xml_escape::text(&r.to_series_title_formula_string())
            ));
            out.push_str("</c:strRef>");
        }
        SeriesTitle::Literal(s) => {
            out.push_str("<c:v>");
            out.push_str(&xml_escape::text(s));
            out.push_str("</c:v>");
        }
    }
    out.push_str("</c:tx>");
}

pub(super) fn emit_title(out: &mut String, t: &Title) {
    out.push_str("<c:title>");
    out.push_str("<c:tx>");
    out.push_str("<c:rich>");
    out.push_str("<a:bodyPr/>");
    out.push_str("<a:p>");
    out.push_str("<a:pPr><a:defRPr/></a:pPr>");
    for run in &t.runs {
        emit_run(out, run);
    }
    out.push_str("</a:p>");
    out.push_str("</c:rich>");
    out.push_str("</c:tx>");
    if let Some(layout) = &t.layout {
        emit_layout(out, layout);
    }
    if let Some(o) = t.overlay {
        out.push_str(&format!("<c:overlay val=\"{}\"/>", bool_str(o)));
    }
    out.push_str("</c:title>");
}

/// `<c:txPr>` for data labels and axes - wraps run-level rich-text
/// formatting in the same `<a:bodyPr><a:p>` skeleton chart titles use,
/// without the surrounding `<c:tx>` container.
pub(super) fn emit_tx_pr(out: &mut String, runs: &[TitleRun]) {
    out.push_str("<c:txPr>");
    out.push_str("<a:bodyPr/>");
    out.push_str("<a:lstStyle/>");
    out.push_str("<a:p>");
    out.push_str("<a:pPr><a:defRPr/></a:pPr>");
    for run in runs {
        emit_run(out, run);
    }
    out.push_str("</a:p>");
    out.push_str("</c:txPr>");
}

fn emit_run(out: &mut String, run: &TitleRun) {
    out.push_str("<a:r>");
    let mut rpr = String::new();
    if let Some(sz) = run.size_pt {
        // Excel encodes pt as 100 * pt.
        rpr.push_str(&format!(" sz=\"{}\"", sz * 100));
    }
    if let Some(b) = run.bold {
        rpr.push_str(&format!(" b=\"{}\"", bool_str(b)));
    }
    if let Some(i) = run.italic {
        rpr.push_str(&format!(" i=\"{}\"", bool_str(i)));
    }
    if let Some(u) = run.underline {
        rpr.push_str(if u { " u=\"sng\"" } else { " u=\"none\"" });
    }
    let has_rpr = !rpr.is_empty() || run.color.is_some() || run.font_name.is_some();
    if has_rpr {
        out.push_str(&format!("<a:rPr lang=\"en-US\"{rpr}>"));
        if let Some(c) = &run.color {
            out.push_str(&format!(
                "<a:solidFill><a:srgbClr val=\"{}\"/></a:solidFill>",
                strip_alpha(c)
            ));
        }
        if let Some(f) = &run.font_name {
            out.push_str(&format!("<a:latin typeface=\"{}\"/>", xml_escape::attr(f)));
        }
        out.push_str("</a:rPr>");
    }
    out.push_str("<a:t>");
    out.push_str(&xml_escape::text(&run.text));
    out.push_str("</a:t>");
    out.push_str("</a:r>");
}
