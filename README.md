# WolfXL Community

MIT-licensed, openpyxl-compatible Excel I/O backed by Rust.

WolfXL Community is the maintained 2.0 generation of WolfXL. It is intended for
local workbook creation, reading, writing, streaming exports, and workloads that
fit the documented 2.0 API.

## Community and Commercial

| | WolfXL Community | WolfXL Commercial |
|---|---|---|
| License | MIT | Commercial |
| Release line | Maintained 2.0 generation | Current 2.1+ generation |
| Workbook I/O | Included | Included |
| Existing 2.0 modify and pivot APIs | Included | Current implementations and fixes |
| Native recalculation | Not included | Included |
| Render, PDF, and image output | Not included | Included |
| Format conversion | Not included | Included |
| VBA and Power Query operations | Not included | Included |
| Production operations SDK | Not included | Included |
| Direct support | Community issues | Included with paid plans |

Community receives critical correctness and security fixes. New engines,
expanded compatibility work, production operations, and direct support ship in
[WolfXL Commercial](https://wolfxl.com).

This split keeps the useful Excel I/O layer open while funding the compatibility,
fidelity, and support work required by production workbook pipelines.

## Install

Install the current Community release with:

```bash
python -m pip install wolfxl==2.0.1
```

WolfXL Community supports Python 3.9 and newer CPython versions for which a wheel
is published.

## Quick start

```python
from wolfxl import Alignment, Font, PatternFill, Workbook, load_workbook

workbook = Workbook()
sheet = workbook.active
sheet.title = "Summary"
sheet["A1"] = "Revenue"
sheet["A1"].font = Font(bold=True, color="FFFFFF")
sheet["A1"].fill = PatternFill(fill_type="solid", fgColor="336699")
sheet["B1"] = 125000
sheet["B1"].alignment = Alignment(horizontal="right")
workbook.save("report.xlsx")

loaded = load_workbook("report.xlsx")
print(loaded["Summary"]["B1"].value)
loaded.close()
```

Most openpyxl-shaped code needs only an import change:

```diff
- from openpyxl import Workbook, load_workbook
+ from wolfxl import Workbook, load_workbook
```

For applications that cannot change every import, install the runtime alias once
at process startup:

```python
import wolfxl

wolfxl.install_as_openpyxl()

import openpyxl
```

## Performance

Median speedups over openpyxl 3.1.5, from the committed benchmark run
(wolfxl 2.0.1 PyPI wheel, Apple M4 Pro, Python 3.13.9, median of 5 rounds):

![WolfXL Community vs openpyxl: median speedup](assets/benchmarks/speedup-vs-openpyxl.svg)

![1.6 million cells: wall-clock seconds](assets/benchmarks/large-file-seconds.svg)

![1.6 million cells: peak memory](assets/benchmarks/large-file-memory.svg)

### Against other open-source Python Excel libraries

Cross-library comparison on a separate machine (AMD EPYC 9655, x86_64 Linux,
Python 3.13, median of 5 rounds) against twelve other libraries: openpyxl,
XlsxWriter, PyExcelerate, pylightxl, pandas, Polars, DuckDB, Tablib, pyexcel,
python-calamine, fastexcel, and xlsx2csv. The bar for inclusion is xlsx
support, no external application, and roughly one million PyPI downloads per
month. Each library is measured only inside its supported scope; write-only,
read-only, DataFrame, and SQL specialists are labeled:

![Write 200,000 x 8 plain values](assets/benchmarks/ecosystem-write-large.svg)

![Write 10,000 x 5 mixed types](assets/benchmarks/ecosystem-write-mixed.svg)

![Write 100,000 x 5 unique strings](assets/benchmarks/ecosystem-write-strings.svg)

![Read 200,000 x 8, all values](assets/benchmarks/ecosystem-read-large.svg)

![Peak memory: write 200,000 x 8](assets/benchmarks/ecosystem-memory-write.svg)

![Peak memory: read 200,000 x 8](assets/benchmarks/ecosystem-memory-read.svg)

wolfxl leads every case in this run, including reads (387 ms vs 394 ms for
Polars and 403 ms for fastexcel, which return Arrow-backed tables rather than
Python cell values). The closest overall rival is DuckDB's excel extension,
which wins the small mixed-type write outright (25 ms vs 35 ms, timed from a
registered DataFrame) and stays within 1.4x elsewhere. pyexcel and
PyExcelerate have the lowest write peak memory; pylightxl's pure-Python writer
scales quadratically (241 s on the large plain write, 1,438 s on unique
strings) and its bars are clipped to keep the charts readable.

Speedups vary by workload, and small workbooks see smaller wins. Raw results,
the benchmark harnesses, and reproduction instructions are in
[`benchmarks/`](benchmarks/README.md). All charts are generated from the
committed results JSON files, never edited by hand.

## Fidelity

The [round-trip fidelity harness](fidelity-harness/README.md) compares workbook
packages before and after a no-edit save. Run it on your own files, inspect the
typed part and relationship differences, and add another engine through the
documented adapter protocol.

## Development

Prerequisites: a supported CPython, Rust, and `maturin`.

```bash
python -m pip install maturin pytest defusedxml openpyxl Pillow
maturin develop
pytest tests/test_community_distribution.py -q
```

The distribution-boundary test verifies the Community version, compiled
backends, and absence of Commercial-only Python modules.

## Commercial capabilities

Use [wolfxl.com](https://wolfxl.com) for the current Commercial package,
evaluation access, pricing, compatibility information, and support. Commercial
source and releases are maintained separately and are not part of this
repository.

## License

WolfXL Community is available under the [MIT License](LICENSE).
