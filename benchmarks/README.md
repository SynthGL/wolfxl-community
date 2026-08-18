# Benchmarks

Reproducible WolfXL Community vs openpyxl benchmarks. Every number shown in the
repository README charts comes from a committed raw results file in
`results/`, and the charts are regenerated from that file, never edited by hand.

## What is measured

`benchmark_openpyxl_vs_wolfxl.py` runs matched workloads through the public
APIs of both libraries in the same process environment:

- plain, mixed-type, wide, formula, and styled row writes
- multi-sheet workbook writes
- full and read-only value reads, formula-text reads
- modify-two-cells-and-save on an existing workbook
- large-file variants (200,000 rows x 8 columns, about 1.6 million cells)
- a separate peak-RSS pass that runs each large case in a fresh process

Each case reports the median of the configured rounds. The results JSON embeds
the machine, Python, and package versions used for the run.

## Reproduce

```bash
python -m venv .bench && .bench/bin/pip install wolfxl==2.0.1 openpyxl==3.1.5
.bench/bin/python benchmarks/benchmark_openpyxl_vs_wolfxl.py \
    --rounds 5 \
    --output-dir /tmp/wolfxl-bench-results \
    --prefix my-run
```

Useful options: `--case <name>[,<name>...]` runs a subset, `--no-large` skips
the 200,000-row workloads, `--no-memory` skips the peak-RSS pass. Run with
`--help` for the full list.

## Regenerate the charts

```bash
python benchmarks/render_charts.py \
    benchmarks/results/2026-08-18-community-2.0.1-vs-openpyxl-3.1.5.json \
    assets/benchmarks
```

The renderer is deterministic and stdlib-only: the same input JSON always
produces byte-identical SVGs.

## Reading the results honestly

- Speedups vary by workload. Large streaming reads and writes are where the
  Rust backend helps most; small workbooks see smaller wins.
- The styled-rows case compares `ws.write_styled_rows()` against per-cell
  styling in openpyxl, which is an API-shape difference as well as an engine
  difference. The plain write cases use the same `append()`/row-iteration
  shapes in both libraries.
- On small workloads, peak memory is roughly equal between the two libraries;
  the memory chart shows the large-file cases where they diverge.
- Numbers are from the pinned versions, hardware, and OS recorded in the
  results JSON. Different machines will produce different absolute times.
