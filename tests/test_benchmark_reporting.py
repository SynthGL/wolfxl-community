from __future__ import annotations

from pathlib import Path

from scripts.benchmark_openpyxl_vs_wolfxl import (
    build_openpyxl_formula,
    build_openpyxl_styled_phased,
    build_wolfxl_styled_phased,
    memory_comparison_rows,
    operation_comparison_rows,
    phase_comparison_rows,
    read_wolfxl_formulas,
    selected_cases,
    write_markdown,
)


def test_selected_cases_accepts_repeated_and_comma_separated_values() -> None:
    assert selected_cases(
        [
            "write_cell_by_cell_plain, read_styled_cells",
            "modify_two_cells_plain",
        ]
    ) == {
        "modify_two_cells_plain",
        "read_styled_cells",
        "write_cell_by_cell_plain",
    }


def test_selected_cases_none_means_every_case() -> None:
    assert selected_cases(None) is None
    assert selected_cases(["", " , "]) is None


def test_phase_comparison_rows_compare_shared_phases_only() -> None:
    results = [
        {
            "case": "modify_two_cells_plain",
            "engine": "openpyxl",
            "phase_medians_seconds": {
                "setup_copy": 0.5,
                "modify_save": 10.0,
                "verify_load": 2.0,
            },
        },
        {
            "case": "modify_two_cells_plain",
            "engine": "wolfxl_modify",
            "phase_medians_seconds": {
                "setup_copy": 0.25,
                "modify_save": 1.0,
            },
        },
    ]

    assert phase_comparison_rows(results) == [
        {
            "case": "modify_two_cells_plain",
            "engine": "wolfxl_modify",
            "phase": "modify_save",
            "openpyxl_seconds": 10.0,
            "wolfxl_seconds": 1.0,
            "speedup_vs_openpyxl": 10.0,
        },
        {
            "case": "modify_two_cells_plain",
            "engine": "wolfxl_modify",
            "phase": "setup_copy",
            "openpyxl_seconds": 0.5,
            "wolfxl_seconds": 0.25,
            "speedup_vs_openpyxl": 2.0,
        },
    ]


def test_operation_comparison_rows_uses_modify_save_phase() -> None:
    phase_rows = [
        {
            "case": "modify_two_cells_plain",
            "engine": "wolfxl_modify",
            "phase": "modify_save",
            "openpyxl_seconds": 8.0,
            "wolfxl_seconds": 1.0,
            "speedup_vs_openpyxl": 8.0,
        },
        {
            "case": "modify_two_cells_plain",
            "engine": "wolfxl_modify",
            "phase": "verify_load",
            "openpyxl_seconds": 2.0,
            "wolfxl_seconds": 4.0,
            "speedup_vs_openpyxl": 0.5,
        },
    ]

    assert operation_comparison_rows(phase_rows) == [
        {
            "case": "modify_two_cells_plain",
            "engine": "wolfxl_modify",
            "phase": "modify_save",
            "openpyxl_seconds": 8.0,
            "wolfxl_seconds": 1.0,
            "speedup_vs_openpyxl": 8.0,
            "speedup_basis": "operation_phase",
        }
    ]


def test_memory_comparison_rows_include_peak_and_delta_context() -> None:
    memory = [
        {
            "case": "read_only_values_plain",
            "engine": "openpyxl",
            "peak_rss_bytes": 60_000_000,
            "delta_rss_bytes": 2_000_000,
        },
        {
            "case": "read_only_values_plain",
            "engine": "wolfxl",
            "peak_rss_bytes": 58_000_000,
            "delta_rss_bytes": 1_000_000,
        },
    ]

    assert memory_comparison_rows(memory) == [
        {
            "case": "read_only_values_plain",
            "engine": "wolfxl",
            "openpyxl_peak_rss_bytes": 60_000_000,
            "wolfxl_peak_rss_bytes": 58_000_000,
            "peak_rss_excess_bytes": -2_000_000,
            "peak_rss_ratio_vs_openpyxl": 58_000_000 / 60_000_000,
            "openpyxl_delta_rss_bytes": 2_000_000,
            "wolfxl_delta_rss_bytes": 1_000_000,
            "delta_rss_excess_bytes": -1_000_000,
            "delta_rss_ratio_vs_openpyxl": 0.5,
        }
    ]


def test_write_markdown_includes_phase_speedups(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    payload = {
        "metadata": {
            "timestamp_utc": "2026-05-31T00:00:00+00:00",
            "git_branch": "branch",
            "git_commit": "abc123",
            "git_dirty": False,
            "python": "3.9",
            "wolfxl_version": "2.0.0",
            "openpyxl_version": "3.1.5",
            "rounds": 3,
        },
        "results": [
            {
                "case": "modify_two_cells_plain",
                "engine": "openpyxl",
                "rows": 10,
                "cols": 5,
                "units_per_second": 1.0,
                "median_seconds": 1.0,
                "phase_medians_seconds": {"modify_save": 0.8},
            }
        ],
        "comparisons": [],
        "phase_comparisons": [
            {
                "case": "modify_two_cells_plain",
                "engine": "wolfxl_modify",
                "phase": "modify_save",
                "openpyxl_seconds": 0.8,
                "wolfxl_seconds": 0.1,
                "speedup_vs_openpyxl": 8.0,
            }
        ],
        "operation_comparisons": [
            {
                "case": "modify_two_cells_plain",
                "engine": "wolfxl_modify",
                "phase": "modify_save",
                "openpyxl_seconds": 0.8,
                "wolfxl_seconds": 0.1,
                "speedup_vs_openpyxl": 8.0,
                "speedup_basis": "operation_phase",
            }
        ],
        "memory": [],
        "memory_comparisons": [],
    }

    write_markdown(report, payload)

    text = report.read_text(encoding="utf-8")
    assert "## Phase speedups" in text
    assert "| modify_two_cells_plain | wolfxl_modify | modify_save | 0.800000 | 0.100000 | 8.00x |" in text
    assert "## Operation speedups" in text


def test_styled_write_builders_report_phases(tmp_path: Path) -> None:
    openpyxl_path = tmp_path / "openpyxl-styled.xlsx"
    wolfxl_path = tmp_path / "wolfxl-styled.xlsx"

    openpyxl_result = build_openpyxl_styled_phased(openpyxl_path, 2, 3)
    wolfxl_result = build_wolfxl_styled_phased(wolfxl_path, 2, 3)

    assert openpyxl_path.stat().st_size > 0
    assert wolfxl_path.stat().st_size > 0
    assert openpyxl_result["units"] == 6
    assert wolfxl_result["units"] == 6
    assert set(openpyxl_result["phase_seconds"]) == {"populate_cells", "save"}
    assert set(wolfxl_result["phase_seconds"]) == {"populate_cells", "save"}


def test_wolfxl_formula_read_benchmark_uses_public_values_only_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "formulas.xlsx"
    build_openpyxl_formula(path, 3, 5)

    import wolfxl

    workbook = wolfxl.load_workbook(path, data_only=False)
    worksheet = workbook.active
    worksheet_cls = type(worksheet)
    original_iter_rows = worksheet_cls.iter_rows
    calls: list[bool] = []

    def recording_iter_rows(self, *args, **kwargs):
        calls.append(bool(kwargs.get("values_only")))
        return original_iter_rows(self, *args, **kwargs)

    monkeypatch.setattr(worksheet_cls, "iter_rows", recording_iter_rows)
    monkeypatch.setattr(wolfxl, "load_workbook", lambda *_args, **_kwargs: workbook)

    assert read_wolfxl_formulas(path) == (3, 6.0, 6)
    assert calls == [True]
