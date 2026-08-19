"""Merge an incremental ecosystem benchmark run into a base results JSON.

Usage:

    python benchmarks/merge_ecosystem_results.py BASE.json INCREMENT.json OUT.json

Engines are measured in isolation (own timing loop, fresh process for the
memory pass), so results from separate runs are comparable if and only if the
environment is identical. This tool enforces that: it refuses to merge unless
CPU, machine, platform, Python, rounds, round budget, and every library
version shared by both runs match exactly. Rows with the same (case, engine)
key are replaced by the increment; new engines are appended. Provenance of
every increment is recorded in the output metadata.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

IDENTITY_KEYS = (
    "cpu_brand",
    "machine",
    "platform",
    "python",
    "rounds",
    "warmup_rounds",
    "round_budget_seconds",
)


def merge_rows(
    base_rows: list[dict], incr_rows: list[dict]
) -> list[dict]:
    merged = list(base_rows)
    index = {(r["case"], r["engine"]): i for i, r in enumerate(merged)}
    for row in incr_rows:
        key = (row["case"], row["engine"])
        if key in index:
            merged[index[key]] = row
        else:
            merged.append(row)
    return merged


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    base_path, incr_path, out_path = (Path(p) for p in sys.argv[1:4])
    base = json.loads(base_path.read_text(encoding="utf-8"))
    incr = json.loads(incr_path.read_text(encoding="utf-8"))
    base_meta, incr_meta = base["metadata"], incr["metadata"]

    mismatches = [
        f"  {key}: base={base_meta.get(key)!r} increment={incr_meta.get(key)!r}"
        for key in IDENTITY_KEYS
        if base_meta.get(key) != incr_meta.get(key)
    ]
    for name in sorted(set(base_meta["versions"]) & set(incr_meta["versions"])):
        b, i = base_meta["versions"][name], incr_meta["versions"][name]
        if b != i:
            mismatches.append(f"  versions[{name}]: base={b!r} increment={i!r}")
    if mismatches:
        raise SystemExit(
            "refusing to merge: the runs are not from an identical "
            "environment\n" + "\n".join(mismatches)
        )

    merged = {
        "metadata": base_meta
        | {
            "versions": base_meta["versions"] | incr_meta["versions"],
            "increments": base_meta.get("increments", [])
            + [
                {
                    "source": incr_path.name,
                    "timestamp_utc": incr_meta["timestamp_utc"],
                }
            ],
        },
        "results": merge_rows(base["results"], incr["results"]),
        "memory": merge_rows(base.get("memory", []), incr.get("memory", [])),
    }
    out_path.write_text(
        json.dumps(merged, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
