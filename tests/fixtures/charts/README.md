# Chart fixtures (Sprint Μ Pod-δ — RFC-046 §8)

One tiny xlsx per chart kind, created with **openpyxl**. They're the
golden reference files for wolfxl's chart parity tests in
`tests/parity/test_charts_parity.py`.

Files:

| File                                | Kind      | Notes                       |
| ----------------------------------- | --------- | --------------------------- |
| `bar_chart_simple.xlsx`             | Bar       | 2 series, categorical x     |
| `line_chart_with_trendline.xlsx`    | Line      | Plain line; trendline added at runtime |
| `pie_chart_with_legend.xlsx`        | Pie       | Single-series with legend   |
| `doughnut_chart_simple.xlsx`        | Doughnut  | holeSize default            |
| `area_chart_simple.xlsx`            | Area      | Stacked grouping            |
| `scatter_chart_simple.xlsx`         | Scatter   | scatterStyle=lineMarker     |
| `bubble_chart_simple.xlsx`          | Bubble    | Single bubble series        |
| `radar_chart_simple.xlsx`           | Radar     | radarStyle=marker           |

Each carries a fixed 6×3 data block (header + 5 rows × 2 numeric
columns) so the parity diff stays focused on chart-XML drift, not
cell-range noise.

## Regenerate

If openpyxl bumps a serialiser, fixtures may need to be rebuilt to
keep parity-diff baselines current. Run from the repo root:

```bash
python scripts/regenerate_chart_fixtures.py
```

The script writes idempotently — re-running with no openpyxl change
produces byte-identical output (modulo timestamps inside the docprops
part, which are zeroed by the script if WOLFXL_TEST_EPOCH is set; see
`scripts/regenerate_chart_fixtures.py`).

## Why are these committed?

Two reasons:

1. **Read-back regression** — wolfxl needs a sample chart-bearing xlsx
   to exercise modify-mode pass-through (Pod-γ).
2. **Parity baseline** — the structural-XML compare in
   `tests/parity/test_charts_parity.py` compares wolfxl's emit against
   *freshly-built* openpyxl output, but the committed fixtures serve as
   a fallback baseline when openpyxl is unavailable.

The fixtures are intentionally tiny (≤ ~5 KB each). If you find one is
larger, suspect a stray feature pickup and trim the `_build()` body in
the regeneration script.
