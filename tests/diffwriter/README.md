# Differential Writer Harness

Runs the native writer (`wolfxl-writer`) against the same build plan
across one structural and one semantic layer plus an opt-in LibreOffice
smoke. The legacy `rust_xlsxwriter` oracle was removed in W5; openpyxl
now serves as the soft secondary oracle for re-parse sanity checks.

## Layers

| Layer | What it checks | Gate |
|-------|---------------|------|
| 1 — semantic re-parse | openpyxl opens the native xlsx and iterates each sheet | ship gate |
| 2 — LibreOffice smoke | `soffice --headless --convert-to xlsx` round-trip | gold-star (≥95%), opt-in |

Byte-canonical and XML-tree comparisons against a committed golden
fixture are tracked as a follow-up RFC; the W5 rip-out commit ships
without them.

## Running

```bash
# All cases on the native writer
uv run pytest tests/diffwriter/
```

## Layer 2 — LibreOffice smoke

Layer 2 is **opt-in**. Without `WOLFXL_RUN_LIBREOFFICE_SMOKE=1` the
`tests/diffwriter/soffice_smoke.py` tests skip cleanly, so the suite is
harmless on machines that don't have LibreOffice installed.

Install LibreOffice locally:

```bash
brew install --cask libreoffice    # macOS
apt-get install libreoffice        # Linux
```

Run:

```bash
WOLFXL_RUN_LIBREOFFICE_SMOKE=1 uv run pytest tests/diffwriter/soffice_smoke.py -v
```

Acceptance gate is ≥95% pass rate across all hand-built cases (auto-discovered
via `_ALL_CASES` — 28 as of W4G) + 15 SynthGL fixtures (43 round-trips total).
A handful of expected failures goes in `_SOFFICE_XFAIL_CASES` in
`cases/__init__.py` so the layer remains green-by-default while documenting
known LO incompatibilities.

Layer 4 is gold-star: a failing case indicates an interop bug worth
chasing in a follow-up slice but does NOT block ship.

### First-run results (W4G — 2026-04-25)

| Metric | Value |
|--------|-------|
| LibreOffice version | 26.2.2.2 (Homebrew cask, macOS arm64) |
| Native cases | 28 / 28 pass |
| SynthGL fixtures | 15 / 15 pass |
| Total round-trips | **43 / 43 pass (100%)** |
| Wall-clock runtime | ~35 s (warm cache) |
| `_SOFFICE_XFAIL_CASES` | empty — no LO-side incompatibilities surfaced |

A clean first-run validates that the native writer's OOXML is interoperable
with an OOXML parser (LO) developed entirely independently of openpyxl,
calamine, and `rust_xlsxwriter`. Wave 5 rip-out is unblocked from this
gate.

## Module status

See `modules.toml` — the source of truth for which modules route to
native vs oracle, and which cases pass on each layer.

## Directory layout

```
tests/diffwriter/
  README.md               # this file
  __init__.py
  modules.toml            # per-module per-case status (source of truth)
  fuzzy_elements.json     # Layer-1 allowlist (timestamps etc.)
  order_rules.py          # Layer-2 child-sort rules
  cases/                  # hand-written test cases (one file per module)
  replay/                 # auto-generated from existing parity fixtures
  reports/                # generated HTML diff reports (gitignored)
```

## Wave status

- **Wave 0**: harness skeleton ✔
- **Wave 1**: foundations (model, refs, zip+container) — in progress
- **Wave 2**: emitters (styles, sheet, SST+workbook)
- **Wave 3**: rich features (comments+VML, tables, CF+DV)
- **Wave 4**: NativeWorkbook pyclass + DualWorkbook + harness wiring
- **Wave 5**: rip-out rust_xlsxwriter
