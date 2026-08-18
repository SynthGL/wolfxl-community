from __future__ import annotations

import pytest

from scripts.benchmark_cell_by_cell_scale import compare_pair, parse_row_sizes


def test_parse_row_sizes_accepts_comma_list() -> None:
    assert parse_row_sizes("100, 2000,5000") == [100, 2000, 5000]


def test_parse_row_sizes_rejects_empty_list() -> None:
    with pytest.raises(Exception):
        parse_row_sizes(" , ")


def test_compare_pair_reports_total_and_phase_speedups() -> None:
    openpyxl_result = {
        "rows": 10,
        "cols": 5,
        "units": 50,
        "median_seconds": 4.0,
        "phase_medians_seconds": {
            "construct_loop": 1.0,
            "save_flush": 3.0,
        },
    }
    wolfxl_result = {
        "rows": 10,
        "cols": 5,
        "units": 50,
        "median_seconds": 2.0,
        "phase_medians_seconds": {
            "construct_loop": 0.5,
            "save_flush": 1.5,
        },
    }

    comparison = compare_pair(openpyxl_result, wolfxl_result)

    assert comparison["speedup_vs_openpyxl"] == 2.0
    assert comparison["phase_speedups_vs_openpyxl"] == {
        "construct_loop": 2.0,
        "save_flush": 2.0,
    }
