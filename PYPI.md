# WolfXL Community

WolfXL Community is the maintained, MIT-licensed 2.0 release line for supported
workbook creation, reading, writing, streaming exports, and existing-workbook
edits. It is a free product, not a trial.

## Install

```bash
python -m pip install wolfxl
```

Most supported openpyxl-shaped code starts with one import change:

```diff
- from openpyxl import Workbook, load_workbook
+ from wolfxl import Workbook, load_workbook
```

Start with one representative workbook, define the output that must remain
correct, and prove that bounded operation before replacing a production path.
Review the [compatibility matrix](https://wolfxl.com/docs/migration/compatibility-matrix/?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09)
and [known limitations](https://wolfxl.com/docs/trust/limitations/?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09).

## Choose the right edition

Community is the free option when supported workbook I/O is sufficient.
Commercial 2.1+ is a separate option for the following workflow requirements:

| Requirement | Community 2.0 line | Commercial 2.1+ |
| --- | --- | --- |
| Supported workbook I/O | Included within the documented surface | Included |
| Native formula recalculation | Not included | [Calculate a supported formula set](https://wolfxl.com/calculate-excel-formulas-python?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09) |
| PDF or image rendering | Not included | [Render supported output](https://wolfxl.com/render-excel-python?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09) |
| Format conversion | Not included | [Scope an evaluation](https://wolfxl.com/pilot?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09) |
| VBA or Power Query operations | Not included | [Scope an evaluation](https://wolfxl.com/pilot?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09) |
| Production operations | Not included | [Scope an evaluation](https://wolfxl.com/pilot?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09) |
| Support | Public Community documentation and issues | [Scope an evaluation](https://wolfxl.com/pilot?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09) |

For existing-template work, review the [bounded preservation approach](https://wolfxl.com/openpyxl-preservation?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09).
Use the [local fit check](https://wolfxl.com/fit-check?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09)
to scope a representative-workbook test. Commercial self-service pricing is
[$30/month or $299/year for one seat](https://wolfxl.com/pricing?utm_source=pypi&utm_medium=registry&utm_campaign=community_commercial_2026_09).
