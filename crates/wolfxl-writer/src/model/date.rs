//! Excel date serial conversion with the 1900-leap-year quirk handled.
//!
//! # The quirk
//!
//! Lotus 1-2-3 treated 1900 as a leap year (it isn't — 1900 is divisible by
//! 100 but not by 400). Excel copied this bug for compatibility, so every
//! Excel date serial ≥ 60 is one day off from a "real" day count. Serial 60
//! corresponds to an imaginary "February 29, 1900" that never existed.
//!
//! # The fix
//!
//! Pick epoch **1899-12-31** (so serial 1 = 1900-01-01), then add +1 to
//! every day count ≥ 60 to simulate the fake leap day Excel believes in:
//!
//! - serial 1 → 1900-01-01 ✓
//! - serial 59 → 1900-02-28 ✓
//! - serial 60 → (skipped — the fake Feb 29 maps to nothing in chrono)
//! - serial 61 → 1900-03-01 ✓ (chrono: 60 days since epoch, +1 shift)
//! - serial 36526 → 2000-01-01 ✓
//! - serial 2958465 → 9999-12-31 ✓ (max date Excel accepts)
//!
//! # Why centralize it
//!
//! The plan calls for a single authoritative converter so the Wave 2 styles
//! emitter, the cell emitter, and the differential harness all agree. Any
//! off-by-one here corrupts every date in the workbook silently.

use chrono::{NaiveDate, NaiveDateTime, NaiveTime, Timelike};

/// The pre-1900 anchor. Picked so `chrono::Duration` from this date to
/// `1900-01-01` is exactly 1 day, making serial 1 = 1900-01-01 with no
/// additional shift for dates before the fake leap day.
fn windows_epoch() -> NaiveDate {
    NaiveDate::from_ymd_opt(1899, 12, 31).expect("1899-12-31 is valid")
}

fn mac_epoch() -> NaiveDate {
    NaiveDate::from_ymd_opt(1904, 1, 1).expect("1904-01-01 is valid")
}

/// The synthetic "February 29, 1900" that the fake-leap-year bug created.
/// Any conversion involving this date is undefined; we pin it to serial 60.
const FAKE_LEAP_SERIAL: i64 = 60;

/// Convert a `NaiveDate` to an Excel serial (whole days).
///
/// Returns `None` for dates before 1900-01-01 (Excel can't represent them
/// as positive serials) and for dates after 9999-12-31.
pub fn date_to_excel_serial(date: NaiveDate) -> Option<f64> {
    date_to_excel_serial_with_epoch(date, false)
}

pub fn date_to_excel_serial_with_epoch(date: NaiveDate, date1904: bool) -> Option<f64> {
    if date1904 {
        let max = NaiveDate::from_ymd_opt(9999, 12, 31)?;
        if date < mac_epoch() || date > max {
            return None;
        }
        return Some(date.signed_duration_since(mac_epoch()).num_days() as f64);
    }

    let min = NaiveDate::from_ymd_opt(1900, 1, 1)?;
    let max = NaiveDate::from_ymd_opt(9999, 12, 31)?;
    if date < min || date > max {
        return None;
    }

    let days = date.signed_duration_since(windows_epoch()).num_days();
    let adjusted = if days >= FAKE_LEAP_SERIAL {
        days + 1 // skip over the fake 1900-02-29
    } else {
        days
    };
    Some(adjusted as f64)
}

/// Convert a `NaiveDateTime` to an Excel serial (whole days + fractional).
pub fn datetime_to_excel_serial(dt: NaiveDateTime) -> Option<f64> {
    datetime_to_excel_serial_with_epoch(dt, false)
}

pub fn datetime_to_excel_serial_with_epoch(dt: NaiveDateTime, date1904: bool) -> Option<f64> {
    let whole = date_to_excel_serial_with_epoch(dt.date(), date1904)?;
    let frac = time_fraction(dt.time());
    Some(whole + frac)
}

/// Convert a `NaiveTime` to the fractional-day portion only.
///
/// `12:00:00` → 0.5, `06:00:00` → 0.25, `00:00:00` → 0.0.
/// Useful when the cell holds a pure time-of-day with no date component
/// (Excel displays these using the `[h]:mm:ss` family of number formats).
pub fn time_to_excel_serial(time: NaiveTime) -> f64 {
    time_fraction(time)
}

fn time_fraction(time: NaiveTime) -> f64 {
    let seconds = time.hour() as i64 * 3600 + time.minute() as i64 * 60 + time.second() as i64;
    let nanos = time.nanosecond() as f64 / 1_000_000_000.0;
    (seconds as f64 + nanos) / 86_400.0
}

/// Generic convenience entrypoint — any chrono value that makes sense as a
/// date serial. Separate typed entrypoints (above) are the primary API;
/// this exists so call sites with a `NaiveDateTime` don't have to remember
/// which function variant to pick.
pub fn to_excel_serial<T: IntoExcelSerial>(value: T) -> Option<f64> {
    value.into_excel_serial()
}

/// Implementation detail for [`to_excel_serial`].
pub trait IntoExcelSerial {
    fn into_excel_serial(self) -> Option<f64>;
}

impl IntoExcelSerial for NaiveDate {
    fn into_excel_serial(self) -> Option<f64> {
        date_to_excel_serial(self)
    }
}

impl IntoExcelSerial for NaiveDateTime {
    fn into_excel_serial(self) -> Option<f64> {
        datetime_to_excel_serial(self)
    }
}

impl IntoExcelSerial for NaiveTime {
    fn into_excel_serial(self) -> Option<f64> {
        Some(time_to_excel_serial(self))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ymd(y: i32, m: u32, d: u32) -> NaiveDate {
        NaiveDate::from_ymd_opt(y, m, d).unwrap()
    }

    #[test]
    fn epoch_anchor_gives_serial_one_for_new_years_day_1900() {
        assert_eq!(date_to_excel_serial(ymd(1900, 1, 1)), Some(1.0));
    }

    #[test]
    fn day_before_fake_leap_is_serial_59() {
        assert_eq!(date_to_excel_serial(ymd(1900, 2, 28)), Some(59.0));
    }

    #[test]
    fn day_after_fake_leap_is_serial_61() {
        // chrono skips 1900-02-29 entirely (correctly), so 1900-03-01 gets
        // serial 61 after our +1 shift — matching Excel's "serial 60 = fake Feb 29".
        assert_eq!(date_to_excel_serial(ymd(1900, 3, 1)), Some(61.0));
    }

    #[test]
    fn known_anchors_match_excel() {
        // Cross-checked against Excel directly.
        assert_eq!(date_to_excel_serial(ymd(2000, 1, 1)), Some(36526.0));
        assert_eq!(date_to_excel_serial(ymd(2026, 1, 1)), Some(46023.0));
        assert_eq!(date_to_excel_serial(ymd(9999, 12, 31)), Some(2_958_465.0));
    }

    #[test]
    fn pre_1900_dates_return_none() {
        assert_eq!(date_to_excel_serial(ymd(1899, 12, 31)), None);
        assert_eq!(date_to_excel_serial(ymd(1800, 1, 1)), None);
    }

    #[test]
    fn noon_is_half_day() {
        let t = NaiveTime::from_hms_opt(12, 0, 0).unwrap();
        assert!((time_to_excel_serial(t) - 0.5).abs() < 1e-12);
    }

    #[test]
    fn datetime_combines_date_and_fraction() {
        let dt = NaiveDate::from_ymd_opt(2026, 1, 1)
            .unwrap()
            .and_hms_opt(18, 0, 0)
            .unwrap();
        let serial = datetime_to_excel_serial(dt).unwrap();
        assert!((serial - 46023.75).abs() < 1e-9);
    }
}
