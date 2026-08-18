"""Render the README benchmark charts from a committed benchmark results JSON.

Usage:

    python benchmarks/render_charts.py \
        benchmarks/results/2026-08-18-community-2.0.1-vs-openpyxl-3.1.5.json \
        assets/benchmarks

Deterministic, stdlib-only. Every number in the SVGs is read from the results
JSON produced by ``benchmarks/benchmark_openpyxl_vs_wolfxl.py``; nothing is
hand-entered.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Visual constants -----------------------------------------------------------

WIDTH = 920
MARGIN_X = 36
PANEL_RADIUS = 14
BG = "#0f172a"
PANEL_STROKE = "#1e293b"
GRID = "#1e293b"
TEXT_PRIMARY = "#e2e8f0"
TEXT_MUTED = "#94a3b8"
WOLFXL_A = "#fbbf24"
WOLFXL_B = "#f59e0b"
OPENPYXL_FILL = "#475569"
FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"


def esc(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def header(title: str, subtitle: str, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{esc(title)}">',
        "<defs>",
        f'<linearGradient id="wolfxl" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{WOLFXL_B}"/>'
        f'<stop offset="1" stop-color="{WOLFXL_A}"/></linearGradient>',
        "</defs>",
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" '
        f'rx="{PANEL_RADIUS}" fill="{BG}" stroke="{PANEL_STROKE}"/>',
        f'<text x="{MARGIN_X}" y="42" font-family="{FONT}" font-size="21" '
        f'font-weight="700" fill="{TEXT_PRIMARY}">{esc(title)}</text>',
        f'<text x="{MARGIN_X}" y="66" font-family="{FONT}" font-size="13" '
        f'fill="{TEXT_MUTED}">{esc(subtitle)}</text>',
    ]


def footer(parts: list[str], notes: list[str], height: int) -> str:
    base_y = height - 18 - 16 * (len(notes) - 1)
    for idx, note in enumerate(notes):
        parts.append(
            f'<text x="{MARGIN_X}" y="{base_y + idx * 16}" font-family="{FONT}" '
            f'font-size="11.5" fill="{TEXT_MUTED}">{esc(note)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def fmt_seconds(value: float) -> str:
    if value >= 10:
        return f"{value:.1f} s"
    if value >= 1:
        return f"{value:.2f} s"
    return f"{value * 1000:.0f} ms"


def render_speedup_chart(rows: list[dict[str, Any]], subtitle: str, notes: list[str]) -> str:
    row_h, top, label_w = 46, 104, 336
    height = top + row_h * len(rows) + 70
    chart_w = WIDTH - MARGIN_X * 2 - label_w - 74
    max_speedup = max(row["speedup"] for row in rows)
    parts = header("WolfXL Community vs openpyxl: median speedup", subtitle, height)
    for tick in (5, 10, 15, 20, 25):
        if tick > max_speedup:
            break
        x = MARGIN_X + label_w + chart_w * tick / max_speedup
        parts.append(
            f'<line x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" '
            f'y2="{top + row_h * len(rows) - 10}" stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{top - 18}" font-family="{FONT}" font-size="11" '
            f'fill="{TEXT_MUTED}" text-anchor="middle">{tick}x</text>'
        )
    for idx, row in enumerate(rows):
        y = top + idx * row_h
        bar_w = max(chart_w * row["speedup"] / max_speedup, 3)
        parts.append(
            f'<text x="{MARGIN_X}" y="{y + 15}" font-family="{FONT}" font-size="13.5" '
            f'font-weight="600" fill="{TEXT_PRIMARY}">{esc(row["label"])}</text>'
        )
        parts.append(
            f'<text x="{MARGIN_X}" y="{y + 31}" font-family="{FONT}" font-size="11" '
            f'fill="{TEXT_MUTED}">{esc(row["sublabel"])}</text>'
        )
        parts.append(
            f'<rect x="{MARGIN_X + label_w}" y="{y + 4}" width="{chart_w}" height="20" '
            f'rx="10" fill="{PANEL_STROKE}" opacity="0.55"/>'
        )
        parts.append(
            f'<rect x="{MARGIN_X + label_w}" y="{y + 4}" width="{bar_w:.1f}" height="20" '
            f'rx="10" fill="url(#wolfxl)"/>'
        )
        parts.append(
            f'<text x="{MARGIN_X + label_w + bar_w + 10:.1f}" y="{y + 19}" '
            f'font-family="{FONT}" font-size="14" font-weight="700" '
            f'fill="{WOLFXL_A}">{row["speedup"]:.1f}x</text>'
        )
    return footer(parts, notes, height)


def render_pair_chart(
    title: str,
    subtitle: str,
    notes: list[str],
    rows: list[dict[str, Any]],
    unit_formatter: Any,
) -> str:
    group_h, top, label_w = 74, 100, 288
    height = top + group_h * len(rows) + 70
    chart_w = WIDTH - MARGIN_X * 2 - label_w - 96
    max_value = max(max(row["openpyxl"], row["wolfxl"]) for row in rows)
    parts = header(title, subtitle, height)
    legend_x = WIDTH - MARGIN_X - 236
    parts.append(
        f'<rect x="{legend_x}" y="30" width="12" height="12" rx="3" fill="url(#wolfxl)"/>'
        f'<text x="{legend_x + 18}" y="41" font-family="{FONT}" font-size="12.5" '
        f'fill="{TEXT_PRIMARY}">WolfXL Community 2.0.1</text>'
        f'<rect x="{legend_x}" y="50" width="12" height="12" rx="3" fill="{OPENPYXL_FILL}"/>'
        f'<text x="{legend_x + 18}" y="61" font-family="{FONT}" font-size="12.5" '
        f'fill="{TEXT_PRIMARY}">openpyxl 3.1.5</text>'
    )
    for idx, row in enumerate(rows):
        y = top + idx * group_h
        parts.append(
            f'<text x="{MARGIN_X}" y="{y + 22}" font-family="{FONT}" font-size="13.5" '
            f'font-weight="600" fill="{TEXT_PRIMARY}">{esc(row["label"])}</text>'
        )
        parts.append(
            f'<text x="{MARGIN_X}" y="{y + 38}" font-family="{FONT}" font-size="11" '
            f'fill="{TEXT_MUTED}">{esc(row["sublabel"])}</text>'
        )
        for offset, engine, fill in (
            (6, "wolfxl", "url(#wolfxl)"),
            (32, "openpyxl", OPENPYXL_FILL),
        ):
            value = row[engine]
            bar_w = max(chart_w * value / max_value, 3)
            parts.append(
                f'<rect x="{MARGIN_X + label_w}" y="{y + offset}" width="{bar_w:.1f}" '
                f'height="18" rx="9" fill="{fill}"/>'
            )
            color = WOLFXL_A if engine == "wolfxl" else TEXT_MUTED
            parts.append(
                f'<text x="{MARGIN_X + label_w + bar_w + 10:.1f}" y="{y + offset + 14}" '
                f'font-family="{FONT}" font-size="13" font-weight="700" '
                f'fill="{color}">{unit_formatter(value)}</text>'
            )
    return footer(parts, notes, height)


def index_results(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(r["case"], r["engine"]): r for r in payload["results"]}


def index_memory(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(m["case"], m["engine"]): m for m in payload["memory"]}


def speedup(results: dict[tuple[str, str], dict[str, Any]], case: str, engine: str) -> float:
    baseline = results[(case, "openpyxl")]["median_seconds"]
    return baseline / results[(case, engine)]["median_seconds"]


def main() -> None:
    results_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    meta = payload["metadata"]
    results = index_results(payload)
    memory = index_memory(payload)

    context = (
        f"wolfxl {meta['wolfxl_version']} (PyPI wheel) vs openpyxl "
        f"{meta['openpyxl_version']} | {meta['cpu_brand']} | Python {meta['python']} | "
        f"median of {meta['rounds']} rounds"
    )
    provenance = [
        f"Raw data: benchmarks/results/{results_path.name} (run {meta['timestamp_utc'][:10]})",
        "Reproduce: python benchmarks/benchmark_openpyxl_vs_wolfxl.py (see benchmarks/README.md)",
    ]

    speedup_rows = [
        {
            "label": "Write 200,000 x 8 rows",
            "sublabel": "ws.write_rows(), plain values",
            "speedup": speedup(results, "large_write_append_plain", "wolfxl_write_rows"),
        },
        {
            "label": "Write 10,000 x 5 mixed types",
            "sublabel": "ws.append(), str/int/float/bool/date",
            "speedup": speedup(results, "write_append_mixed", "wolfxl_append"),
        },
        {
            "label": "Write 2,000 x 5 styled rows",
            "sublabel": "ws.write_styled_rows() vs per-cell styling",
            "speedup": speedup(results, "write_styled_cells", "wolfxl_write_styled_rows"),
        },
        {
            "label": "Write 2,000 x 5 formulas",
            "sublabel": "ws.write_rows(), formula strings",
            "speedup": speedup(results, "write_append_formulas", "wolfxl_write_rows_fast_formula"),
        },
        {
            "label": "Write 5-sheet workbook",
            "sublabel": "ws.write_rows(), 1,000 x 5 per sheet",
            "speedup": speedup(
                results, "write_multi_sheet_plain", "wolfxl_write_rows_fast_multi_sheet"
            ),
        },
        {
            "label": "Read 200,000 x 8 rows",
            "sublabel": "load_workbook(read_only=True), value iteration",
            "speedup": speedup(results, "large_read_only_values_plain", "wolfxl"),
        },
        {
            "label": "Read 10,000 x 5 rows",
            "sublabel": "load_workbook(), value iteration",
            "speedup": speedup(results, "read_values_plain", "wolfxl"),
        },
        {
            "label": "Read formula text",
            "sublabel": "2,000 x 5, data_only=False",
            "speedup": speedup(results, "read_formula_text", "wolfxl"),
        },
        {
            "label": "Modify 2 cells + save, 200,000 x 8",
            "sublabel": "load_workbook(modify=True)",
            "speedup": speedup(results, "large_modify_two_cells_plain", "wolfxl_modify"),
        },
    ]
    (output_dir / "speedup-vs-openpyxl.svg").write_text(
        render_speedup_chart(speedup_rows, context, provenance), encoding="utf-8"
    )

    large_rows = [
        {
            "label": "Write 200,000 x 8",
            "sublabel": "ws.write_rows() vs ws.append()",
            "wolfxl": results[("large_write_append_plain", "wolfxl_write_rows")][
                "median_seconds"
            ],
            "openpyxl": results[("large_write_append_plain", "openpyxl")]["median_seconds"],
        },
        {
            "label": "Read 200,000 x 8",
            "sublabel": "load_workbook(), value iteration",
            "wolfxl": results[("large_read_values_plain", "wolfxl")]["median_seconds"],
            "openpyxl": results[("large_read_values_plain", "openpyxl")]["median_seconds"],
        },
        {
            "label": "Read 200,000 x 8, read-only",
            "sublabel": "load_workbook(read_only=True)",
            "wolfxl": results[("large_read_only_values_plain", "wolfxl")]["median_seconds"],
            "openpyxl": results[("large_read_only_values_plain", "openpyxl")][
                "median_seconds"
            ],
        },
        {
            "label": "Modify 2 cells + save",
            "sublabel": "200,000 x 8 existing workbook",
            "wolfxl": results[("large_modify_two_cells_plain", "wolfxl_modify")][
                "median_seconds"
            ],
            "openpyxl": results[("large_modify_two_cells_plain", "openpyxl")][
                "median_seconds"
            ],
        },
    ]
    (output_dir / "large-file-seconds.svg").write_text(
        render_pair_chart(
            "1.6 million cells: wall-clock seconds (lower is better)",
            context,
            provenance,
            large_rows,
            fmt_seconds,
        ),
        encoding="utf-8",
    )

    def fmt_mib(value: float) -> str:
        return f"{value:.0f} MiB"

    memory_rows = [
        {
            "label": "Read 200,000 x 8",
            "sublabel": "peak RSS, fresh process per run",
            "wolfxl": memory[("large_read_values_plain", "wolfxl")]["peak_rss_bytes"] / 2**20,
            "openpyxl": memory[("large_read_values_plain", "openpyxl")]["peak_rss_bytes"]
            / 2**20,
        },
        {
            "label": "Modify 2 cells + save, 200,000 x 8",
            "sublabel": "peak RSS, fresh process per run",
            "wolfxl": memory[("large_modify_two_cells_plain", "wolfxl")]["peak_rss_bytes"]
            / 2**20,
            "openpyxl": memory[("large_modify_two_cells_plain", "openpyxl")]["peak_rss_bytes"]
            / 2**20,
        },
        {
            "label": "Write 200,000 x 8",
            "sublabel": "peak RSS, fresh process per run",
            "wolfxl": memory[("large_write_append_plain", "wolfxl")]["peak_rss_bytes"] / 2**20,
            "openpyxl": memory[("large_write_append_plain", "openpyxl")]["peak_rss_bytes"]
            / 2**20,
        },
    ]
    (output_dir / "large-file-memory.svg").write_text(
        render_pair_chart(
            "1.6 million cells: peak memory (lower is better)",
            context,
            provenance,
            memory_rows,
            fmt_mib,
        ),
        encoding="utf-8",
    )
    print(f"Wrote 3 charts to {output_dir}")


if __name__ == "__main__":
    main()
