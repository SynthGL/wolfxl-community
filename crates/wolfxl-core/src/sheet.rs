use std::fs::File;
use std::io::BufReader;

use calamine_styles::{Data, Reader, Sheets};
use chrono::{NaiveDate, NaiveDateTime, NaiveTime};

use crate::cell::{Cell, CellValue};
use crate::error::{Error, Result};
use crate::format::{classify_format, FormatCategory};
use crate::workbook::WorkbookStyles;
use wolfxl_reader::{
    Cell as NativeCell, CellValue as NativeCellValue, NativeXlsbBook, WorksheetData,
};

/// The calamine-styles reader bundle dispatch-wraps Xlsx/Xls/Ods behind a
/// single enum. All three implement the `Reader` trait, so `worksheet_range`
/// and `worksheet_style` work uniformly; xls/ods return an empty `StyleRange`
/// (styles walker is xlsx-only), which is the expected behavior.
pub(crate) type SheetsReader = Sheets<BufReader<File>>;

pub struct Sheet {
    pub name: String,
    rows: Vec<Vec<Cell>>,
}

impl Sheet {
    pub(crate) fn load(
        wb: &mut SheetsReader,
        name: &str,
        mut styles: Option<&mut WorkbookStyles>,
    ) -> Result<Self> {
        let value_range = wb
            .worksheet_range(name)
            .map_err(|e| Error::Xlsx(format!("read range for {name:?}: {e}")))?;

        let style_range = wb.worksheet_style(name).ok();

        // Pre-populate the per-cell styleId map once so we don't re-walk
        // the worksheet XML per cell. Failure here (e.g. missing sheet
        // part in the zip) degrades gracefully to the calamine-only path.
        if let Some(s) = styles.as_mut() {
            let _ = s.sheet_style_ids_mut(name);
        }

        let (h, w) = value_range.get_size();
        let (start_row, start_col) = value_range.start().unwrap_or((0, 0));
        let mut rows: Vec<Vec<Cell>> = Vec::with_capacity(h);
        for r in 0..h {
            let mut row: Vec<Cell> = Vec::with_capacity(w);
            for c in 0..w {
                let value = value_range
                    .get((r, c))
                    .map(data_to_cell_value)
                    .unwrap_or(CellValue::Empty);
                let absolute_position = absolute_position(start_row, start_col, r, c);
                let number_format = style_range
                    .as_ref()
                    .and_then(|sr| {
                        let (row, col) = absolute_position?;
                        style_at_absolute_position(sr, row, col)
                    })
                    .and_then(extract_number_format)
                    .or_else(|| {
                        // Calamine fast path missed. Fall back to the
                        // cellXfs walker for openpyxl-style workbooks
                        // where Style::get_number_format returns None.
                        styles
                            .as_ref()
                            .and_then(|s| walker_number_format(s, name, start_row, start_col, r, c))
                    });
                row.push(Cell {
                    value,
                    number_format,
                });
            }
            rows.push(row);
        }

        Ok(Self {
            name: name.to_string(),
            rows,
        })
    }

    pub(crate) fn load_native_xlsb(book: &NativeXlsbBook, name: &str) -> Result<Self> {
        let data = book
            .worksheet(name)
            .map_err(|e| Error::Xlsx(format!("read native xlsb sheet {name:?}: {e}")))?;
        Ok(Self::from_native_xlsb_data(
            name.to_string(),
            data,
            book,
            book.date1904(),
        ))
    }

    fn from_native_xlsb_data(
        name: String,
        data: WorksheetData,
        book: &NativeXlsbBook,
        date1904: bool,
    ) -> Self {
        let Some((min_row, min_col, max_row, max_col)) = native_bounds(&data.cells) else {
            return Self {
                name,
                rows: Vec::new(),
            };
        };
        let height = (max_row - min_row + 1) as usize;
        let width = (max_col - min_col + 1) as usize;
        let mut rows = vec![
            vec![
                Cell {
                    value: CellValue::Empty,
                    number_format: None,
                };
                width
            ];
            height
        ];
        for native in &data.cells {
            let row = (native.row - min_row) as usize;
            let col = (native.col - min_col) as usize;
            let number_format = native
                .style_id
                .and_then(|style_id| book.number_format_for_style_id(style_id))
                .map(str::to_string);
            rows[row][col] = Cell {
                value: native_to_cell_value(native, number_format.as_deref(), date1904),
                number_format,
            };
        }
        Self { name, rows }
    }

    pub fn dimensions(&self) -> (usize, usize) {
        let h = self.rows.len();
        let w = self.rows.first().map(|r| r.len()).unwrap_or(0);
        (h, w)
    }

    /// Test-only constructor: build a `Sheet` from a pre-shaped grid without
    /// round-tripping through xlsx. Lets crate-internal tests (e.g. the
    /// classifier in `map.rs`) cover branches the committed fixtures don't
    /// exercise.
    #[cfg(test)]
    pub(crate) fn from_rows_for_test(name: &str, rows: Vec<Vec<Cell>>) -> Self {
        Self {
            name: name.to_string(),
            rows,
        }
    }

    /// Build a `Sheet` from a pre-shaped grid. Used by the CSV backend
    /// internally; also public so third-party callers (notably the
    /// PyO3 bridge in the sibling `wolfxl` cdylib) can feed externally-
    /// sourced rows through `infer_sheet_schema` / `classify_sheet`
    /// without reading from disk. No styles / number formats are
    /// attached - callers with that information should set
    /// `Cell::number_format` on the cells they build.
    pub fn from_rows(name: String, rows: Vec<Vec<Cell>>) -> Self {
        Self { name, rows }
    }

    pub fn rows(&self) -> &[Vec<Cell>] {
        &self.rows
    }

    pub fn row(&self, idx: usize) -> Option<&[Cell]> {
        self.rows.get(idx).map(|r| r.as_slice())
    }

    /// First row stringified - the conventional "header" row for table-shaped
    /// sheets. Empty cells become empty strings so position is preserved.
    pub fn headers(&self) -> Vec<String> {
        self.rows
            .first()
            .map(|row| {
                row.iter()
                    .map(|c| match &c.value {
                        CellValue::String(s) => s.clone(),
                        CellValue::Empty => String::new(),
                        other => format_value_plain(other),
                    })
                    .collect()
            })
            .unwrap_or_default()
    }
}

fn native_bounds(cells: &[NativeCell]) -> Option<(u32, u32, u32, u32)> {
    let mut iter = cells.iter();
    let first = iter.next()?;
    let mut min_row = first.row;
    let mut min_col = first.col;
    let mut max_row = first.row;
    let mut max_col = first.col;
    for cell in iter {
        min_row = min_row.min(cell.row);
        min_col = min_col.min(cell.col);
        max_row = max_row.max(cell.row);
        max_col = max_col.max(cell.col);
    }
    Some((min_row, min_col, max_row, max_col))
}

fn native_to_cell_value(
    cell: &NativeCell,
    number_format: Option<&str>,
    date1904: bool,
) -> CellValue {
    match &cell.value {
        NativeCellValue::Empty => CellValue::Empty,
        NativeCellValue::String(s) => CellValue::String(s.clone()),
        NativeCellValue::Bool(b) => CellValue::Bool(*b),
        NativeCellValue::Error(e) => CellValue::Error(e.clone()),
        NativeCellValue::Number(n) => native_number_to_cell_value(*n, number_format, date1904),
    }
}

fn native_number_to_cell_value(
    value: f64,
    number_format: Option<&str>,
    date1904: bool,
) -> CellValue {
    match number_format.map(classify_format) {
        Some(FormatCategory::Date | FormatCategory::Time | FormatCategory::DateTime) => {
            excel_serial_to_datetime_with_epoch(value, date1904)
        }
        _ if value.fract() == 0.0 && value.abs() < (i64::MAX as f64) => {
            CellValue::Int(value as i64)
        }
        _ => CellValue::Float(value),
    }
}

fn absolute_position(
    start_row: u32,
    start_col: u32,
    row_offset: usize,
    col_offset: usize,
) -> Option<(u32, u32)> {
    let row = start_row.checked_add(u32::try_from(row_offset).ok()?)?;
    let col = start_col.checked_add(u32::try_from(col_offset).ok()?)?;
    Some((row, col))
}

fn style_at_absolute_position(
    range: &calamine_styles::StyleRange,
    row: u32,
    col: u32,
) -> Option<&calamine_styles::Style> {
    let (start_row, start_col) = range.start()?;
    if row < start_row || col < start_col {
        return None;
    }
    let rel_row = usize::try_from(row - start_row).ok()?;
    let rel_col = usize::try_from(col - start_col).ok()?;
    range.get((rel_row, rel_col))
}

fn format_value_plain(v: &CellValue) -> String {
    match v {
        CellValue::Empty => String::new(),
        CellValue::String(s) => s.clone(),
        CellValue::Int(n) => n.to_string(),
        CellValue::Float(n) => n.to_string(),
        CellValue::Bool(b) => if *b { "TRUE" } else { "FALSE" }.to_string(),
        CellValue::Date(d) => d.format("%Y-%m-%d").to_string(),
        CellValue::DateTime(dt) => dt.format("%Y-%m-%d %H:%M:%S").to_string(),
        CellValue::Time(t) => t.format("%H:%M:%S").to_string(),
        CellValue::Error(e) => e.clone(),
    }
}

fn data_to_cell_value(d: &Data) -> CellValue {
    match d {
        Data::Empty => CellValue::Empty,
        Data::String(s) => CellValue::String(s.clone()),
        Data::Int(i) => CellValue::Int(*i),
        Data::Float(f) => {
            if f.fract() == 0.0 && f.abs() < (i64::MAX as f64) {
                CellValue::Int(*f as i64)
            } else {
                CellValue::Float(*f)
            }
        }
        Data::Bool(b) => CellValue::Bool(*b),
        Data::DateTime(dt) => excel_serial_to_datetime(dt.as_f64()),
        Data::DateTimeIso(s) => parse_iso_datetime_or_string(s),
        Data::DurationIso(s) => CellValue::String(s.clone()),
        Data::Error(e) => CellValue::Error(format!("{e:?}")),
        Data::RichText(rt) => CellValue::String(rt.plain_text().to_string()),
    }
}

/// Excel serial date → chrono. Sub-day fractions become Time; ≥1.0 with no
/// fractional part becomes Date; otherwise DateTime. Serial 0.0 is the Excel
/// epoch but for time-formatted cells means midnight; route it to Time(0,0,0)
/// to match openpyxl rather than returning the epoch date.
fn excel_serial_to_datetime(serial: f64) -> CellValue {
    excel_serial_to_datetime_with_epoch(serial, false)
}

fn excel_serial_to_datetime_with_epoch(serial: f64, date1904: bool) -> CellValue {
    if serial < 1.0 && serial >= 0.0 {
        let mut secs = (serial * 86_400.0).round() as u32;
        // 0.99999999 rounds to 86_400, which makes h=24 and `from_hms_opt`
        // returns None — without this carry, the prior fallback emitted
        // `CellValue::Float(serial)` and silently demoted a time-typed
        // cell to a numeric. Mirror the day-carry the date+time branch
        // does below: for a pure sub-day value, "next midnight" is just
        // 00:00:00.
        if secs >= 86_400 {
            secs -= 86_400;
        }
        let h = secs / 3600;
        let m = (secs % 3600) / 60;
        let s = secs % 60;
        return NaiveTime::from_hms_opt(h, m, s)
            .map(CellValue::Time)
            .unwrap_or_else(|| CellValue::Float(serial));
    }
    let mut days = serial.trunc() as i64;
    let frac = serial - (days as f64);
    // Excel's 1900 leap-year bug: serial 60 maps to the non-existent
    // 1900-02-29. openpyxl uses base 1899-12-30 (instead of 1899-12-31) to
    // dodge the bug for serials >= 60, but that leaves serials 1..59 off by
    // one day. The +1 correction restores serial 1 -> 1900-01-01 etc., which
    // matches openpyxl.utils.datetime.from_excel.
    if !date1904 && serial > 0.0 && serial < 60.0 {
        days += 1;
    }
    if frac.abs() < f64::EPSILON {
        return CellValue::Date(days_to_date_from_excel_base(days, date1904));
    }
    // Keep the day-fraction arithmetic signed until normalized into
    // [0, 86_400) — a negative serial like -0.5 produces frac = -0.5 here,
    // and the prior `(frac * 86_400).round() as u32` would wrap a negative
    // f64 to a huge positive u32, then the next-day carry branch would
    // emit a corrupted pre-1900 datetime. Borrow whole days off `days`
    // until secs lands in the valid range; then carry forward the same
    // way the existing 0.99999999 → 86_400 case does.
    let mut secs_signed = (frac * 86_400.0).round() as i64;
    if secs_signed < 0 {
        let borrow_days = (-secs_signed + 86_399) / 86_400; // ceil division
        secs_signed += borrow_days * 86_400;
        days -= borrow_days;
    } else if secs_signed >= 86_400 {
        let carry_days = secs_signed / 86_400;
        secs_signed -= carry_days * 86_400;
        days += carry_days;
    }
    let secs = secs_signed as u32; // now in [0, 86_400)
    let date = days_to_date_from_excel_base(days, date1904);
    let h = secs / 3600;
    let m = (secs % 3600) / 60;
    let s = secs % 60;
    let time = NaiveTime::from_hms_opt(h, m, s)
        .unwrap_or_else(|| NaiveTime::from_hms_opt(0, 0, 0).unwrap());
    CellValue::DateTime(NaiveDateTime::new(date, time))
}

fn days_to_date_from_excel_base(days: i64, date1904: bool) -> NaiveDate {
    let base = if date1904 {
        NaiveDate::from_ymd_opt(1904, 1, 1).expect("static date")
    } else {
        NaiveDate::from_ymd_opt(1899, 12, 30).expect("static date")
    };
    if days >= 0 {
        base.checked_add_days(chrono::Days::new(days as u64))
    } else {
        // u64 cast on negative i64 wraps; subtract the absolute value.
        base.checked_sub_days(chrono::Days::new((-days) as u64))
    }
    .unwrap_or(base)
}

fn parse_iso_datetime_or_string(s: &str) -> CellValue {
    if let Ok(dt) = NaiveDateTime::parse_from_str(s, "%Y-%m-%dT%H:%M:%S%.f") {
        return CellValue::DateTime(dt);
    }
    if let Ok(dt) = NaiveDateTime::parse_from_str(s, "%Y-%m-%dT%H:%M:%S") {
        return CellValue::DateTime(dt);
    }
    if let Ok(d) = NaiveDate::parse_from_str(s, "%Y-%m-%d") {
        return CellValue::Date(d);
    }
    CellValue::String(s.to_string())
}

/// Pull the resolved format-code string off a calamine-styles `Style`. The
/// upstream crate handles built-in vs custom (>=164) resolution; we just
/// normalize the result and skip the no-op "General".
fn extract_number_format(style: &calamine_styles::Style) -> Option<String> {
    let nf = style.get_number_format()?;
    let code = nf.format_code.trim();
    if code.is_empty() || code.eq_ignore_ascii_case("general") {
        None
    } else {
        Some(code.to_string())
    }
}

/// Walker fallback: look up the cell's styleId in the pre-parsed map and
/// resolve it against cellXfs + numFmts. Returns `None` when the cell has
/// no style override (the common case) or when the referenced format is
/// `General` / absent.
fn walker_number_format(
    styles: &WorkbookStyles,
    sheet_name: &str,
    start_row: u32,
    start_col: u32,
    r: usize,
    c: usize,
) -> Option<String> {
    let row = start_row.checked_add(u32::try_from(r).ok()?)?;
    let col = start_col.checked_add(u32::try_from(c).ok()?)?;
    let style_id = styles
        .sheet_style_ids(sheet_name)?
        .get(&(row, col))
        .copied()?;
    styles
        .number_format_for_style_id(style_id)
        .map(|s| s.to_string())
}

#[cfg(test)]
mod tests {
    use chrono::Datelike;

    use super::*;

    fn date(value: CellValue) -> NaiveDate {
        match value {
            CellValue::Date(d) => d,
            other => panic!("expected Date, got {other:?}"),
        }
    }

    #[test]
    fn absolute_position_overflow_returns_none() {
        assert_eq!(absolute_position(10, 20, 2, 3), Some((12, 23)));
        assert_eq!(absolute_position(u32::MAX, 20, 1, 0), None);
        assert_eq!(absolute_position(10, u32::MAX, 0, 1), None);
        assert_eq!(absolute_position(10, 20, usize::MAX, 0), None);
    }

    #[test]
    fn excel_serial_matches_openpyxl_for_pre_leap_serials() {
        // openpyxl maps serial 1 -> 1900-01-01 thanks to its +1 correction
        // for serials in (0, 60). Serial 59 -> 1900-02-28.
        assert_eq!(
            date(excel_serial_to_datetime(1.0)),
            NaiveDate::from_ymd_opt(1900, 1, 1).unwrap()
        );
        assert_eq!(
            date(excel_serial_to_datetime(59.0)),
            NaiveDate::from_ymd_opt(1900, 2, 28).unwrap()
        );
        // Serial 61 -> 1900-03-01 (Excel's fake serial-60 leap day is skipped).
        assert_eq!(
            date(excel_serial_to_datetime(61.0)),
            NaiveDate::from_ymd_opt(1900, 3, 1).unwrap()
        );
        // A modern serial: 44197 -> 2021-01-01.
        assert_eq!(
            date(excel_serial_to_datetime(44197.0)),
            NaiveDate::from_ymd_opt(2021, 1, 1).unwrap()
        );
    }

    #[test]
    fn excel_serial_negative_does_not_wrap() {
        // Bad/sentinel serials shouldn't panic or produce a date in the
        // far future via u64 wrap. Fall back to the epoch.
        let value = excel_serial_to_datetime(-100.0);
        let d = date(value);
        assert!(d.year() < 1900, "got {d}");
    }

    #[test]
    fn excel_serial_sub_day_near_midnight_carries_to_zero_time() {
        // 0.99999999 rounds to 86_400 secs (h=24 is invalid). The prior
        // fallback emitted CellValue::Float(serial), silently demoting a
        // time-typed cell to a numeric. The carry should land on
        // Time(00:00:00) — equivalent of "next midnight" with no date to
        // carry into.
        let value = excel_serial_to_datetime(0.99999999);
        match value {
            CellValue::Time(t) => {
                assert_eq!(t, NaiveTime::from_hms_opt(0, 0, 0).unwrap());
            }
            other => panic!("expected Time(00:00:00), got {other:?}"),
        }
    }

    #[test]
    fn excel_serial_zero_returns_midnight_time() {
        // Serial 0 is the Excel epoch (1899-12-30) but for time-formatted
        // cells means midnight. openpyxl returns Time(0,0,0) here; we
        // match that rather than emitting the epoch date.
        let value = excel_serial_to_datetime(0.0);
        match value {
            CellValue::Time(t) => {
                assert_eq!(t, NaiveTime::from_hms_opt(0, 0, 0).unwrap());
            }
            other => panic!("expected Time(00:00:00), got {other:?}"),
        }
    }

    #[test]
    fn excel_serial_negative_fractional_borrows_into_prior_day() {
        // Serial -0.5 means "12:00 the day before 1899-12-30", i.e.
        // 1899-12-29 12:00:00. The prior code computed
        // `(frac * 86_400).round() as u32` where frac was -0.5; the
        // negative→u32 cast wrapped to a huge positive, and the
        // "carry into next day" branch then emitted a corrupted
        // far-future datetime. Signed arithmetic with a borrow keeps
        // the result in chrono's representable range and on the
        // correct calendar day.
        let value = excel_serial_to_datetime(-0.5);
        match value {
            CellValue::DateTime(dt) => {
                assert_eq!(
                    dt.date(),
                    NaiveDate::from_ymd_opt(1899, 12, 29).unwrap(),
                    "expected borrow into prior day, got {dt}",
                );
                assert_eq!(dt.time(), NaiveTime::from_hms_opt(12, 0, 0).unwrap());
            }
            other => panic!("expected DateTime, got {other:?}"),
        }
    }

    #[test]
    fn excel_serial_carries_near_midnight_fraction_to_next_day() {
        // 44197 + 0.99999999 rounds up to 86_400 secs in the day-fraction
        // calc; that must carry into 2021-01-02 00:00:00 instead of clamping
        // to 23:00:00 on 2021-01-01.
        let value = excel_serial_to_datetime(44197.0 + 0.99999999);
        match value {
            CellValue::DateTime(dt) => {
                assert_eq!(dt.date(), NaiveDate::from_ymd_opt(2021, 1, 2).unwrap(),);
                assert_eq!(dt.time(), NaiveTime::from_hms_opt(0, 0, 0).unwrap());
            }
            other => panic!("expected DateTime, got {other:?}"),
        }
    }
}
