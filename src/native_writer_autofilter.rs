//! AutoFilter installation for the native writer backend.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use wolfxl_autofilter::evaluate::{evaluate, Cell as AfCell};
use wolfxl_writer::model::cell::{FormulaResult, WriteCellValue};
use wolfxl_writer::model::Worksheet;

/// Install autoFilter XML and row-hidden flags on a native writer worksheet.
pub(crate) fn install_autofilter(ws: &mut Worksheet, d: &Bound<'_, PyDict>) -> PyResult<()> {
    let dv = crate::wolfxl::autofilter::pyany_to_dictvalue(&d.as_any().clone())?;
    let af = wolfxl_autofilter::parse::parse_autofilter(&dv)
        .map_err(|e| PyValueError::new_err(format!("set_autofilter_native: {e}")))?;
    let bytes = wolfxl_autofilter::emit::emit(&af);
    ws.auto_filter_xml = if bytes.is_empty() { None } else { Some(bytes) };

    // Reset hidden flags from prior filter runs (the user may have
    // mutated the autofilter and re-flushed). We only clear hidden
    // flags on rows in the autofilter's data range to avoid
    // stomping on user-set `row.hidden` outside the filter scope.
    let Some(ref_str) = af.ref_.as_deref() else {
        return Ok(()); // no range -> nothing to evaluate
    };
    let Some((top_row, bot_row, left_col, right_col)) =
        crate::wolfxl::autofilter_helpers::parse_a1_range(ref_str)
    else {
        return Ok(()); // malformed -> emit XML only, no evaluation
    };

    // Header is the first row; data rows are top_row+1..=bot_row.
    if top_row >= bot_row {
        return Ok(());
    }
    let data_top = top_row + 1;
    for r in data_top..=bot_row {
        ws.rows.entry(r).or_default().hidden = false;
    }

    let grid = autofilter_grid(ws, data_top, bot_row, left_col, right_col);

    // Re-shift filter_columns col_id from autofilter-relative to absolute
    // is unnecessary: RFC-056 section 2.1 colId is already relative to the
    // autoFilter ref's leftmost column, which matches our grid layout.
    let result = evaluate(&grid, &af.filter_columns, af.sort_state.as_ref(), None);
    for hidden_idx in result.hidden_row_indices {
        let abs_row = data_top + hidden_idx;
        ws.rows.entry(abs_row).or_default().hidden = true;
    }
    Ok(())
}

fn autofilter_grid(
    ws: &Worksheet,
    data_top: u32,
    bot_row: u32,
    left_col: u32,
    right_col: u32,
) -> Vec<Vec<AfCell>> {
    let n_cols = (right_col - left_col + 1) as usize;
    let mut grid: Vec<Vec<AfCell>> = Vec::with_capacity((bot_row - data_top + 1) as usize);
    for r in data_top..=bot_row {
        let mut row_cells: Vec<AfCell> = vec![AfCell::Empty; n_cols];
        for col_1based in left_col..=right_col {
            let Some(wc) = ws.cell(r, col_1based) else {
                continue;
            };
            let idx = (col_1based - left_col) as usize;
            row_cells[idx] = write_cell_to_autofilter_cell(&wc.value);
        }
        grid.push(row_cells);
    }
    grid
}

fn write_cell_to_autofilter_cell(value: &WriteCellValue) -> AfCell {
    match value {
        WriteCellValue::Blank => AfCell::Empty,
        WriteCellValue::Number(n) => AfCell::Number(*n),
        WriteCellValue::String(s) => AfCell::String(s.clone()),
        WriteCellValue::Error(s) => AfCell::String(s.clone()),
        WriteCellValue::Boolean(b) => AfCell::Bool(*b),
        WriteCellValue::DateSerial(n) => AfCell::Date(*n),
        WriteCellValue::Formula { result, .. } => match result {
            Some(FormulaResult::Number(n)) => AfCell::Number(*n),
            Some(FormulaResult::String(s)) => AfCell::String(s.clone()),
            Some(FormulaResult::Boolean(b)) => AfCell::Bool(*b),
            _ => AfCell::Empty,
        },
        WriteCellValue::InlineRichText(runs) => {
            let text: String = runs.iter().map(|run| run.text.as_str()).collect();
            AfCell::String(text)
        }
        // RFC-057 array / data-table / spill-child cells: the evaluator only
        // filters on values, so treat these as empty for filter predicates.
        WriteCellValue::ArrayFormula { .. }
        | WriteCellValue::DataTableFormula { .. }
        | WriteCellValue::SpillChild => AfCell::Empty,
    }
}
