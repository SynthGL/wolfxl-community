from __future__ import annotations

from pathlib import Path

from scripts.summarize_benchmark_weak_lanes import summarize_weak_lanes, write_markdown


def test_summarize_weak_lanes_reports_slowest_speed_and_memory() -> None:
    payload = {
        "metadata": {"git_dirty": False, "timestamp_utc": "2026-06-01T00:00:00Z"},
        "comparisons": [
            {"case": "fast_case", "engine": "wolfxl", "speedup_vs_openpyxl": 8.0},
            {"case": "weak_case", "engine": "wolfxl", "speedup_vs_openpyxl": 1.9},
            {"case": "phase_case", "engine": "wolfxl_modify", "speedup_vs_openpyxl": 1.1},
        ],
        "operation_comparisons": [
            {
                "case": "phase_case",
                "engine": "wolfxl_modify",
                "phase": "modify_save",
                "speedup_vs_openpyxl": 2.5,
            }
        ],
        "memory_comparisons": [
            {"case": "good_memory", "engine": "wolfxl", "peak_rss_ratio_vs_openpyxl": 0.4},
            {"case": "near_memory", "engine": "wolfxl", "peak_rss_ratio_vs_openpyxl": 0.97},
        ],
        "memory": [
            {
                "case": "near_memory",
                "engine": "openpyxl",
                "peak_rss_bytes": 60_000_000,
                "delta_rss_bytes": 2_000_000,
            },
            {
                "case": "near_memory",
                "engine": "wolfxl",
                "peak_rss_bytes": 58_200_000,
                "delta_rss_bytes": 1_000_000,
            },
        ],
    }

    summary = summarize_weak_lanes(payload, source_benchmark="baseline.json")

    assert summary["summary"]["minimum_end_to_end_speedup_vs_openpyxl"] == 1.1
    assert summary["summary"]["highest_memory_ratio_vs_openpyxl"] == 0.97
    assert summary["summary"]["actionable_speed_lane_count"] == 2
    assert summary["actionable_speed_lanes"] == [
        {"case": "weak_case", "engine": "wolfxl", "speedup_vs_openpyxl": 1.9, "speedup_basis": "end_to_end"},
        {
            "case": "phase_case",
            "engine": "wolfxl_modify",
            "phase": "modify_save",
            "speedup_vs_openpyxl": 2.5,
            "speedup_basis": "operation_phase",
        },
    ]
    assert summary["weak_speed_lanes"] == [
        {"case": "phase_case", "engine": "wolfxl_modify", "speedup_vs_openpyxl": 1.1},
        {"case": "weak_case", "engine": "wolfxl", "speedup_vs_openpyxl": 1.9}
    ]
    assert summary["weak_operation_lanes"] == [
        {
            "case": "phase_case",
            "engine": "wolfxl_modify",
            "phase": "modify_save",
            "speedup_vs_openpyxl": 2.5,
        }
    ]
    assert summary["weak_memory_lanes"] == [
        {
            "case": "near_memory",
            "engine": "wolfxl",
            "peak_rss_ratio_vs_openpyxl": 0.97,
            "openpyxl_peak_rss_bytes": 60_000_000,
            "wolfxl_peak_rss_bytes": 58_200_000,
            "peak_rss_excess_bytes": -1_800_000,
            "openpyxl_delta_rss_bytes": 2_000_000,
            "wolfxl_delta_rss_bytes": 1_000_000,
            "delta_rss_excess_bytes": -1_000_000,
            "delta_rss_ratio_vs_openpyxl": 0.5,
        }
    ]


def test_write_markdown_includes_plain_english_targets(tmp_path: Path) -> None:
    summary = {
        "metadata": {
            "source_benchmark": "baseline.json",
            "source_metadata": {
                "timestamp_utc": "2026-06-01T00:00:00Z",
                "git_commit": "abc123",
                "git_dirty": False,
                "python": "3.12",
                "wolfxl_version": "2.0.0",
                "openpyxl_version": "3.1.5",
            },
        },
        "summary": {
            "comparison_count": 1,
            "operation_comparison_count": 0,
            "memory_comparison_count": 1,
            "minimum_end_to_end_speedup_vs_openpyxl": 2.0,
            "highest_memory_ratio_vs_openpyxl": 0.95,
        },
        "actionable_speed_lanes": [
            {
                "case": "write_styled_cells",
                "engine": "wolfxl_cell",
                "speedup_basis": "end_to_end",
                "speedup_vs_openpyxl": 2.0,
            }
        ],
        "weak_speed_lanes": [
            {"case": "write_styled_cells", "engine": "wolfxl_cell", "speedup_vs_openpyxl": 2.0}
        ],
        "weak_operation_lanes": [],
        "weak_memory_lanes": [
            {
                "case": "write_append_plain",
                "engine": "wolfxl",
                "peak_rss_ratio_vs_openpyxl": 0.95,
                "delta_rss_ratio_vs_openpyxl": 0.5,
                "delta_rss_excess_bytes": -1_000_000,
            }
        ],
    }
    report = tmp_path / "weak.md"

    write_markdown(report, summary)

    text = report.read_text(encoding="utf-8")
    assert "Plain English" in text
    assert "## Actionable Speed Lanes" in text
    assert "| write_styled_cells | wolfxl_cell | end_to_end | 2.000x |" in text
    assert "| write_styled_cells | wolfxl_cell | 2.000x |" in text
    assert "| write_append_plain | wolfxl | 0.950x | 0.500x | -1.0 MiB |" in text
