//! `wolfxl map <file>` — workbook overview for agent orientation.
//!
//! Emits one record per sheet (name, dims, class, headers, anchored
//! tables) plus workbook-level defined names. Two output formats:
//!
//! - `json` (default): machine-parseable, single-pass deserializable
//! - `text`: terminal-friendly, sectioned per sheet

use std::path::PathBuf;

use anyhow::{Context, Result};
use serde_json::{json, Value};
use wolfxl_core::{Workbook, WorkbookMap};

use crate::MapFormat;

pub fn run(file: PathBuf, format: MapFormat) -> Result<()> {
    let mut wb =
        Workbook::open(&file).with_context(|| format!("opening workbook {}", file.display()))?;
    let map = wb
        .map()
        .with_context(|| format!("building map for {}", file.display()))?;

    match format {
        MapFormat::Json => print_json(&map)?,
        MapFormat::Text => print_text(&map),
    }
    Ok(())
}

fn print_json(map: &WorkbookMap) -> Result<()> {
    let value = json!({
        "path": map.path,
        "sheets": map.sheets.iter().map(|s| json!({
            "name": s.name,
            "rows": s.rows,
            "cols": s.cols,
            "class": s.class.as_str(),
            "headers": s.headers,
            "tables": s.tables,
        })).collect::<Vec<Value>>(),
        "named_ranges": map.named_ranges.iter().map(|(n, f)| json!({
            "name": n,
            "formula": f,
        })).collect::<Vec<Value>>(),
    });
    println!("{}", serde_json::to_string_pretty(&value)?);
    Ok(())
}

fn print_text(map: &WorkbookMap) {
    println!("workbook: {}", map.path);
    println!("sheets:   {}", map.sheets.len());
    if !map.named_ranges.is_empty() {
        println!("named ranges: {}", map.named_ranges.len());
    }
    println!();
    for s in &map.sheets {
        println!(
            "[{}] {}  ({} rows × {} cols)",
            s.class.as_str(),
            s.name,
            s.rows,
            s.cols
        );
        if !s.headers.is_empty() {
            // Truncate header preview at 8 columns to keep the per-sheet
            // block short. A wide-table dump in a `map` view is noise —
            // use `peek` for the full width.
            let preview: Vec<String> = s
                .headers
                .iter()
                .take(8)
                .map(|h| {
                    if h.is_empty() {
                        "∅".to_string()
                    } else {
                        h.clone()
                    }
                })
                .collect();
            let suffix = if s.headers.len() > 8 {
                format!("  … (+{} more)", s.headers.len() - 8)
            } else {
                String::new()
            };
            println!("  headers: {}{}", preview.join(" | "), suffix);
        }
        if !s.tables.is_empty() {
            println!("  tables:  {}", s.tables.join(", "));
        }
        println!();
    }
    if !map.named_ranges.is_empty() {
        println!("named ranges:");
        for (name, formula) in &map.named_ranges {
            println!("  {} = {}", name, formula);
        }
    }
}
