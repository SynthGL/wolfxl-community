use anyhow::{Context, Result};
use wolfxl_core::Workbook;

use crate::render::{self, RenderOptions};
use crate::{ExportFormat, PeekArgs};

pub fn run(args: PeekArgs) -> Result<()> {
    let mut wb = Workbook::open(&args.file)
        .with_context(|| format!("opening workbook: {}", args.file.display()))?;

    let sheet_names: Vec<String> = wb.sheet_names().to_vec();
    let target = match &args.sheet {
        Some(name) => {
            if !sheet_names.iter().any(|n| n == name) {
                anyhow::bail!(
                    "sheet {name:?} not found; available: {}",
                    sheet_names.join(", ")
                );
            }
            name.clone()
        }
        None => sheet_names
            .first()
            .cloned()
            .ok_or_else(|| anyhow::anyhow!("workbook has no sheets"))?,
    };

    let sheet = wb
        .sheet(&target)
        .with_context(|| format!("loading sheet {target:?}"))?;

    let opts = RenderOptions {
        max_rows: if args.max_rows == 0 {
            None
        } else {
            Some(args.max_rows)
        },
        max_width: args.max_width.max(3),
        all_sheets: &sheet_names,
    };

    let mut out = std::io::stdout().lock();
    match args.export {
        Some(ExportFormat::Csv) => render::csv(&mut out, &sheet, &opts)?,
        Some(ExportFormat::Json) => render::json(&mut out, &sheet, &opts)?,
        Some(ExportFormat::Markdown) => render::markdown(&mut out, &sheet, &opts)?,
        Some(ExportFormat::Text) => render::text(&mut out, &sheet, &opts)?,
        Some(ExportFormat::Box) | None => render::boxed(&mut out, &sheet, &opts)?,
    }
    Ok(())
}
