# wolfxl-pivot

OOXML pivot-cache and pivot-table model + emit, pure Rust, no PyO3.

Used by both:

- the wolfxl patcher (modify mode) via `serialize_pivot_cache_dict`
  / `serialize_pivot_records_dict` / `serialize_pivot_table_dict`
  PyO3 bindings in `src/wolfxl/`;
- the native writer (write mode) via
  `crates/wolfxl-writer/src/emit/pivot_*.rs`.

## Sprint Ν status

This crate is the foundation for v2.0.0 pivot-table construction
(Sprint Ν). It is currently **scaffolded** — the §10 contract
types from RFC-047 / RFC-048 / RFC-049 are pinned, the emit
functions emit minimally-valid OOXML, and round-trip parity tests
will land via the parallel pods.

See:
- `Plans/sprint-nu.md` — sprint plan
- `Plans/rfcs/047-pivot-caches.md` — pivot-cache contract (§10)
- `Plans/rfcs/048-pivot-tables.md` — pivot-table contract (§10)
- `Plans/rfcs/049-pivot-charts.md` — chart linkage (§10)

## Modules

```
wolfxl-pivot
├── model        — typed OOXML pivot model
│   ├── cache    — PivotCache, CacheField, SharedItems, CacheValue
│   ├── records  — CacheRecord, RecordCell
│   └── table    — PivotTable, PivotField, DataField, AxisItem
├── emit         — XML emitters
│   ├── cache    — pivot_cache_definition_xml
│   ├── records  — pivot_cache_records_xml
│   └── table    — pivot_table_xml
└── parse        — internal: dict → model converters (PyO3-free here;
                   PyO3 layer in src/wolfxl/ wraps these)
```

## Determinism

All emitters write deterministic byte-stable output for a given
input model — required for `WOLFXL_TEST_EPOCH=0` golden tests.
Attribute order is fixed; child element order matches OOXML
schema. No timestamps, no random ids.
