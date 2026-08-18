//! Chart graphical property emission.

use crate::model::chart::GraphicalProperties;
use crate::xml_escape;

use super::primitives::strip_alpha;

pub(super) fn emit_graphical_props(out: &mut String, g: &GraphicalProperties) {
    out.push_str("<c:spPr>");
    if g.no_fill {
        out.push_str("<a:noFill/>");
    } else if let Some(c) = &g.fill_color {
        out.push_str(&format!(
            "<a:solidFill><a:srgbClr val=\"{}\"/></a:solidFill>",
            strip_alpha(c)
        ));
    }

    let has_line_attrs =
        g.line_color.is_some() || g.line_width_emu.is_some() || g.line_dash.is_some() || g.no_line;
    if has_line_attrs {
        if let Some(w) = g.line_width_emu {
            out.push_str(&format!("<a:ln w=\"{w}\">"));
        } else {
            out.push_str("<a:ln>");
        }
        if g.no_line {
            out.push_str("<a:noFill/>");
        } else if let Some(c) = &g.line_color {
            out.push_str(&format!(
                "<a:solidFill><a:srgbClr val=\"{}\"/></a:solidFill>",
                strip_alpha(c)
            ));
        }
        if let Some(d) = &g.line_dash {
            out.push_str(&format!("<a:prstDash val=\"{}\"/>", xml_escape::attr(d)));
        }
        out.push_str("</a:ln>");
    }
    out.push_str("</c:spPr>");
}
