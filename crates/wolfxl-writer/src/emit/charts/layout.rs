//! Chart layout, legend, and 3D-view emission.

use crate::model::chart::{Layout, Legend, View3D};

use super::primitives::{bool_str, fmt_f64};

pub(super) fn emit_legend(out: &mut String, l: &Legend) {
    out.push_str("<c:legend>");
    out.push_str(&format!("<c:legendPos val=\"{}\"/>", l.position.as_str()));
    if let Some(layout) = &l.layout {
        emit_layout(out, layout);
    }
    if let Some(o) = l.overlay {
        out.push_str(&format!("<c:overlay val=\"{}\"/>", bool_str(o)));
    }
    out.push_str("</c:legend>");
}

pub(super) fn emit_layout(out: &mut String, layout: &Layout) {
    out.push_str("<c:layout>");
    out.push_str("<c:manualLayout>");
    if let Some(t) = layout.layout_target {
        out.push_str(&format!("<c:layoutTarget val=\"{}\"/>", t.as_str()));
    }
    out.push_str("<c:xMode val=\"edge\"/>");
    out.push_str("<c:yMode val=\"edge\"/>");
    out.push_str(&format!("<c:x val=\"{}\"/>", fmt_f64(layout.x)));
    out.push_str(&format!("<c:y val=\"{}\"/>", fmt_f64(layout.y)));
    out.push_str(&format!("<c:w val=\"{}\"/>", fmt_f64(layout.w)));
    out.push_str(&format!("<c:h val=\"{}\"/>", fmt_f64(layout.h)));
    out.push_str("</c:manualLayout>");
    out.push_str("</c:layout>");
}

/// Emit `<c:view3D>` at chart level before plotArea.
pub(super) fn emit_view_3d(out: &mut String, v: &View3D) {
    out.push_str("<c:view3D>");
    if let Some(rx) = v.rot_x {
        out.push_str(&format!("<c:rotX val=\"{rx}\"/>"));
    }
    if let Some(ry) = v.rot_y {
        out.push_str(&format!("<c:rotY val=\"{ry}\"/>"));
    }
    if let Some(p) = v.perspective {
        out.push_str(&format!("<c:perspective val=\"{p}\"/>"));
    }
    if let Some(b) = v.right_angle_axes {
        out.push_str(&format!("<c:rAngAx val=\"{}\"/>", bool_str(b)));
    }
    if let Some(b) = v.auto_scale {
        out.push_str(&format!("<c:autoScale val=\"{}\"/>", bool_str(b)));
    }
    if let Some(d) = v.depth_percent {
        out.push_str(&format!("<c:depthPercent val=\"{d}\"/>"));
    }
    if let Some(h) = v.h_percent {
        out.push_str(&format!("<c:hPercent val=\"{h}\"/>"));
    }
    out.push_str("</c:view3D>");
}
