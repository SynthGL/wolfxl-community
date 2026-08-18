//! `wolfxl schema <file>` — per-column type/cardinality/format inference.
//!
//! Defaults to JSON for agent consumption; `--format text` produces a
//! terminal-friendly tabular view. Omit `--sheet` to schema every sheet
//! in the workbook; pass it to scope to one sheet.
//!
//! The heuristics live in `wolfxl_core::schema` so third-party Rust
//! callers (and the future Python binding) get the same answers as the
//! CLI; this module is pure rendering.

use std::path::PathBuf;

use anyhow::{Context, Result};
use serde_json::{json, Value};
use unicode_width::UnicodeWidthStr;
use wolfxl_core::{infer_sheet_schema, SheetSchema, Workbook};

use crate::SchemaFormat;

pub fn run(file: PathBuf, format: SchemaFormat, sheet: Option<String>) -> Result<()> {
    let mut wb =
        Workbook::open(&file).with_context(|| format!("opening workbook {}", file.display()))?;

    let sheet_names: Vec<String> = wb.sheet_names().to_vec();
    let targets: Vec<String> = match sheet {
        Some(name) => {
            if !sheet_names.iter().any(|n| n == &name) {
                anyhow::bail!(
                    "sheet {name:?} not found; available: {}",
                    sheet_names.join(", ")
                );
            }
            vec![name]
        }
        None => sheet_names.clone(),
    };

    let mut schemas: Vec<SheetSchema> = Vec::with_capacity(targets.len());
    for name in &targets {
        let s = wb
            .sheet(name)
            .with_context(|| format!("loading sheet {name:?}"))?;
        schemas.push(infer_sheet_schema(&s));
    }

    match format {
        SchemaFormat::Json => print_json(&file, &schemas)?,
        SchemaFormat::Text => print_text(&schemas),
    }
    Ok(())
}

fn print_json(file: &std::path::Path, schemas: &[SheetSchema]) -> Result<()> {
    let value = json!({
        "path": file.to_string_lossy(),
        "sheets": schemas.iter().map(sheet_to_json).collect::<Vec<Value>>(),
    });
    println!("{}", serde_json::to_string_pretty(&value)?);
    Ok(())
}

fn sheet_to_json(s: &SheetSchema) -> Value {
    json!({
        "name": s.sheet,
        "rows": s.rows,
        "columns": s.columns.iter().map(|c| json!({
            "name": c.name,
            "type": c.inferred_type.as_str(),
            "format": c.format_category.as_str(),
            "null_count": c.null_count,
            "unique_count": c.unique_count,
            "unique_capped": c.unique_capped,
            "cardinality": c.cardinality.as_str(),
            "samples": c.sample_values,
        })).collect::<Vec<Value>>(),
    })
}

fn print_text(schemas: &[SheetSchema]) {
    for (i, s) in schemas.iter().enumerate() {
        if i > 0 {
            println!();
        }
        println!("Sheet: {}  ({} rows)", s.sheet, s.rows);
        println!(
            "{:<24} {:<9} {:<11} {:<7} {:<7} {:<16} samples",
            "column", "type", "format", "nulls", "unique", "cardinality"
        );
        println!("{}", "-".repeat(96));
        for c in &s.columns {
            let unique = if c.unique_capped {
                format!("{}+", c.unique_count)
            } else {
                c.unique_count.to_string()
            };
            // Rendered samples can contain commas — join with `|` so a
            // copy-paste back into the shell or a CSV stays unambiguous.
            let samples = c.sample_values.join(" | ");
            println!(
                "{:<24} {:<9} {:<11} {:<7} {:<7} {:<16} {}",
                truncate(&c.name, 24),
                c.inferred_type.as_str(),
                c.format_category.as_str(),
                c.null_count,
                unique,
                c.cardinality.as_str(),
                truncate(&samples, 40),
            );
        }
    }
}

/// Truncate `s` so its terminal display width fits in `max` columns,
/// appending `…` (1-wide) when truncation happens. Uses unicode-width to
/// match the column-alignment behavior of `wolfxl peek`'s boxed renderer
/// — `chars().count()` would misalign on CJK / wide glyphs.
fn truncate(s: &str, max: usize) -> String {
    if s.width() <= max {
        return s.to_string();
    }
    let budget = max.saturating_sub(1); // reserve 1 column for the ellipsis
    let mut out = String::new();
    let mut used = 0usize;
    for ch in s.chars() {
        let w = ch.to_string().width();
        if used + w > budget {
            break;
        }
        out.push(ch);
        used += w;
    }
    out.push('…');
    out
}
