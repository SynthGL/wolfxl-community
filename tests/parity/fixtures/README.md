# Parity fixture corpora

This directory seeds the WolfXL parity harness with representative xlsx/xlsb/xls
files. Two orthogonal things matter:

1. **Breadth** — every archetype SynthGL actually ingests must be represented.
2. **Stability** — fixtures are committed (not generated) so parity diffs are
   reproducible across machines and across upstream openpyxl/wolfxl versions.

## Layout

```
fixtures/
├── synthgl_snapshot/   # ~15 xlsx copied from SynthGL's ingestion tests
│   ├── aging/          # AR/AP aging-bucket workbooks
│   ├── flat_register/  # AP / AR / GL transaction registers
│   ├── rollforward/    # Budget, fixed-asset movements
│   ├── time_series/    # Quarterly/SEC/PE reporting
│   ├── cross_ref/      # Buried-header entity rollups
│   ├── key_value/      # Report metadata blocks
│   └── stress/         # Archetype-confusion cases
├── xls/                # Sprint Κ — legacy BIFF8 (5 fixtures via LibreOffice)
└── xlsb/               # Sprint Κ — binary Excel (5 fixtures vendored from calamine)
```

Large/messy corpora (ExcelBench tier2/3) stay in the ExcelBench repo — the
ExcelBench CI job provides breadth; this corpus provides SynthGL-shape
specificity.

## Updating the snapshot

When SynthGL adds new archetypes:

```bash
# From wolfxl repo root, refresh against SynthGL's current fixtures.
SYNTHGL="$HOME/Projects/SynthGL"
for category in aging flat_register rollforward time_series cross_ref key_value stress; do
  dst="tests/parity/fixtures/synthgl_snapshot/$category"
  mkdir -p "$dst"
  # pick 3 representative fixtures per category
  ls "$SYNTHGL/tests/app/fixtures/ingestion/$category"/*.xlsx 2>/dev/null | head -3 | xargs -I {} cp {} "$dst/"
done
```

Then re-run the harness and commit any ratchet.json updates.

## Env-var alternative

Set `SYNTHGL_FIXTURES=/path/to/SynthGL/tests/app/fixtures/ingestion` to run
the harness against the live corpus without copying. CI uses the committed
snapshot; local dev can run against live. See `conftest.py`.
