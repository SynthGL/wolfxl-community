# Python Excel ecosystem benchmark

AMD EPYC 9654 96-Core Processor | Python 3.13.15 | median of 5 rounds

## write_plain_large

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 1.0013 | 1,597,870 |
| openpyxl | full read/write | 11.8427 | 135,104 |
| xlsxwriter | write-only | 6.4486 | 248,115 |
| pyexcelerate | write-only | 5.2183 | 306,614 |
| pylightxl | pure-Python read/write | DNF (> 240 s/round) | - |
| pandas_openpyxl | DataFrame I/O, openpyxl engine | 15.2766 | 104,735 |
| polars | DataFrame I/O, wraps XlsxWriter/fastexcel | 8.6315 | 185,368 |

## write_mixed

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 0.0495 | 1,009,514 |
| openpyxl | full read/write | 0.3680 | 135,881 |
| xlsxwriter | write-only | 0.2004 | 249,518 |
| pyexcelerate | write-only | 0.1706 | 293,131 |
| pandas_openpyxl | DataFrame I/O, openpyxl engine | 0.6134 | 81,516 |
| polars | DataFrame I/O, wraps XlsxWriter/fastexcel | 0.2502 | 199,830 |

## write_unique_strings

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 0.3900 | 1,282,006 |
| openpyxl | full read/write | 4.5967 | 108,774 |
| xlsxwriter | write-only | 2.7466 | 182,046 |
| pyexcelerate | write-only | 1.9217 | 260,193 |
| pylightxl | pure-Python read/write | DNF (> 240 s/round) | - |
| pandas_openpyxl | DataFrame I/O, openpyxl engine | 6.0806 | 82,229 |
| polars | DataFrame I/O, wraps XlsxWriter/fastexcel | 3.3009 | 151,476 |

## read_values_large

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 0.6126 | 2,611,859 |
| openpyxl | full read/write | 6.5235 | 245,269 |
| python_calamine | read-only, Python values | 0.8332 | 1,920,197 |
| fastexcel | read-only, Arrow tables | 0.5721 | 2,796,830 |
| pylightxl | pure-Python read/write | 12.9287 | 123,755 |
| pandas_openpyxl | DataFrame I/O, openpyxl engine | 8.1244 | 196,937 |
| pandas_calamine | DataFrame read, calamine engine | 1.6607 | 963,438 |
| polars | DataFrame I/O, wraps XlsxWriter/fastexcel | 0.5722 | 2,796,396 |

## memory_write_large

| engine | peak RSS MiB |
|---|---|
| grid_baseline | 233 |
| wolfxl | 611 |
| openpyxl | 743 |
| xlsxwriter | 430 |
| pyexcelerate | 263 |
| pylightxl | DNF (> 240 s) |
| pandas_openpyxl | 868 |
| polars | 718 |

## memory_read_large

| engine | peak RSS MiB |
|---|---|
| wolfxl | 153 |
| openpyxl | 169 |
| python_calamine | 286 |
| fastexcel | 266 |
| pylightxl | 1,485 |
| pandas_openpyxl | 293 |
| pandas_calamine | 388 |
| polars | 266 |

