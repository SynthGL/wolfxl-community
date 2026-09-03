from __future__ import annotations

from importlib.metadata import version
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory

import wolfxl
from wolfxl import Workbook, load_workbook


assert version("wolfxl") == "2.0.3"
assert wolfxl.__version__ == "2.0.3"

assert find_spec("wolfxl.operations") is not None
for module_name in (
    "wolfxl.render",
    "wolfxl.integrations",
    "wolfxl._conversion",
    "wolfxl._power_query",
    "wolfxl._vba_runtime",
):
    assert find_spec(module_name) is None, module_name

with TemporaryDirectory() as directory:
    path = Path(directory) / "community-smoke.xlsx"
    workbook = Workbook()
    workbook.active["A1"] = "community"
    workbook.save(path)

    loaded = load_workbook(path)
    assert loaded.active["A1"].value == "community"
    loaded.close()

    path2 = Path(directory) / "community-smoke-2.xlsx"
    loaded = load_workbook(path)
    loaded.save(path2)
    loaded.close()

    # Guard and compare smoke test
    comparison = wolfxl.compare_workbooks(path, path2)
    assert comparison.passed is True
    assert comparison.issue_count == 0

    from wolfxl.operations.cli import main as cli_main
    rc = cli_main(["guard", str(path), str(path2)])
    assert rc == 0

print("community artifact smoke: ok")
