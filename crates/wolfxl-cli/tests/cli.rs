//! Integration tests for `wolfxl peek`.
//!
//! Goldens lock in the rendering contract for `text`, `csv`, `json`, and `markdown`
//! exporters: integer thousand-grouping, two-decimal float formatting,
//! ISO date/time, RFC 4180 CSV quoting, and the JSON `{sheet, rows,
//! columns, headers, data}` shape. If you change a renderer and a golden
//! moves, either regenerate the golden intentionally and update the token
//! tables in `spreadsheet-peek`, or fix the bug.
//!
//! The boxed renderer isn't goldened - its banner is wolfxl-branded and
//! column widths can drift on minor rendering tweaks. Smoke-tested
//! instead via `boxed_smoke`.

use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use assert_cmd::Command;

fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name)
}

fn golden(name: &str) -> String {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/golden")
        .join(name);
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("read golden {}: {e}", path.display()))
}

fn run(args: &[&str]) -> String {
    let out = Command::cargo_bin("wolfxl")
        .expect("wolfxl bin built")
        .args(args)
        .output()
        .expect("run wolfxl");
    assert!(
        out.status.success(),
        "wolfxl {:?} failed: stderr={}",
        args,
        String::from_utf8_lossy(&out.stderr)
    );
    String::from_utf8(out.stdout).expect("utf-8 stdout")
}

fn temp_csv(prefix: &str, contents: &str) -> PathBuf {
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time moves forward")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("{prefix}-{stamp}.csv"));
    std::fs::write(&path, contents)
        .unwrap_or_else(|e| panic!("write temp csv {}: {e}", path.display()));
    path
}

#[test]
fn text_export_matches_golden_sample() {
    let path = fixture("sample-financials.xlsx");
    let actual = run(&["peek", path.to_str().unwrap(), "-e", "text"]);
    assert_eq!(actual, golden("sample-financials.text"));
}

#[test]
fn csv_export_matches_golden_sample() {
    let path = fixture("sample-financials.xlsx");
    let actual = run(&["peek", path.to_str().unwrap(), "-e", "csv"]);
    assert_eq!(actual, golden("sample-financials.csv"));
}

#[test]
fn json_export_matches_golden_sample() {
    let path = fixture("sample-financials.xlsx");
    let actual = run(&["peek", path.to_str().unwrap(), "-e", "json"]);
    assert_eq!(actual, golden("sample-financials.json"));
}

#[test]
fn markdown_export_matches_golden_sample() {
    let path = fixture("sample-financials.xlsx");
    let actual = run(&["peek", path.to_str().unwrap(), "-e", "markdown"]);
    assert_eq!(actual, golden("sample-financials.markdown"));
}

#[test]
fn text_export_matches_golden_wide() {
    let path = fixture("wide-table.xlsx");
    let actual = run(&["peek", path.to_str().unwrap(), "-e", "text"]);
    assert_eq!(actual, golden("wide-table.text"));
}

#[test]
fn csv_export_matches_golden_wide() {
    let path = fixture("wide-table.xlsx");
    let actual = run(&["peek", path.to_str().unwrap(), "-e", "csv"]);
    assert_eq!(actual, golden("wide-table.csv"));
}

#[test]
fn json_export_matches_golden_wide() {
    let path = fixture("wide-table.xlsx");
    let actual = run(&["peek", path.to_str().unwrap(), "-e", "json"]);
    assert_eq!(actual, golden("wide-table.json"));
}

#[test]
fn json_export_bounds_rows_and_columns_without_hiding_sheet_dimensions() {
    let path = fixture("wide-table.xlsx");
    let out = run(&[
        "peek",
        path.to_str().unwrap(),
        "-e",
        "json",
        "--max-rows",
        "2",
        "--max-columns",
        "3",
    ]);
    let value: serde_json::Value = serde_json::from_str(&out).expect("json parses");

    assert_eq!(value["rows"], 24, "rows remains the full-sheet count");
    assert_eq!(value["columns"], 29, "columns remains the full-sheet count");
    assert_eq!(value["headers"].as_array().unwrap().len(), 3);
    let data = value["data"].as_array().unwrap();
    assert_eq!(data.len(), 2);
    assert!(data.iter().all(|row| row.as_array().unwrap().len() <= 3));
}

#[test]
fn text_export_respects_number_formats_on_human_surface() {
    let path = fixture("formatted-values.xlsx");
    let out = run(&["peek", path.to_str().unwrap(), "-e", "text"]);
    assert!(
        out.contains("Revenue\t$1,234,567.50\t23.4%\t2024-03-31\t2,505.15"),
        "text export should render currency and percent formats: {out}"
    );
}

#[test]
fn csv_export_respects_number_formats_on_human_surface() {
    let path = fixture("formatted-values.xlsx");
    let out = run(&["peek", path.to_str().unwrap(), "-e", "csv"]);
    assert!(
        out.contains("Revenue,\"$1,234,567.50\",23.4%,2024-03-31,\"2,505.15\""),
        "csv export should render currency and percent formats: {out}"
    );
}

#[test]
fn markdown_export_respects_number_formats_on_human_surface() {
    let path = fixture("formatted-values.xlsx");
    let out = run(&["peek", path.to_str().unwrap(), "-e", "markdown"]);
    assert!(
        out.contains("| Revenue | $1,234,567.50 | 23.4% | 2024-03-31 | 2,505.15 |"),
        "markdown export should render currency and percent formats: {out}"
    );
}

#[test]
fn markdown_export_escapes_table_breaking_characters() {
    let path = temp_csv(
        "markdown-escape",
        "Name,Notes\nAcme,\"pipe | backslash \\ tab\tquote \"\"ok\"\"\"\nGlobex,\"line one\nline two\"\n",
    );
    let out = run(&["peek", path.to_str().unwrap(), "-e", "markdown"]);
    assert!(
        out.contains("| Name | Notes |"),
        "missing markdown header: {out}"
    );
    assert!(
        out.contains("|---|---|"),
        "missing markdown separator: {out}"
    );
    assert!(
        out.contains("| Acme | pipe \\| backslash \\\\ tab\\tquote \"ok\" |"),
        "table-breaking characters should be escaped: {out}"
    );
    assert!(
        out.contains("| Globex | line one\\nline two |"),
        "multiline cells should stay on one table row: {out}"
    );
}

#[test]
fn boxed_export_respects_number_formats_on_human_surface() {
    let path = fixture("formatted-values.xlsx");
    let out = run(&["peek", path.to_str().unwrap(), "-n", "2"]);
    assert!(out.contains("$1,234,567.50"), "missing currency: {out}");
    assert!(out.contains("23.4%"), "missing percent: {out}");
}

#[test]
fn json_export_keeps_machine_values_for_formatted_cells() {
    let path = fixture("formatted-values.xlsx");
    let out = run(&["peek", path.to_str().unwrap(), "-e", "json"]);
    let v: serde_json::Value = serde_json::from_str(&out).expect("json parses");
    let data = v["data"].as_array().expect("data array");
    assert_eq!(data[0][1], 1234567.5);
    assert_eq!(data[0][2], 0.234);
    assert!(
        !out.contains("$1,234,567.50") && !out.contains("23.4%"),
        "json should stay value-shaped, not display-shaped: {out}"
    );
}

#[test]
fn boxed_smoke() {
    let path = fixture("sample-financials.xlsx");
    let out = run(&["peek", path.to_str().unwrap(), "-n", "5"]);
    assert!(out.contains("wolfxl peek"), "missing banner: {out}");
    assert!(out.contains("Sheet: P&L"), "missing sheet header: {out}");
    assert!(out.contains("Available sheets:"), "missing sheet list");
    assert!(
        out.contains("Showing 5 of 20 rows"),
        "missing truncation footer: {out}"
    );
    assert!(out.contains("│"), "missing box-drawing char");
}

#[test]
fn boxed_named_sheet() {
    let path = fixture("sample-financials.xlsx");
    let out = run(&[
        "peek",
        path.to_str().unwrap(),
        "-s",
        "Revenue Breakdown",
        "-n",
        "3",
    ]);
    assert!(
        out.contains("Sheet: Revenue Breakdown"),
        "wrong sheet: {out}"
    );
    assert!(out.contains("Showing 3 of 12 rows"), "wrong cap: {out}");
}

#[test]
fn boxed_max_width_truncates() {
    let path = fixture("wide-table.xlsx");
    let out = run(&["peek", path.to_str().unwrap(), "-n", "2", "-w", "10"]);
    assert!(out.contains("…"), "expected ellipsis from -w 10: {out}");
}

#[test]
fn unknown_sheet_errors() {
    let path = fixture("sample-financials.xlsx");
    let out = Command::cargo_bin("wolfxl")
        .unwrap()
        .args(["peek", path.to_str().unwrap(), "-s", "Does Not Exist"])
        .output()
        .unwrap();
    assert!(!out.status.success());
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(stderr.contains("not found"), "stderr was: {stderr}");
}

#[test]
fn missing_file_errors() {
    let out = Command::cargo_bin("wolfxl")
        .unwrap()
        .args(["peek", "/nonexistent/wolfxl-test.xlsx"])
        .output()
        .unwrap();
    assert!(!out.status.success());
}

#[test]
fn map_text_lists_every_sheet_with_class_and_dims() {
    let path = fixture("sample-financials.xlsx");
    let out = run(&["map", path.to_str().unwrap(), "--format", "text"]);
    // All three sheets appear with their classification tag.
    assert!(
        out.contains("[data] P&L  (21 rows × 7 cols)"),
        "missing P&L line: {out}"
    );
    assert!(
        out.contains("[data] Balance Sheet  (27 rows × 5 cols)"),
        "missing Balance Sheet line"
    );
    assert!(
        out.contains("[data] Revenue Breakdown  (13 rows × 7 cols)"),
        "missing Revenue line"
    );
    // Header preview surfaces the first column of P&L so callers can
    // tell which sheet has which schema without a `peek`.
    assert!(
        out.contains("Account | Jan 2024"),
        "missing P&L headers: {out}"
    );
}

#[test]
fn map_json_is_valid_and_has_expected_shape() {
    let path = fixture("sample-financials.xlsx");
    let out = run(&["map", path.to_str().unwrap()]);
    let value: serde_json::Value = serde_json::from_str(&out).expect("map JSON parses");
    let sheets = value["sheets"].as_array().expect("sheets is array");
    assert_eq!(sheets.len(), 3, "expected 3 sheets in sample-financials");
    assert_eq!(sheets[0]["name"], "P&L");
    assert_eq!(sheets[0]["rows"], 21);
    assert_eq!(sheets[0]["cols"], 7);
    assert_eq!(sheets[0]["class"], "data");
    assert_eq!(sheets[0]["headers"][0], "Account");
    assert!(
        value["named_ranges"].is_array(),
        "named_ranges field must exist"
    );
}

#[test]
fn map_handles_wide_table_with_truncated_header_preview() {
    let path = fixture("wide-table.xlsx");
    let out = run(&["map", path.to_str().unwrap(), "--format", "text"]);
    // Wide table has 29 columns; text view caps the header preview at 8
    // and reports the overflow count so an agent can decide whether to
    // `peek` the full width.
    assert!(
        out.contains("[data] Dept Operations  (25 rows × 29 cols)"),
        "missing dims: {out}"
    );
    assert!(
        out.contains("… (+21 more)"),
        "missing overflow marker: {out}"
    );
}

#[test]
fn agent_picks_largest_data_sheet_and_emits_overview_plus_samples() {
    let path = fixture("sample-financials.xlsx");
    let out = run(&["agent", path.to_str().unwrap(), "--max-tokens", "800"]);
    // Workbook overview lists every sheet with class + first column.
    assert!(
        out.contains("WORKBOOK: sample-financials.xlsx"),
        "missing workbook line: {out}"
    );
    assert!(
        out.contains("- P&L (21r×7c) [data]"),
        "missing P&L overview: {out}"
    );
    assert!(
        out.contains("- Balance Sheet (27r×5c) [data]"),
        "missing balance sheet overview"
    );
    // Balance Sheet is the largest data sheet (27 > 21 > 13) so it's
    // picked when --sheet isn't given.
    assert!(
        out.contains("SHEET: Balance Sheet  [data]  27 rows × 5 cols"),
        "wrong target sheet: {out}"
    );
    assert!(
        out.contains("HEADERS: Account\tMar 31 2024"),
        "missing headers row: {out}"
    );
    // All three row sections fit at 800-token budget.
    assert!(out.contains("ROWS (head 3 of"), "missing head block: {out}");
    assert!(out.contains("ROWS (tail 2 of"), "missing tail block: {out}");
    assert!(
        out.contains("ROWS (middle stratified"),
        "missing middle block: {out}"
    );
    // Footer reports cl100k_base accounting.
    assert!(out.contains("# wolfxl agent:"), "missing footer: {out}");
    assert!(
        out.contains("/800 tokens (cl100k_base)"),
        "wrong footer format: {out}"
    );
}

#[test]
fn agent_respects_explicit_sheet_override() {
    let path = fixture("sample-financials.xlsx");
    let out = run(&["agent", path.to_str().unwrap(), "-s", "Revenue Breakdown"]);
    assert!(
        out.contains("SHEET: Revenue Breakdown"),
        "explicit --sheet should win over largest-data heuristic: {out}"
    );
}

#[test]
fn agent_keeps_compact_raw_numbers_for_formatted_cells() {
    let path = fixture("formatted-values.xlsx");
    let out = run(&["agent", path.to_str().unwrap(), "--max-tokens", "400"]);
    assert!(
        out.contains("Revenue\t1234567.50\t0.23\t2024-03-31\t2505.15"),
        "agent output should keep cheap numeric rendering: {out}"
    );
    assert!(
        !out.contains("$1,234,567.50") && !out.contains("23.4%"),
        "agent should not spend tokens on display symbols: {out}"
    );
}

#[test]
fn agent_falls_back_to_orientation_when_budget_too_small() {
    // 100-token budget can't fit the orientation core for a 3-sheet
    // workbook with 5-7 column headers; we still emit it (overage
    // reported in footer) and skip every row block. The agent at least
    // learns the workbook structure.
    let path = fixture("sample-financials.xlsx");
    let out = run(&["agent", path.to_str().unwrap(), "--max-tokens", "100"]);
    assert!(out.contains("WORKBOOK:"), "must always emit workbook line");
    assert!(out.contains("SHEET:"), "must always emit sheet header");
    assert!(out.contains("HEADERS:"), "must always emit columns");
    assert!(
        !out.contains("ROWS (head"),
        "head block must drop at tight budget: {out}"
    );
    assert!(
        !out.contains("ROWS (tail"),
        "tail block must drop at tight budget: {out}"
    );
}

#[test]
fn agent_unknown_sheet_errors() {
    let path = fixture("sample-financials.xlsx");
    let out = Command::cargo_bin("wolfxl")
        .unwrap()
        .args(["agent", path.to_str().unwrap(), "-s", "Does Not Exist"])
        .output()
        .unwrap();
    assert!(!out.status.success());
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(stderr.contains("not found"), "stderr was: {stderr}");
}

#[test]
fn schema_default_emits_all_sheets_as_json() {
    let path = fixture("sample-financials.xlsx");
    let out = run(&["schema", path.to_str().unwrap()]);
    let v: serde_json::Value = serde_json::from_str(&out).expect("schema JSON parses");
    let sheets = v["sheets"].as_array().expect("sheets is array");
    assert_eq!(sheets.len(), 3, "default scopes to all sheets");
    let names: Vec<&str> = sheets.iter().map(|s| s["name"].as_str().unwrap()).collect();
    assert!(names.contains(&"P&L"));
    assert!(names.contains(&"Balance Sheet"));
    assert!(names.contains(&"Revenue Breakdown"));
}

#[test]
fn schema_revenue_breakdown_classifies_segment_as_categorical() {
    // The Segment column has 4 distinct values across the body rows
    // (Enterprise / Mid-Market / SMB / one more). With unique * 2 ≤ non_null
    // and unique ≤ 20 it should be classed as `categorical` — the bucket
    // an agent uses to recognize lookup-friendly dimensions.
    let path = fixture("sample-financials.xlsx");
    let out = run(&[
        "schema",
        path.to_str().unwrap(),
        "--sheet",
        "Revenue Breakdown",
    ]);
    let v: serde_json::Value = serde_json::from_str(&out).unwrap();
    let cols = v["sheets"][0]["columns"].as_array().unwrap();
    let segment = cols
        .iter()
        .find(|c| c["name"] == "Segment")
        .expect("Segment column present");
    assert_eq!(segment["type"], "string");
    assert_eq!(segment["cardinality"], "categorical");
    let samples = segment["samples"].as_array().unwrap();
    assert!(samples.len() <= 3, "samples capped at 3");
}

#[test]
fn schema_text_format_renders_table_with_header() {
    let path = fixture("sample-financials.xlsx");
    let out = run(&[
        "schema",
        path.to_str().unwrap(),
        "--sheet",
        "Revenue Breakdown",
        "--format",
        "text",
    ]);
    assert!(
        out.contains("Sheet: Revenue Breakdown"),
        "missing sheet header: {out}"
    );
    assert!(out.contains("column") && out.contains("type") && out.contains("cardinality"));
    assert!(out.contains("Customer"), "missing column row: {out}");
}

#[test]
fn schema_unknown_sheet_errors() {
    let path = fixture("sample-financials.xlsx");
    let out = Command::cargo_bin("wolfxl")
        .unwrap()
        .args(["schema", path.to_str().unwrap(), "--sheet", "Nope"])
        .output()
        .unwrap();
    assert!(!out.status.success());
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(stderr.contains("not found"), "stderr: {stderr}");
}

// ---- multi-format smoke tests (sprint-2 task #21) ----
//
// These don't lock goldens: xls/ods backends can return empty styles so the
// boxed renderer's column-width math can legitimately differ from xlsx/xlsb
// output, and CSV has no number formats to drive the styled path. The
// contract being tested is "Workbook::open dispatches and every CLI surface
// renders something sensible" - the per-format value/schema correctness is
// asserted in `wolfxl-core`'s integration tests.

struct MultiFormatCase {
    file: &'static str,
    peek_marker: &'static str,
    sheet_marker: &'static str,
}

fn multi_format_cases() -> [MultiFormatCase; 4] {
    [
        MultiFormatCase {
            file: "sample-minimal.csv",
            peek_marker: "Revenue",
            sheet_marker: "sample-minimal",
        },
        MultiFormatCase {
            file: "sample-minimal.xls",
            peek_marker: "Account",
            sheet_marker: "P&L",
        },
        MultiFormatCase {
            file: "sample-minimal.ods",
            peek_marker: "Account",
            sheet_marker: "P&L",
        },
        MultiFormatCase {
            // Fixture source: calamine's MIT-licensed `tests/date.xlsb`.
            file: "sample-date.xlsb",
            peek_marker: "2021-01-02",
            sheet_marker: "Sheet1",
        },
    ]
}

#[test]
fn peek_reads_csv_fixture() {
    let path = fixture("sample-minimal.csv");
    let out = run(&["peek", path.to_str().unwrap(), "-n", "3"]);
    assert!(out.contains("Account"), "missing CSV header: {out}");
    assert!(out.contains("Revenue"), "missing CSV data row: {out}");
    assert!(out.contains("│"), "expected boxed renderer output");
}

#[test]
fn peek_reads_xls_fixture() {
    let path = fixture("sample-minimal.xls");
    let out = run(&["peek", path.to_str().unwrap(), "-n", "3"]);
    assert!(out.contains("Account"), "missing xls header: {out}");
    assert!(out.contains("P&L"), "missing xls sheet name: {out}");
}

#[test]
fn peek_reads_ods_fixture() {
    let path = fixture("sample-minimal.ods");
    let out = run(&["peek", path.to_str().unwrap(), "-n", "3"]);
    assert!(out.contains("Account"), "missing ods header: {out}");
}

#[test]
fn schema_reads_csv_fixture() {
    let path = fixture("sample-minimal.csv");
    // `wolfxl schema file.csv` with no --sheet emits all-sheets JSON.
    // CSV exposes one synthetic sheet named after the filename stem.
    let out = run(&["schema", path.to_str().unwrap(), "--format", "json"]);
    assert!(
        out.contains("\"sample-minimal\""),
        "missing synthetic sheet name: {out}"
    );
    // Numeric columns (Jan/Feb/Mar/Q1) should classify as int via
    // schema-layer string parsing, per invariant B4. Account column
    // stays string.
    assert!(
        out.contains("\"type\": \"int\""),
        "expected int-classified columns: {out}"
    );
    assert!(
        out.contains("\"type\": \"string\""),
        "expected Account as string: {out}"
    );
}

#[test]
fn peek_reads_every_supported_fixture_shape() {
    for case in multi_format_cases() {
        let path = fixture(case.file);
        let out = run(&["peek", path.to_str().unwrap(), "-n", "3"]);
        assert!(
            out.contains(case.peek_marker),
            "peek missing marker {:?} for {}:\n{out}",
            case.peek_marker,
            case.file
        );
        assert!(out.contains("wolfxl peek"), "missing boxed banner: {out}");
    }
}

#[test]
fn map_reads_every_supported_fixture_shape() {
    for case in multi_format_cases() {
        let path = fixture(case.file);
        let out = run(&["map", path.to_str().unwrap(), "--format", "text"]);
        assert!(
            out.contains(case.sheet_marker),
            "map missing sheet marker {:?} for {}:\n{out}",
            case.sheet_marker,
            case.file
        );
        assert!(out.contains("sheets:"), "missing sheet count: {out}");
    }
}

#[test]
fn schema_reads_every_supported_fixture_shape() {
    for case in multi_format_cases() {
        let path = fixture(case.file);
        let out = run(&["schema", path.to_str().unwrap(), "--format", "json"]);
        let v: serde_json::Value = serde_json::from_str(&out)
            .unwrap_or_else(|e| panic!("schema JSON parses for {}: {e}\n{out}", case.file));
        let sheets = v["sheets"].as_array().expect("sheets is array");
        assert!(!sheets.is_empty(), "no schema sheets for {}", case.file);
        assert_eq!(sheets[0]["name"], case.sheet_marker);
        assert!(
            sheets[0]["columns"]
                .as_array()
                .is_some_and(|cols| !cols.is_empty()),
            "schema columns missing for {}:\n{out}",
            case.file
        );
    }
}

#[test]
fn agent_reads_every_supported_fixture_shape() {
    for case in multi_format_cases() {
        let path = fixture(case.file);
        let out = run(&["agent", path.to_str().unwrap(), "--max-tokens", "400"]);
        assert!(
            out.contains(&format!("WORKBOOK: {}", case.file)),
            "agent missing workbook name for {}:\n{out}",
            case.file
        );
        assert!(
            out.contains(&format!("SHEET: {}", case.sheet_marker)),
            "agent missing target sheet {:?} for {}:\n{out}",
            case.sheet_marker,
            case.file
        );
        assert!(
            out.contains("# wolfxl agent:"),
            "missing token footer: {out}"
        );
    }
}

#[test]
fn help_mentions_supported_input_formats() {
    for command in ["peek", "map", "schema", "agent"] {
        let out = run(&[command, "--help"]);
        for ext in [
            ".xlsx", ".xlsm", ".xls", ".xlsb", ".ods", ".csv", ".tsv", ".txt",
        ] {
            assert!(
                out.contains(ext),
                "{command} help missing {ext} support boundary:\n{out}"
            );
        }
    }
}
