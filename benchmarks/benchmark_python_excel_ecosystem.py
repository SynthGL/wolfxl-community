"""Benchmark WolfXL Community against other open-source Python Excel libraries.

Engines and their honest scope:

- wolfxl           full read/write (this project)
- openpyxl         full read/write (the de-facto standard, baseline)
- XlsxWriter       write-only
- PyExcelerate     write-only
- python-calamine  read-only, returns Python values
- fastexcel        read-only, returns Arrow tables (not Python cell objects)

Write-only libraries appear only in write cases and read-only libraries only
in read cases. Read cases share one fixture written by openpyxl so no reader
is parsing its own writer's output.

Usage:

    python benchmarks/benchmark_python_excel_ecosystem.py \
        --rounds 5 --output-dir /tmp/ecosystem-results --prefix my-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata
import json
import platform
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import openpyxl
import pyexcelerate
import xlsxwriter
import wolfxl
from python_calamine import CalamineWorkbook

import fastexcel

BASE_DT = dt.datetime(2024, 1, 1, 9, 30, 0)


def plain_row(row_idx: int, cols: int) -> list[Any]:
    row: list[Any] = [f"r{row_idx}c0"]
    for col in range(1, cols):
        if col % 2 == 0:
            row.append(row_idx * 31 + col)
        else:
            row.append(row_idx + col / 7.0)
    return row


def mixed_row(row_idx: int) -> list[Any]:
    return [
        f"name-{row_idx}",
        row_idx * 17,
        row_idx / 3.0,
        row_idx % 2 == 0,
        BASE_DT + dt.timedelta(minutes=row_idx),
    ]


# --- write engines ---------------------------------------------------------


def write_wolfxl(path: Path, grid: list[list[Any]]) -> None:
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.write_rows(grid)
    wb.save(str(path))


def write_openpyxl(path: Path, grid: list[list[Any]]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    for row in grid:
        ws.append(row)
    wb.save(str(path))


def write_xlsxwriter(path: Path, grid: list[list[Any]]) -> None:
    wb = xlsxwriter.Workbook(str(path), {"default_date_format": "yyyy-mm-dd hh:mm:ss"})
    ws = wb.add_worksheet()
    for row_idx, row in enumerate(grid):
        ws.write_row(row_idx, 0, row)
    wb.close()


def write_pyexcelerate(path: Path, grid: list[list[Any]]) -> None:
    wb = pyexcelerate.Workbook()
    wb.new_sheet("Sheet1", data=grid)
    wb.save(str(path))


# --- read engines ----------------------------------------------------------


def read_wolfxl(path: Path) -> int:
    wb = wolfxl.load_workbook(str(path), read_only=True)
    ws = wb.active
    assert ws is not None
    count = 0
    for row in ws.iter_rows(values_only=True):
        count += len(row)
    wb.close()
    return count


def read_openpyxl(path: Path) -> int:
    wb = openpyxl.load_workbook(str(path), read_only=True)
    ws = wb.active
    assert ws is not None
    count = 0
    for row in ws.iter_rows(values_only=True):
        count += len(row)
    wb.close()
    return count


def read_python_calamine(path: Path) -> int:
    wb = CalamineWorkbook.from_path(str(path))
    rows = wb.get_sheet_by_index(0).to_python(skip_empty_area=False)
    return sum(len(row) for row in rows)


def read_fastexcel(path: Path) -> int:
    reader = fastexcel.read_excel(str(path))
    table = reader.load_sheet(0, header_row=None).to_arrow()
    return table.num_rows * table.num_columns


WRITE_ENGINES: dict[str, Callable[[Path, list[list[Any]]], None]] = {
    "wolfxl": write_wolfxl,
    "openpyxl": write_openpyxl,
    "xlsxwriter": write_xlsxwriter,
    "pyexcelerate": write_pyexcelerate,
}

READ_ENGINES: dict[str, Callable[[Path], int]] = {
    "wolfxl": read_wolfxl,
    "openpyxl": read_openpyxl,
    "python_calamine": read_python_calamine,
    "fastexcel": read_fastexcel,
}

ENGINE_SCOPE = {
    "wolfxl": "full read/write",
    "openpyxl": "full read/write",
    "xlsxwriter": "write-only",
    "pyexcelerate": "write-only",
    "python_calamine": "read-only, Python values",
    "fastexcel": "read-only, Arrow tables",
}


def cpu_brand() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    try:
        import subprocess

        return subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return platform.processor() or "unknown"


def library_versions() -> dict[str, str]:
    versions = {}
    for dist in (
        "wolfxl",
        "openpyxl",
        "XlsxWriter",
        "PyExcelerate",
        "python-calamine",
        "fastexcel",
        "pyarrow",
    ):
        try:
            versions[dist] = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            versions[dist] = "not installed"
    return versions


def measure(fn: Callable[[], Any], rounds: int) -> list[float]:
    fn()  # warmup, discarded
    samples = []
    for _ in range(rounds):
        started = perf_counter()
        fn()
        samples.append(perf_counter() - started)
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=200_000)
    parser.add_argument("--cols", type=int, default=8)
    parser.add_argument("--mixed-rows", type=int, default=10_000)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/ecosystem-results"))
    parser.add_argument("--prefix", default="ecosystem")
    parser.add_argument("--case", default=None, help="comma-separated case filter")
    args = parser.parse_args()

    case_filter = set(args.case.split(",")) if args.case else None
    args.output_dir.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="wolfxl-ecosystem-"))

    plain_grid = [plain_row(idx, args.cols) for idx in range(1, args.rows + 1)]
    mixed_grid = [mixed_row(idx) for idx in range(1, args.mixed_rows + 1)]

    cases: list[dict[str, Any]] = []
    if case_filter is None or "write_plain_large" in case_filter:
        cases.append(
            {
                "case": "write_plain_large",
                "kind": "write",
                "rows": args.rows,
                "cols": args.cols,
                "grid": plain_grid,
            }
        )
    if case_filter is None or "write_mixed" in case_filter:
        cases.append(
            {
                "case": "write_mixed",
                "kind": "write",
                "rows": args.mixed_rows,
                "cols": 5,
                "grid": mixed_grid,
            }
        )
    if case_filter is None or "read_values_large" in case_filter:
        fixture = workdir / "read-fixture.xlsx"
        write_openpyxl(fixture, plain_grid)
        cases.append(
            {
                "case": "read_values_large",
                "kind": "read",
                "rows": args.rows,
                "cols": args.cols,
                "fixture": fixture,
            }
        )

    results: list[dict[str, Any]] = []
    for spec in cases:
        units = spec["rows"] * spec["cols"]
        if spec["kind"] == "write":
            engines: dict[str, Callable[[], Any]] = {}
            for name, writer in WRITE_ENGINES.items():
                target = workdir / f"{spec['case']}-{name}.xlsx"
                engines[name] = (lambda w=writer, t=target, g=spec["grid"]: w(t, g))
        else:
            fixture = spec["fixture"]
            expected = units
            engines = {}
            for name, reader in READ_ENGINES.items():

                def run_read(r=reader, f=fixture, e=expected) -> None:
                    count = r(f)
                    if count != e:
                        raise AssertionError(f"read {count} cells, expected {e}")

                engines[name] = run_read

        for name, fn in engines.items():
            print(f"[{spec['case']}] {name} ...", flush=True)
            samples = measure(fn, args.rounds)
            median = statistics.median(samples)
            results.append(
                {
                    "case": spec["case"],
                    "engine": name,
                    "scope": ENGINE_SCOPE[name],
                    "rows": spec["rows"],
                    "cols": spec["cols"],
                    "samples_seconds": [round(s, 6) for s in samples],
                    "median_seconds": round(median, 6),
                    "units": units,
                    "units_per_second": round(units / median, 2) if median else None,
                }
            )

    comparisons = []
    by_case: dict[str, dict[str, float]] = {}
    for row in results:
        by_case.setdefault(row["case"], {})[row["engine"]] = row["median_seconds"]
    for case, engines_medians in sorted(by_case.items()):
        baseline = engines_medians.get("openpyxl")
        if not baseline:
            continue
        for engine, median in sorted(engines_medians.items()):
            if engine == "openpyxl":
                continue
            comparisons.append(
                {
                    "case": case,
                    "engine": engine,
                    "speedup_vs_openpyxl": round(baseline / median, 4),
                }
            )

    payload = {
        "metadata": {
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_brand": cpu_brand(),
            "rounds": args.rounds,
            "warmup_rounds": 1,
            "read_fixture_writer": "openpyxl",
            "versions": library_versions(),
            "engine_scope": ENGINE_SCOPE,
        },
        "results": results,
        "comparisons": comparisons,
    }

    json_path = args.output_dir / f"{args.prefix}.json"
    json_path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    lines = ["# Python Excel ecosystem benchmark", ""]
    meta = payload["metadata"]
    lines.append(
        f"{meta['cpu_brand']} | Python {meta['python']} | median of {meta['rounds']} rounds"
    )
    lines.append("")
    for case in by_case:
        lines.append(f"## {case}")
        lines.append("")
        lines.append("| engine | scope | median s | units/s |")
        lines.append("|---|---|---|---|")
        for row in results:
            if row["case"] != case:
                continue
            lines.append(
                f"| {row['engine']} | {row['scope']} | {row['median_seconds']:.4f} "
                f"| {row['units_per_second']:,.0f} |"
            )
        lines.append("")
    md_path = args.output_dir / f"{args.prefix}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    sys.exit(main())
