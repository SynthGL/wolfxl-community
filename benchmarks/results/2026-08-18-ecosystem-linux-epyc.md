# Python Excel ecosystem benchmark

AMD EPYC 9654 96-Core Processor | Python 3.13.15 | median of 5 rounds

## write_plain_large

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 1.0086 | 1,586,350 |
| openpyxl | full read/write | 11.8412 | 135,122 |
| xlsxwriter | write-only | 6.4872 | 246,640 |
| pyexcelerate | write-only | 5.0779 | 315,093 |

## write_mixed

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 0.0491 | 1,017,573 |
| openpyxl | full read/write | 0.3698 | 135,224 |
| xlsxwriter | write-only | 0.2021 | 247,443 |
| pyexcelerate | write-only | 0.1684 | 296,874 |

## read_values_large

| engine | scope | median s | units/s |
|---|---|---|---|
| wolfxl | full read/write | 0.6270 | 2,551,817 |
| openpyxl | full read/write | 6.7153 | 238,260 |
| python_calamine | read-only, Python values | 0.8626 | 1,854,770 |
| fastexcel | read-only, Arrow tables | 0.5960 | 2,684,604 |

