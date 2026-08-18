# Rejected External-Oracle Sources

These workbooks are preserved for provenance, but they are not active
external-oracle fixtures because Microsoft Excel rejects them before any
WolfXL mutation.

- `apache-poi-table-validation-image-comment.xlsx`
- `exceljs-table-validation-image-comment.xlsx`

The active fixture pack replaces their table, data-validation, comment,
drawing, and image coverage with `openpyxl-table-validation-image-comment.xlsx`,
which passes Microsoft Excel open/save smoke.

Rechecked on 2026-05-08 with `scripts/run_ooxml_app_smoke.py` against the
source files: both rejected workbooks still failed Microsoft Excel app-smoke
before any WolfXL mutation, timing out while Excel attempted to open them.
