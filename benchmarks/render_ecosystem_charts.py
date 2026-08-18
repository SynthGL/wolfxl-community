"""Render the ecosystem comparison charts from a committed results JSON.

Usage:

    python benchmarks/render_ecosystem_charts.py \
        benchmarks/results/2026-08-18-ecosystem-linux-epyc.json \
        assets/benchmarks

Deterministic, stdlib-only. Every number is read from the results JSON
produced by ``benchmarks/benchmark_python_excel_ecosystem.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from render_charts import (
    FONT,
    MARGIN_X,
    OPENPYXL_FILL,
    TEXT_MUTED,
    TEXT_PRIMARY,
    WIDTH,
    WOLFXL_A,
    esc,
    fmt_seconds,
    footer,
    header,
)

OTHER_FILL = "#64748b"

ENGINE_LABELS = {
    "wolfxl": ("WolfXL Community", "full read/write"),
    "openpyxl": ("openpyxl", "full read/write"),
    "xlsxwriter": ("XlsxWriter", "write-only"),
    "pyexcelerate": ("PyExcelerate", "write-only"),
    "python_calamine": ("python-calamine", "read-only, Python values"),
    "fastexcel": ("fastexcel", "read-only, Arrow tables"),
}

CASE_TITLES = {
    "write_plain_large": "Write 200,000 x 8 plain values",
    "write_mixed": "Write 10,000 x 5 mixed types (str/int/float/bool/datetime)",
    "read_values_large": "Read 200,000 x 8, all values",
}


def render_case_chart(
    title: str,
    subtitle: str,
    notes: list[str],
    case_rows: list[dict[str, Any]],
    versions: dict[str, str],
) -> str:
    bar_h, gap, top, label_w = 24, 34, 96, 300
    height = top + gap * len(case_rows) + 76
    chart_w = WIDTH - MARGIN_X * 2 - label_w - 110
    max_median = max(row["median_seconds"] for row in case_rows)
    parts = header(title, subtitle, height)
    version_key = {
        "wolfxl": "wolfxl",
        "openpyxl": "openpyxl",
        "xlsxwriter": "XlsxWriter",
        "pyexcelerate": "PyExcelerate",
        "python_calamine": "python-calamine",
        "fastexcel": "fastexcel",
    }
    for idx, row in enumerate(sorted(case_rows, key=lambda r: r["median_seconds"])):
        y = top + idx * gap
        engine = row["engine"]
        name, scope = ENGINE_LABELS[engine]
        version = versions.get(version_key[engine], "")
        is_wolfxl = engine == "wolfxl"
        fill = "url(#wolfxl)" if is_wolfxl else (
            OPENPYXL_FILL if engine == "openpyxl" else OTHER_FILL
        )
        label_fill = TEXT_PRIMARY if is_wolfxl else TEXT_MUTED
        weight = "700" if is_wolfxl else "600"
        parts.append(
            f'<text x="{MARGIN_X}" y="{y + 12}" font-family="{FONT}" font-size="13" '
            f'font-weight="{weight}" fill="{label_fill}">{esc(f"{name} {version}")}</text>'
        )
        parts.append(
            f'<text x="{MARGIN_X}" y="{y + 26}" font-family="{FONT}" font-size="10.5" '
            f'fill="{TEXT_MUTED}">{esc(scope)}</text>'
        )
        bar_w = max(chart_w * row["median_seconds"] / max_median, 3)
        parts.append(
            f'<rect x="{MARGIN_X + label_w}" y="{y}" width="{bar_w:.1f}" '
            f'height="{bar_h}" rx="{bar_h / 2}" fill="{fill}"/>'
        )
        value_fill = WOLFXL_A if is_wolfxl else TEXT_MUTED
        parts.append(
            f'<text x="{MARGIN_X + label_w + bar_w + 10:.1f}" y="{y + 17}" '
            f'font-family="{FONT}" font-size="13.5" font-weight="700" '
            f'fill="{value_fill}">{esc(fmt_seconds(row["median_seconds"]))}</text>'
        )
    return footer(parts, notes, height)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    results_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    meta = payload["metadata"]

    subtitle = (
        f"{meta['cpu_brand']} | {meta['machine']} Linux | Python {meta['python']} | "
        f"median of {meta['rounds']} rounds | lower is better"
    )
    provenance = [
        f"Raw data: benchmarks/results/{results_path.name} (run {meta['timestamp_utc'][:10]})",
        "Reproduce: python benchmarks/benchmark_python_excel_ecosystem.py "
        "(see benchmarks/README.md)",
    ]

    by_case: dict[str, list[dict[str, Any]]] = {}
    for row in payload["results"]:
        by_case.setdefault(row["case"], []).append(row)

    outputs = {
        "write_plain_large": "ecosystem-write-large.svg",
        "write_mixed": "ecosystem-write-mixed.svg",
        "read_values_large": "ecosystem-read-large.svg",
    }
    extra_notes = {
        "read_values_large": [
            "fastexcel returns Arrow tables, not Python cell objects; "
            "read fixture written by openpyxl.",
        ],
        "write_plain_large": [],
        "write_mixed": [],
    }
    for case, filename in outputs.items():
        rows = by_case.get(case)
        if not rows:
            continue
        chart = render_case_chart(
            CASE_TITLES[case],
            subtitle,
            extra_notes[case] + provenance,
            rows,
            meta["versions"],
        )
        (output_dir / filename).write_text(chart, encoding="utf-8")
    print(f"Wrote {len(outputs)} charts to {output_dir}")


if __name__ == "__main__":
    main()
