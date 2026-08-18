//! VML drawing anchor shifts for comment shapes.

use crate::axis::{Axis, ShiftPlan};
use crate::shift_anchors::shift_anchor;

/// Rewrite a VML drawing part. Looks for `<x:Anchor>` elements (or
/// `<Anchor>` without prefix) and shifts the row component (axis 1
/// in 0-based, i.e. the second integer in the comma-separated list).
///
/// VML structure:
///
/// ```vml
/// <x:Anchor>1, 0, 5, 0, 3, 0, 7, 0</x:Anchor>
///                ^row(0-based)        ^row-bottom(0-based)
/// ```
///
/// Eight ints: col-left, col-left-offset, row-top, row-top-offset,
/// col-right, col-right-offset, row-bottom, row-bottom-offset.
/// (Reference: Microsoft `[MS-OI29500]` VML anchor format.)
///
/// On a row shift we mutate ints #2 (row-top) and #6 (row-bottom).
/// On a col shift we mutate ints #0 (col-left) and #4 (col-right).
/// Tombstoned anchors collapse the entire VML shape (drop it).
pub fn shift_vml_xml(xml: &[u8], plan: &ShiftPlan) -> Vec<u8> {
    if plan.is_noop() {
        return xml.to_vec();
    }
    // VML is a different XML namespace and quick-xml parsing it
    // robustly would require special handling. Use a string-rewrite
    // pass: find `<x:Anchor>...</x:Anchor>` (or `<Anchor>...</Anchor>`),
    // mutate the int list. Track whether any anchor goes #REF! — if
    // so, drop the enclosing `<v:shape>` element.
    let s = match std::str::from_utf8(xml) {
        Ok(s) => s,
        Err(_) => return xml.to_vec(),
    };

    // Walk shapes in order. We assume the file is small (typical
    // commentsN VML is <10KB).
    let mut out = String::with_capacity(s.len());
    let mut cursor = 0;
    while cursor < s.len() {
        let rest = &s[cursor..];
        if let Some((shape_start_rel, shape_open_end_rel)) = find_start_tag_by_local(rest, "shape")
        {
            out.push_str(&rest[..shape_start_rel]);
            let shape_start = cursor + shape_start_rel;
            let shape_open_end = cursor + shape_open_end_rel;
            let shape_end = match element_end_for_start_tag(s, shape_start, shape_open_end) {
                Some(e) => e,
                None => {
                    out.push_str(&s[shape_start..]);
                    break;
                }
            };
            let shape_block = &s[shape_start..shape_end];
            let new_block = match shift_vml_anchor_in_shape(shape_block, plan) {
                Some(b) => b,
                None => {
                    cursor = shape_end;
                    continue;
                }
            };
            out.push_str(&new_block);
            cursor = shape_end;
        } else {
            out.push_str(rest);
            break;
        }
    }
    out.into_bytes()
}

fn find_start_tag_by_local(s: &str, local: &str) -> Option<(usize, usize)> {
    let mut search_from = 0usize;
    while let Some(rel) = s[search_from..].find('<') {
        let start = search_from + rel;
        if s[start + 1..].starts_with('/') {
            search_from = start + 1;
            continue;
        }
        let end = s[start..].find('>')? + start + 1;
        let name_end = s[start + 1..end]
            .find(|c: char| c == ' ' || c == '>' || c == '/')
            .map(|i| start + 1 + i)
            .unwrap_or(end - 1);
        let name = &s[start + 1..name_end];
        let name_local = name.rsplit(':').next().unwrap_or(name);
        if name_local == local {
            return Some((start, end));
        }
        search_from = end;
    }
    None
}

fn start_tag_name(s: &str, start: usize, open_end: usize) -> Option<&str> {
    let name_start = start.checked_add(1)?;
    if s[name_start..open_end].starts_with('/') {
        return None;
    }
    let name_end = s[name_start..open_end]
        .find(|c: char| c == ' ' || c == '>' || c == '/')
        .map(|i| name_start + i)
        .unwrap_or(open_end - 1);
    Some(&s[name_start..name_end])
}

fn element_end_for_start_tag(s: &str, start: usize, open_end: usize) -> Option<usize> {
    let open_tag = &s[start..open_end];
    if open_tag.trim_end().ends_with("/>") {
        return Some(open_end);
    }
    let tag_name = start_tag_name(s, start, open_end)?;
    let close_tag = format!("</{tag_name}>");
    Some(open_end + s[open_end..].find(&close_tag)? + close_tag.len())
}

fn shift_vml_anchor_in_shape(shape: &str, plan: &ShiftPlan) -> Option<String> {
    let out = shift_vml_anchor_tag(shape, plan)?;
    let out = match plan.axis {
        Axis::Row => shift_vml_numeric_marker(&out, "Row", plan),
        Axis::Col => shift_vml_numeric_marker(&out, "Column", plan),
    }?;
    Some(shift_vml_formula_range(&out, plan))
}

fn shift_vml_formula_range(shape: &str, plan: &ShiftPlan) -> String {
    let Some((open, open_end)) = find_start_tag_by_local(shape, "FmlaRange") else {
        return shape.to_string();
    };
    let Some(tag_name) = start_tag_name(shape, open, open_end) else {
        return shape.to_string();
    };
    let close_tag = format!("</{tag_name}>");
    let Some(close_rel) = shape[open_end..].find(&close_tag) else {
        return shape.to_string();
    };
    let close = open_end + close_rel;
    let payload = shape[open_end..close].trim();
    let shifted = shift_anchor(payload, plan);
    if shifted == "#REF!" {
        return shape.to_string();
    }
    let mut out = String::with_capacity(shape.len());
    out.push_str(&shape[..open_end]);
    out.push_str(&shifted);
    out.push_str(&shape[close..]);
    out
}

fn shift_vml_anchor_tag(shape: &str, plan: &ShiftPlan) -> Option<String> {
    let Some((open, open_end)) = find_start_tag_by_local(shape, "Anchor") else {
        return Some(shape.to_string());
    };
    let tag_name = start_tag_name(shape, open, open_end)?;
    let close_tag = format!("</{tag_name}>");
    let close = shape[open_end..].find(&close_tag)? + open_end;
    if close <= open {
        return Some(shape.to_string());
    }
    let payload = &shape[open_end..close];
    let new_payload = shift_vml_anchor_payload(payload, plan)?;
    let mut out = String::with_capacity(shape.len());
    out.push_str(&shape[..open_end]);
    out.push_str(&new_payload);
    out.push_str(&shape[close..]);
    Some(out)
}

fn shift_vml_numeric_marker(shape: &str, local: &str, plan: &ShiftPlan) -> Option<String> {
    let Some((open, open_end)) = find_start_tag_by_local(shape, local) else {
        return Some(shape.to_string());
    };
    let tag_name = start_tag_name(shape, open, open_end)?;
    let close_tag = format!("</{tag_name}>");
    let close = shape[open_end..].find(&close_tag)? + open_end;
    if close <= open {
        return Some(shape.to_string());
    }
    let payload = shape[open_end..close].trim();
    let value = payload.parse::<i64>().ok()?;
    let new_value = shift_vml_point(value, plan)?;
    let max = match plan.axis {
        Axis::Row => crate::MAX_ROW as i64,
        Axis::Col => crate::MAX_COL as i64,
    };
    if new_value < 0 || new_value >= max {
        return None;
    }
    let mut out = String::with_capacity(shape.len());
    out.push_str(&shape[..open_end]);
    out.push_str(&new_value.to_string());
    out.push_str(&shape[close..]);
    Some(out)
}

fn shift_vml_point(zero_based: i64, plan: &ShiftPlan) -> Option<i64> {
    if plan.is_insert() {
        if zero_based + 1 >= plan.idx as i64 {
            Some(zero_based + plan.n as i64)
        } else {
            Some(zero_based)
        }
    } else {
        let delete_start = plan.idx as i64 - 1;
        let delete_end = delete_start + plan.abs_n() as i64;
        if zero_based >= delete_start && zero_based < delete_end {
            None
        } else if zero_based >= delete_end {
            Some(zero_based + plan.n as i64)
        } else {
            Some(zero_based)
        }
    }
}

fn shift_vml_anchor_payload(payload: &str, plan: &ShiftPlan) -> Option<String> {
    let parts: Vec<&str> = payload.split(',').map(|p| p.trim()).collect();
    if parts.len() != 8 {
        return Some(payload.to_string());
    }
    let mut nums: Vec<i64> = Vec::with_capacity(8);
    for p in &parts {
        nums.push(p.parse::<i64>().ok()?);
    }
    match plan.axis {
        Axis::Row => {
            if plan.is_insert() {
                for &i in &[2usize, 6usize] {
                    if nums[i] + 1 >= plan.idx as i64 {
                        nums[i] += plan.n as i64;
                    }
                }
            } else if !shift_deleted_anchor_span(&mut nums, 2, 6, plan) {
                return None;
            }
            if nums[2] < 0
                || nums[6] < 0
                || nums[2] >= crate::MAX_ROW as i64
                || nums[6] >= crate::MAX_ROW as i64
                || nums[6] < nums[2]
            {
                return None;
            }
        }
        Axis::Col => {
            if plan.is_insert() {
                for &i in &[0usize, 4usize] {
                    if nums[i] + 1 >= plan.idx as i64 {
                        nums[i] += plan.n as i64;
                    }
                }
            } else if !shift_deleted_anchor_span(&mut nums, 0, 4, plan) {
                return None;
            }
            if nums[0] < 0
                || nums[4] < 0
                || nums[0] >= crate::MAX_COL as i64
                || nums[4] >= crate::MAX_COL as i64
                || nums[4] < nums[0]
            {
                return None;
            }
        }
    }
    Some(
        nums.iter()
            .map(|n| n.to_string())
            .collect::<Vec<_>>()
            .join(", "),
    )
}

fn shift_deleted_anchor_span(
    nums: &mut [i64],
    start_idx: usize,
    end_idx: usize,
    plan: &ShiftPlan,
) -> bool {
    let delete_start = plan.idx as i64 - 1;
    let delete_end = delete_start + plan.abs_n() as i64;
    let start = nums[start_idx];
    let end = nums[end_idx];
    let start_deleted = start >= delete_start && start < delete_end;
    let end_deleted = end >= delete_start && end < delete_end;
    if start_deleted && end_deleted {
        return false;
    }

    if start_deleted {
        nums[start_idx] = delete_start;
    } else if nums[start_idx] >= delete_end {
        nums[start_idx] += plan.n as i64;
    }
    if end_deleted {
        nums[end_idx] = delete_start.saturating_sub(1);
    } else if nums[end_idx] >= delete_end {
        nums[end_idx] += plan.n as i64;
    }
    true
}
