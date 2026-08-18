//! `<col>` span splitter (RFC-031, col-only quirk).
//!
//! `<col min="" max="">` describes a range of columns sharing the
//! same width / style metadata. Insert and delete must split / merge
//! these spans correctly. See RFC-031 §5.3 for the algorithm.

use crate::{Axis, ShiftPlan};

/// One parsed `<col>` element. We keep the original raw bytes so we
/// can re-emit attributes (width, customWidth, hidden, style, etc.)
/// verbatim — only `min`/`max` are rewritten.
#[derive(Debug, Clone)]
pub struct ColSpan {
    pub min: u32,
    pub max: u32,
    /// Raw attributes other than `min`/`max`, in source order. Each
    /// element is a `key="value"` pair without trailing space, with
    /// double-quoted values exactly as the source had them.
    pub other_attrs: Vec<(String, String)>,
}

impl ColSpan {
    /// Re-emit as `<col min="..." max="..." ...other... />`.
    pub fn render(&self) -> String {
        let mut s = format!("<col min=\"{}\" max=\"{}\"", self.min, self.max);
        for (k, v) in &self.other_attrs {
            s.push(' ');
            s.push_str(k);
            s.push_str("=\"");
            s.push_str(v);
            s.push_str("\"");
        }
        s.push_str("/>");
        s
    }
}

/// Apply an axis-shift to a list of `<col>` spans, splitting or merging
/// as required. See RFC-031 §5.3.
///
/// Inputs:
/// - `spans` — the existing `<col>` spans, in source order.
/// - `shift` — must have `axis == Axis::Col` (panics otherwise — a
///   programmer error, not a runtime input).
///
/// Returns the new spans in source order. Spans entirely below the
/// pivot are passed through; spans at-or-above shift; spans straddling
/// the pivot are split.
pub fn split_col_spans(spans: Vec<ColSpan>, plan: ShiftPlan) -> Vec<ColSpan> {
    assert_eq!(plan.axis, Axis::Col, "split_col_spans: axis must be Col");
    let n = plan.n;
    let idx = plan.idx;

    if n == 0 {
        return spans;
    }

    let mut out: Vec<ColSpan> = Vec::with_capacity(spans.len() + 1);

    if n > 0 {
        // Insert
        for span in spans {
            if span.max < idx {
                // Entirely below — leave alone.
                out.push(span);
            } else if span.min >= idx {
                // Entirely above — shift.
                let shifted = ColSpan {
                    min: span.min.saturating_add(n as u32),
                    max: span.max.saturating_add(n as u32),
                    other_attrs: span.other_attrs,
                };
                out.push(shifted);
            } else {
                // Straddles: span.min < idx <= span.max.
                // Split into [min..=idx-1] and [idx+n..=max+n].
                let lower = ColSpan {
                    min: span.min,
                    max: idx - 1,
                    other_attrs: span.other_attrs.clone(),
                };
                let upper = ColSpan {
                    min: idx.saturating_add(n as u32),
                    max: span.max.saturating_add(n as u32),
                    other_attrs: span.other_attrs,
                };
                out.push(lower);
                out.push(upper);
            }
        }
    } else {
        // Delete: deleted band is [idx, idx + |n| - 1].
        let delete_n = (-n) as u32;
        let band_lo = idx;
        let band_hi = idx + delete_n - 1;

        for span in spans {
            if span.max < band_lo {
                // Entirely below — leave alone.
                out.push(span);
            } else if span.min > band_hi {
                // Entirely above — shift down by delete_n.
                let shifted = ColSpan {
                    min: span.min - delete_n,
                    max: span.max - delete_n,
                    other_attrs: span.other_attrs,
                };
                out.push(shifted);
            } else {
                // Overlap with band.
                if span.min < band_lo {
                    // Lower part survives.
                    out.push(ColSpan {
                        min: span.min,
                        max: band_lo - 1,
                        other_attrs: span.other_attrs.clone(),
                    });
                }
                if span.max > band_hi {
                    // Upper part survives, shifted.
                    out.push(ColSpan {
                        min: band_hi + 1 - delete_n,
                        max: span.max - delete_n,
                        other_attrs: span.other_attrs,
                    });
                }
                // If both parts collapsed — span entirely consumed → drop.
            }
        }
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn span(min: u32, max: u32) -> ColSpan {
        ColSpan {
            min,
            max,
            other_attrs: vec![("width".to_string(), "12".to_string())],
        }
    }

    fn col_shift(at: u32, n: i32) -> ShiftPlan {
        ShiftPlan {
            axis: Axis::Col,
            idx: at,
            n,
        }
    }

    // ----- INSERT -----

    #[test]
    fn insert_below_span_no_change() {
        // span [10..15], insert at 3, n=2 → unchanged
        let out = split_col_spans(vec![span(10, 15)], col_shift(3, 2));
        // Wait — actually insert at 3 means cols >= 3 shift; [10..15] is
        // entirely above. Should shift. Use a real "below" case.
        let out2 = split_col_spans(vec![span(2, 4)], col_shift(10, 2));
        assert_eq!(out2.len(), 1);
        assert_eq!((out2[0].min, out2[0].max), (2, 4));
        // sanity check the other case
        assert_eq!(out.len(), 1);
        assert_eq!((out[0].min, out[0].max), (12, 17));
    }

    #[test]
    fn insert_above_span_shifts() {
        // span [3..7], insert at 3, n=2 → span shifts to [5..9]
        let out = split_col_spans(vec![span(3, 7)], col_shift(3, 2));
        assert_eq!(out.len(), 1);
        assert_eq!((out[0].min, out[0].max), (5, 9));
    }

    #[test]
    fn insert_splits_straddling_span() {
        // span [3..7], insert at 5, n=2 → split into [3..4] and [7..9]
        let out = split_col_spans(vec![span(3, 7)], col_shift(5, 2));
        assert_eq!(out.len(), 2);
        assert_eq!((out[0].min, out[0].max), (3, 4));
        assert_eq!((out[1].min, out[1].max), (7, 9));
    }

    #[test]
    fn insert_splits_at_max_boundary() {
        // span [3..5], insert at 5, n=2 → straddles (min=3 < 5 ≤ max=5):
        // split into [3..4] and [7..7]
        let out = split_col_spans(vec![span(3, 5)], col_shift(5, 2));
        assert_eq!(out.len(), 2);
        assert_eq!((out[0].min, out[0].max), (3, 4));
        assert_eq!((out[1].min, out[1].max), (7, 7));
    }

    // ----- DELETE -----

    #[test]
    fn delete_below_span_no_change() {
        // span [2..4], delete band [10..11] → unchanged
        let out = split_col_spans(vec![span(2, 4)], col_shift(10, -2));
        assert_eq!(out.len(), 1);
        assert_eq!((out[0].min, out[0].max), (2, 4));
    }

    #[test]
    fn delete_above_span_shifts_down() {
        // span [10..15], delete band [3..4] (n=-2) → span shifts to [8..13]
        let out = split_col_spans(vec![span(10, 15)], col_shift(3, -2));
        assert_eq!(out.len(), 1);
        assert_eq!((out[0].min, out[0].max), (8, 13));
    }

    #[test]
    fn delete_fully_covers_span() {
        // span [3..5], delete band [3..7] → span dropped
        let out = split_col_spans(vec![span(3, 5)], col_shift(3, -5));
        assert!(out.is_empty());
    }

    #[test]
    fn delete_partial_overlap_left() {
        // span [3..7], delete band [5..10] (n=-6) → only [3..4] survives
        let out = split_col_spans(vec![span(3, 7)], col_shift(5, -6));
        assert_eq!(out.len(), 1);
        assert_eq!((out[0].min, out[0].max), (3, 4));
    }

    #[test]
    fn delete_partial_overlap_right() {
        // span [5..15], delete band [3..7] (n=-5) → only upper [3..10] survives
        // (lower part: span.min=5 < band_lo=3? No, 5 > 3, so no lower part)
        // upper part: band_hi=7, span.max=15, shift by -5 → min=8-5=3, max=10
        let out = split_col_spans(vec![span(5, 15)], col_shift(3, -5));
        assert_eq!(out.len(), 1);
        assert_eq!((out[0].min, out[0].max), (3, 10));
    }

    #[test]
    fn delete_band_inside_span_splits() {
        // span [3..15], delete band [7..9] (n=-3) → split into [3..6] and [7..12]
        // lower: [3..6] (band_lo-1=6)
        // upper: shift band_hi+1=10 by -3 → 7; max 15-3=12 → [7..12]
        let out = split_col_spans(vec![span(3, 15)], col_shift(7, -3));
        assert_eq!(out.len(), 2);
        assert_eq!((out[0].min, out[0].max), (3, 6));
        assert_eq!((out[1].min, out[1].max), (7, 12));
    }

    #[test]
    fn render_preserves_other_attrs() {
        let s = ColSpan {
            min: 3,
            max: 5,
            other_attrs: vec![
                ("width".to_string(), "14.5".to_string()),
                ("customWidth".to_string(), "1".to_string()),
            ],
        };
        let out = s.render();
        assert_eq!(
            out,
            r#"<col min="3" max="5" width="14.5" customWidth="1"/>"#
        );
    }

    #[test]
    fn no_op_when_n_is_zero() {
        let out = split_col_spans(vec![span(3, 7)], col_shift(5, 0));
        assert_eq!(out.len(), 1);
        assert_eq!((out[0].min, out[0].max), (3, 7));
    }
}

// ---------------------------------------------------------------------------
// XML-level helper used by `shift_workbook::apply_workbook_shift` so the
// `<cols>...</cols>` block of every sheet.xml gets rewritten on Axis::Col
// shifts. Pure byte-level — no quick-xml dep here so the parse mirrors
// what `shift_cells` does.
// ---------------------------------------------------------------------------

/// Rewrite the `<cols>...</cols>` block in `sheet_xml` for a Col-axis
/// shift plan. Returns the new bytes. If `plan.axis != Col`, or if the
/// sheet has no `<cols>` block, the input is returned unchanged.
pub fn shift_sheet_cols_block(sheet_xml: &[u8], plan: ShiftPlan) -> Vec<u8> {
    if plan.axis != Axis::Col || plan.is_noop() {
        return sheet_xml.to_vec();
    }
    let s = match std::str::from_utf8(sheet_xml) {
        Ok(s) => s,
        Err(_) => return sheet_xml.to_vec(),
    };
    let Some(open) = s.find("<cols>") else {
        return sheet_xml.to_vec();
    };
    let Some(close_rel) = s[open..].find("</cols>") else {
        return sheet_xml.to_vec();
    };
    let close = open + close_rel;
    let inner = &s[open + "<cols>".len()..close];

    // Parse `<col ... />` elements.
    let mut spans: Vec<ColSpan> = Vec::new();
    let mut i = 0usize;
    while let Some(start) = inner[i..].find("<col ") {
        let abs_start = i + start;
        let end = match inner[abs_start..].find("/>") {
            Some(e) => abs_start + e + 2,
            None => break,
        };
        let elt = &inner[abs_start..end];
        if let Some(span) = parse_col_element(elt) {
            spans.push(span);
        }
        i = end;
    }
    if spans.is_empty() {
        return sheet_xml.to_vec();
    }

    // `split_col_spans` already handles both insert + delete (drop /
    // clip / shift) per RFC-031 §5.3.
    let new_spans = split_col_spans(spans, plan);

    let mut new_inner = String::new();
    for s in &new_spans {
        new_inner.push_str(&s.render());
    }

    let mut out = Vec::with_capacity(sheet_xml.len());
    out.extend_from_slice(s[..open + "<cols>".len()].as_bytes());
    out.extend_from_slice(new_inner.as_bytes());
    out.extend_from_slice(s[close..].as_bytes());
    out
}

/// Parse `<col min="..." max="..." key="value" .../>` into a ColSpan.
fn parse_col_element(elt: &str) -> Option<ColSpan> {
    // Strip leading "<col " and trailing "/>".
    let body = elt
        .strip_prefix("<col ")
        .or_else(|| elt.strip_prefix("<col"))?;
    let body = body.strip_suffix("/>").unwrap_or(body).trim();

    let mut min: Option<u32> = None;
    let mut max: Option<u32> = None;
    let mut other: Vec<(String, String)> = Vec::new();

    for (key, val) in iter_attrs(body) {
        match key.as_str() {
            "min" => min = val.parse().ok(),
            "max" => max = val.parse().ok(),
            _ => other.push((key, val)),
        }
    }
    Some(ColSpan {
        min: min?,
        max: max?,
        other_attrs: other,
    })
}

/// Yield `(key, value)` from a string of `key="value"` pairs. Tolerant
/// of the whitespace patterns openpyxl emits.
fn iter_attrs(s: &str) -> Vec<(String, String)> {
    let mut out = Vec::new();
    let bytes = s.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() {
        while i < bytes.len() && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        if i >= bytes.len() {
            break;
        }
        let key_start = i;
        while i < bytes.len() && bytes[i] != b'=' && !bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        let key = std::str::from_utf8(&bytes[key_start..i])
            .unwrap_or("")
            .to_string();
        while i < bytes.len() && (bytes[i] == b'=' || bytes[i].is_ascii_whitespace()) {
            i += 1;
        }
        if i >= bytes.len() || bytes[i] != b'"' {
            break;
        }
        i += 1; // skip opening quote
        let val_start = i;
        while i < bytes.len() && bytes[i] != b'"' {
            i += 1;
        }
        let val = std::str::from_utf8(&bytes[val_start..i])
            .unwrap_or("")
            .to_string();
        if i < bytes.len() {
            i += 1; // skip closing quote
        }
        if !key.is_empty() {
            out.push((key, val));
        }
    }
    out
}

#[cfg(test)]
mod xml_tests {
    use super::*;

    fn sheet_with_cols(inner: &str) -> Vec<u8> {
        format!(
            r#"<worksheet><sheetFormatPr defaultRowHeight="15"/><cols>{inner}</cols><sheetData/></worksheet>"#
        )
        .into_bytes()
    }

    #[test]
    fn rewrites_per_col_entries_on_insert() {
        let xml = sheet_with_cols(
            r#"<col min="3" max="3" width="14.5" customWidth="1"/><col min="5" max="5" width="14.5" customWidth="1"/>"#,
        );
        let out = shift_sheet_cols_block(
            &xml,
            ShiftPlan {
                axis: Axis::Col,
                idx: 5,
                n: 2,
            },
        );
        let s = String::from_utf8(out).unwrap();
        assert!(s.contains(r#"min="3" max="3""#), "got: {s}");
        assert!(s.contains(r#"min="7" max="7""#), "got: {s}");
    }

    #[test]
    fn splits_true_span_on_insert() {
        let xml = sheet_with_cols(r#"<col min="3" max="7" width="14.5" customWidth="1"/>"#);
        let out = shift_sheet_cols_block(
            &xml,
            ShiftPlan {
                axis: Axis::Col,
                idx: 5,
                n: 2,
            },
        );
        let s = String::from_utf8(out).unwrap();
        assert!(s.contains(r#"min="3" max="4""#), "got: {s}");
        assert!(s.contains(r#"min="7" max="9""#), "got: {s}");
    }

    #[test]
    fn drops_span_inside_delete_band() {
        let xml = sheet_with_cols(
            r#"<col min="3" max="3"/><col min="4" max="4"/><col min="7" max="7"/>"#,
        );
        let out = shift_sheet_cols_block(
            &xml,
            ShiftPlan {
                axis: Axis::Col,
                idx: 3,
                n: -2,
            },
        );
        let s = String::from_utf8(out).unwrap();
        assert!(!s.contains(r#"min="3""#), "got: {s}");
        assert!(!s.contains(r#"min="4""#), "got: {s}");
        assert!(s.contains(r#"min="5" max="5""#), "got: {s}"); // 7 -> 5
    }

    #[test]
    fn noop_for_row_axis() {
        let xml = sheet_with_cols(r#"<col min="3" max="3"/>"#);
        let out = shift_sheet_cols_block(
            &xml,
            ShiftPlan {
                axis: Axis::Row,
                idx: 5,
                n: 2,
            },
        );
        assert_eq!(out, xml);
    }
}
