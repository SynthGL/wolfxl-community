"""Reproducible public-API benchmark for Community dense batch writes.

The script runs one isolated sample and emits a single JSON record. The CI
evidence workflow alternates exact base/candidate processes and computes the
statistics, avoiding shared-interpreter state between implementations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter_ns
from typing import Any

import wolfxl


def make_row(lane: str, row: int, cols: int) -> list[Any]:
    if lane.endswith("numeric"):
        return [row * col for col in range(1, cols + 1)]
    if lane.endswith("mixed"):
        return [
            f"account-{row:08d}-{col:03d}" if col % 3 == 0 else row * col
            for col in range(1, cols + 1)
        ]
    return [f"unique-{row:08d}-{col:03d}" for col in range(1, cols + 1)]


def run(lane: str, rows: int, cols: int, output: Path) -> dict[str, int | str]:
    total_started = perf_counter_ns()
    wb = wolfxl.Workbook()
    ws = wb.active
    assert ws is not None

    populate_started = perf_counter_ns()
    if lane.startswith("append-"):
        for row in range(1, rows + 1):
            ws.append(make_row(lane, row, cols))
    else:
        grid = [make_row(lane, row, cols) for row in range(1, rows + 1)]
        ws.write_rows(grid, copy=False, plain_values_only=True)
    populate_ns = perf_counter_ns() - populate_started

    save_started = perf_counter_ns()
    wb.save(str(output))
    save_ns = perf_counter_ns() - save_started
    wb.close()
    total_ns = perf_counter_ns() - total_started

    return {
        "lane": lane,
        "rows": rows,
        "cols": cols,
        "cells": rows * cols,
        "populate_ns": populate_ns,
        "save_ns": save_ns,
        "total_ns": total_ns,
        "output_bytes": output.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "lane",
        choices=("append-numeric", "append-mixed", "write-rows-numeric", "write-rows-unique"),
    )
    parser.add_argument("rows", type=int)
    parser.add_argument("cols", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.lane, args.rows, args.cols, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
