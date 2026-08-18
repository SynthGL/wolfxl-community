# `.xlsb` parity fixtures (Sprint Κ Pod-γ)

Five committed `.xlsb` files plus JSON sidecars used by
`tests/parity/test_xlsb_reads.py` to assert native BIFF12 reads match the
dependency-free golden values.

| File              | Source                          | Notes                              |
|-------------------|---------------------------------|------------------------------------|
| `numbers.xlsb`    | calamine `tests/issue_419.xlsb` | numeric values                     |
| `strings.xlsb`    | calamine `tests/issue_186.xlsb` | string content                     |
| `dates.xlsb`      | calamine `tests/date.xlsb`      | dates / datetimes / time-deltas    |
| `formulas.xlsb`   | calamine `tests/issue127.xlsb`  | multi-sheet, mixed types           |
| `multisheet.xlsb` | calamine `tests/any_sheets.xlsb`| visible / hidden / very-hidden     |

Additional long-tail fixtures live under `excelgen/`. They are tested by
targeted assertions instead of full value sidecars because some sheets are
large visual feature matrices:

| File                                           | Source sample                         | Notes                                  |
|------------------------------------------------|---------------------------------------|----------------------------------------|
| `excelgen/data-validations-and-tables.xlsb`    | ExcelGen `samples/test-dataval.xlsb`  | data validations and table parts       |
| `excelgen/conditional-formatting.xlsb`         | ExcelGen `samples/cond-formatting.xlsb` | conditional-formatting record coverage |
| `excelgen/merged-cells.xlsb`                   | ExcelGen `samples/merged-cells.xlsb`  | merged range coverage                  |
| `excelgen/style-showcase.xlsb`                 | ExcelGen `samples/style-showcase.xlsb` | table styles, merges, style matrices   |
| `excelgen/image-drawing.xlsb`                  | ExcelGen `samples/test-image-2.xlsb`  | drawing relationship and image payload |
| `excelgen/formulas-and-names.xlsb`             | ExcelGen `samples/test-formula.xlsb`  | shared formulas and defined-name refs  |
| `excelgen/links-and-hyperlink-formulas.xlsb`   | ExcelGen `samples/test-links.xlsb`    | HYPERLINK formulas and relative refs    |
| `excelgen/lookup-formulas-and-table.xlsb`      | ExcelGen `samples/test-image-1.xlsb`  | VLOOKUP/INDIRECT formulas and table     |

## License & attribution

These fixtures are vendored from upstream
[`tafia/calamine`](https://github.com/tafia/calamine), MIT License,
Copyright © 2016 Johann Tuffe. The MIT license text is reproduced upstream.
We keep them committed so CI runners don't need network access to validate
parity.

The `excelgen/` fixtures are vendored from upstream
[`mbleron/ExcelGen`](https://github.com/mbleron/ExcelGen), MIT License,
Copyright © 2020-2024 Marc Bleron.

## Why vendored, not generated?

LibreOffice 26.x exposes filter names like `Calc MS Excel 2007 Binary` and
`Calc Office Open XML Binary`, but the actual export call returns
`Error Area:Io Class:Parameter Code:26`. Neither `openpyxl` nor `xlsxwriter`
write `.xlsb`. Producing a real `.xlsb` requires either Excel itself or a
commercial library (Aspose). Vendoring real-world `.xlsb` fixtures from
calamine's MIT-licensed corpus is the canonical workaround, and matches
the read-only nature of wolfxl's `.xlsb` support.

## Refreshing the corpus

```bash
git clone https://github.com/tafia/calamine.git /tmp/calamine
git clone https://github.com/mbleron/ExcelGen.git /tmp/ExcelGen
python3 scripts/sprint_kappa_build_fixtures.py /tmp/calamine /tmp/ExcelGen
```

The script copies five calamine `tests/*.xlsb` files into this directory and,
when the ExcelGen path is passed, the ExcelGen samples into `excelgen/`
under stable wolfxl-side names (see the tables above).
