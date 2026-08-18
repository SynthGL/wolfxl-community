use std::io::Cursor;

use crate::{AlignmentInfo, BorderInfo, FillInfo, FontInfo, StyleTables, XfEntry};
use zip::ZipArchive;

use super::{
    find_trailing_wide_string, le_u16, le_u32, read_zip_part_optional, wide_string, Records, Result,
};

pub(super) fn read_styles(zip: &mut ZipArchive<Cursor<Vec<u8>>>) -> Result<StyleTables> {
    let Some(data) = read_zip_part_optional(zip, "xl/styles.bin")? else {
        return Ok(StyleTables::default());
    };
    let mut styles = StyleTables::default();
    let mut in_cell_xfs = false;
    for record in Records::new(&data) {
        let record = record?;
        match record.typ {
            0x0269 => in_cell_xfs = true,
            0x026a => in_cell_xfs = false,
            0x002c => {
                if record.payload.len() >= 6 {
                    let id = le_u16(&record.payload[0..2]) as u32;
                    let mut consumed = 0;
                    let code = wide_string(&record.payload[2..], &mut consumed)?;
                    styles.custom_num_fmts.insert(id, code);
                }
            }
            0x002b => styles.fonts.push(parse_font(record.payload)),
            0x002d => styles.fills.push(parse_fill(record.payload)),
            0x002e => styles.borders.push(parse_border(record.payload)),
            0x002f if in_cell_xfs => styles.cell_xfs.push(parse_xf(record.payload)),
            _ => {}
        }
    }
    if styles.cell_xfs.is_empty() {
        styles.cell_xfs.push(XfEntry::default());
    }
    Ok(styles)
}

fn parse_xf(payload: &[u8]) -> XfEntry {
    XfEntry {
        num_fmt_id: payload.get(2..4).map(le_u16).unwrap_or_default() as u32,
        font_id: payload.get(4..6).map(le_u16).unwrap_or_default() as u32,
        border_id: payload.get(6..8).map(le_u16).unwrap_or_default() as u32,
        fill_id: payload.get(8..10).map(le_u16).unwrap_or_default() as u32,
        // XLSB BIFF12 BrtXF carries xfId at bytes 0..2 of the payload, but
        // we keep it 0 for now: named-style support is XLSX-only at this
        // stage. Wire this up when XLSB write or modify needs it.
        xf_id: 0,
        alignment: parse_binary_alignment(payload),
        protection: None,
    }
}

fn parse_font(payload: &[u8]) -> FontInfo {
    let mut font = FontInfo::default();
    if payload.len() >= 2 {
        let size_twips = le_u16(&payload[0..2]);
        if size_twips > 0 {
            font.size = Some(size_twips as f64 / 20.0);
        }
    }
    if let Some((_, name)) = find_trailing_wide_string(payload) {
        if !name.is_empty() {
            font.name = Some(name);
        }
    }
    font
}

fn parse_fill(payload: &[u8]) -> FillInfo {
    let _ = payload;
    FillInfo::default()
}

fn parse_border(payload: &[u8]) -> BorderInfo {
    let _ = payload;
    BorderInfo::default()
}

fn parse_binary_alignment(payload: &[u8]) -> Option<AlignmentInfo> {
    let flags = payload.get(12..16).map(le_u32).unwrap_or_default();
    let wrap_text = flags & 0x20 != 0;
    wrap_text.then_some(AlignmentInfo {
        horizontal: None,
        vertical: None,
        wrap_text,
        text_rotation: None,
        indent: None,
    })
}
