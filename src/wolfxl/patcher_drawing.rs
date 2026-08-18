//! Drawing helpers for patcher image and chart queues.

use std::collections::HashMap;
use std::fs::File;

use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use zip::ZipArchive;

use crate::ooxml_util;

use super::patcher_models::{QueuedChartAdd, QueuedChartRemove, QueuedImageAdd, QueuedImageAnchor};
use super::patcher_workbook;
use super::{content_types, XlsxPatcher};

pub(crate) fn parse_queued_image_anchor(d: &Bound<'_, PyDict>) -> PyResult<QueuedImageAnchor> {
    let kind: String = d
        .get_item("type")?
        .ok_or_else(|| PyValueError::new_err("anchor dict missing 'type'"))?
        .extract()?;
    let q_int = |key: &str, default: u32| -> PyResult<u32> {
        Ok(d.get_item(key)?
            .and_then(|v| v.extract().ok())
            .unwrap_or(default))
    };
    let q_i64 = |key: &str, default: i64| -> PyResult<i64> {
        Ok(d.get_item(key)?
            .and_then(|v| v.extract().ok())
            .unwrap_or(default))
    };
    match kind.as_str() {
        "one_cell" => Ok(QueuedImageAnchor::OneCell {
            from_col: q_int("from_col", 0)?,
            from_row: q_int("from_row", 0)?,
            from_col_off: q_i64("from_col_off", 0)?,
            from_row_off: q_i64("from_row_off", 0)?,
        }),
        "two_cell" => Ok(QueuedImageAnchor::TwoCell {
            from_col: q_int("from_col", 0)?,
            from_row: q_int("from_row", 0)?,
            from_col_off: q_i64("from_col_off", 0)?,
            from_row_off: q_i64("from_row_off", 0)?,
            to_col: q_int("to_col", 0)?,
            to_row: q_int("to_row", 0)?,
            to_col_off: q_i64("to_col_off", 0)?,
            to_row_off: q_i64("to_row_off", 0)?,
            edit_as: d
                .get_item("edit_as")?
                .and_then(|v| v.extract().ok())
                .unwrap_or_else(|| "oneCell".to_string()),
        }),
        "absolute" => Ok(QueuedImageAnchor::Absolute {
            x_emu: q_i64("x_emu", 0)?,
            y_emu: q_i64("y_emu", 0)?,
            cx_emu: q_i64("cx_emu", 0)?,
            cy_emu: q_i64("cy_emu", 0)?,
        }),
        other => Err(PyValueError::new_err(format!(
            "unknown anchor type: {other:?}"
        ))),
    }
}

/// Build the `xl/drawings/drawingN.xml` body for the queued images.
pub(crate) fn build_drawing_xml(images: &[QueuedImageAdd]) -> String {
    let xdr_ns = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing";
    let a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main";
    let r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
    let emu_per_px: i64 = 9525;
    let mut out = String::with_capacity(512 + images.len() * 512);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!(
        "<xdr:wsDr xmlns:xdr=\"{xdr_ns}\" xmlns:a=\"{a_ns}\" xmlns:r=\"{r_ns}\">"
    ));
    for (i, img) in images.iter().enumerate() {
        let pic_id = (i + 1) as u32;
        let rid = format!("rId{}", i + 1);
        match &img.anchor {
            QueuedImageAnchor::OneCell {
                from_col,
                from_row,
                from_col_off,
                from_row_off,
            } => {
                out.push_str("<xdr:oneCellAnchor>");
                out.push_str(&format!(
                    "<xdr:from><xdr:col>{from_col}</xdr:col><xdr:colOff>{from_col_off}</xdr:colOff>\
                     <xdr:row>{from_row}</xdr:row><xdr:rowOff>{from_row_off}</xdr:rowOff></xdr:from>"
                ));
                let cx = img.width_px as i64 * emu_per_px;
                let cy = img.height_px as i64 * emu_per_px;
                out.push_str(&format!("<xdr:ext cx=\"{cx}\" cy=\"{cy}\"/>"));
            }
            QueuedImageAnchor::TwoCell {
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
                    "<xdr:from><xdr:col>{from_col}</xdr:col><xdr:colOff>{from_col_off}</xdr:colOff>\
                     <xdr:row>{from_row}</xdr:row><xdr:rowOff>{from_row_off}</xdr:rowOff></xdr:from>"
                ));
                out.push_str(&format!(
                    "<xdr:to><xdr:col>{to_col}</xdr:col><xdr:colOff>{to_col_off}</xdr:colOff>\
                     <xdr:row>{to_row}</xdr:row><xdr:rowOff>{to_row_off}</xdr:rowOff></xdr:to>"
                ));
            }
            QueuedImageAnchor::Absolute {
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
        let cx = img.width_px as i64 * emu_per_px;
        let cy = img.height_px as i64 * emu_per_px;
        out.push_str(&format!(
            "<xdr:pic><xdr:nvPicPr><xdr:cNvPr id=\"{pic_id}\" name=\"Picture {pic_id}\" descr=\"Picture {pic_id}\"/>\
             <xdr:cNvPicPr><a:picLocks noChangeAspect=\"1\"/></xdr:cNvPicPr></xdr:nvPicPr>\
             <xdr:blipFill><a:blip xmlns:r=\"{r_ns}\" r:embed=\"{rid}\"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>\
             <xdr:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>\
             <a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic>"
        ));
        out.push_str("<xdr:clientData/>");
        match &img.anchor {
            QueuedImageAnchor::OneCell { .. } => out.push_str("</xdr:oneCellAnchor>"),
            QueuedImageAnchor::TwoCell { .. } => out.push_str("</xdr:twoCellAnchor>"),
            QueuedImageAnchor::Absolute { .. } => out.push_str("</xdr:absoluteAnchor>"),
        }
    }
    out.push_str("</xdr:wsDr>");
    out
}

/// Build `xl/drawings/_rels/drawingN.xml.rels` for the given images.
pub(crate) fn build_drawing_rels_xml(images: &[QueuedImageAdd], image_indices: &[u32]) -> String {
    debug_assert_eq!(images.len(), image_indices.len());
    let mut g = wolfxl_rels::RelsGraph::new();
    for (img, &n) in images.iter().zip(image_indices.iter()) {
        g.add(
            wolfxl_rels::rt::IMAGE,
            &format!("../media/image{n}.{}", img.ext),
            wolfxl_rels::TargetMode::Internal,
        );
    }
    String::from_utf8(g.serialize()).expect("rels serialize is utf8")
}

/// Append one anchor per queued image to an existing drawing XML body.
pub(crate) fn append_pic_anchors(
    drawing_xml: &[u8],
    queued: &[QueuedImageAdd],
    image_rids: &[String],
) -> Result<Vec<u8>, String> {
    debug_assert_eq!(queued.len(), image_rids.len());
    let body = std::str::from_utf8(drawing_xml).map_err(|e| e.to_string())?;
    let use_xdr_prefix = body.contains("<xdr:wsDr") || body.contains("xmlns:xdr=");
    let existing_count: u32 = (body.matches("<xdr:graphicFrame").count()
        + body.matches("<graphicFrame").count()
        + body.matches("<xdr:pic").count()
        + body.matches("<pic").count()) as u32;
    let mut new_anchors = String::with_capacity(queued.len() * 512);
    for (i, (img, rid)) in queued.iter().zip(image_rids.iter()).enumerate() {
        new_anchors.push_str(&render_pic_anchor_styled(
            img,
            rid,
            existing_count + (i + 1) as u32,
            use_xdr_prefix,
        ));
    }
    let pos_opt = body.rfind("</xdr:wsDr>").or_else(|| body.rfind("</wsDr>"));
    if let Some(pos) = pos_opt {
        let mut out = String::with_capacity(body.len() + new_anchors.len());
        out.push_str(&body[..pos]);
        out.push_str(&new_anchors);
        out.push_str(&body[pos..]);
        Ok(out.into_bytes())
    } else {
        let xdr_ns = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing";
        let a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main";
        let r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
        let mut out = String::with_capacity(new_anchors.len() + 256);
        out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
        out.push_str(&format!(
            "<xdr:wsDr xmlns:xdr=\"{xdr_ns}\" xmlns:a=\"{a_ns}\" xmlns:r=\"{r_ns}\">"
        ));
        out.push_str(&new_anchors);
        out.push_str("</xdr:wsDr>");
        Ok(out.into_bytes())
    }
}

fn render_pic_anchor_styled(
    img: &QueuedImageAdd,
    image_rid: &str,
    unique_id: u32,
    use_xdr_prefix: bool,
) -> String {
    let xdr_ns = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing";
    let a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main";
    let r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
    let emu_per_px: i64 = 9525;
    let p = if use_xdr_prefix { "xdr:" } else { "" };
    let root_xmlns = if use_xdr_prefix {
        String::new()
    } else {
        format!(" xmlns=\"{xdr_ns}\" xmlns:a=\"{a_ns}\" xmlns:r=\"{r_ns}\"")
    };

    let mut out = String::with_capacity(768);
    match &img.anchor {
        QueuedImageAnchor::OneCell {
            from_col,
            from_row,
            from_col_off,
            from_row_off,
        } => {
            out.push_str(&format!("<{p}oneCellAnchor{root_xmlns}>"));
            out.push_str(&format!(
                "<{p}from><{p}col>{from_col}</{p}col><{p}colOff>{from_col_off}</{p}colOff>\
                 <{p}row>{from_row}</{p}row><{p}rowOff>{from_row_off}</{p}rowOff></{p}from>"
            ));
            let cx = img.width_px as i64 * emu_per_px;
            let cy = img.height_px as i64 * emu_per_px;
            out.push_str(&format!("<{p}ext cx=\"{cx}\" cy=\"{cy}\"/>"));
        }
        QueuedImageAnchor::TwoCell {
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
            out.push_str(&format!(
                "<{p}twoCellAnchor editAs=\"{edit_as}\"{root_xmlns}>"
            ));
            out.push_str(&format!(
                "<{p}from><{p}col>{from_col}</{p}col><{p}colOff>{from_col_off}</{p}colOff>\
                 <{p}row>{from_row}</{p}row><{p}rowOff>{from_row_off}</{p}rowOff></{p}from>"
            ));
            out.push_str(&format!(
                "<{p}to><{p}col>{to_col}</{p}col><{p}colOff>{to_col_off}</{p}colOff>\
                 <{p}row>{to_row}</{p}row><{p}rowOff>{to_row_off}</{p}rowOff></{p}to>"
            ));
        }
        QueuedImageAnchor::Absolute {
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        } => {
            out.push_str(&format!("<{p}absoluteAnchor{root_xmlns}>"));
            out.push_str(&format!("<{p}pos x=\"{x_emu}\" y=\"{y_emu}\"/>"));
            out.push_str(&format!("<{p}ext cx=\"{cx_emu}\" cy=\"{cy_emu}\"/>"));
        }
    }

    let cx = img.width_px as i64 * emu_per_px;
    let cy = img.height_px as i64 * emu_per_px;
    out.push_str(&format!(
        "<{p}pic xmlns:a=\"{a_ns}\" xmlns:r=\"{r_ns}\">\
         <{p}nvPicPr><{p}cNvPr id=\"{unique_id}\" name=\"Picture {unique_id}\" descr=\"Picture {unique_id}\"/>\
         <{p}cNvPicPr><a:picLocks noChangeAspect=\"1\"/></{p}cNvPicPr></{p}nvPicPr>\
         <{p}blipFill><a:blip r:embed=\"{image_rid}\"/><a:stretch><a:fillRect/></a:stretch></{p}blipFill>\
         <{p}spPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>\
         <a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></{p}spPr></{p}pic>"
    ));
    out.push_str(&format!("<{p}clientData/>"));
    match &img.anchor {
        QueuedImageAnchor::OneCell { .. } => out.push_str(&format!("</{p}oneCellAnchor>")),
        QueuedImageAnchor::TwoCell { .. } => out.push_str(&format!("</{p}twoCellAnchor>")),
        QueuedImageAnchor::Absolute { .. } => out.push_str(&format!("</{p}absoluteAnchor>")),
    }
    out
}

/// Splice a `<drawing r:id="rIdN"/>` element into a sheet XML body.
pub(crate) fn splice_drawing_ref(sheet_xml: &str, rid: &str) -> Result<String, &'static str> {
    if find_start_tag_by_local_name(sheet_xml, "drawing").is_some() {
        return Err("sheet already has a <drawing> element");
    }
    let Some(worksheet) = root_start_tag_by_local_name(sheet_xml, "worksheet") else {
        return Err("sheet xml has no <worksheet> root tag");
    };
    let prefix = worksheet
        .name
        .rsplit_once(':')
        .map(|(p, _)| format!("{p}:"))
        .unwrap_or_default();
    let elem = format!("<{prefix}drawing r:id=\"{rid}\"/>");
    let with_drawing = if let Some(idx) = find_start_tag_by_local_name(sheet_xml, "legacyDrawing") {
        let mut out = String::with_capacity(sheet_xml.len() + elem.len());
        out.push_str(&sheet_xml[..idx]);
        out.push_str(&elem);
        out.push_str(&sheet_xml[idx..]);
        out
    } else if let Some(idx) = find_end_tag_by_local_name(sheet_xml, "worksheet") {
        let mut out = String::with_capacity(sheet_xml.len() + elem.len());
        out.push_str(&sheet_xml[..idx]);
        out.push_str(&elem);
        out.push_str(&sheet_xml[idx..]);
        out
    } else {
        return Err("sheet xml has no </worksheet> closing tag");
    };
    Ok(ensure_xmlns_r_on_worksheet(&with_drawing))
}

/// Ensure the `<worksheet>` root element declares the `r` prefix.
pub(crate) fn ensure_xmlns_r_on_worksheet(sheet_xml: &str) -> String {
    let r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
    let worksheet = match root_start_tag_by_local_name(sheet_xml, "worksheet") {
        Some(tag) => tag,
        None => return sheet_xml.to_string(),
    };
    let start = worksheet.start;
    let end = worksheet.end;
    let open_tag = &sheet_xml[start..=end];
    if open_tag.contains("xmlns:r=") {
        return sheet_xml.to_string();
    }
    let inserted = if open_tag.ends_with("/>") {
        format!("{} xmlns:r=\"{r_ns}\"/>", &open_tag[..open_tag.len() - 2])
    } else {
        format!("{} xmlns:r=\"{r_ns}\">", &open_tag[..open_tag.len() - 1])
    };
    let mut out = String::with_capacity(sheet_xml.len() + 80);
    out.push_str(&sheet_xml[..start]);
    out.push_str(&inserted);
    out.push_str(&sheet_xml[end + 1..]);
    out
}

#[derive(Debug, Clone, Copy)]
struct StartTag<'a> {
    start: usize,
    end: usize,
    name: &'a str,
}

fn root_start_tag_by_local_name<'a>(source: &'a str, local_name: &str) -> Option<StartTag<'a>> {
    let mut idx = 0;
    while let Some(rel) = source[idx..].find('<') {
        let start = idx + rel;
        let after = source[start + 1..].chars().next()?;
        if after == '?' || after == '!' || after == '/' {
            idx = start + 1;
            continue;
        }
        let tag = parse_start_tag(source, start)?;
        return (local_part(tag.name) == local_name).then_some(tag);
    }
    None
}

fn find_start_tag_by_local_name(source: &str, local_name: &str) -> Option<usize> {
    let mut idx = 0;
    while let Some(rel) = source[idx..].find('<') {
        let start = idx + rel;
        let Some(after) = source[start + 1..].chars().next() else {
            return None;
        };
        if after == '?' || after == '!' || after == '/' {
            idx = start + 1;
            continue;
        }
        let Some(tag) = parse_start_tag(source, start) else {
            return None;
        };
        if local_part(tag.name) == local_name {
            return Some(start);
        }
        idx = tag.end + 1;
    }
    None
}

fn find_end_tag_by_local_name(source: &str, local_name: &str) -> Option<usize> {
    let mut out = None;
    let mut idx = 0;
    while let Some(rel) = source[idx..].find("</") {
        let start = idx + rel;
        let name_start = start + 2;
        let name_end = source[name_start..]
            .find(|c: char| c == '>' || c.is_whitespace())
            .map(|rel| name_start + rel)?;
        if local_part(&source[name_start..name_end]) == local_name {
            out = Some(start);
        }
        idx = name_end + 1;
    }
    out
}

fn parse_start_tag<'a>(source: &'a str, start: usize) -> Option<StartTag<'a>> {
    let end = source[start..].find('>').map(|rel| start + rel)?;
    let name_start = start + 1;
    let name_end = source[name_start..]
        .find(|c: char| c == '>' || c == '/' || c.is_whitespace())
        .map(|rel| name_start + rel)?;
    Some(StartTag {
        start,
        end,
        name: &source[name_start..name_end],
    })
}

fn local_part(name: &str) -> &str {
    name.rsplit_once(':')
        .map(|(_, local)| local)
        .unwrap_or(name)
}

/// Parse an A1-style coordinate into zero-based `(col, row)`.
pub(crate) fn parse_a1_coord(s: &str) -> Option<(u32, u32)> {
    let s = s.trim().trim_start_matches('$');
    let mut col: u32 = 0;
    let mut iter = s.chars().peekable();
    let mut col_chars = 0;
    while let Some(&c) = iter.peek() {
        if c.is_ascii_alphabetic() {
            let v = (c.to_ascii_uppercase() as u32) - ('A' as u32) + 1;
            col = col * 26 + v;
            iter.next();
            col_chars += 1;
        } else {
            break;
        }
    }
    if col_chars == 0 || col == 0 {
        return None;
    }
    let rest: String = iter.collect();
    let rest = rest.trim_start_matches('$');
    let row: u32 = rest.parse().ok()?;
    if row == 0 {
        return None;
    }
    Some((col - 1, row - 1))
}

/// Resolve a relative or absolute OOXML rel target against a base directory.
pub(crate) fn resolve_relative_path(base_dir: &str, target: &str) -> String {
    wolfxl_rels::resolve_target(base_dir, target)
}

fn remove_image_anchor_by_index(
    drawing_xml: &[u8],
    remove_index: usize,
) -> Result<(Vec<u8>, String, usize), String> {
    let source = std::str::from_utf8(drawing_xml).map_err(|e| e.to_string())?;
    let mut out = String::with_capacity(source.len());
    let mut cursor = 0usize;
    let mut image_index: usize = 0;
    let mut removed_rid: Option<String> = None;
    let mut kept_anchor_count: usize = 0;

    while let Some((start, end, anchor_xml)) = next_anchor_segment(source, cursor)? {
        out.push_str(&source[cursor..start]);
        let anchor_rid = extract_r_embed(anchor_xml);
        if anchor_rid.is_some() {
            if image_index == remove_index {
                removed_rid = anchor_rid;
            } else {
                out.push_str(anchor_xml);
                kept_anchor_count += 1;
            }
            image_index += 1;
        } else {
            out.push_str(anchor_xml);
            kept_anchor_count += 1;
        }
        cursor = end;
    }
    out.push_str(&source[cursor..]);

    let rid = removed_rid.ok_or_else(|| {
        format!("image index {remove_index} out of range for drawing image count {image_index}")
    })?;
    Ok((out.into_bytes(), rid, kept_anchor_count))
}

fn remove_chart_anchor_by_rid(
    drawing_xml: &[u8],
    chart_rid: &str,
) -> Result<(Vec<u8>, usize), String> {
    let source = std::str::from_utf8(drawing_xml).map_err(|e| e.to_string())?;
    let mut out = String::with_capacity(source.len());
    let mut cursor = 0usize;
    let mut removed = false;
    let mut kept_anchor_count: usize = 0;

    while let Some((start, end, anchor_xml)) = next_anchor_segment(source, cursor)? {
        out.push_str(&source[cursor..start]);
        if anchor_has_chart_rid(anchor_xml, chart_rid) {
            removed = true;
        } else {
            out.push_str(anchor_xml);
            kept_anchor_count += 1;
        }
        cursor = end;
    }
    out.push_str(&source[cursor..]);

    if !removed {
        return Err(format!("chart rId {chart_rid} not found in drawing"));
    }
    Ok((out.into_bytes(), kept_anchor_count))
}

fn next_anchor_segment<'a>(
    source: &'a str,
    from: usize,
) -> Result<Option<(usize, usize, &'a str)>, String> {
    let patterns = [
        "<xdr:oneCellAnchor",
        "<xdr:twoCellAnchor",
        "<xdr:absoluteAnchor",
        "<oneCellAnchor",
        "<twoCellAnchor",
        "<absoluteAnchor",
    ];
    let mut best: Option<usize> = None;
    for pattern in patterns {
        if let Some(rel) = source[from..].find(pattern) {
            let abs = from + rel;
            if best.map(|current| abs < current).unwrap_or(true) {
                best = Some(abs);
            }
        }
    }
    let Some(start) = best else {
        return Ok(None);
    };

    let tag_end = source[start..]
        .find('>')
        .ok_or_else(|| "drawing anchor start tag missing '>'".to_string())?
        + start;
    let start_tag = &source[start + 1..tag_end];
    let tag_name = start_tag
        .split_whitespace()
        .next()
        .ok_or_else(|| "drawing anchor tag name missing".to_string())?;
    if start_tag.trim_end().ends_with('/') {
        let end = tag_end + 1;
        return Ok(Some((start, end, &source[start..end])));
    }
    let close_token = format!("</{tag_name}>");
    let close_rel = source[tag_end + 1..]
        .find(&close_token)
        .ok_or_else(|| format!("closing token {close_token} not found"))?;
    let end = tag_end + 1 + close_rel + close_token.len();
    Ok(Some((start, end, &source[start..end])))
}

fn extract_r_embed(anchor_xml: &str) -> Option<String> {
    let token = "r:embed=\"";
    if let Some(start) = anchor_xml.find(token) {
        let value_start = start + token.len();
        let value_end = anchor_xml[value_start..].find('"')? + value_start;
        return Some(anchor_xml[value_start..value_end].to_string());
    }
    let token_plain = "embed=\"";
    if let Some(start) = anchor_xml.find(token_plain) {
        let value_start = start + token_plain.len();
        let value_end = anchor_xml[value_start..].find('"')? + value_start;
        return Some(anchor_xml[value_start..value_end].to_string());
    }
    None
}

fn anchor_has_chart_rid(anchor_xml: &str, chart_rid: &str) -> bool {
    if !(anchor_xml.contains(":chart") || anchor_xml.contains("<chart")) {
        return false;
    }
    anchor_xml.contains(&format!("r:id=\"{chart_rid}\""))
        || anchor_xml.contains(&format!("id=\"{chart_rid}\""))
}

fn remove_sheet_drawing_ref(sheet_xml: &str, rid: &str) -> Result<String, String> {
    let rid_token = format!("r:id=\"{rid}\"");
    let rid_pos = sheet_xml
        .find(&rid_token)
        .ok_or_else(|| format!("sheet drawing ref {rid} not found"))?;
    let start = sheet_xml[..rid_pos]
        .rfind('<')
        .ok_or_else(|| "sheet drawing tag start not found".to_string())?;
    let tag = parse_start_tag(sheet_xml, start)
        .ok_or_else(|| "sheet drawing tag parse failed".to_string())?;
    if local_part(tag.name) != "drawing" {
        return Err("sheet drawing tag start not found".to_string());
    }
    let tail = &sheet_xml[rid_pos..];
    let end = if let Some(rel) = tail.find("/>") {
        rid_pos + rel + 2
    } else if let Some(rel) = tail.find(&format!("</{}>", tag.name)) {
        rid_pos + rel + tag.name.len() + 3
    } else {
        return Err("sheet drawing tag end not found".into());
    };
    let mut out = String::with_capacity(sheet_xml.len());
    out.push_str(&sheet_xml[..start]);
    out.push_str(&sheet_xml[end..]);
    Ok(out)
}

/// Best-effort extract `N` from `xl/drawings/drawingN.xml`.
#[cfg(test)]
pub(crate) fn drawing_n_from_path(path: &str) -> Option<u32> {
    let fname = path.rsplit('/').next()?;
    let core = fname.strip_suffix(".xml")?;
    let n_str = core.strip_prefix("drawing")?;
    n_str.parse::<u32>().ok()
}

/// Build a fresh `xl/drawings/drawingN.xml` body for queued charts.
pub(crate) fn build_chart_drawing_xml(queued: &[QueuedChartAdd], chart_rids: &[String]) -> String {
    debug_assert_eq!(queued.len(), chart_rids.len());
    let xdr_ns = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing";
    let a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main";
    let r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
    let c_ns = "http://schemas.openxmlformats.org/drawingml/2006/chart";
    let mut out = String::with_capacity(512 + queued.len() * 768);
    out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
    out.push_str(&format!(
        "<xdr:wsDr xmlns:xdr=\"{xdr_ns}\" xmlns:a=\"{a_ns}\" xmlns:r=\"{r_ns}\" xmlns:c=\"{c_ns}\">"
    ));
    for (i, (chart, rid)) in queued.iter().zip(chart_rids.iter()).enumerate() {
        out.push_str(&render_graphic_frame_anchor(chart, rid, (i + 1) as u32));
    }
    out.push_str("</xdr:wsDr>");
    out
}

/// Append one anchor per queued chart to an existing drawing XML body.
pub(crate) fn append_graphic_frames(
    drawing_xml: &[u8],
    queued: &[QueuedChartAdd],
    chart_rids: &[String],
) -> Result<Vec<u8>, String> {
    debug_assert_eq!(queued.len(), chart_rids.len());
    let body = std::str::from_utf8(drawing_xml).map_err(|e| e.to_string())?;
    let use_xdr_prefix = body.contains("<xdr:wsDr") || body.contains("xmlns:xdr=");
    let existing_count: u32 =
        (body.matches("<graphicFrame").count() + body.matches("<pic").count()) as u32;
    let mut new_anchors = String::with_capacity(queued.len() * 512);
    for (i, (chart, rid)) in queued.iter().zip(chart_rids.iter()).enumerate() {
        new_anchors.push_str(&render_graphic_frame_anchor_styled(
            chart,
            rid,
            existing_count + (i + 1) as u32,
            use_xdr_prefix,
        ));
    }
    let pos_opt = body.rfind("</xdr:wsDr>").or_else(|| body.rfind("</wsDr>"));
    if let Some(pos) = pos_opt {
        let mut out = String::with_capacity(body.len() + new_anchors.len());
        out.push_str(&body[..pos]);
        out.push_str(&new_anchors);
        out.push_str(&body[pos..]);
        Ok(out.into_bytes())
    } else {
        let xdr_ns = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing";
        let a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main";
        let r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
        let c_ns = "http://schemas.openxmlformats.org/drawingml/2006/chart";
        let mut out = String::with_capacity(new_anchors.len() + 256);
        out.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\r\n");
        out.push_str(&format!(
            "<xdr:wsDr xmlns:xdr=\"{xdr_ns}\" xmlns:a=\"{a_ns}\" xmlns:r=\"{r_ns}\" xmlns:c=\"{c_ns}\">"
        ));
        out.push_str(&new_anchors);
        out.push_str("</xdr:wsDr>");
        Ok(out.into_bytes())
    }
}

fn render_graphic_frame_anchor(chart: &QueuedChartAdd, chart_rid: &str, unique_id: u32) -> String {
    render_graphic_frame_anchor_styled(chart, chart_rid, unique_id, true)
}

fn render_graphic_frame_anchor_styled(
    chart: &QueuedChartAdd,
    chart_rid: &str,
    unique_id: u32,
    use_xdr_prefix: bool,
) -> String {
    let (col0, row0) = parse_a1_coord(&chart.anchor_a1).unwrap_or((3, 1));
    let cx = chart.width_emu;
    let cy = chart.height_emu;
    let xdr_ns = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing";
    let a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main";
    let r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
    let c_ns = "http://schemas.openxmlformats.org/drawingml/2006/chart";

    let p = if use_xdr_prefix { "xdr:" } else { "" };
    let root_xmlns = if use_xdr_prefix {
        String::new()
    } else {
        format!(" xmlns=\"{xdr_ns}\" xmlns:a=\"{a_ns}\" xmlns:r=\"{r_ns}\" xmlns:c=\"{c_ns}\"")
    };

    let mut out = String::with_capacity(640);
    out.push_str(&format!("<{p}oneCellAnchor{root_xmlns}>"));
    out.push_str(&format!(
        "<{p}from><{p}col>{col0}</{p}col><{p}colOff>0</{p}colOff>\
         <{p}row>{row0}</{p}row><{p}rowOff>0</{p}rowOff></{p}from>"
    ));
    out.push_str(&format!("<{p}ext cx=\"{cx}\" cy=\"{cy}\"/>"));
    out.push_str(&format!(
        "<{p}graphicFrame macro=\"\">\
           <{p}nvGraphicFramePr>\
             <{p}cNvPr id=\"{unique_id}\" name=\"Chart {unique_id}\"/>\
             <{p}cNvGraphicFramePr/>\
           </{p}nvGraphicFramePr>\
           <{p}xfrm>\
             <a:off x=\"0\" y=\"0\" xmlns:a=\"{a_ns}\"/>\
             <a:ext cx=\"{cx}\" cy=\"{cy}\" xmlns:a=\"{a_ns}\"/>\
           </{p}xfrm>\
           <a:graphic xmlns:a=\"{a_ns}\">\
             <a:graphicData uri=\"{c_ns}\">\
               <c:chart xmlns:c=\"{c_ns}\" \
                        xmlns:r=\"{r_ns}\" \
                        r:id=\"{chart_rid}\"/>\
             </a:graphicData>\
           </a:graphic>\
         </{p}graphicFrame>"
    ));
    out.push_str(&format!("<{p}clientData/>"));
    out.push_str(&format!("</{p}oneCellAnchor>"));
    out
}

pub(super) fn apply_image_removes_phase(
    patcher: &mut XlsxPatcher,
    file_patches: &mut HashMap<String, Vec<u8>>,
    zip: &mut ZipArchive<File>,
) -> PyResult<()> {
    let drained: Vec<(String, Vec<usize>)> = patcher
        .sheet_order
        .iter()
        .filter_map(|s| {
            patcher
                .queued_image_removes
                .remove(s)
                .map(|v| (s.clone(), v))
        })
        .collect();
    if drained.is_empty() {
        patcher.queued_image_removes.clear();
        return Ok(());
    }

    for (sheet_name, remove_ops) in drained {
        if remove_ops.is_empty() {
            continue;
        }

        let sheet_path = patcher
            .sheet_paths
            .get(&sheet_name)
            .cloned()
            .ok_or_else(|| {
                PyValueError::new_err(format!("queue_image_remove: no such sheet: {sheet_name}"))
            })?;

        let sheet_rels_path = patcher_workbook::sheet_rels_path_for(&sheet_path);
        let mut sheet_rels =
            patcher_workbook::current_or_empty_rels(patcher, zip, &sheet_rels_path)?;

        for remove_index in remove_ops {
            let drawing_rel = sheet_rels
                .iter()
                .find(|r| r.rel_type == wolfxl_rels::rt::DRAWING)
                .cloned()
                .ok_or_else(|| {
                    PyErr::new::<PyValueError, _>(format!(
                        "queue_image_remove on sheet {sheet_name:?}: sheet has no drawing rel"
                    ))
                })?;

            let sheet_dir = sheet_path
                .rsplit_once('/')
                .map(|(d, _)| d)
                .unwrap_or("")
                .to_string();
            let drawing_path = resolve_relative_path(&sheet_dir, &drawing_rel.target);
            let drawing_rels_path = patcher_workbook::part_rels_path_for(&drawing_path)?;

            let mut drawing_rels =
                patcher_workbook::current_or_empty_rels(patcher, zip, &drawing_rels_path)?;

            let drawing_xml = patcher_workbook::current_part_bytes(
                file_patches,
                &patcher.file_adds,
                zip,
                &drawing_path,
            )
            .ok_or_else(|| {
                PyErr::new::<PyIOError, _>(format!(
                    "queue_image_remove: drawing part missing at {drawing_path}"
                ))
            })?;

            let (updated_xml, removed_rid, kept_anchor_count) =
                remove_image_anchor_by_index(&drawing_xml, remove_index).map_err(|e| {
                    PyErr::new::<PyValueError, _>(format!("queue_image_remove: {e}"))
                })?;
            drawing_rels.remove(&wolfxl_rels::RelId(removed_rid));

            if kept_anchor_count == 0 {
                sheet_rels.remove(&drawing_rel.id);
                let sheet_xml = if let Some(bytes) = file_patches.get(&sheet_path) {
                    String::from_utf8_lossy(bytes).into_owned()
                } else if let Some(bytes) = patcher.file_adds.get(&sheet_path) {
                    String::from_utf8_lossy(bytes).into_owned()
                } else {
                    ooxml_util::zip_read_to_string(zip, &sheet_path)?
                };
                let stripped_sheet_xml = remove_sheet_drawing_ref(&sheet_xml, &drawing_rel.id.0)
                    .map_err(|e| {
                        PyErr::new::<PyIOError, _>(format!("remove sheet drawing ref: {e}"))
                    })?;
                file_patches.insert(sheet_path.clone(), stripped_sheet_xml.into_bytes());
                patcher.file_deletes.insert(drawing_path.clone());
                patcher.file_deletes.insert(drawing_rels_path.clone());
                file_patches.remove(&drawing_path);
                file_patches.remove(&drawing_rels_path);
                patcher.file_adds.remove(&drawing_path);
                patcher.file_adds.remove(&drawing_rels_path);
                patcher.rels_patches.remove(&drawing_rels_path);
            } else {
                if zip.by_name(&drawing_path).is_ok() {
                    file_patches.insert(drawing_path.clone(), updated_xml);
                } else {
                    patcher.file_adds.insert(drawing_path.clone(), updated_xml);
                }
                patcher.rels_patches.insert(drawing_rels_path, drawing_rels);
            }
        }

        patcher.rels_patches.insert(sheet_rels_path, sheet_rels);
    }

    Ok(())
}

pub(super) fn apply_image_adds_phase(
    patcher: &mut XlsxPatcher,
    file_patches: &mut HashMap<String, Vec<u8>>,
    zip: &mut ZipArchive<File>,
    part_id_allocator: &mut wolfxl_rels::PartIdAllocator,
) -> PyResult<()> {
    // Drain queued_images into a stable order — sheet_order so two
    // saves of the same workbook with the same calls produce the
    // same output.
    let drained: Vec<(String, Vec<QueuedImageAdd>)> = patcher
        .sheet_order
        .iter()
        .filter_map(|s| patcher.queued_images.remove(s).map(|v| (s.clone(), v)))
        .collect();
    if drained.is_empty() {
        // Defensive — should be unreachable since the caller checked.
        patcher.queued_images.clear();
        return Ok(());
    }

    for (sheet_name, queued) in drained {
        if queued.is_empty() {
            continue;
        }
        let sheet_path = patcher
            .sheet_paths
            .get(&sheet_name)
            .cloned()
            .ok_or_else(|| {
                PyValueError::new_err(format!("queue_image_add: no such sheet: {sheet_name}"))
            })?;

        let sheet_rels_path = patcher_workbook::sheet_rels_path_for(&sheet_path);
        let mut rels_graph =
            patcher_workbook::current_or_empty_rels(patcher, zip, &sheet_rels_path)?;

        let existing_drawing_target = rels_graph
            .iter()
            .find(|r| r.rel_type == wolfxl_rels::rt::DRAWING)
            .map(|r| r.target.clone());

        let image_indices: Vec<u32> = queued
            .iter()
            .map(|_| part_id_allocator.alloc_image())
            .collect();

        for (img, &n) in queued.iter().zip(image_indices.iter()) {
            let media_path = format!("xl/media/image{n}.{}", img.ext);
            patcher.file_adds.insert(media_path, img.data.clone());
        }

        let mut seen_exts: std::collections::HashSet<String> = std::collections::HashSet::new();
        let mut ops: Vec<content_types::ContentTypeOp> = Vec::new();
        for img in &queued {
            if seen_exts.insert(img.ext.clone()) {
                let ct = content_types::image_content_type_for_ext(&img.ext);
                ops.push(content_types::ContentTypeOp::EnsureDefault(
                    img.ext.clone(),
                    ct.to_string(),
                ));
            }
        }

        if let Some(target) = existing_drawing_target {
            let sheet_dir = sheet_path
                .rsplit_once('/')
                .map(|(d, _)| d)
                .unwrap_or("")
                .to_string();
            let drawing_path = resolve_relative_path(&sheet_dir, &target);
            let drawing_rels_path = patcher_workbook::part_rels_path_for(&drawing_path)?;
            let mut drawing_rels =
                patcher_workbook::current_or_empty_rels(patcher, zip, &drawing_rels_path)?;
            let mut image_rids: Vec<String> = Vec::with_capacity(queued.len());
            for (img, &n) in queued.iter().zip(image_indices.iter()) {
                let rid = drawing_rels.add(
                    wolfxl_rels::rt::IMAGE,
                    &format!("../media/image{n}.{}", img.ext),
                    wolfxl_rels::TargetMode::Internal,
                );
                image_rids.push(rid.0);
            }
            let existing_drawing_xml = patcher_workbook::current_part_bytes(
                file_patches,
                &patcher.file_adds,
                zip,
                &drawing_path,
            )
            .unwrap_or_default();
            let merged = append_pic_anchors(&existing_drawing_xml, &queued, &image_rids)
                .map_err(|e| PyErr::new::<PyIOError, _>(format!("merge drawing: {e}")))?;
            if zip.by_name(&drawing_path).is_ok() {
                file_patches.insert(drawing_path.clone(), merged);
            } else {
                patcher.file_adds.insert(drawing_path.clone(), merged);
            }
            patcher.rels_patches.insert(drawing_rels_path, drawing_rels);
        } else {
            let drawing_n = part_id_allocator.alloc_drawing();
            let drawing_xml = build_drawing_xml(&queued);
            let drawing_rels_xml = build_drawing_rels_xml(&queued, &image_indices);
            let drawing_path = format!("xl/drawings/drawing{drawing_n}.xml");
            let drawing_rels_path = format!("xl/drawings/_rels/drawing{drawing_n}.xml.rels");
            patcher
                .file_adds
                .insert(drawing_path.clone(), drawing_xml.into_bytes());
            patcher
                .file_adds
                .insert(drawing_rels_path, drawing_rels_xml.into_bytes());

            let drawing_rid = rels_graph.add(
                wolfxl_rels::rt::DRAWING,
                &format!("../drawings/drawing{drawing_n}.xml"),
                wolfxl_rels::TargetMode::Internal,
            );

            let sheet_xml = if let Some(b) = file_patches.get(&sheet_path) {
                String::from_utf8_lossy(b).into_owned()
            } else if let Some(b) = patcher.file_adds.get(&sheet_path) {
                String::from_utf8_lossy(b).into_owned()
            } else {
                ooxml_util::zip_read_to_string(zip, &sheet_path)?
            };
            let after = splice_drawing_ref(&sheet_xml, &drawing_rid.0)
                .map_err(|e| PyErr::new::<PyIOError, _>(format!("splice drawing: {e}")))?;
            file_patches.insert(sheet_path.clone(), after.into_bytes());

            ops.push(content_types::ContentTypeOp::AddOverride(
                format!("/xl/drawings/drawing{drawing_n}.xml"),
                content_types::CT_DRAWING.to_string(),
            ));
        }

        patcher.rels_patches.insert(sheet_rels_path, rels_graph);
        patcher
            .queued_content_type_ops
            .entry(format!("__rfc045_images_{sheet_name}__"))
            .or_default()
            .extend(ops);
    }
    Ok(())
}

pub(super) fn apply_chart_removes_phase(
    patcher: &mut XlsxPatcher,
    file_patches: &mut HashMap<String, Vec<u8>>,
    zip: &mut ZipArchive<File>,
) -> PyResult<()> {
    let drained: Vec<(String, Vec<QueuedChartRemove>)> = patcher
        .sheet_order
        .iter()
        .filter_map(|s| {
            patcher
                .queued_chart_removes
                .remove(s)
                .map(|v| (s.clone(), v))
        })
        .collect();
    if drained.is_empty() {
        patcher.queued_chart_removes.clear();
        return Ok(());
    }

    for (sheet_name, remove_ops) in drained {
        let sheet_path = patcher
            .sheet_paths
            .get(&sheet_name)
            .cloned()
            .ok_or_else(|| {
                PyValueError::new_err(format!("queue_chart_remove: no such sheet: {sheet_name}"))
            })?;
        let sheet_rels_path = patcher_workbook::sheet_rels_path_for(&sheet_path);
        let mut sheet_rels =
            patcher_workbook::current_or_empty_rels(patcher, zip, &sheet_rels_path)?;

        for op in remove_ops {
            let drawing_rels_path = patcher_workbook::part_rels_path_for(&op.drawing_path)?;
            let mut drawing_rels =
                patcher_workbook::current_or_empty_rels(patcher, zip, &drawing_rels_path)?;
            let drawing_xml = patcher_workbook::current_part_bytes(
                file_patches,
                &patcher.file_adds,
                zip,
                &op.drawing_path,
            )
            .ok_or_else(|| {
                PyErr::new::<PyIOError, _>(format!(
                    "queue_chart_remove: drawing part missing at {}",
                    op.drawing_path
                ))
            })?;
            let (updated_xml, kept_anchor_count) =
                remove_chart_anchor_by_rid(&drawing_xml, &op.chart_rid).map_err(|e| {
                    PyErr::new::<PyValueError, _>(format!("queue_chart_remove: {e}"))
                })?;
            drawing_rels.remove(&wolfxl_rels::RelId(op.chart_rid.clone()));
            patcher.file_deletes.insert(op.chart_path.clone());
            let chart_rels_path = patcher_workbook::part_rels_path_for(&op.chart_path)?;
            patcher.file_deletes.insert(chart_rels_path);
            patcher
                .queued_content_type_ops
                .entry("__chart_removes__".to_string())
                .or_default()
                .push(content_types::ContentTypeOp::RemoveOverride(format!(
                    "/{}",
                    op.chart_path
                )));

            if kept_anchor_count == 0 {
                if should_preserve_empty_drawing_shell(&drawing_xml, &updated_xml) {
                    if zip.by_name(&op.drawing_path).is_ok() {
                        file_patches.insert(op.drawing_path.clone(), updated_xml);
                    } else {
                        patcher
                            .file_adds
                            .insert(op.drawing_path.clone(), updated_xml);
                    }
                    if drawing_rels.is_empty() {
                        patcher.file_deletes.insert(drawing_rels_path.clone());
                        file_patches.remove(&drawing_rels_path);
                        patcher.file_adds.remove(&drawing_rels_path);
                        patcher.rels_patches.remove(&drawing_rels_path);
                    } else {
                        patcher.rels_patches.insert(drawing_rels_path, drawing_rels);
                    }
                    continue;
                }
                let drawing_rel = sheet_rels
                    .iter()
                    .find(|r| r.rel_type == wolfxl_rels::rt::DRAWING)
                    .cloned();
                if let Some(drawing_rel) = drawing_rel {
                    sheet_rels.remove(&drawing_rel.id);
                    let sheet_xml = if let Some(bytes) = file_patches.get(&sheet_path) {
                        String::from_utf8_lossy(bytes).into_owned()
                    } else if let Some(bytes) = patcher.file_adds.get(&sheet_path) {
                        String::from_utf8_lossy(bytes).into_owned()
                    } else {
                        ooxml_util::zip_read_to_string(zip, &sheet_path)?
                    };
                    let stripped_sheet_xml =
                        remove_sheet_drawing_ref(&sheet_xml, &drawing_rel.id.0).map_err(|e| {
                            PyErr::new::<PyIOError, _>(format!("remove sheet drawing ref: {e}"))
                        })?;
                    file_patches.insert(sheet_path.clone(), stripped_sheet_xml.into_bytes());
                }
                patcher.file_deletes.insert(op.drawing_path.clone());
                patcher.file_deletes.insert(drawing_rels_path.clone());
                file_patches.remove(&op.drawing_path);
                file_patches.remove(&drawing_rels_path);
                patcher.file_adds.remove(&op.drawing_path);
                patcher.file_adds.remove(&drawing_rels_path);
                patcher.rels_patches.remove(&drawing_rels_path);
                patcher
                    .queued_content_type_ops
                    .entry("__chart_removes__".to_string())
                    .or_default()
                    .push(content_types::ContentTypeOp::RemoveOverride(format!(
                        "/{}",
                        op.drawing_path
                    )));
            } else {
                if zip.by_name(&op.drawing_path).is_ok() {
                    file_patches.insert(op.drawing_path.clone(), updated_xml);
                } else {
                    patcher
                        .file_adds
                        .insert(op.drawing_path.clone(), updated_xml);
                }
                patcher.rels_patches.insert(drawing_rels_path, drawing_rels);
            }
        }

        patcher.rels_patches.insert(sheet_rels_path, sheet_rels);
    }
    Ok(())
}

fn should_preserve_empty_drawing_shell(original_xml: &[u8], updated_xml: &[u8]) -> bool {
    let Ok(original) = std::str::from_utf8(original_xml) else {
        return false;
    };
    let Ok(updated) = std::str::from_utf8(updated_xml) else {
        return false;
    };
    if drawing_root_has_relationship_namespace(original) {
        return false;
    }
    find_start_tag_by_local_name(updated, "oneCellAnchor").is_none()
        && find_start_tag_by_local_name(updated, "twoCellAnchor").is_none()
        && find_start_tag_by_local_name(updated, "absoluteAnchor").is_none()
}

fn drawing_root_has_relationship_namespace(drawing_xml: &str) -> bool {
    let Some(root) = root_start_tag_by_local_name(drawing_xml, "wsDr") else {
        return false;
    };
    drawing_xml[root.start..=root.end].contains("xmlns:r=")
}

pub(super) fn apply_chart_adds_phase(
    patcher: &mut XlsxPatcher,
    file_patches: &mut HashMap<String, Vec<u8>>,
    zip: &mut ZipArchive<File>,
    part_id_allocator: &mut wolfxl_rels::PartIdAllocator,
) -> PyResult<()> {
    // Drain in sheet_order for stable output across saves.
    let drained: Vec<(String, Vec<QueuedChartAdd>)> = patcher
        .sheet_order
        .iter()
        .filter_map(|s| patcher.queued_charts.remove(s).map(|v| (s.clone(), v)))
        .collect();
    if drained.is_empty() {
        patcher.queued_charts.clear();
        return Ok(());
    }

    for (sheet_name, queued) in drained {
        if queued.is_empty() {
            continue;
        }
        let sheet_path = patcher
            .sheet_paths
            .get(&sheet_name)
            .cloned()
            .ok_or_else(|| {
                PyValueError::new_err(format!("queue_chart_add: no such sheet: {sheet_name}"))
            })?;

        // 1. Get sheet rels graph (rels_patches → file_adds → ZIP).
        let sheet_rels_path = patcher_workbook::sheet_rels_path_for(&sheet_path);
        let mut sheet_rels =
            patcher_workbook::current_or_empty_rels(patcher, zip, &sheet_rels_path)?;

        // 2. Probe for existing drawing rel + drawing path.
        let mut existing_drawing_target: Option<String> = None;
        for r in sheet_rels.iter() {
            if r.rel_type == wolfxl_rels::rt::DRAWING {
                existing_drawing_target = Some(r.target.clone());
                break;
            }
        }

        // Allocate one chart part per queued chart.
        let chart_indices: Vec<u32> = queued
            .iter()
            .map(|_| part_id_allocator.alloc_chart())
            .collect();

        // Pre-content-type ops accumulator for this sheet.
        let mut ct_ops: Vec<content_types::ContentTypeOp> = Vec::new();
        for &n in &chart_indices {
            ct_ops.push(content_types::ContentTypeOp::AddOverride(
                format!("/xl/charts/chart{n}.xml"),
                content_types::CT_CHART.to_string(),
            ));
        }

        // Emit the chart XML parts up front.
        for (chart, &n) in queued.iter().zip(chart_indices.iter()) {
            let path = format!("xl/charts/chart{n}.xml");
            patcher.file_adds.insert(path, chart.chart_xml.clone());
        }

        // Branch on fresh vs. existing drawing.
        let drawing_path: String;
        let drawing_rels_path: String;
        let mut drawing_rels: wolfxl_rels::RelsGraph;
        let new_drawing_xml_bytes: Vec<u8>;
        if let Some(target) = existing_drawing_target {
            // Existing: resolve the drawing path relative to the
            // OWNING PART's directory (i.e. the sheet itself, not
            // the rels file). Rels targets are interpreted
            // relative to the part the rels graph describes —
            // here that's `xl/worksheets/sheetN.xml`, so the base
            // is `xl/worksheets/`.
            let sheet_dir = sheet_path
                .rsplit_once('/')
                .map(|(d, _)| d)
                .unwrap_or("")
                .to_string();
            let resolved = resolve_relative_path(&sheet_dir, &target);
            drawing_path = resolved.clone();
            drawing_rels_path = patcher_workbook::part_rels_path_for(&drawing_path)?;
            // Load existing drawing rels (if any) — drawing
            // graphs without rels are legal but rare.
            drawing_rels =
                patcher_workbook::current_or_empty_rels(patcher, zip, &drawing_rels_path)?;
            // Add a chart rel per queued chart.
            let mut chart_rids: Vec<String> = Vec::with_capacity(queued.len());
            for &n in &chart_indices {
                let rid = drawing_rels.add(
                    wolfxl_rels::rt::CHART,
                    &format!("../charts/chart{n}.xml"),
                    wolfxl_rels::TargetMode::Internal,
                );
                chart_rids.push(rid.0);
            }
            // Read existing drawing XML.
            let existing_drawing_xml = patcher_workbook::current_part_bytes(
                file_patches,
                &patcher.file_adds,
                zip,
                &drawing_path,
            )
            .unwrap_or_default();
            // SAX-merge: append a graphicFrame per queued chart.
            let merged = append_graphic_frames(&existing_drawing_xml, &queued, &chart_rids)
                .map_err(|e| PyErr::new::<PyIOError, _>(format!("merge drawing: {e}")))?;
            new_drawing_xml_bytes = merged;
            // No new <Override> for the drawing — already in
            // [Content_Types].xml.
        } else {
            // Fresh drawing.
            let drawing_n = part_id_allocator.alloc_drawing();
            drawing_path = format!("xl/drawings/drawing{drawing_n}.xml");
            drawing_rels_path = format!("xl/drawings/_rels/drawing{drawing_n}.xml.rels");
            drawing_rels = wolfxl_rels::RelsGraph::new();
            let mut chart_rids: Vec<String> = Vec::with_capacity(queued.len());
            for &n in &chart_indices {
                let rid = drawing_rels.add(
                    wolfxl_rels::rt::CHART,
                    &format!("../charts/chart{n}.xml"),
                    wolfxl_rels::TargetMode::Internal,
                );
                chart_rids.push(rid.0);
            }
            // Build a fresh drawing XML body.
            let body = build_chart_drawing_xml(&queued, &chart_rids);
            new_drawing_xml_bytes = body.into_bytes();
            // Splice <drawing r:id> into sheet XML.
            let drawing_rid = sheet_rels.add(
                wolfxl_rels::rt::DRAWING,
                &format!("../drawings/drawing{drawing_n}.xml"),
                wolfxl_rels::TargetMode::Internal,
            );
            let sheet_xml = if let Some(b) = file_patches.get(&sheet_path) {
                String::from_utf8_lossy(b).into_owned()
            } else if let Some(b) = patcher.file_adds.get(&sheet_path) {
                String::from_utf8_lossy(b).into_owned()
            } else {
                ooxml_util::zip_read_to_string(zip, &sheet_path)?
            };
            let after = splice_drawing_ref(&sheet_xml, &drawing_rid.0)
                .map_err(|e| PyErr::new::<PyIOError, _>(format!("splice drawing: {e}")))?;
            file_patches.insert(sheet_path.clone(), after.into_bytes());
            ct_ops.push(content_types::ContentTypeOp::AddOverride(
                format!("/xl/drawings/drawing{drawing_n}.xml"),
                content_types::CT_DRAWING.to_string(),
            ));
        }

        // Emit drawing XML + drawing rels into file_adds /
        // file_patches. We use file_patches for in-place updates
        // of an existing drawing (so the per-emit pass picks the
        // mutated bytes); file_adds for fresh-drawing emit. The
        // ZIP probe is the source-of-truth: if the path is
        // already in the source ZIP we MUST patch (file_adds
        // panics on collision in the final emit pass).
        if zip.by_name(&drawing_path).is_ok() {
            file_patches.insert(drawing_path.clone(), new_drawing_xml_bytes);
        } else {
            patcher
                .file_adds
                .insert(drawing_path.clone(), new_drawing_xml_bytes);
        }
        patcher.rels_patches.insert(drawing_rels_path, drawing_rels);

        // Persist sheet rels mutation.
        patcher.rels_patches.insert(sheet_rels_path, sheet_rels);

        // Queue content-type ops under a synthetic per-sheet key.
        patcher
            .queued_content_type_ops
            .entry(format!("__rfc046_charts_{sheet_name}__"))
            .or_default()
            .extend(ct_ops);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splice_drawing_before_legacy_drawing() {
        let xml = r#"<?xml version="1.0"?><worksheet><sheetData/><legacyDrawing r:id="rId2"/></worksheet>"#;
        let out = splice_drawing_ref(xml, "rId5").unwrap();
        assert!(out.contains("<drawing r:id=\"rId5\"/><legacyDrawing"));
    }

    #[test]
    fn splice_drawing_before_close_when_no_legacy() {
        let xml = r#"<?xml version="1.0"?><worksheet><sheetData/></worksheet>"#;
        let out = splice_drawing_ref(xml, "rId1").unwrap();
        assert!(out.contains("<drawing r:id=\"rId1\"/></worksheet>"));
    }

    #[test]
    fn splice_drawing_handles_prefixed_worksheet_root() {
        let xml = r#"<?xml version="1.0"?><x:worksheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><x:sheetData/><x:legacyDrawing r:id="rId2"/></x:worksheet>"#;
        let out = splice_drawing_ref(xml, "rId5").unwrap();
        assert!(out.contains("<x:drawing r:id=\"rId5\"/><x:legacyDrawing"));
        assert!(out.contains(
            "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\""
        ));
    }

    #[test]
    fn splice_drawing_errors_when_prefixed_drawing_already_present() {
        let xml = r#"<x:worksheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><x:sheetData/><x:drawing r:id="rId7"/></x:worksheet>"#;
        assert!(splice_drawing_ref(xml, "rId1").is_err());
    }

    #[test]
    fn splice_drawing_errors_when_already_present() {
        let xml =
            r#"<?xml version="1.0"?><worksheet><sheetData/><drawing r:id="rId7"/></worksheet>"#;
        assert!(splice_drawing_ref(xml, "rId1").is_err());
    }

    #[test]
    fn build_drawing_xml_roundtrip() {
        let imgs = vec![QueuedImageAdd {
            data: vec![],
            ext: "png".into(),
            width_px: 10,
            height_px: 5,
            anchor: QueuedImageAnchor::OneCell {
                from_col: 1,
                from_row: 4,
                from_col_off: 0,
                from_row_off: 0,
            },
        }];
        let xml = build_drawing_xml(&imgs);
        assert!(xml.contains("<xdr:oneCellAnchor>"));
        assert!(xml.contains("r:embed=\"rId1\""));
    }

    #[test]
    fn parse_a1_basic_cells() {
        assert_eq!(parse_a1_coord("A1"), Some((0, 0)));
        assert_eq!(parse_a1_coord("D2"), Some((3, 1)));
        assert_eq!(parse_a1_coord("Z1"), Some((25, 0)));
        assert_eq!(parse_a1_coord("AA1"), Some((26, 0)));
        assert_eq!(parse_a1_coord("$D$2"), Some((3, 1)));
        assert!(parse_a1_coord("").is_none());
        assert!(parse_a1_coord("1A").is_none());
    }

    #[test]
    fn resolve_relative_basic() {
        assert_eq!(
            resolve_relative_path("xl/worksheets", "../drawings/drawing1.xml"),
            "xl/drawings/drawing1.xml"
        );
        assert_eq!(
            resolve_relative_path("xl/drawings", "../charts/chart1.xml"),
            "xl/charts/chart1.xml"
        );
    }

    #[test]
    fn drawing_n_extract() {
        assert_eq!(drawing_n_from_path("xl/drawings/drawing7.xml"), Some(7));
        assert_eq!(drawing_n_from_path("xl/drawings/drawing.xml"), None);
        assert_eq!(drawing_n_from_path("nope.xml"), None);
    }

    #[test]
    fn build_drawing_xml_for_one_chart() {
        let q = vec![QueuedChartAdd {
            chart_xml: b"<chartSpace/>".to_vec(),
            anchor_a1: "D2".into(),
            width_emu: 4_572_000,
            height_emu: 2_743_200,
        }];
        let rids = vec!["rId1".to_string()];
        let body = build_chart_drawing_xml(&q, &rids);
        assert!(body.contains("<xdr:graphicFrame"));
        assert!(body.contains("r:id=\"rId1\""));
        assert!(body.contains("<xdr:col>3</xdr:col>"));
        assert!(body.contains("<xdr:row>1</xdr:row>"));
    }

    #[test]
    fn append_graphic_frame_inserts_before_close() {
        let original = b"<?xml version=\"1.0\"?><xdr:wsDr xmlns:xdr=\"x\" xmlns:r=\"r\" xmlns:c=\"c\"><xdr:oneCellAnchor/></xdr:wsDr>";
        let q = vec![QueuedChartAdd {
            chart_xml: vec![],
            anchor_a1: "B5".into(),
            width_emu: 100,
            height_emu: 200,
        }];
        let rids = vec!["rId7".to_string()];
        let merged = append_graphic_frames(original, &q, &rids).unwrap();
        let s = std::str::from_utf8(&merged).unwrap();
        assert!(s.contains("<xdr:oneCellAnchor/>"));
        assert!(s.contains("<xdr:graphicFrame"));
        assert!(s.contains("r:id=\"rId7\""));
        assert!(s.ends_with("</xdr:wsDr>"));
    }

    #[test]
    fn append_pic_anchor_inserts_before_close() {
        let original = b"<?xml version=\"1.0\"?><xdr:wsDr xmlns:xdr=\"x\" xmlns:a=\"a\" xmlns:r=\"r\"><xdr:oneCellAnchor><xdr:pic><xdr:blipFill><a:blip r:embed=\"rId1\"/></xdr:blipFill></xdr:pic><xdr:clientData/></xdr:oneCellAnchor></xdr:wsDr>";
        let imgs = vec![QueuedImageAdd {
            data: vec![],
            ext: "png".into(),
            width_px: 10,
            height_px: 5,
            anchor: QueuedImageAnchor::OneCell {
                from_col: 3,
                from_row: 4,
                from_col_off: 0,
                from_row_off: 0,
            },
        }];
        let rids = vec!["rId2".to_string()];
        let merged = append_pic_anchors(original, &imgs, &rids).unwrap();
        let s = std::str::from_utf8(&merged).unwrap();
        assert!(s.contains("r:embed=\"rId1\""));
        assert!(s.contains("r:embed=\"rId2\""));
        assert!(s.contains("<xdr:col>3</xdr:col>"));
        assert_eq!(s.matches("<xdr:pic").count(), 2);
        assert!(s.ends_with("</xdr:wsDr>"));
    }

    #[test]
    fn remove_image_anchor_by_index_removes_expected_rid() {
        let xml = br#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <xdr:oneCellAnchor>
    <xdr:pic><xdr:blipFill><a:blip r:embed="rId1"/></xdr:blipFill></xdr:pic><xdr:clientData/>
  </xdr:oneCellAnchor>
  <xdr:oneCellAnchor>
    <xdr:pic><xdr:blipFill><a:blip r:embed="rId2"/></xdr:blipFill></xdr:pic><xdr:clientData/>
  </xdr:oneCellAnchor>
</xdr:wsDr>"#;
        let (updated, removed_rid, kept_anchor_count) =
            remove_image_anchor_by_index(xml, 1).unwrap();
        let s = String::from_utf8(updated).unwrap();
        assert_eq!(removed_rid, "rId2");
        assert_eq!(kept_anchor_count, 1);
        assert!(s.contains("r:embed=\"rId1\""));
        assert!(!s.contains("r:embed=\"rId2\""));
    }

    #[test]
    fn remove_sheet_drawing_ref_drops_exact_tag() {
        let xml = r#"<?xml version="1.0"?><worksheet><sheetData/><drawing r:id="rId7"/><legacyDrawing r:id="rId9"/></worksheet>"#;
        let out = remove_sheet_drawing_ref(xml, "rId7").unwrap();
        assert!(!out.contains("rId7"));
        assert!(out.contains("<legacyDrawing r:id=\"rId9\"/>"));
    }

    #[test]
    fn remove_sheet_drawing_ref_drops_prefixed_tag() {
        let xml = r#"<x:worksheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><x:sheetData/><x:drawing r:id="rId7"/><x:legacyDrawing r:id="rId9"/></x:worksheet>"#;
        let out = remove_sheet_drawing_ref(xml, "rId7").unwrap();
        assert!(!out.contains("rId7"));
        assert!(out.contains("<x:legacyDrawing r:id=\"rId9\"/>"));
    }
}
