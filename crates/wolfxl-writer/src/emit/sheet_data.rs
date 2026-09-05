//! `<sheetData>` row and cell emitter for worksheet XML.
//!
//! Two entry points:
//!
//! - [`emit`] writes the entire `<sheetData>` block (open tag, every row,
//!   close tag) into an in-memory `String`. This is the eager-mode path
//!   used by every regular `Workbook()` save.
//! - [`emit_row_to`] writes a single `<row r="…">…</row>` element into any
//!   `fmt::Write` sink. Streaming write-only mode (`Workbook(write_only=True)`)
//!   wraps a per-sheet temp file with `IoFmtAdapter` and calls this helper
//!   once per `ws.append(...)`. Sharing the same row encoder is what
//!   guarantees byte-identical output between the eager and streaming paths.

use core::fmt;

use crate::intern::SstBuilder;
use crate::model::cell::{FormulaResult, WriteCell, WriteCellValue};
use crate::model::worksheet::{visit_merged_row_cells, DenseRow, Row, Worksheet};
use crate::{refs, xml_escape};

/// Emit `<sheetData>...</sheetData>` for worksheet rows and cells.
pub fn emit(out: &mut String, sheet: &Worksheet, sst: &mut SstBuilder) {
    if sheet.rows.is_empty() && sheet.dense_rows.is_empty() {
        out.push_str("<sheetData/>");
        return;
    }

    out.push_str("<sheetData>");
    sheet
        .visit_logical_rows(|row_num, row, dense| emit_merged_row_to(out, row_num, row, dense, sst))
        .expect("formatting into a String is infallible");
    out.push_str("</sheetData>");
}

/// Encode a single `<row r="…">…</row>` element into `out`.
///
/// Returns `fmt::Result` from the underlying writes — pushing into a
/// `String` never errors, but the streaming path uses an `io::Write`
/// adapter that surfaces I/O errors as `fmt::Error`. The streaming
/// caller checks back the original `io::Error` separately on each
/// append; the `fmt::Result` here is just the pass-through signal.
pub(crate) fn emit_row_to<W: fmt::Write>(
    out: &mut W,
    row_num: u32,
    row: &Row,
    sst: &mut SstBuilder,
) -> fmt::Result {
    emit_merged_row_to(out, row_num, Some(row), &[], sst)
}

fn emit_merged_row_to<W: fmt::Write>(
    out: &mut W,
    row_num: u32,
    row: Option<&Row>,
    dense_rows: &[DenseRow],
    sst: &mut SstBuilder,
) -> fmt::Result {
    let (has_cells, has_real_cells) = if row.is_none_or(|row| row.cells.is_empty()) {
        (
            !dense_rows.is_empty(),
            dense_rows.iter().any(|dense| dense.emittable_cells > 0),
        )
    } else {
        let mut has_cells = false;
        let mut has_real_cells = false;
        visit_merged_row_cells::<()>(row, dense_rows, |_, cell| {
            has_cells = true;
            has_real_cells |=
                !matches!(cell.value, WriteCellValue::Blank) || cell.style_id.is_some();
            Ok(())
        })
        .expect("row cell scan is infallible");
        (has_cells, has_real_cells)
    };
    let has_attrs =
        row.is_some_and(|row| row.custom_height.is_some() || row.hidden || row.style_id.is_some());

    if !has_cells && !has_attrs {
        return Ok(());
    }

    write!(out, "<row r=\"{}\"", row_num)?;

    if let Some(row) = row {
        if let Some(h) = row.custom_height {
            write!(out, " ht=\"{}\" customHeight=\"1\"", format_f64(h))?;
        }
        if row.hidden {
            out.write_str(" hidden=\"1\"")?;
        }
        if let Some(s) = row.style_id {
            write!(out, " s=\"{}\" customFormat=\"1\"", s)?;
        }
    }

    if !has_real_cells {
        out.write_str("/>")?;
        return Ok(());
    }

    out.write_char('>')?;
    visit_merged_row_cells(row, dense_rows, |col_num, cell| {
        emit_cell_to(out, row_num, col_num, cell, sst)
    })?;
    out.write_str("</row>")
}

fn emit_cell_to<W: fmt::Write>(
    out: &mut W,
    row_num: u32,
    col_num: u32,
    cell: &WriteCell,
    sst: &mut SstBuilder,
) -> fmt::Result {
    let cell_ref = refs::A1Ref::new(row_num, col_num);

    match &cell.value {
        WriteCellValue::Blank => {
            if let Some(s) = cell.style_id {
                write!(out, "<c r=\"{}\" s=\"{}\"/>", cell_ref, s)?;
            }
        }

        WriteCellValue::Number(n) => {
            write!(out, "<c r=\"{}\"", cell_ref)?;
            if let Some(s) = cell.style_id {
                write!(out, " s=\"{}\"", s)?;
            }
            write!(out, "><v>{}</v></c>", format_number(*n))?;
        }

        WriteCellValue::String(s) => {
            let idx = sst.intern(s);
            write!(out, "<c r=\"{}\" t=\"s\"", cell_ref)?;
            if let Some(style) = cell.style_id {
                write!(out, " s=\"{}\"", style)?;
            }
            write!(out, "><v>{}</v></c>", idx)?;
        }

        WriteCellValue::Error(s) => {
            write!(out, "<c r=\"{}\" t=\"e\"", cell_ref)?;
            if let Some(style) = cell.style_id {
                write!(out, " s=\"{}\"", style)?;
            }
            write!(out, "><v>{}</v></c>", xml_escape::text(s))?;
        }

        WriteCellValue::Boolean(b) => {
            write!(out, "<c r=\"{}\" t=\"b\"", cell_ref)?;
            if let Some(s) = cell.style_id {
                write!(out, " s=\"{}\"", s)?;
            }
            let bval = if *b { 1 } else { 0 };
            write!(out, "><v>{}</v></c>", bval)?;
        }

        WriteCellValue::Formula { expr, result } => {
            write!(out, "<c r=\"{}\"", cell_ref)?;
            match result {
                Some(FormulaResult::String(_)) => out.write_str(" t=\"str\"")?,
                Some(FormulaResult::Boolean(_)) => out.write_str(" t=\"b\"")?,
                _ => {}
            }
            if let Some(style) = cell.style_id {
                write!(out, " s=\"{}\"", style)?;
            }
            out.write_str("><f>")?;
            xml_escape::write_text_to(out, expr)?;
            out.write_str("</f>")?;
            match result {
                Some(FormulaResult::Number(n)) => write!(out, "<v>{}</v>", format_number(*n))?,
                Some(FormulaResult::String(value)) => {
                    out.write_str("<v>")?;
                    xml_escape::write_text_to(out, value)?;
                    out.write_str("</v>")?;
                }
                Some(FormulaResult::Boolean(value)) => write!(out, "<v>{}</v>", u8::from(*value))?,
                None => {}
            }
            out.write_str("</c>")?;
        }

        WriteCellValue::DateSerial(f) => {
            write!(out, "<c r=\"{}\"", cell_ref)?;
            if let Some(s) = cell.style_id {
                write!(out, " s=\"{}\"", s)?;
            }
            write!(out, "><v>{}</v></c>", format_number(*f))?;
        }

        WriteCellValue::InlineRichText(runs) => {
            write!(out, "<c r=\"{}\" t=\"inlineStr\"", cell_ref)?;
            if let Some(s) = cell.style_id {
                write!(out, " s=\"{}\"", s)?;
            }
            out.write_str("><is>")?;
            out.write_str(&crate::rich_text::emit_runs(runs))?;
            out.write_str("</is></c>")?;
        }

        WriteCellValue::ArrayFormula { ref_range, text } => {
            write!(out, "<c r=\"{}\"", cell_ref)?;
            if let Some(s) = cell.style_id {
                write!(out, " s=\"{}\"", s)?;
            }
            write!(
                out,
                "><f t=\"array\" ref=\"{}\">{}</f></c>",
                xml_escape::attr(ref_range),
                xml_escape::text(text),
            )?;
        }

        WriteCellValue::DataTableFormula {
            ref_range,
            ca,
            dt2_d,
            dtr,
            r1,
            r2,
            del1,
            del2,
        } => {
            write!(out, "<c r=\"{}\"", cell_ref)?;
            if let Some(s) = cell.style_id {
                write!(out, " s=\"{}\"", s)?;
            }
            out.write_str("><f t=\"dataTable\"")?;
            write!(out, " ref=\"{}\"", xml_escape::attr(ref_range))?;
            if *ca {
                out.write_str(" ca=\"1\"")?;
            }
            if *dt2_d {
                out.write_str(" dt2D=\"1\"")?;
            }
            if *dtr {
                out.write_str(" dtr=\"1\"")?;
            }
            if let Some(r1v) = r1 {
                write!(out, " r1=\"{}\"", xml_escape::attr(r1v))?;
            }
            if let Some(r2v) = r2 {
                write!(out, " r2=\"{}\"", xml_escape::attr(r2v))?;
            }
            if *del1 {
                out.write_str(" del1=\"1\"")?;
            }
            if *del2 {
                out.write_str(" del2=\"1\"")?;
            }
            out.write_str("/></c>")?;
        }

        WriteCellValue::SpillChild => {
            write!(out, "<c r=\"{}\"", cell_ref)?;
            if let Some(s) = cell.style_id {
                write!(out, " s=\"{}\"", s)?;
            }
            out.write_str("/>")?;
        }
    }
    Ok(())
}

struct Number(f64);

impl fmt::Display for Number {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let n = self.0;
        if n == (n as i64) as f64 {
            write!(f, "{}", n as i64)
        } else {
            write!(f, "{}", n)
        }
    }
}

fn format_number(n: f64) -> Number {
    Number(n)
}

fn format_f64(n: f64) -> String {
    if n == (n as i64) as f64 && n.abs() < 1e15 {
        format!("{}", n as i64)
    } else {
        format!("{}", n)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn direct_numbers_preserve_legacy_formatting() {
        let mut values = vec![
            0.0,
            -0.0,
            0.1,
            -1.25,
            f64::MIN_POSITIVE,
            f64::MAX,
            f64::INFINITY,
            f64::NEG_INFINITY,
            f64::NAN,
            i64::MAX as f64,
            i64::MIN as f64,
        ];
        let mut bits = 123456789_u64;
        for _ in 0..10_000 {
            bits = bits.wrapping_mul(6364136223846793005).wrapping_add(1);
            values.push(f64::from_bits(bits));
        }
        for n in values {
            let expected = if n == (n as i64) as f64 {
                format!("{}", n as i64)
            } else {
                format!("{n}")
            };
            assert_eq!(format_number(n).to_string(), expected);
        }
    }

    #[test]
    fn empty_sheet_data_self_closes() {
        let sheet = Worksheet::new("S");
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert_eq!(out, "<sheetData/>");
    }

    #[test]
    fn string_cells_intern_into_shared_string_table() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::String("hello".into())));
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert!(out.contains("<c r=\"A1\" t=\"s\"><v>0</v></c>"));
        assert_eq!(sst.unique_count(), 1);
    }

    #[test]
    fn styled_blank_cells_emit_self_closing_cell() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(2, 3, WriteCell::new(WriteCellValue::Blank).with_style(4));
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert!(out.contains("<c r=\"C2\" s=\"4\"/>"));
    }

    #[test]
    fn unstyled_blank_cells_are_skipped() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::Blank));
        sheet.set_cell(1, 2, WriteCell::new(WriteCellValue::Number(5.0)));
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert!(!out.contains("<c r=\"A1\""));
        assert!(out.contains("<c r=\"B1\""));
    }

    #[test]
    fn numeric_cells_use_integer_format_when_exact() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::Number(42.0)));
        sheet.set_cell(1, 2, WriteCell::new(WriteCellValue::Number(1.5)));
        sheet.set_cell(1, 3, WriteCell::new(WriteCellValue::Number(-17.5)));
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert!(out.contains("<c r=\"A1\"><v>42</v></c>"));
        assert!(!out.contains("<v>42.0</v>"));
        assert!(out.contains("<c r=\"B1\"><v>1.5</v></c>"));
        assert!(out.contains("<c r=\"C1\"><v>-17.5</v></c>"));
    }

    #[test]
    fn strings_intern_in_insertion_order() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::String("beta".into())));
        sheet.set_cell(2, 1, WriteCell::new(WriteCellValue::String("alpha".into())));
        sheet.set_cell(3, 1, WriteCell::new(WriteCellValue::String("beta".into())));
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert_eq!(sst.total_count(), 3);
        assert_eq!(sst.unique_count(), 2);
        let collected: Vec<(u32, &str)> = sst.iter().collect();
        assert_eq!(collected[0], (0, "beta"));
        assert_eq!(collected[1], (1, "alpha"));
        assert!(out.contains("<c r=\"A1\" t=\"s\"><v>0</v></c>"));
        assert!(out.contains("<c r=\"A2\" t=\"s\"><v>1</v></c>"));
        assert!(out.contains("<c r=\"A3\" t=\"s\"><v>0</v></c>"));
    }

    #[test]
    fn boolean_cells_emit_b_type() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::Boolean(true)));
        sheet.set_cell(1, 2, WriteCell::new(WriteCellValue::Boolean(false)));
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert!(out.contains("<c r=\"A1\" t=\"b\"><v>1</v></c>"));
        assert!(out.contains("<c r=\"B1\" t=\"b\"><v>0</v></c>"));
    }

    #[test]
    fn error_cells_emit_error_type_without_sst_entry() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::Error("#N/A".into())));
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert!(out.contains("<c r=\"A1\" t=\"e\"><v>#N/A</v></c>"));
        assert_eq!(sst.unique_count(), 0);
    }

    #[test]
    fn formula_result_variants_emit_expected_cell_types() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(
            1,
            1,
            WriteCell::new(WriteCellValue::Formula {
                expr: "SUM(A1:A10)".into(),
                result: None,
            }),
        );
        sheet.set_cell(
            1,
            2,
            WriteCell::new(WriteCellValue::Formula {
                expr: "1+6".into(),
                result: Some(FormulaResult::Number(7.0)),
            }),
        );
        sheet.set_cell(
            1,
            3,
            WriteCell::new(WriteCellValue::Formula {
                expr: "CONCAT(\"fo\",\"o\")".into(),
                result: Some(FormulaResult::String("foo".into())),
            }),
        );
        sheet.set_cell(
            1,
            4,
            WriteCell::new(WriteCellValue::Formula {
                expr: "TRUE()".into(),
                result: Some(FormulaResult::Boolean(true)),
            }),
        );
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert!(out.contains("<f>SUM(A1:A10)</f></c>"));
        assert!(out.contains("<f>1+6</f><v>7</v>"));
        assert!(out.contains("t=\"str\""));
        assert!(out.contains("<v>foo</v>"));
        assert!(out.contains("<c r=\"D1\" t=\"b\"><f>TRUE()</f><v>1</v></c>"));
    }

    #[test]
    fn date_serial_emits_as_number_without_type() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::DateSerial(44927.5)));
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert!(out.contains("<c r=\"A1\"><v>44927.5</v></c>"));
        assert!(!out.contains("t=\"s\""));
        assert!(!out.contains("t=\"b\""));
    }

    #[test]
    fn style_id_emits_s_attribute_only_when_present() {
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(
            1,
            1,
            WriteCell::new(WriteCellValue::Number(1.0)).with_style(5),
        );
        sheet.set_cell(1, 2, WriteCell::new(WriteCellValue::Number(1.0)));
        let mut sst = SstBuilder::default();
        let mut out = String::new();

        emit(&mut out, &sheet, &mut sst);

        assert!(out.contains("<c r=\"A1\" s=\"5\"><v>1</v></c>"));
        let b1_start = out.find("<c r=\"B1\"").expect("B1 cell");
        let b1_end = out[b1_start..].find('>').expect(">") + b1_start;
        let tag = &out[b1_start..=b1_end];
        assert!(!tag.contains("s="), "no s attr when no style: {tag}");
    }

    #[test]
    fn emit_row_to_matches_eager_byte_for_byte() {
        // Streaming and eager paths share emit_row_to. This locks the
        // contract that single-row encoding is identical regardless of
        // whether the sink is the eager <sheetData> String or a
        // per-sheet temp file.
        let mut sheet = Worksheet::new("S");
        sheet.set_cell(1, 1, WriteCell::new(WriteCellValue::Number(42.0)));
        sheet.set_cell(1, 2, WriteCell::new(WriteCellValue::String("hi".into())));
        sheet.set_cell(1, 3, WriteCell::new(WriteCellValue::Boolean(true)));

        let mut eager_sst = SstBuilder::default();
        let mut eager = String::new();
        emit(&mut eager, &sheet, &mut eager_sst);

        let mut streaming_sst = SstBuilder::default();
        let mut streaming = String::new();
        let row = sheet.rows.get(&1).unwrap();
        emit_row_to(&mut streaming, 1, row, &mut streaming_sst).unwrap();

        // The eager path wraps with <sheetData>...</sheetData>; strip it
        // off so the row payload is comparable.
        let inner = eager
            .trim_start_matches("<sheetData>")
            .trim_end_matches("</sheetData>");
        assert_eq!(inner, streaming);
    }

    #[test]
    fn dense_rows_match_sparse_xml_and_accept_sparse_overlays() {
        let cells = vec![
            WriteCell::new(WriteCellValue::Number(42.0)),
            WriteCell::new(WriteCellValue::Blank),
            WriteCell::new(WriteCellValue::String("dense".into())),
        ];
        let mut sparse = Worksheet::new("S");
        for (offset, cell) in cells.iter().cloned().enumerate() {
            sparse.set_cell(3, 2 + offset as u32, cell);
        }
        sparse.set_cell(3, 4, WriteCell::new(WriteCellValue::String("edit".into())));

        let mut dense = Worksheet::new("S");
        dense.append_dense_row(3, 2, cells).unwrap();
        dense.set_cell(3, 4, WriteCell::new(WriteCellValue::String("edit".into())));

        let mut sparse_sst = SstBuilder::default();
        let mut sparse_xml = String::new();
        emit(&mut sparse_xml, &sparse, &mut sparse_sst);
        let mut dense_sst = SstBuilder::default();
        let mut dense_xml = String::new();
        emit(&mut dense_xml, &dense, &mut dense_sst);

        assert_eq!(dense_xml, sparse_xml);
        assert_eq!(
            dense_sst.iter().collect::<Vec<_>>(),
            sparse_sst.iter().collect::<Vec<_>>()
        );
    }
}
