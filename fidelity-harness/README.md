# Round-trip fidelity harness

Open a workbook, change nothing, save it, then compare the two OOXML packages.

That operation gives each engine the easiest possible preservation task. No edit can justify a dropped package part, relationship, content type, or semantic feature fingerprint.

The grader is engine-neutral. `ooxml_fidelity.py` reads the before and after ZIP packages with the Python standard library. It never opens a workbook through WolfXL, openpyxl, Microsoft Excel, or LibreOffice.

## Reproduce the bundled comparison

From the repository root:

```bash
python3 -m venv .venv-fidelity
. .venv-fidelity/bin/activate
python -m pip install "wolfxl==2.0.1" "openpyxl==3.1.5" "Pillow>=10"

python fidelity-harness/corpus.py fidelity-harness/.artifacts/corpus
python fidelity-harness/roundtrip.py fidelity-harness/.artifacts/corpus \
  --json fidelity-harness/.artifacts/results.json \
  --markdown fidelity-harness/.artifacts/results.md
```

Pillow is required for a fair openpyxl comparison. Without it, openpyxl cannot read embedded images and will drop them during save.

The default engines are:

- `openpyxl`: full-DOM save with `keep_links=True`, `rich_text=True`, `data_only=False`, and `keep_vba=True` for macro-enabled files.
- `wolfxl-modify`: WolfXL's surgical `modify=True` save path.

The JSON report records engine versions, preservation settings, Python and platform details, SHA-256 hashes for every generated workbook, SHA-256 hashes for the harness implementation, every typed audit issue, and the warnings emitted by each engine.

Use `--fail-on-change` when any detected package difference should fail CI.

## Current result

The source-matched run in [`results/2026-08-18.json`](results/2026-08-18.json) compared openpyxl 3.1.5 with Pillow 12.3.0 against the public WolfXL 2.0.1 wheel on Python 3.13.9 arm64.

| Engine | Workbooks | Package semantics unchanged | Package changed | Parts lost | Relationships lost |
| --- | ---: | ---: | ---: | ---: | ---: |
| openpyxl 3.1.5 | 8 | 3 | 5 | 7 | 16 |
| WolfXL 2.0.1 modify mode | 8 | 8 | 0 | 0 | 0 |

Read the full [Markdown report](results/2026-08-18.md) and machine-readable JSON before drawing a conclusion. The aggregate combines two fixture tiers with different evidence strength.

## Corpus tiers

Every workbook is generated locally. No third-party workbook bytes are distributed.

### `openpyxl-authored`

These workbooks are created through openpyxl's public API. They cover styles, formulas, tables, structured references, data validation, conditional formatting, charts, comments, defined names, hyperlinks, page setup, and print settings.

### `synthetic-injection`

These workbooks start from an openpyxl-authored package, then receive package parts that openpyxl cannot author from scratch: pivot caches, slicers, timelines, VBA, custom XML, and embedded media.

The injected parts are intentionally minimal. They are labelled synthetic in the manifest and report. Their result is evidence about package-part and relationship retention. It is not evidence that the fixture matches every detail of an Excel-authored workbook, and it must not be presented as Excel application round-trip proof.

`corpus.py` validates ZIP integrity, XML well-formedness, expected parts, content types, and relationship targets. The checked-in run also opened every generated fixture in headless LibreOffice. Microsoft Excel was not used.

The generator normalizes core-property and ZIP timestamps. Two clean runs produce byte-identical workbook files and therefore identical input hashes.

## Run it on your files

Point the runner at any directory containing `.xlsx`, `.xlsm`, `.xltx`, `.xltm`, or `.xlsb` files:

```bash
python fidelity-harness/roundtrip.py /path/to/workbooks \
  --engine openpyxl \
  --engine wolfxl-modify \
  --json results.json \
  --markdown results.md
```

The runner works on temporary copies. It does not modify the input directory.

## Add another engine

Create a Python module with a zero-argument factory that returns `engines.Engine`:

```python
from pathlib import Path

from engines import Engine


def build() -> Engine:
    import another_library

    def round_trip(source: Path, target: Path) -> None:
        workbook = another_library.load(source)
        workbook.save(target)

    return Engine(
        name="another-library",
        version=another_library.__version__,
        round_trip=round_trip,
        notes="Describe the exact save path and every preservation setting.",
        settings={"preserve_unknown_parts": True},
    )
```

Run it by module path:

```bash
PYTHONPATH=/path/to/adapter \
python fidelity-harness/roundtrip.py fidelity-harness/.artifacts/corpus \
  --engine my_adapter:build
```

A useful adapter must use the engine's strongest documented preservation settings and disclose them in `settings`. If an optional dependency affects fidelity, require it rather than publishing a weaker strawman configuration.

## Interpret results carefully

- `faithful` means this comparator found no package-level or semantic difference for that workbook and operation.
- `changed` means at least one typed issue was detected. Inspect `issues`, `issues_by_kind`, and the exact part lists in JSON.
- `unsupported` means the engine refused to open the workbook. It is kept separate from data loss.
- Part counts alone are insufficient. An engine can keep a part while removing the relationship that makes it reachable.
- A clean no-op result does not prove that later edits preserve the same features. Mutation testing is a separate claim.
- A generated corpus does not replace evaluation on representative production workbooks.

## Files

| File | Purpose |
| --- | --- |
| `corpus.py` | Deterministic fixture generator and structural validator |
| `engines.py` | Built-in adapters and third-party adapter loader |
| `roundtrip.py` | Corpus runner and JSON/Markdown report generator |
| `ooxml_fidelity.py` | Engine-neutral OOXML package and semantic comparator |
| `tests/` | Focused regression tests for measurement integrity and cleanup safety |
| `results/` | Compact source-matched result artifacts; generated workbooks are not committed |

## License

This harness is MIT licensed under SynthGL, Inc. See [`LICENSE`](LICENSE).
