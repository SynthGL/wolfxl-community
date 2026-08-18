//! CSV backend for `Workbook`.
//!
//! A CSV file is not a spreadsheet in the Excel sense (no styles, no
//! formulas, no multiple sheets) but agents routinely use `wolfxl peek`
//! / `wolfxl schema` on them, so the CLI needs a value-only path that
//! feels native rather than bolted on.
//!
//! The design per sprint-2 invariant B4: a CSV becomes exactly one
//! synthetic Sheet named for the filename stem. Cells are returned as
//! `CellValue::String` — the `schema` module's inference layer is the
//! single source of truth for "this column is actually numbers". That
//! avoids drift where CSV type-detection here and schema inference
//! elsewhere disagree on the same column.

use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use crate::cell::{Cell, CellValue};
use crate::error::{Error, Result};
use crate::sheet::Sheet;

pub(crate) struct CsvBackend {
    sheet_name: String,
    rows: Vec<Vec<Cell>>,
}

impl CsvBackend {
    pub(crate) fn open(path: &Path) -> Result<Self> {
        let sheet_name = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("Sheet1")
            .to_string();

        let file = File::open(path)?;
        let mut reader = BufReader::new(file);
        let rows = parse_delimited(&mut reader, delimiter_for_path(path))?;

        Ok(Self { sheet_name, rows })
    }

    pub(crate) fn sheet_names(&self) -> Vec<String> {
        vec![self.sheet_name.clone()]
    }

    pub(crate) fn load_sheet(&self, name: &str) -> Result<Sheet> {
        if name != self.sheet_name {
            return Err(Error::SheetNotFound(name.to_string()));
        }
        Ok(Sheet::from_rows(self.sheet_name.clone(), self.rows.clone()))
    }
}

fn delimiter_for_path(path: &Path) -> char {
    match path
        .extension()
        .and_then(|s| s.to_str())
        .map(|s| s.to_ascii_lowercase())
        .as_deref()
    {
        Some("tsv") => '\t',
        _ => ',',
    }
}

/// RFC-4180-ish delimited parser. Handles quoted fields with embedded delimiters,
/// doubled quotes (`""` → `"`), and `\r\n` / `\n` line endings. A
/// quoted field may span multiple lines. Anything more exotic (custom
/// encodings other than UTF-8) is out of scope — we pull in the `csv`
/// crate for that later if users actually hit it.
fn parse_delimited<R: BufRead>(reader: &mut R, delimiter: char) -> Result<Vec<Vec<Cell>>> {
    let mut buf = String::new();
    reader
        .read_to_string(&mut buf)
        .map_err(|e| Error::Format(format!("read delimited text: {e}")))?;

    let mut rows: Vec<Vec<Cell>> = Vec::new();
    let mut current_row: Vec<Cell> = Vec::new();
    let mut field = String::new();
    let mut in_quotes = false;
    let mut chars = buf.chars().peekable();

    while let Some(ch) = chars.next() {
        if in_quotes {
            match ch {
                '"' => {
                    // Doubled quote inside a quoted field = literal quote.
                    if chars.peek() == Some(&'"') {
                        field.push('"');
                        chars.next();
                    } else {
                        in_quotes = false;
                    }
                }
                _ => field.push(ch),
            }
            continue;
        }
        match ch {
            '"' if field.is_empty() => in_quotes = true,
            '"' => field.push('"'),
            d if d == delimiter => {
                current_row.push(cell_from_field(std::mem::take(&mut field)));
            }
            '\r' => {
                // Swallow \r; handle \n (whether it's alone or after \r).
                if chars.peek() == Some(&'\n') {
                    chars.next();
                }
                current_row.push(cell_from_field(std::mem::take(&mut field)));
                rows.push(std::mem::take(&mut current_row));
            }
            '\n' => {
                current_row.push(cell_from_field(std::mem::take(&mut field)));
                rows.push(std::mem::take(&mut current_row));
            }
            _ => field.push(ch),
        }
    }

    // Final row: if the file didn't end with a newline, flush whatever's
    // accumulated. A file ending in `\n` will have already pushed the
    // final row and we'll have an empty `current_row` + empty `field` —
    // skip that so we don't tack a spurious empty row on the end.
    let has_tail = !field.is_empty() || !current_row.is_empty();
    if has_tail {
        current_row.push(cell_from_field(field));
        rows.push(current_row);
    }

    // Normalize: every row to the max column width. Agents downstream
    // rely on rectangular shape for `dimensions()` and `headers()`.
    let max_cols = rows.iter().map(|r| r.len()).max().unwrap_or(0);
    for row in &mut rows {
        while row.len() < max_cols {
            row.push(Cell::empty());
        }
    }

    Ok(rows)
}

#[cfg(test)]
fn parse_csv<R: BufRead>(reader: &mut R) -> Result<Vec<Vec<Cell>>> {
    parse_delimited(reader, ',')
}

fn cell_from_field(field: String) -> Cell {
    if field.is_empty() {
        Cell::empty()
    } else {
        Cell {
            value: CellValue::String(field),
            number_format: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn parse(input: &str) -> Vec<Vec<Cell>> {
        let mut reader = Cursor::new(input.as_bytes());
        parse_csv(&mut reader).expect("parse ok")
    }

    fn parse_tsv(input: &str) -> Vec<Vec<Cell>> {
        let mut reader = Cursor::new(input.as_bytes());
        parse_delimited(&mut reader, '\t').expect("parse ok")
    }

    #[test]
    fn parses_plain_csv() {
        let rows = parse("a,b,c\n1,2,3\n");
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].len(), 3);
        assert!(matches!(&rows[0][0].value, CellValue::String(s) if s == "a"));
        assert!(matches!(&rows[1][2].value, CellValue::String(s) if s == "3"));
    }

    #[test]
    fn handles_quoted_fields_with_commas() {
        let rows = parse(
            r#"name,desc
"Alice","she, specifically"
"#,
        );
        assert_eq!(rows.len(), 2);
        match &rows[1][1].value {
            CellValue::String(s) => assert_eq!(s, "she, specifically"),
            other => panic!("expected string, got {other:?}"),
        }
    }

    #[test]
    fn parses_tsv_with_tab_delimiter() {
        let rows = parse_tsv("name\tamount\nAlice\t10\n");
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].len(), 2);
        assert!(matches!(&rows[0][1].value, CellValue::String(s) if s == "amount"));
        assert!(matches!(&rows[1][1].value, CellValue::String(s) if s == "10"));
    }

    #[test]
    fn quote_inside_unquoted_field_is_literal() {
        let rows = parse("name,note\nAlice,pre\"quoted\n");
        match &rows[1][1].value {
            CellValue::String(s) => assert_eq!(s, "pre\"quoted"),
            other => panic!("expected string, got {other:?}"),
        }
    }

    #[test]
    fn handles_doubled_quotes_and_crlf() {
        let rows = parse("a,b\r\n\"She said \"\"hi\"\"\",x\r\n");
        assert_eq!(rows.len(), 2);
        match &rows[1][0].value {
            CellValue::String(s) => assert_eq!(s, r#"She said "hi""#),
            other => panic!("expected string, got {other:?}"),
        }
    }

    #[test]
    fn pads_ragged_rows_to_max_width() {
        let rows = parse("a,b,c\nx\ny,z\n");
        // all rows padded to 3 cols
        assert!(rows.iter().all(|r| r.len() == 3));
        assert!(rows[1][1].value.is_empty());
        assert!(rows[1][2].value.is_empty());
        assert!(rows[2][2].value.is_empty());
    }

    #[test]
    fn empty_fields_become_empty_cells() {
        let rows = parse("a,,c\n");
        assert_eq!(rows.len(), 1);
        assert!(rows[0][1].value.is_empty());
    }

    #[test]
    fn no_trailing_newline_still_flushes_final_row() {
        let rows = parse("a,b\n1,2");
        assert_eq!(rows.len(), 2);
        assert!(matches!(&rows[1][1].value, CellValue::String(s) if s == "2"));
    }
}
