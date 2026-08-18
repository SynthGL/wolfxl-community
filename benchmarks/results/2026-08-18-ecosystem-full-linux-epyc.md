# Python Excel ecosystem benchmark

AMD EPYC 9655 96-Core Processor | Python 3.13.15 | median of 5 rounds

## write_plain_large

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 0.7258 | 2,204,332 |
| openpyxl | full read/write | 8.0567 | 198,593 |
| xlsxwriter | write-only | 4.6858 | 341,458 |
| pyexcelerate | write-only | 3.6387 | 439,722 |
| pylightxl | pure-Python read/write | 241.0861 | 6,637 |
| pandas_openpyxl | DataFrame I/O, openpyxl engine | 10.4210 | 153,537 |
| polars | DataFrame I/O, wraps XlsxWriter/fastexcel | 6.1348 | 260,808 |
| duckdb | SQL engine; DataFrame in, Arrow out | 0.9743 | 1,642,135 |
| tablib | Dataset wrapper, openpyxl backend | 11.1541 | 143,444 |
| pyexcel | wrapper, openpyxl backend | 6.4000 | 250,000 |

## write_mixed

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 0.0345 | 1,449,799 |
| openpyxl | full read/write | 0.2441 | 204,828 |
| xlsxwriter | write-only | 0.1392 | 359,086 |
| pyexcelerate | write-only | 0.1200 | 416,550 |
| pandas_openpyxl | DataFrame I/O, openpyxl engine | 0.3366 | 148,540 |
| polars | DataFrame I/O, wraps XlsxWriter/fastexcel | 0.2664 | 187,682 |
| duckdb | SQL engine; DataFrame in, Arrow out | 0.0254 | 1,967,280 |
| tablib | Dataset wrapper, openpyxl backend | 0.4503 | 111,043 |
| pyexcel | wrapper, openpyxl backend | 0.2454 | 203,724 |

## write_unique_strings

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 0.3091 | 1,617,787 |
| openpyxl | full read/write | 3.1452 | 158,971 |
| xlsxwriter | write-only | 2.1100 | 236,964 |
| pyexcelerate | write-only | 1.3407 | 372,940 |
| pylightxl | pure-Python read/write | 1437.6584 | 348 |
| pandas_openpyxl | DataFrame I/O, openpyxl engine | 4.1893 | 119,351 |
| polars | DataFrame I/O, wraps XlsxWriter/fastexcel | 2.4738 | 202,119 |
| duckdb | SQL engine; DataFrame in, Arrow out | 0.3987 | 1,254,210 |
| tablib | Dataset wrapper, openpyxl backend | 3.9683 | 125,999 |
| pyexcel | wrapper, openpyxl backend | 2.5904 | 193,017 |

## read_values_large

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 0.3868 | 4,135,996 |
| openpyxl | full read/write | 4.5856 | 348,917 |
| python_calamine | read-only, Python values | 0.5771 | 2,772,389 |
| fastexcel | read-only, Arrow tables | 0.4030 | 3,970,112 |
| pylightxl | pure-Python read/write | 9.3911 | 170,374 |
| pandas_openpyxl | DataFrame I/O, openpyxl engine | 5.8278 | 274,547 |
| pandas_calamine | DataFrame read, calamine engine | 1.3215 | 1,210,763 |
| polars | DataFrame I/O, wraps XlsxWriter/fastexcel | 0.3942 | 4,059,331 |
| duckdb | SQL engine; DataFrame in, Arrow out | 0.4961 | 3,225,464 |
| tablib | Dataset wrapper, openpyxl backend | 5.9722 | 267,908 |
| pyexcel | wrapper, openpyxl backend | 14.8379 | 107,832 |
| xlsx2csv | read-only, transcodes to CSV text | 3.4531 | 463,347 |

## memory_write_large

| engine | peak RSS MiB |
|---|---|
| grid_baseline | 233 |
| wolfxl | 610 |
| openpyxl | 743 |
| xlsxwriter | 430 |
| pyexcelerate | 264 |
| pylightxl | 805 |
| pandas_openpyxl | 868 |
| polars | 719 |
| duckdb | 325 |
| tablib | 833 |
| pyexcel | 263 |

## memory_read_large

| engine | peak RSS MiB |
|---|---|
| wolfxl | 153 |
| openpyxl | 169 |
| python_calamine | 286 |
| fastexcel | 267 |
| pylightxl | 1,485 |
| pandas_openpyxl | 293 |
| pandas_calamine | 388 |
| polars | 267 |
| duckdb | 207 |
| tablib | 280 |
| pyexcel | 949 |
| xlsx2csv | 152 |

