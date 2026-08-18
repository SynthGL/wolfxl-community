use crate::{
    row_col_to_a1, ColumnWidth, Comment, FreezePane, HeaderFooterInfo, HeaderFooterItemInfo,
    Hyperlink, PageMarginsInfo, PageSetupInfo, PaneMode, PrintOptionsInfo, RowHeight,
    SelectionInfo, SheetFormatInfo, SheetPropertiesInfo, SheetProtection, SheetViewInfo,
};
use wolfxl_rels::{RelId, RelsGraph};

use super::{
    find_trailing_wide_string, le_f64, le_i32, le_u16, le_u32, wide_string, Records, Result,
};

#[derive(Debug, Clone, Copy, PartialEq)]
pub(super) struct RowHeaderInfo {
    pub(super) row: u32,
    pub(super) hidden: bool,
    pub(super) outline_level: u8,
    pub(super) height: Option<RowHeight>,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub(super) struct ColumnInfo {
    pub(super) width: ColumnWidth,
    pub(super) hidden: bool,
    pub(super) outline_level: u8,
}

pub(super) fn parse_ws_dimension(payload: &[u8]) -> Option<String> {
    if payload.len() < 16 {
        return None;
    }
    let min_row = le_u32(&payload[0..4]) + 1;
    let max_row = le_u32(&payload[4..8]) + 1;
    let min_col = le_u32(&payload[8..12]) + 1;
    let max_col = le_u32(&payload[12..16]) + 1;
    if max_row < min_row || max_col < min_col {
        return None;
    }
    Some(format!(
        "{}:{}",
        row_col_to_a1(min_row, min_col),
        row_col_to_a1(max_row, max_col)
    ))
}

pub(super) fn parse_row_header(payload: &[u8]) -> Option<RowHeaderInfo> {
    if payload.len() < 12 {
        return None;
    }
    let row = le_u32(&payload[0..4]) + 1;
    let height_twips = le_u16(&payload[8..10]);
    let flags = le_u16(&payload[10..12]);
    let outline_level = ((flags >> 8) & 0x07) as u8;
    let hidden = flags & 0x1000 != 0;
    let custom_height = flags & 0x2000 != 0;
    let height = custom_height.then_some(RowHeight {
        height: height_twips as f64 / 20.0,
        custom_height: true,
    });
    Some(RowHeaderInfo {
        row,
        hidden,
        outline_level,
        height,
    })
}

pub(super) fn parse_column_info(payload: &[u8]) -> Option<ColumnInfo> {
    if payload.len() < 18 {
        return None;
    }
    let min = le_u32(&payload[0..4]) + 1;
    let max = le_u32(&payload[4..8]) + 1;
    let width_raw = le_u32(&payload[8..12]);
    let flags = le_u16(&payload[16..18]);
    Some(ColumnInfo {
        width: ColumnWidth {
            min,
            max,
            width: width_raw as f64 / 256.0,
            custom_width: flags & 0x0002 != 0,
        },
        hidden: flags & 0x0001 != 0,
        outline_level: ((flags >> 8) & 0x07) as u8,
    })
}

pub(super) fn parse_merged_range(payload: &[u8]) -> Option<String> {
    if payload.len() < 16 {
        return None;
    }
    let first_row = le_u32(&payload[0..4]) + 1;
    let last_row = le_u32(&payload[4..8]) + 1;
    let first_col = le_u32(&payload[8..12]) + 1;
    let last_col = le_u32(&payload[12..16]) + 1;
    if last_row < first_row || last_col < first_col {
        return None;
    }
    Some(format!(
        "{}:{}",
        row_col_to_a1(first_row, first_col),
        row_col_to_a1(last_row, last_col)
    ))
}

pub(super) fn parse_pane(payload: &[u8]) -> Option<FreezePane> {
    if payload.len() < 29 {
        return None;
    }
    let x_split = le_f64(&payload[0..8]);
    let y_split = le_f64(&payload[8..16]);
    let top_row = le_u32(&payload[16..20]) + 1;
    let left_col = le_u32(&payload[20..24]) + 1;
    let active_pane = active_pane_name(le_u32(&payload[24..28]));
    let flags = payload[28];
    let frozen = flags & 0x03 != 0;
    Some(FreezePane {
        mode: if frozen {
            PaneMode::Freeze
        } else {
            PaneMode::Split
        },
        top_left_cell: Some(row_col_to_a1(top_row, left_col)),
        x_split: Some(x_split.round() as i64),
        y_split: Some(y_split.round() as i64),
        active_pane,
    })
}

fn active_pane_name(pnn: u32) -> Option<String> {
    let name = match pnn {
        0 => "bottomRight",
        1 => "topRight",
        2 => "bottomLeft",
        3 => "topLeft",
        _ => return None,
    };
    Some(name.to_string())
}

pub(super) fn parse_sheet_view(payload: &[u8]) -> Option<SheetViewInfo> {
    if payload.len() < 30 {
        return None;
    }
    let flags = le_u16(&payload[0..2]);
    let view = match le_u32(&payload[2..6]) {
        1 => "pageBreakPreview",
        2 => "pageLayout",
        _ => "normal",
    };
    let top_row = le_u32(&payload[6..10]) + 1;
    let left_col = le_u32(&payload[10..14]) + 1;
    let top_left_cell = (top_row != 1 || left_col != 1).then(|| row_col_to_a1(top_row, left_col));
    Some(SheetViewInfo {
        zoom_scale: le_u16(&payload[18..20]) as u32,
        zoom_scale_normal: match le_u16(&payload[20..22]) as u32 {
            0 => 100,
            value => value,
        },
        view: view.to_string(),
        show_grid_lines: Some(flags & 0x0004 != 0),
        show_row_col_headers: Some(flags & 0x0008 != 0),
        show_outline_symbols: Some(flags & 0x0100 != 0),
        show_zeros: Some(flags & 0x0010 != 0),
        right_to_left: Some(flags & 0x0020 != 0),
        tab_selected: Some(flags & 0x0040 != 0),
        top_left_cell,
        workbook_view_id: le_u32(&payload[26..30]),
        pane: None,
        selections: Vec::new(),
    })
}

pub(super) fn parse_selection(payload: &[u8]) -> Option<SelectionInfo> {
    if payload.len() < 20 {
        return None;
    }
    let pane = active_pane_name(le_u32(&payload[0..4]));
    let active_row = le_u32(&payload[4..8]) + 1;
    let active_col = le_u32(&payload[8..12]) + 1;
    let active_cell_id = le_u32(&payload[12..16]);
    let active_cell = row_col_to_a1(active_row, active_col);
    Some(SelectionInfo {
        pane,
        active_cell: Some(active_cell.clone()),
        sqref: parse_sqref(payload.get(16..)?).or(Some(active_cell)),
        active_cell_id: Some(active_cell_id),
    })
}

pub(super) fn parse_sqref(payload: &[u8]) -> Option<String> {
    let count = payload.get(0..4).map(le_u32)? as usize;
    if count == 0 {
        return None;
    }
    let ranges: Vec<String> = payload
        .get(4..)?
        .chunks_exact(16)
        .take(count)
        .filter_map(parse_rfx)
        .collect();
    (!ranges.is_empty()).then(|| ranges.join(" "))
}

pub(super) fn parse_rfx(payload: &[u8]) -> Option<String> {
    if payload.len() < 16 {
        return None;
    }
    let first_row = le_u32(&payload[0..4]) + 1;
    let last_row = le_u32(&payload[4..8]) + 1;
    let first_col = le_u32(&payload[8..12]) + 1;
    let last_col = le_u32(&payload[12..16]) + 1;
    if last_row < first_row || last_col < first_col {
        return None;
    }
    let first = row_col_to_a1(first_row, first_col);
    let last = row_col_to_a1(last_row, last_col);
    if first == last {
        Some(first)
    } else {
        Some(format!("{first}:{last}"))
    }
}

#[derive(Debug)]
pub(super) struct HyperlinkNode {
    cell: String,
    rid: Option<String>,
    location: Option<String>,
    display: Option<String>,
    tooltip: Option<String>,
}

pub(super) fn parse_hyperlink(payload: &[u8]) -> Option<HyperlinkNode> {
    let cell = parse_rfx(payload.get(0..16)?)?;
    let mut offset = 16;
    let rid = read_wide_string_at(payload, &mut offset).filter(|value| !value.is_empty());
    let location = read_wide_string_at(payload, &mut offset).filter(|value| !value.is_empty());
    let tooltip = read_wide_string_at(payload, &mut offset).filter(|value| !value.is_empty());
    let display = read_wide_string_at(payload, &mut offset).filter(|value| !value.is_empty());
    Some(HyperlinkNode {
        cell,
        rid,
        location,
        display,
        tooltip,
    })
}

pub(super) fn read_wide_string_at(payload: &[u8], offset: &mut usize) -> Option<String> {
    let mut consumed = 0;
    let value = wide_string(payload.get(*offset..)?, &mut consumed).ok()?;
    *offset += consumed;
    Some(value)
}

pub(super) fn resolve_hyperlinks(
    nodes: Vec<HyperlinkNode>,
    rels: Option<&RelsGraph>,
) -> Vec<Hyperlink> {
    let mut out = Vec::new();
    for node in nodes {
        let internal = node.location.is_some() && node.rid.is_none();
        let target = if let Some(rid) = &node.rid {
            rels.and_then(|rels| rels.get(&RelId(rid.clone())))
                .map(|rel| rel.target.clone())
                .unwrap_or_default()
        } else {
            node.location.clone().unwrap_or_default()
        };
        if target.is_empty() {
            continue;
        }
        let display = node
            .display
            .filter(|value| !value.is_empty())
            .unwrap_or_default();
        out.push(Hyperlink {
            cell: node.cell,
            target,
            location: node.location,
            display,
            tooltip: node.tooltip,
            internal,
        });
    }
    out
}

pub(super) fn comments_target(rels: &RelsGraph) -> Option<String> {
    rels.iter()
        .find(|rel| rel.rel_type.ends_with("/comments") || rel.rel_type == "comments")
        .map(|rel| rel.target.clone())
}

pub(super) fn parse_comments_bin(data: &[u8]) -> Result<Vec<Comment>> {
    let mut authors = Vec::new();
    let mut comments = Vec::new();
    let mut current: Option<PendingComment> = None;

    for record in Records::new(data) {
        let record = record?;
        match record.typ {
            0x0278 => {
                let mut consumed = 0;
                authors.push(wide_string(record.payload, &mut consumed)?);
            }
            0x027b => {
                current =
                    parse_comment_header(record.payload).map(|(author_id, cell)| PendingComment {
                        cell,
                        author_id,
                        text: String::new(),
                    });
            }
            0x027d => {
                if let Some(comment) = current.as_mut() {
                    comment.text = parse_rich_string(record.payload)?;
                }
            }
            0x027c => {
                if let Some(comment) = current.take() {
                    comments.push(Comment {
                        cell: comment.cell,
                        text: comment.text,
                        author: authors.get(comment.author_id).cloned().unwrap_or_default(),
                        threaded: false,
                    });
                }
            }
            _ => {}
        }
    }
    Ok(comments)
}

#[derive(Debug)]
struct PendingComment {
    cell: String,
    author_id: usize,
    text: String,
}

fn parse_comment_header(payload: &[u8]) -> Option<(usize, String)> {
    let author_id = payload.get(0..4).map(le_u32)? as usize;
    let cell = parse_rfx(payload.get(4..20)?)?;
    Some((author_id, cell))
}

fn parse_rich_string(payload: &[u8]) -> Result<String> {
    let mut consumed = 0;
    if payload.len() > 1 {
        if let Ok(value) = wide_string(&payload[1..], &mut consumed) {
            return Ok(value);
        }
    }
    wide_string(payload, &mut consumed)
}

pub(super) fn parse_sheet_protection(payload: &[u8]) -> Option<SheetProtection> {
    if payload.len() < 66 {
        return None;
    }
    let password = le_u16(&payload[0..2]);
    let flag = |idx: usize| le_u32(&payload[idx..idx + 4]) != 0;
    Some(SheetProtection {
        sheet: flag(2),
        objects: flag(6),
        scenarios: flag(10),
        format_cells: flag(14),
        format_columns: flag(18),
        format_rows: flag(22),
        insert_columns: flag(26),
        insert_rows: flag(30),
        insert_hyperlinks: flag(34),
        delete_columns: flag(38),
        delete_rows: flag(42),
        select_locked_cells: flag(46),
        sort: flag(50),
        auto_filter: flag(54),
        pivot_tables: flag(58),
        select_unlocked_cells: flag(62),
        password_hash: (password != 0).then(|| format!("{password:04X}")),
    })
}

pub(super) fn parse_page_margins(payload: &[u8]) -> Option<PageMarginsInfo> {
    if payload.len() < 48 {
        return None;
    }
    Some(PageMarginsInfo {
        left: le_f64(&payload[0..8]),
        right: le_f64(&payload[8..16]),
        top: le_f64(&payload[16..24]),
        bottom: le_f64(&payload[24..32]),
        header: le_f64(&payload[32..40]),
        footer: le_f64(&payload[40..48]),
    })
}

pub(super) fn parse_page_setup(payload: &[u8]) -> Option<PageSetupInfo> {
    if payload.len() < 34 {
        return None;
    }
    let paper_size = le_u32(&payload[0..4]);
    let scale = le_u32(&payload[4..8]);
    let horizontal_dpi = le_u32(&payload[8..12]);
    let vertical_dpi = le_u32(&payload[12..16]);
    let first_page_number = le_i32(&payload[20..24]);
    let fit_to_width = le_u32(&payload[24..28]);
    let fit_to_height = le_u32(&payload[28..32]);
    let flags = le_u16(&payload[32..34]);
    let no_orientation = flags & (1 << 6) != 0;
    let print_comments = flags & (1 << 5) != 0;
    let comments_at_end = flags & (1 << 8) != 0;
    Some(PageSetupInfo {
        orientation: if no_orientation {
            None
        } else if flags & (1 << 1) != 0 {
            Some("landscape".to_string())
        } else {
            Some("portrait".to_string())
        },
        paper_size: (paper_size != 0).then_some(paper_size),
        fit_to_width: Some(fit_to_width),
        fit_to_height: Some(fit_to_height),
        scale: (scale != 0).then_some(scale),
        first_page_number: (flags & (1 << 7) != 0 && first_page_number >= 0)
            .then_some(first_page_number as u32),
        horizontal_dpi: (horizontal_dpi != 0).then_some(horizontal_dpi),
        vertical_dpi: (vertical_dpi != 0).then_some(vertical_dpi),
        cell_comments: Some(
            if print_comments {
                if comments_at_end {
                    "atEnd"
                } else {
                    "asDisplayed"
                }
            } else {
                "none"
            }
            .to_string(),
        ),
        errors: Some(print_errors_as((flags >> 9) & 0x03).to_string()),
        use_first_page_number: Some(flags & (1 << 7) != 0),
        use_printer_defaults: Some(no_orientation),
        black_and_white: Some(flags & (1 << 3) != 0),
        draft: Some(flags & (1 << 4) != 0),
        ..PageSetupInfo::default()
    })
}

fn print_errors_as(value: u16) -> &'static str {
    match value {
        1 => "blank",
        2 => "dash",
        3 => "NA",
        _ => "displayed",
    }
}

pub(super) fn parse_print_options(payload: &[u8]) -> Option<PrintOptionsInfo> {
    let flags = payload.get(0..2).map(le_u16)?;
    Some(PrintOptionsInfo {
        horizontal_centered: Some(flags & 0x0001 != 0),
        vertical_centered: Some(flags & 0x0002 != 0),
        headings: Some(flags & 0x0008 != 0),
        grid_lines: Some(flags & 0x0004 != 0),
        grid_lines_set: Some(flags & 0x0010 != 0),
    })
}

pub(super) fn parse_header_footer(payload: &[u8]) -> Option<HeaderFooterInfo> {
    if payload.len() < 2 {
        return None;
    }
    let flags = le_u16(&payload[0..2]);
    let mut offset = 2;
    let odd_header = read_nullable_wide_string_at(payload, &mut offset)?;
    let odd_footer = read_nullable_wide_string_at(payload, &mut offset)?;
    let even_header = read_nullable_wide_string_at(payload, &mut offset)?;
    let even_footer = read_nullable_wide_string_at(payload, &mut offset)?;
    let first_header = read_nullable_wide_string_at(payload, &mut offset)?;
    let first_footer = read_nullable_wide_string_at(payload, &mut offset)?;
    Some(HeaderFooterInfo {
        odd_header: odd_header
            .as_deref()
            .map(parse_header_footer_item_text)
            .unwrap_or_default(),
        odd_footer: odd_footer
            .as_deref()
            .map(parse_header_footer_item_text)
            .unwrap_or_default(),
        even_header: even_header
            .as_deref()
            .map(parse_header_footer_item_text)
            .unwrap_or_default(),
        even_footer: even_footer
            .as_deref()
            .map(parse_header_footer_item_text)
            .unwrap_or_default(),
        first_header: first_header
            .as_deref()
            .map(parse_header_footer_item_text)
            .unwrap_or_default(),
        first_footer: first_footer
            .as_deref()
            .map(parse_header_footer_item_text)
            .unwrap_or_default(),
        different_odd_even: flags & 0x0001 != 0,
        different_first: flags & 0x0002 != 0,
        scale_with_doc: flags & 0x0004 != 0,
        align_with_margins: flags & 0x0008 != 0,
    })
}

pub(super) fn read_nullable_wide_string_at(
    payload: &[u8],
    offset: &mut usize,
) -> Option<Option<String>> {
    let raw_len = payload.get(*offset..*offset + 4).map(le_i32)?;
    if raw_len < 0 {
        *offset += 4;
        return Some(None);
    }
    read_wide_string_at(payload, offset).map(Some)
}

pub(super) fn parse_header_footer_item_text(text: &str) -> HeaderFooterItemInfo {
    let mut item = HeaderFooterItemInfo::default();
    let mut current: Option<u8> = None;
    let mut buf = String::new();
    let mut chars = text.chars().peekable();

    while let Some(ch) = chars.next() {
        if ch == '&' {
            match chars.peek().copied() {
                Some('L') | Some('C') | Some('R') => {
                    assign_header_footer_segment(&mut item, current, std::mem::take(&mut buf));
                    current = chars.next().map(|marker| marker as u8);
                    continue;
                }
                _ => {}
            }
        }
        buf.push(ch);
    }
    assign_header_footer_segment(&mut item, current, buf);
    item
}

fn assign_header_footer_segment(
    item: &mut HeaderFooterItemInfo,
    segment: Option<u8>,
    value: String,
) {
    if value.is_empty() {
        return;
    }
    match segment.unwrap_or(b'C') {
        b'L' => item.left = Some(value),
        b'R' => item.right = Some(value),
        _ => item.center = Some(value),
    }
}

pub(super) fn parse_sheet_format(payload: &[u8]) -> Option<SheetFormatInfo> {
    if payload.len() < 12 {
        return None;
    }
    let default_col_width_raw = le_u32(&payload[0..4]);
    let flags = le_u32(&payload[8..12]);
    Some(SheetFormatInfo {
        base_col_width: le_u16(&payload[4..6]) as u32,
        default_col_width: (default_col_width_raw != u32::MAX)
            .then_some(default_col_width_raw as f64 / 256.0),
        default_row_height: le_u16(&payload[6..8]) as f64 / 20.0,
        custom_height: Some(flags & 0x0001 != 0),
        zero_height: Some(flags & 0x0002 != 0),
        thick_top: Some(flags & 0x0004 != 0),
        thick_bottom: Some(flags & 0x0008 != 0),
        outline_level_row: (flags >> 16) & 0xff,
        outline_level_col: (flags >> 24) & 0xff,
    })
}

pub(super) fn parse_sheet_properties(payload: &[u8]) -> Option<SheetPropertiesInfo> {
    let code_name = find_trailing_wide_string(payload)
        .and_then(|(offset, value)| (offset >= 23 && !value.is_empty()).then_some(value));
    code_name.map(|code_name| SheetPropertiesInfo {
        code_name: Some(code_name),
        ..SheetPropertiesInfo::default()
    })
}
