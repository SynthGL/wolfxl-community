# wolfxl-formula

A1-syntax Excel formula tokenizer and reference translator.

Pure Rust, no PyO3. Used by both the wolfxl modify-mode patcher and the
native writer.

Implements RFC-012 — `Plans/rfcs/012-formula-xlator.md`.

## Public API

```rust
use wolfxl_formula::{shift, rename_sheet, move_range, ShiftPlan, Axis, Range};

// Insert 3 rows starting at row 5 (every ref with row >= 5 shifts down 3)
let f = "=SUM($A$5:B10)+Sheet2!C7";
let out = shift(f, &ShiftPlan {
    axis: Axis::Row, at: 5, n: 3,
    respect_dollar: false, // BLOCKER: see below
});

// Rename a sheet referenced from elsewhere
let out = rename_sheet("=Forecast!B5", "Forecast", "Forecast_v2");

// Re-anchor refs that point INTO `src` to point INTO `dst`
let src = Range { min_row: 5, max_row: 7, min_col: 2, max_col: 3 };
let dst = Range { min_row: 10, max_row: 12, min_col: 5, max_col: 6 };
let out = move_range("=B5+Z99", &src, &dst, true);
```

For richer control (deleted-range tombstones, sheet-scoped tombstones,
combined shift + rename), use the lower-level `translate` /
`translate_with_meta` functions and construct a `RefDelta` directly.

## ⚠️ Open Question — `respect_dollar` (BLOCKER)

Per RFC-012 §5.5 and `Plans/rfcs/INDEX.md` open question #3, **the
default value of `respect_dollar` for row/col-shift operations
(`shift`) has not yet been verified in Excel.** The 5-minute
verification doc at `Plans/rfcs/notes/excel-respect-dollar-check.md`
must be run before:

- a `Default` impl is added for `ShiftPlan`;
- `RefDelta::respect_dollar` gets a documented default;
- RFC-030 (`insert_rows` / `delete_rows`) and RFC-031
  (`insert_cols` / `delete_cols`) wire the patcher path.

Until then the field is **required** at every call site so that callers
make an informed decision.

The two possible semantics:

- `respect_dollar = false` (current spec assumption — coordinate-remap):
  every reference whose row/col is `>= at` shifts by `n`, regardless of
  whether the source had `$` markers. Matches the assumption that
  insert-row is a coordinate-space remap.
- `respect_dollar = true` (Excel paste-style): `$`-marked rows/cols are
  pinned and do NOT shift. Other references shift normally.

`move_range` always uses `respect_dollar = true` (paste-style), which
is correct independent of the open question because move-range only
re-anchors references that point INTO the moved rectangle.

## Out-of-scope (passes through verbatim)

- External-workbook references: `[Book2.xlsx]Sheet1!A1`,
  `'C:\path\[Book2.xlsx]Sheet1'!A1`.
- Structured table references: `Table1[Col1]`, `Table1[#Headers]`,
  `Table1[[#This Row], [Col1]]`. (Table-rename is RFC-024-Y2.)
- Defined-name references: `=MyTotal`. (RFC-021 handles
  defined-name rescoping; this crate is invoked by RFC-021 to rewrite
  the formula text inside a `<definedName>` element.)
- Shared-formula expansion (RFC-021).
- Array-formula `<f t="array" ref="...">` `ref` attribute updates
  (RFC-030 owns).

## Verification

```bash
cargo test -p wolfxl-formula --quiet
```

Should report >=80 unit tests passing, including:

- `t01..t40` — every reference syntax in §2.
- `t41_synthgl_corpus_round_trip` — identity translation is byte-
  identical for >=100 formulas drawn from
  `tests/parity/fixtures/synthgl_snapshot/` and `tests/fixtures/`.
- `t42_perf_100k_formulas_under_1s` — 100k complex-formula translations
  finish in <1s on M1 / Ryzen 5000 hardware.
