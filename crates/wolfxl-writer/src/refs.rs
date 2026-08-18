//! A1 / column-letter / sheet-name helpers.
//!
//! The writer emits cell addresses, defined-name targets, and sheet names in
//! OOXML text form. Those three tasks all sit on the same handful of
//! primitives:
//!
//! - Column numbers ↔ letters (`1 ↔ A`, `27 ↔ AA`, `16_384 ↔ XFD`), using
//!   **bijective base-26** (no zero digit).
//! - A1 cell addresses ↔ `(row, col)` pairs, both 1-based to match Excel.
//! - A1 ranges ↔ `((top-left), (bottom-right))` pairs, with endpoint
//!   normalization so `D20:A1` round-trips as `A1:D20`.
//! - Excel's sheet-name rules: strip `/\?*[]:`, truncate to 31 Unicode chars,
//!   quote and escape when a name contains whitespace, punctuation, or starts
//!   with a digit (required for `definedName` refs like `'2024 Data'!A1`).
//!
//! All helpers in this module are pure — no I/O, no allocation beyond the
//! returned `String`s — so Wave 2/3 emitters can call them freely from inside
//! tight loops without surprises.

/// The maximum column Excel accepts: `XFD` = 16_384.
pub const MAX_COL: u32 = 16_384;

/// The maximum row Excel accepts: 1,048,576.
pub const MAX_ROW: u32 = 1_048_576;

/// Convert a 1-based column number to its A1 letter form.
///
/// `1` → `"A"`, `26` → `"Z"`, `27` → `"AA"`, `16_384` → `"XFD"`.
///
/// # Panics
///
/// Panics if `col == 0` or `col > MAX_COL`. The caller is responsible for
/// validating the column before calling — an out-of-range column is an
/// invariant violation, not a recoverable error.
///
/// # Algorithm
///
/// Excel column letters are **bijective base-26**: there is no zero digit.
/// The straightforward `digit = n % 26; n /= 26` loop would produce
/// `'A'..='Z'` mapping to `0..=25`, which makes `Z` wrap to `0` after `A`.
/// Subtracting one before each division fixes the off-by-one:
///
/// ```text
/// n -= 1;
/// digit = n % 26;   // now 0..=25, with 0 = 'A'
/// n /= 26;
/// ```
pub fn col_to_letters(col: u32) -> String {
    assert!(
        (1..=MAX_COL).contains(&col),
        "column out of range: {col} (expected 1..={MAX_COL})"
    );
    let mut n = col;
    let mut out = Vec::new();
    while n > 0 {
        n -= 1;
        out.push(b'A' + (n % 26) as u8);
        n /= 26;
    }
    out.reverse();
    String::from_utf8(out).expect("base-26 A..Z is ASCII")
}

/// Convert an A1 letter sequence to a 1-based column number.
///
/// Accepts upper, lower, or mixed case. Returns `None` for the empty string,
/// any non-ASCII-letter character (including digits and punctuation), and
/// values greater than `MAX_COL` (e.g. `"XFE"`).
///
/// # Examples
///
/// ```
/// # use wolfxl_writer::refs::letters_to_col;
/// assert_eq!(letters_to_col("A"),   Some(1));
/// assert_eq!(letters_to_col("z"),   Some(26));
/// assert_eq!(letters_to_col("Aa"),  Some(27));
/// assert_eq!(letters_to_col("XFD"), Some(16_384));
/// assert_eq!(letters_to_col("XFE"), None);
/// assert_eq!(letters_to_col(""),    None);
/// assert_eq!(letters_to_col("A1"),  None);
/// ```
pub fn letters_to_col(s: &str) -> Option<u32> {
    if s.is_empty() {
        return None;
    }
    let mut n: u32 = 0;
    for ch in s.chars() {
        let v = match ch {
            'A'..='Z' => (ch as u32) - ('A' as u32) + 1,
            'a'..='z' => (ch as u32) - ('a' as u32) + 1,
            _ => return None,
        };
        n = n.checked_mul(26)?.checked_add(v)?;
    }
    if n == 0 || n > MAX_COL {
        None
    } else {
        Some(n)
    }
}

/// Parse an A1 cell address into `(row, col)`, both 1-based.
///
/// `"A1"` → `Some((1, 1))`, `"XFD1048576"` → `Some((1_048_576, 16_384))`.
/// Lowercase is accepted (`"a1"` → `Some((1, 1))`).
///
/// Returns `None` for:
///
/// - the empty string,
/// - leading digits (`"1A"`),
/// - missing row portion (`"A"`),
/// - absolute references (`"$A$1"`, `"A$1"`, `"$A1"`) — those belong to
///   `parse_a1_absolute` if we ever add one,
/// - out-of-range rows (`"A1048577"`) or columns (`"XFE1"`),
/// - any trailing junk.
pub fn parse_a1(s: &str) -> Option<(u32, u32)> {
    if s.is_empty() {
        return None;
    }
    // Reject absolute refs up-front: `$` is an Excel token that doesn't
    // belong in a plain A1 string. The writer's defined-name and formula
    // paths build those up from `(row, col)` pairs directly.
    if s.contains('$') {
        return None;
    }

    // Split at the first ASCII digit. Everything before is the column
    // letters, everything after is the row number.
    let split = s.char_indices().find(|(_, c)| c.is_ascii_digit())?.0;
    if split == 0 {
        // Leading digit → no column letters.
        return None;
    }
    let (letters, digits) = s.split_at(split);
    if digits.is_empty() {
        return None;
    }
    // Reject trailing junk: every char in the digit slice must be a digit.
    if !digits.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }

    let col = letters_to_col(letters)?;
    let row: u32 = digits.parse().ok()?;
    if row == 0 || row > MAX_ROW {
        return None;
    }
    Some((row, col))
}

/// Format a `(row, col)` pair (both 1-based) as an A1 cell address.
///
/// # Panics
///
/// Panics if `row == 0`, `row > MAX_ROW`, `col == 0`, or `col > MAX_COL`.
/// Out-of-range coordinates are an invariant violation — the caller should
/// clamp or validate before calling.
pub fn format_a1(row: u32, col: u32) -> String {
    assert!(
        (1..=MAX_ROW).contains(&row),
        "row out of range: {row} (expected 1..={MAX_ROW})"
    );
    // `col_to_letters` handles its own bounds check; we still assert here so
    // the panic message names the function the caller actually invoked.
    assert!(
        (1..=MAX_COL).contains(&col),
        "column out of range: {col} (expected 1..={MAX_COL})"
    );
    let mut out = col_to_letters(col);
    out.push_str(&row.to_string());
    out
}

/// Parse an A1 range into `((top_left), (bottom_right))`, both `(row, col)`.
///
/// A single-cell form (`"A1"`) is accepted and returns the same cell as both
/// endpoints: `Some(((1,1), (1,1)))`.
///
/// Out-of-order inputs are normalized: `"D20:A1"` returns the same tuple as
/// `"A1:D20"`, with top-left (smaller row *and* smaller column) first. This
/// matters because OOXML consumers (and conditional-formatting rules) expect
/// the range attribute in canonical order.
///
/// Returns `None` if either endpoint is malformed or if the range separator
/// appears more than once (`"A1:B2:C3"`).
pub fn parse_range(s: &str) -> Option<((u32, u32), (u32, u32))> {
    let mut parts = s.split(':');
    let first = parts.next()?;
    let second = parts.next();
    if parts.next().is_some() {
        // Three or more `:` parts — not a valid range.
        return None;
    }
    let (r1, c1) = parse_a1(first)?;
    let (r2, c2) = match second {
        Some(tail) => parse_a1(tail)?,
        None => (r1, c1),
    };
    // Normalize to top-left / bottom-right. Excel's convention is
    // row-major, so we sort row and column independently — this correctly
    // handles `"D1:A20"` (mixed corners) as well as `"D20:A1"` (reversed).
    let top = (r1.min(r2), c1.min(c2));
    let bottom = (r1.max(r2), c1.max(c2));
    Some((top, bottom))
}

/// Format a range. Returns `"A1"` when both endpoints are equal and
/// `"A1:D20"` otherwise.
///
/// Endpoints are not reordered — the caller is expected to pass top-left
/// first. If you have a pair from [`parse_range`] you already got back the
/// canonical form.
///
/// # Panics
///
/// Panics if any coordinate is out of range (inherited from [`format_a1`]).
pub fn format_range(top_left: (u32, u32), bottom_right: (u32, u32)) -> String {
    let tl = format_a1(top_left.0, top_left.1);
    if top_left == bottom_right {
        return tl;
    }
    let br = format_a1(bottom_right.0, bottom_right.1);
    let mut out = String::with_capacity(tl.len() + 1 + br.len());
    out.push_str(&tl);
    out.push(':');
    out.push_str(&br);
    out
}

/// Sanitize a sheet name for use in `xl/workbook.xml` and sheet tab labels.
///
/// Applies, in order:
///
/// 1. Strip every occurrence of Excel's forbidden character set: `/ \ ? * [ ] :`.
/// 2. Strip leading/trailing `'` — Excel treats these as quoting tokens and
///    will refuse to open a workbook whose sheet name starts or ends with one.
/// 3. Truncate to 31 **Unicode scalar values** (not bytes). Emoji and
///    other multibyte characters each count as 1.
/// 4. If the result is empty, return `"Sheet"` as a fallback so the emitter
///    never produces a nameless tab.
///
/// The returned name may still need [`quote_sheet_name_if_needed`] before
/// being embedded in a `definedName` ref or formula.
pub fn sanitize_sheet_name(name: &str) -> String {
    // Strip forbidden chars first. Excel's list: / \ ? * [ ] :
    let mut stripped: String = name
        .chars()
        .filter(|c| !matches!(*c, '/' | '\\' | '?' | '*' | '[' | ']' | ':'))
        .collect();

    // Strip leading/trailing apostrophes.
    while stripped.starts_with('\'') {
        stripped.remove(0);
    }
    while stripped.ends_with('\'') {
        stripped.pop();
    }

    // Truncate to 31 Unicode scalar values. `char_indices().nth(31)` lands
    // on the byte offset of the 32nd character, or `None` if the string is
    // already short enough.
    if let Some((idx, _)) = stripped.char_indices().nth(31) {
        stripped.truncate(idx);
    }

    if stripped.is_empty() {
        "Sheet".to_string()
    } else {
        stripped
    }
}

/// Wrap a sheet name in single quotes and escape embedded quotes if Excel
/// requires it for the given context (defined-name refs, cross-sheet formula
/// references).
///
/// A name needs quoting when it:
///
/// - contains any of: space, `,`, `!`, `?`, `'`, `-`,
/// - or starts with a digit.
///
/// Embedded `'` characters are doubled (`O'Brien's` → `'O''Brien''s'`),
/// matching Excel's quoting convention. This is the inverse of what the
/// reader would do when it encounters `'…'!A1` in a formula.
///
/// Sheet names that pass all checks are returned as-is, so the common case
/// (`"Sheet1"` → `"Sheet1"`) is a no-op allocation-wise.
pub fn quote_sheet_name_if_needed(name: &str) -> String {
    let needs_quote = name.chars().next().is_some_and(|c| c.is_ascii_digit())
        || name
            .chars()
            .any(|c| matches!(c, ' ' | ',' | '!' | '?' | '\'' | '-'));
    if !needs_quote {
        return name.to_string();
    }
    let mut out = String::with_capacity(name.len() + 2);
    out.push('\'');
    for ch in name.chars() {
        if ch == '\'' {
            out.push('\'');
            out.push('\'');
        } else {
            out.push(ch);
        }
    }
    out.push('\'');
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    // ---- col_to_letters / letters_to_col ----

    #[test]
    fn col_letters_round_trip() {
        for &col in &[1u32, 26, 27, 52, 702, 703, MAX_COL] {
            let letters = col_to_letters(col);
            assert_eq!(
                letters_to_col(&letters),
                Some(col),
                "col={col}, letters={letters}"
            );
        }
    }

    #[test]
    fn well_known_anchors() {
        assert_eq!(col_to_letters(1), "A");
        assert_eq!(col_to_letters(26), "Z");
        assert_eq!(col_to_letters(27), "AA");
        assert_eq!(col_to_letters(52), "AZ");
        assert_eq!(col_to_letters(702), "ZZ");
        assert_eq!(col_to_letters(703), "AAA");
        assert_eq!(col_to_letters(MAX_COL), "XFD");
    }

    #[test]
    fn letters_to_col_well_known() {
        assert_eq!(letters_to_col("A"), Some(1));
        assert_eq!(letters_to_col("Z"), Some(26));
        assert_eq!(letters_to_col("AA"), Some(27));
        assert_eq!(letters_to_col("AZ"), Some(52));
        assert_eq!(letters_to_col("ZZ"), Some(702));
        assert_eq!(letters_to_col("AAA"), Some(703));
        assert_eq!(letters_to_col("XFD"), Some(MAX_COL));
    }

    #[test]
    fn letters_to_col_accepts_lowercase() {
        assert_eq!(letters_to_col("a"), Some(1));
        assert_eq!(letters_to_col("z"), Some(26));
        assert_eq!(letters_to_col("aa"), Some(27));
        assert_eq!(letters_to_col("xfd"), Some(MAX_COL));
    }

    #[test]
    fn letters_to_col_accepts_mixed_case() {
        assert_eq!(letters_to_col("Aa"), Some(27));
        assert_eq!(letters_to_col("aA"), Some(27));
        assert_eq!(letters_to_col("XfD"), Some(MAX_COL));
    }

    #[test]
    fn letters_to_col_rejects_empty() {
        assert_eq!(letters_to_col(""), None);
    }

    #[test]
    fn letters_to_col_rejects_out_of_range() {
        assert_eq!(letters_to_col("XFE"), None);
        assert_eq!(letters_to_col("XFZ"), None);
        assert_eq!(letters_to_col("ZZZZ"), None);
    }

    #[test]
    fn letters_to_col_rejects_digits_and_punctuation() {
        assert_eq!(letters_to_col("1"), None);
        assert_eq!(letters_to_col("A1"), None);
        assert_eq!(letters_to_col("A-B"), None);
        assert_eq!(letters_to_col("A!"), None);
        assert_eq!(letters_to_col(" A"), None);
        assert_eq!(letters_to_col("AAé"), None);
    }

    #[test]
    #[should_panic(expected = "column out of range")]
    fn col_to_letters_panics_on_zero() {
        let _ = col_to_letters(0);
    }

    #[test]
    #[should_panic(expected = "column out of range")]
    fn col_to_letters_panics_above_max() {
        let _ = col_to_letters(MAX_COL + 1);
    }

    // ---- parse_a1 / format_a1 ----

    #[test]
    fn parse_a1_round_trip() {
        for &(row, col, repr) in &[
            (1u32, 1u32, "A1"),
            (1, 27, "AA1"),
            (MAX_ROW, MAX_COL, "XFD1048576"),
        ] {
            assert_eq!(parse_a1(repr), Some((row, col)));
            assert_eq!(format_a1(row, col), repr);
        }
    }

    #[test]
    fn parse_a1_accepts_lowercase() {
        assert_eq!(parse_a1("a1"), Some((1, 1)));
        assert_eq!(parse_a1("xfd1"), Some((1, MAX_COL)));
    }

    #[test]
    fn parse_a1_rejects_empty() {
        assert_eq!(parse_a1(""), None);
    }

    #[test]
    fn parse_a1_rejects_leading_digits() {
        assert_eq!(parse_a1("1A"), None);
        assert_eq!(parse_a1("123"), None);
    }

    #[test]
    fn parse_a1_rejects_missing_row() {
        assert_eq!(parse_a1("A"), None);
        assert_eq!(parse_a1("AAA"), None);
    }

    #[test]
    fn parse_a1_rejects_absolute_refs() {
        assert_eq!(parse_a1("$A$1"), None);
        assert_eq!(parse_a1("$A1"), None);
        assert_eq!(parse_a1("A$1"), None);
    }

    #[test]
    fn parse_a1_rejects_out_of_range_row() {
        assert_eq!(parse_a1("A1048577"), None);
        assert_eq!(parse_a1("A0"), None);
    }

    #[test]
    fn parse_a1_rejects_out_of_range_col() {
        assert_eq!(parse_a1("XFE1"), None);
        assert_eq!(parse_a1("ZZZZ1"), None);
    }

    #[test]
    fn parse_a1_rejects_trailing_junk() {
        assert_eq!(parse_a1("A1 "), None);
        assert_eq!(parse_a1("A1B2"), None);
        assert_eq!(parse_a1("A1.5"), None);
    }

    #[test]
    #[should_panic(expected = "row out of range")]
    fn format_a1_panics_on_zero_row() {
        let _ = format_a1(0, 1);
    }

    #[test]
    #[should_panic(expected = "row out of range")]
    fn format_a1_panics_above_max_row() {
        let _ = format_a1(MAX_ROW + 1, 1);
    }

    #[test]
    #[should_panic(expected = "column out of range")]
    fn format_a1_panics_above_max_col() {
        let _ = format_a1(1, MAX_COL + 1);
    }

    // ---- parse_range / format_range ----

    #[test]
    fn parse_range_single_cell() {
        assert_eq!(parse_range("A1"), Some(((1, 1), (1, 1))));
        assert_eq!(parse_range("D20"), Some(((20, 4), (20, 4))));
    }

    #[test]
    fn parse_range_basic() {
        assert_eq!(parse_range("A1:D20"), Some(((1, 1), (20, 4))));
        assert_eq!(
            parse_range("B2:XFD1048576"),
            Some(((2, 2), (MAX_ROW, MAX_COL)))
        );
    }

    #[test]
    fn parse_range_normalizes_out_of_order() {
        // Reversed endpoints should still land at top-left = (1,1),
        // bottom-right = (20,4).
        assert_eq!(parse_range("D20:A1"), Some(((1, 1), (20, 4))));
        // Mixed corners (different row + col winners on each side)
        // should still normalize independently.
        assert_eq!(parse_range("D1:A20"), Some(((1, 1), (20, 4))));
        assert_eq!(parse_range("A20:D1"), Some(((1, 1), (20, 4))));
    }

    #[test]
    fn parse_range_rejects_garbage() {
        assert_eq!(parse_range(""), None);
        assert_eq!(parse_range(":"), None);
        assert_eq!(parse_range("A1:"), None);
        assert_eq!(parse_range(":A1"), None);
        assert_eq!(parse_range("A1:B2:C3"), None);
        assert_eq!(parse_range("XFE1:A1"), None);
    }

    #[test]
    fn format_range_single_cell() {
        assert_eq!(format_range((1, 1), (1, 1)), "A1");
        assert_eq!(format_range((20, 4), (20, 4)), "D20");
    }

    #[test]
    fn format_range_basic() {
        assert_eq!(format_range((1, 1), (20, 4)), "A1:D20");
        assert_eq!(format_range((1, 1), (MAX_ROW, MAX_COL)), "A1:XFD1048576");
    }

    #[test]
    fn range_round_trip() {
        for repr in &["A1", "A1:D20", "B2:XFD1048576"] {
            let (tl, br) = parse_range(repr).unwrap();
            assert_eq!(format_range(tl, br), *repr, "repr={repr}");
        }
    }

    // ---- sanitize_sheet_name ----

    #[test]
    fn sanitize_strips_each_forbidden_char() {
        assert_eq!(sanitize_sheet_name("a/b"), "ab");
        assert_eq!(sanitize_sheet_name("a\\b"), "ab");
        assert_eq!(sanitize_sheet_name("a?b"), "ab");
        assert_eq!(sanitize_sheet_name("a*b"), "ab");
        assert_eq!(sanitize_sheet_name("a[b"), "ab");
        assert_eq!(sanitize_sheet_name("a]b"), "ab");
        assert_eq!(sanitize_sheet_name("a:b"), "ab");
        // All at once.
        assert_eq!(sanitize_sheet_name("/\\?*[]:weird"), "weird");
    }

    #[test]
    fn sanitize_strips_leading_trailing_apostrophes() {
        assert_eq!(sanitize_sheet_name("'Sheet1"), "Sheet1");
        assert_eq!(sanitize_sheet_name("Sheet1'"), "Sheet1");
        assert_eq!(sanitize_sheet_name("'''Sheet1'''"), "Sheet1");
        // Interior apostrophes are preserved.
        assert_eq!(sanitize_sheet_name("O'Brien"), "O'Brien");
    }

    #[test]
    fn sanitize_truncates_to_31_chars() {
        let long = "a".repeat(100);
        let s = sanitize_sheet_name(&long);
        assert_eq!(s.chars().count(), 31);
        assert_eq!(s, "a".repeat(31));
    }

    #[test]
    fn sanitize_truncates_by_unicode_chars_not_bytes() {
        // Each emoji is a single `char` (scalar value) but ~4 bytes in UTF-8.
        // We should keep 31 of them, not truncate mid-emoji by byte count.
        let rocket = "\u{1F680}"; // rocket emoji
        let long = rocket.repeat(50);
        let s = sanitize_sheet_name(&long);
        assert_eq!(s.chars().count(), 31);
        // Every char in the output should be the rocket — no mid-codepoint cut.
        assert!(s.chars().all(|c| c == '\u{1F680}'));
    }

    #[test]
    fn sanitize_empty_falls_back_to_sheet() {
        assert_eq!(sanitize_sheet_name(""), "Sheet");
        // A name that's nothing but forbidden chars also collapses to "Sheet".
        assert_eq!(sanitize_sheet_name("/\\?*[]:"), "Sheet");
        // Nothing-but-apostrophes likewise.
        assert_eq!(sanitize_sheet_name("'''"), "Sheet");
    }

    // ---- quote_sheet_name_if_needed ----

    #[test]
    fn quote_leaves_plain_names_alone() {
        assert_eq!(quote_sheet_name_if_needed("Sheet1"), "Sheet1");
        assert_eq!(quote_sheet_name_if_needed("Summary"), "Summary");
        assert_eq!(quote_sheet_name_if_needed("A"), "A");
    }

    #[test]
    fn quote_wraps_names_with_spaces() {
        assert_eq!(
            quote_sheet_name_if_needed("Quarterly Data"),
            "'Quarterly Data'"
        );
        assert_eq!(quote_sheet_name_if_needed("a b c"), "'a b c'");
    }

    #[test]
    fn quote_wraps_names_starting_with_digit() {
        assert_eq!(quote_sheet_name_if_needed("2024"), "'2024'");
        assert_eq!(quote_sheet_name_if_needed("1-Year"), "'1-Year'");
    }

    #[test]
    fn quote_wraps_names_with_punctuation() {
        assert_eq!(quote_sheet_name_if_needed("a,b"), "'a,b'");
        assert_eq!(quote_sheet_name_if_needed("a!b"), "'a!b'");
        assert_eq!(quote_sheet_name_if_needed("a?b"), "'a?b'");
        assert_eq!(quote_sheet_name_if_needed("a-b"), "'a-b'");
    }

    #[test]
    fn quote_doubles_embedded_apostrophes() {
        assert_eq!(quote_sheet_name_if_needed("O'Brien's"), "'O''Brien''s'");
        assert_eq!(quote_sheet_name_if_needed("'"), "''''");
        assert_eq!(quote_sheet_name_if_needed("a'b'c"), "'a''b''c'");
    }
}
