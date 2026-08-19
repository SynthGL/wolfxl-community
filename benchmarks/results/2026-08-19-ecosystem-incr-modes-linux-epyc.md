# Python Excel ecosystem benchmark

AMD EPYC 9655 96-Core Processor | Python 3.13.15 | median of 5 rounds

## write_plain_large

| engine | scope | median s | units/s |
|---|---|---|---|
| openpyxl_wo | openpyxl write_only mode | 6.0537 | 264,299 |
| xlsxwriter_cm | XlsxWriter constant_memory mode | 3.7372 | 428,131 |
| pandas_xlsxwriter | DataFrame I/O, xlsxwriter engine | 7.7776 | 205,720 |

## memory_write_large

| engine | peak RSS MiB |
|---|---|
| openpyxl_wo | 234 |
| xlsxwriter_cm | 234 |
| pandas_xlsxwriter | 525 |

