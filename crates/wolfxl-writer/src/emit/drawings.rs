//! `xl/drawings/drawingN.xml` emitter.
//!
//! One drawing part per sheet that has at least one image or chart.
//! The part is a `<xdr:wsDr>` element containing one
//! `<xdr:oneCellAnchor>` / `<xdr:twoCellAnchor>` / `<xdr:absoluteAnchor>`
//! per visual, each wrapping a `<xdr:pic>` (for images, referencing the
//! image rel by `r:embed`) or a `<xdr:graphicFrame>` (for charts,
//! referencing the chart rel by `r:id`).
//!
//! # Coordinate units
//!
//! - `oneCellAnchor`/`twoCellAnchor`: 0-based `<col>` + `<row>` plus
//!   per-axis EMU offsets (`<colOff>`, `<rowOff>`). Pixel offsets are
//!   converted using 9525 EMU per pixel (Excel's standard for 96 DPI).
//! - `absoluteAnchor`: raw EMU `<pos>` and `<ext>`.
//!
//! # Constants
//!
//! `EMU_PER_PIXEL = 9525` matches openpyxl's
//! ``openpyxl.utils.units.pixels_to_EMU`` which uses 914400 EMU/inch ÷
//! 96 px/inch = 9525 EMU/px. The output is byte-stable for
//! `WOLFXL_TEST_EPOCH=0`.

use crate::model::image::{ImageAnchor, SheetImage};

const EMU_PER_PIXEL: i64 = 9525;

/// One visual on a sheet's drawing part.
#[derive(Debug, Clone)]
pub enum DrawingItem {
    /// Image — emitted as `<xdr:pic>` inside the anchor.
    Image {
        image: SheetImage,
        /// Pre-allocated rId in the drawing's _rels (e.g. `"rId1"`).
        rid: String,
    },
    /// Chart — emitted as `<xdr:graphicFrame>` inside the anchor. The
    /// `chart_id` is the per-drawing graphicFrame id (1-based, unique
    /// within this part). The `rid` points at the chart rel in
    /// `xl/drawings/_rels/drawingN.xml.rels`.
    Chart {
        anchor: ImageAnchor,
        rid: String,
        chart_id: u32,
        name: String,
    },
}

/// XML namespaces used by `xdr:wsDr`. Excel emits these in this exact
/// order; openpyxl ignores order on read but downstream byte-equality
/// targets require we match upstream.
const XDR_NS: &str = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing";
const A_NS: &str = "http://schemas.openxmlformats.org/drawingml/2006/main";
const R_NS: &str = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

/// Emit `xl/drawings/drawingN.xml` for the given list of images.
///
/// `image_rel_ids` is parallel to `images` — each entry is the `rId` (e.g.
/// `"rId3"`) the caller has allocated in the drawing's `_rels/drawingN.xml.rels`
/// for that image. The emitter writes `r:embed="rIdN"` on each `<a:blip>`.
pub fn emit(images: &[SheetImage], image_rel_ids: &[String]) -> Vec<u8> {
    debug_assert_eq!(images.len(), image_rel_ids.len());

    let mut out = String::with_capacity(512 + images.len() * 512);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!(
        "<xdr:wsDr xmlns:xdr=\"{XDR_NS}\" xmlns:a=\"{A_NS}\" xmlns:r=\"{R_NS}\">"
    ));

    // 1-based picture id (cNvPr's `id` attr) — unique within this part.
    for (i, (img, rid)) in images.iter().zip(image_rel_ids.iter()).enumerate() {
        let pic_id = (i + 1) as u32;
        emit_anchor_open(&mut out, img);
        emit_pic(&mut out, pic_id, rid, img);
        emit_anchor_close(&mut out, &img.anchor);
    }

    out.push_str("</xdr:wsDr>");
    out.into_bytes()
}

/// Emit `xl/drawings/drawingN.xml` for a mixed list of [`DrawingItem`]s.
///
/// Used by the writer driver when at least one chart is anchored on the sheet.
///
/// The cNvPr `id` is unique within the part; we assign it as 1+index
/// in the items list so a chart that appears third on a sheet with
/// two prior images has cNvPr id="3".
pub fn emit_drawing_xml(items: &[DrawingItem]) -> Vec<u8> {
    let mut out = String::with_capacity(512 + items.len() * 600);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!(
        "<xdr:wsDr xmlns:xdr=\"{XDR_NS}\" xmlns:a=\"{A_NS}\" xmlns:r=\"{R_NS}\">"
    ));
    for (i, item) in items.iter().enumerate() {
        let cnv_id = (i + 1) as u32;
        match item {
            DrawingItem::Image { image, rid } => {
                emit_anchor_open(&mut out, image);
                emit_pic(&mut out, cnv_id, rid, image);
                emit_anchor_close(&mut out, &image.anchor);
            }
            DrawingItem::Chart {
                anchor,
                rid,
                chart_id: _,
                name,
            } => {
                emit_chart_anchor_open(&mut out, anchor);
                emit_graphic_frame(&mut out, cnv_id, rid, name);
                emit_anchor_close(&mut out, anchor);
            }
        }
    }
    out.push_str("</xdr:wsDr>");
    out.into_bytes()
}

fn emit_anchor_open(out: &mut String, img: &SheetImage) {
    match &img.anchor {
        ImageAnchor::OneCell {
            from_col,
            from_row,
            from_col_off,
            from_row_off,
        } => {
            out.push_str("<xdr:oneCellAnchor>");
            out.push_str(&format!(
                "<xdr:from><xdr:col>{}</xdr:col><xdr:colOff>{}</xdr:colOff>\
                 <xdr:row>{}</xdr:row><xdr:rowOff>{}</xdr:rowOff></xdr:from>",
                from_col, from_col_off, from_row, from_row_off
            ));
            // Extent from image pixel dimensions (Excel default for
            // one-cell anchors lacks a `<to>` element; uses `<ext>`).
            let cx = img.width_px as i64 * EMU_PER_PIXEL;
            let cy = img.height_px as i64 * EMU_PER_PIXEL;
            out.push_str(&format!("<xdr:ext cx=\"{cx}\" cy=\"{cy}\"/>"));
        }
        ImageAnchor::TwoCell {
            from_col,
            from_row,
            from_col_off,
            from_row_off,
            to_col,
            to_row,
            to_col_off,
            to_row_off,
            edit_as,
        } => {
            // editAs is "oneCell" / "twoCell" / "absolute"; default
            // openpyxl emits "oneCell" for cell-anchored images.
            out.push_str(&format!("<xdr:twoCellAnchor editAs=\"{edit_as}\">"));
            out.push_str(&format!(
                "<xdr:from><xdr:col>{}</xdr:col><xdr:colOff>{}</xdr:colOff>\
                 <xdr:row>{}</xdr:row><xdr:rowOff>{}</xdr:rowOff></xdr:from>",
                from_col, from_col_off, from_row, from_row_off
            ));
            out.push_str(&format!(
                "<xdr:to><xdr:col>{}</xdr:col><xdr:colOff>{}</xdr:colOff>\
                 <xdr:row>{}</xdr:row><xdr:rowOff>{}</xdr:rowOff></xdr:to>",
                to_col, to_col_off, to_row, to_row_off
            ));
        }
        ImageAnchor::Absolute {
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        } => {
            out.push_str("<xdr:absoluteAnchor>");
            out.push_str(&format!("<xdr:pos x=\"{x_emu}\" y=\"{y_emu}\"/>"));
            out.push_str(&format!("<xdr:ext cx=\"{cx_emu}\" cy=\"{cy_emu}\"/>"));
        }
    }
}

fn emit_anchor_close(out: &mut String, anchor: &ImageAnchor) {
    // The `<xdr:clientData/>` is required by all three anchor flavours.
    out.push_str("<xdr:clientData/>");
    match anchor {
        ImageAnchor::OneCell { .. } => out.push_str("</xdr:oneCellAnchor>"),
        ImageAnchor::TwoCell { .. } => out.push_str("</xdr:twoCellAnchor>"),
        ImageAnchor::Absolute { .. } => out.push_str("</xdr:absoluteAnchor>"),
    }
}

/// Open an anchor element for a chart. Charts don't carry pixel
/// dimensions, so a `OneCell` anchor uses a default ext (one cell wide
/// × ten rows tall ≈ openpyxl's `default_size`). Two-cell anchors use
/// the explicit `to_*` cells; absolute anchors use the explicit EMU.
fn emit_chart_anchor_open(out: &mut String, anchor: &ImageAnchor) {
    match anchor {
        ImageAnchor::OneCell {
            from_col,
            from_row,
            from_col_off,
            from_row_off,
        } => {
            out.push_str("<xdr:oneCellAnchor>");
            out.push_str(&format!(
                "<xdr:from><xdr:col>{}</xdr:col><xdr:colOff>{}</xdr:colOff>\
                 <xdr:row>{}</xdr:row><xdr:rowOff>{}</xdr:rowOff></xdr:from>",
                from_col, from_col_off, from_row, from_row_off
            ));
            // Default chart ext: 15 cols × 10 rows ≈ openpyxl default. We
            // pick 5_400_000 × 3_000_000 EMU which renders close to that.
            out.push_str("<xdr:ext cx=\"5400000\" cy=\"3000000\"/>");
        }
        ImageAnchor::TwoCell {
            from_col,
            from_row,
            from_col_off,
            from_row_off,
            to_col,
            to_row,
            to_col_off,
            to_row_off,
            edit_as,
        } => {
            out.push_str(&format!("<xdr:twoCellAnchor editAs=\"{edit_as}\">"));
            out.push_str(&format!(
                "<xdr:from><xdr:col>{}</xdr:col><xdr:colOff>{}</xdr:colOff>\
                 <xdr:row>{}</xdr:row><xdr:rowOff>{}</xdr:rowOff></xdr:from>",
                from_col, from_col_off, from_row, from_row_off
            ));
            out.push_str(&format!(
                "<xdr:to><xdr:col>{}</xdr:col><xdr:colOff>{}</xdr:colOff>\
                 <xdr:row>{}</xdr:row><xdr:rowOff>{}</xdr:rowOff></xdr:to>",
                to_col, to_col_off, to_row, to_row_off
            ));
        }
        ImageAnchor::Absolute {
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        } => {
            out.push_str("<xdr:absoluteAnchor>");
            out.push_str(&format!("<xdr:pos x=\"{x_emu}\" y=\"{y_emu}\"/>"));
            out.push_str(&format!("<xdr:ext cx=\"{cx_emu}\" cy=\"{cy_emu}\"/>"));
        }
    }
}

/// Emit a `<xdr:graphicFrame>` referencing a chart part. The element
/// shape matches openpyxl's GraphicFrame emit:
///
/// ```xml
/// <xdr:graphicFrame macro="">
///   <xdr:nvGraphicFramePr>
///     <xdr:cNvPr id="3" name="Chart 1"/>
///     <xdr:cNvGraphicFramePr/>
///   </xdr:nvGraphicFramePr>
///   <xdr:xfrm>
///     <a:off x="0" y="0"/>
///     <a:ext cx="0" cy="0"/>
///   </xdr:xfrm>
///   <a:graphic>
///     <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">
///       <c:chart xmlns:c="…/chart" xmlns:r="…/relationships" r:id="rId1"/>
///     </a:graphicData>
///   </a:graphic>
/// </xdr:graphicFrame>
/// ```
fn emit_graphic_frame(out: &mut String, cnv_id: u32, rid: &str, name: &str) {
    out.push_str("<xdr:graphicFrame macro=\"\">");
    out.push_str("<xdr:nvGraphicFramePr>");
    out.push_str(&format!("<xdr:cNvPr id=\"{cnv_id}\" name=\"{name}\"/>"));
    out.push_str("<xdr:cNvGraphicFramePr/>");
    out.push_str("</xdr:nvGraphicFramePr>");
    out.push_str("<xdr:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/></xdr:xfrm>");
    out.push_str("<a:graphic>");
    out.push_str("<a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/chart\">");
    out.push_str(&format!(
        "<c:chart xmlns:c=\"http://schemas.openxmlformats.org/drawingml/2006/chart\" \
         xmlns:r=\"{R_NS}\" r:id=\"{rid}\"/>"
    ));
    out.push_str("</a:graphicData>");
    out.push_str("</a:graphic>");
    out.push_str("</xdr:graphicFrame>");
}

fn emit_pic(out: &mut String, pic_id: u32, rid: &str, img: &SheetImage) {
    let cx = img.width_px as i64 * EMU_PER_PIXEL;
    let cy = img.height_px as i64 * EMU_PER_PIXEL;
    let name = format!("Picture {pic_id}");
    out.push_str("<xdr:pic>");
    // <xdr:nvPicPr>
    out.push_str("<xdr:nvPicPr>");
    out.push_str(&format!(
        "<xdr:cNvPr id=\"{pic_id}\" name=\"{name}\" descr=\"{name}\"/>"
    ));
    out.push_str("<xdr:cNvPicPr><a:picLocks noChangeAspect=\"1\"/></xdr:cNvPicPr>");
    out.push_str("</xdr:nvPicPr>");
    // <xdr:blipFill>
    out.push_str(&format!(
        "<xdr:blipFill><a:blip xmlns:r=\"{R_NS}\" r:embed=\"{rid}\"/>\
         <a:stretch><a:fillRect/></a:stretch></xdr:blipFill>"
    ));
    // <xdr:spPr>
    out.push_str("<xdr:spPr>");
    out.push_str(&format!(
        "<a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>"
    ));
    out.push_str("<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>");
    out.push_str("</xdr:spPr>");
    out.push_str("</xdr:pic>");
}

/// Compute the OOXML content type for a given image extension. Used by
/// the content-types emitter to write `<Default Extension="png" .../>`.
pub fn content_type_for_ext(ext: &str) -> &'static str {
    match ext.to_ascii_lowercase().as_str() {
        "png" => "image/png",
        "jpeg" | "jpg" => "image/jpeg",
        "gif" => "image/gif",
        "bmp" => "image/bmp",
        "tiff" | "tif" => "image/tiff",
        _ => "application/octet-stream",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::image::{ImageAnchor, SheetImage};
    use quick_xml::events::Event;
    use quick_xml::Reader;

    fn dummy_img(anchor: ImageAnchor) -> SheetImage {
        SheetImage {
            data: b"\x89PNG\r\n\x1a\n".to_vec(),
            ext: "png".into(),
            width_px: 100,
            height_px: 50,
            anchor,
        }
    }

    fn parse_ok(bytes: &[u8]) {
        let text = std::str::from_utf8(bytes).expect("utf8");
        let mut reader = Reader::from_str(text);
        let mut buf = Vec::new();
        loop {
            match reader.read_event_into(&mut buf) {
                Ok(Event::Eof) => break,
                Err(e) => panic!("parse error: {e}"),
                _ => (),
            }
            buf.clear();
        }
    }

    #[test]
    fn one_cell_anchor_emits_xdr_one_cell_anchor() {
        let img = dummy_img(ImageAnchor::one_cell(1, 4));
        let bytes = emit(&[img], &["rId1".to_string()]);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<xdr:oneCellAnchor>"), "wrong anchor: {text}");
        assert!(text.contains("<xdr:col>1</xdr:col>"));
        assert!(text.contains("<xdr:row>4</xdr:row>"));
        // Extent from 100x50 px @ 9525 EMU/px.
        assert!(text.contains("cx=\"952500\""));
        assert!(text.contains("cy=\"476250\""));
        assert!(text.contains("r:embed=\"rId1\""));
    }

    #[test]
    fn two_cell_anchor_emits_to() {
        let img = dummy_img(ImageAnchor::TwoCell {
            from_col: 1,
            from_row: 4,
            from_col_off: 0,
            from_row_off: 0,
            to_col: 5,
            to_row: 10,
            to_col_off: 0,
            to_row_off: 0,
            edit_as: "oneCell".into(),
        });
        let bytes = emit(&[img], &["rId1".to_string()]);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<xdr:twoCellAnchor editAs=\"oneCell\">"));
        assert!(text.contains("<xdr:from>"));
        assert!(text.contains("<xdr:to>"));
        assert!(text.contains("<xdr:col>5</xdr:col>"));
        assert!(text.contains("<xdr:row>10</xdr:row>"));
    }

    #[test]
    fn absolute_anchor_uses_emu() {
        let img = dummy_img(ImageAnchor::Absolute {
            x_emu: 0,
            y_emu: 0,
            cx_emu: 914400,
            cy_emu: 914400,
        });
        let bytes = emit(&[img], &["rId1".to_string()]);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<xdr:absoluteAnchor>"));
        assert!(text.contains("<xdr:pos x=\"0\" y=\"0\"/>"));
        assert!(text.contains("<xdr:ext cx=\"914400\" cy=\"914400\"/>"));
    }

    #[test]
    fn multiple_images_assigned_distinct_pic_ids() {
        let imgs = vec![
            dummy_img(ImageAnchor::one_cell(0, 0)),
            dummy_img(ImageAnchor::one_cell(2, 2)),
        ];
        let rids = vec!["rId1".to_string(), "rId2".to_string()];
        let bytes = emit(&imgs, &rids);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("id=\"1\""));
        assert!(text.contains("id=\"2\""));
        assert!(text.contains("r:embed=\"rId1\""));
        assert!(text.contains("r:embed=\"rId2\""));
    }

    #[test]
    fn content_type_for_known_extensions() {
        assert_eq!(content_type_for_ext("png"), "image/png");
        assert_eq!(content_type_for_ext("PNG"), "image/png");
        assert_eq!(content_type_for_ext("jpeg"), "image/jpeg");
        assert_eq!(content_type_for_ext("jpg"), "image/jpeg");
        assert_eq!(content_type_for_ext("gif"), "image/gif");
        assert_eq!(content_type_for_ext("bmp"), "image/bmp");
        assert_eq!(content_type_for_ext("xyz"), "application/octet-stream");
    }

    #[test]
    fn emits_well_formed_xml_when_empty() {
        let bytes = emit(&[], &[]);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<xdr:wsDr"));
        assert!(text.contains("</xdr:wsDr>"));
    }

    // ----- Chart anchors via graphicFrame ---------------------------------

    #[test]
    fn drawing_xml_with_chart_only_emits_graphic_frame() {
        let items = vec![DrawingItem::Chart {
            anchor: ImageAnchor::one_cell(2, 4),
            rid: "rId1".to_string(),
            chart_id: 1,
            name: "Chart 1".to_string(),
        }];
        let bytes = emit_drawing_xml(&items);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<xdr:graphicFrame macro=\"\">"));
        assert!(text.contains("<xdr:cNvPr id=\"1\" name=\"Chart 1\"/>"));
        assert!(text.contains("r:id=\"rId1\""));
        assert!(text.contains("uri=\"http://schemas.openxmlformats.org/drawingml/2006/chart\""));
        // OneCell anchor with default chart ext.
        assert!(text.contains("<xdr:oneCellAnchor>"));
        assert!(text.contains("<xdr:ext cx=\"5400000\" cy=\"3000000\"/>"));
    }

    #[test]
    fn drawing_xml_mixes_image_then_chart() {
        let items = vec![
            DrawingItem::Image {
                image: dummy_img(ImageAnchor::one_cell(0, 0)),
                rid: "rId1".to_string(),
            },
            DrawingItem::Chart {
                anchor: ImageAnchor::TwoCell {
                    from_col: 1,
                    from_row: 4,
                    from_col_off: 0,
                    from_row_off: 0,
                    to_col: 5,
                    to_row: 10,
                    to_col_off: 0,
                    to_row_off: 0,
                    edit_as: "oneCell".into(),
                },
                rid: "rId2".to_string(),
                chart_id: 1,
                name: "Chart 1".to_string(),
            },
        ];
        let bytes = emit_drawing_xml(&items);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<xdr:pic>"));
        assert!(text.contains("<xdr:graphicFrame"));
        // First item gets cNvPr id=1, second gets id=2.
        assert!(text.contains("<xdr:cNvPr id=\"2\" name=\"Chart 1\"/>"));
        // Two-cell anchor for chart.
        assert!(text.contains("<xdr:twoCellAnchor"));
    }

    #[test]
    fn drawing_xml_chart_with_absolute_anchor() {
        let items = vec![DrawingItem::Chart {
            anchor: ImageAnchor::Absolute {
                x_emu: 1_000_000,
                y_emu: 2_000_000,
                cx_emu: 5_000_000,
                cy_emu: 3_000_000,
            },
            rid: "rId7".to_string(),
            chart_id: 1,
            name: "My Chart".to_string(),
        }];
        let bytes = emit_drawing_xml(&items);
        parse_ok(&bytes);
        let text = String::from_utf8(bytes).unwrap();
        assert!(text.contains("<xdr:absoluteAnchor>"));
        assert!(text.contains("<xdr:pos x=\"1000000\" y=\"2000000\"/>"));
        assert!(text.contains("<xdr:ext cx=\"5000000\" cy=\"3000000\"/>"));
        assert!(text.contains("<xdr:cNvPr id=\"1\" name=\"My Chart\"/>"));
        assert!(text.contains("r:id=\"rId7\""));
    }
}
