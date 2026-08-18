# Benchmarks

Reproducible benchmarks for WolfXL Community. Every number shown in the
repository README charts comes from a committed raw results file in
`results/`, and the charts are regenerated from that file, never edited by hand.

Two harnesses:

- `benchmark_openpyxl_vs_wolfxl.py`: deep openpyxl comparison (writes, reads,
  modify-and-save, styled rows, multi-sheet, peak memory).
- `benchmark_python_excel_ecosystem.py`: cross-library comparison against
  other open-source Python Excel libraries, each measured only inside its
  supported scope.

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

## Ecosystem comparison

`benchmark_python_excel_ecosystem.py` compares, in one environment:

| Library | Scope |
|---|---|
| wolfxl | full read/write |
| openpyxl | full read/write (baseline) |
| XlsxWriter | write-only |
| PyExcelerate | write-only |
| python-calamine | read-only, returns Python values |
| fastexcel | read-only, returns Arrow tables |

Write-only libraries appear only in write cases and read-only libraries only
in read cases. The read fixture is written by openpyxl so no reader parses its
own writer's output.

```bash
.bench/bin/pip install wolfxl==2.0.1 openpyxl==3.1.5 xlsxwriter pyexcelerate \
    python-calamine fastexcel pyarrow
.bench/bin/python benchmarks/benchmark_python_excel_ecosystem.py \
    --rounds 5 --output-dir /tmp/ecosystem-results --prefix my-run
```

## Regenerate the charts

```bash
python benchmarks/render_charts.py \
    benchmarks/results/2026-08-18-community-2.0.1-vs-openpyxl-3.1.5.json \
    assets/benchmarks
python benchmarks/render_ecosystem_charts.py \
    benchmarks/results/2026-08-18-ecosystem-linux-epyc.json \
    assets/benchmarks
```

Both renderers are deterministic and stdlib-only: the same input JSON always
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
- In the ecosystem read case, fastexcel is slightly faster than wolfxl but
  returns Arrow tables; wolfxl and python-calamine return Python cell values,
  and only wolfxl and openpyxl can also write.
- PyExcelerate serializes floats with fewer significant digits than the other
  writers, so its speed comes with a round-trip precision difference.
- Numbers are from the pinned versions, hardware, and OS recorded in the
  results JSON. Different machines will produce different absolute times.
