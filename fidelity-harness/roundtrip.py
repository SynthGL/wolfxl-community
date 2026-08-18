#!/usr/bin/env python3
"""Round-trip fidelity harness: open a workbook, save it, measure what survived.

The measurement is deliberately the least flattering thing you can ask of a
spreadsheet library, and the hardest to argue with:

    open the file, change nothing, save it somewhere else

Nothing was edited, so nothing can justify a difference. Any part,
relationship, or feature that is absent afterwards was dropped by the save
path. There is no "you asked for that" defence available to any engine here,
including ours.

What is counted comes from `ooxml_fidelity.audit`, which compares the two zip
packages directly and never opens a workbook through any library, so it cannot
favour the engine that produced it.

Usage:
    python3 corpus.py corpus
    python3 roundtrip.py corpus --engine openpyxl --engine wolfxl --markdown

Exit status is 0 when the run completes. Pass --fail-on-change to make any
detected package difference a nonzero exit for CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import tempfile
import time
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Import the sibling modules whatever directory the harness is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ooxml_fidelity  # noqa: E402  # pyright: ignore[reportMissingImports]
from engines import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    Engine,
    EngineUnavailable,
    WorkbookUnsupported,
    load_engine,
)

STATUS_FAITHFUL = "faithful"
STATUS_CHANGED = "changed"
STATUS_UNSUPPORTED = "unsupported"
STATUS_ERROR = "error"


@dataclass
class Result:
    """One engine against one workbook."""

    engine: str
    workbook: str
    tier: str
    status: str
    parts_before: int = 0
    parts_after: int = 0
    parts_lost: int = 0
    relationships_before: int = 0
    relationships_after: int = 0
    relationships_lost: int = 0
    features_lost: list[str] = field(default_factory=list)
    semantic_drift: list[str] = field(default_factory=list)
    lost_parts: list[str] = field(default_factory=list)
    issue_count: int = 0
    issues: list[dict[str, object]] = field(default_factory=list)
    issues_by_kind: dict[str, int] = field(default_factory=dict)
    engine_warnings: list[str] = field(default_factory=list)
    detail: str = ""
    seconds: float = 0.0


def _feature_losses(parts: list[str]) -> list[str]:
    """Feature-specific families represented by parts that actually vanished.

    Never infer this from aggregate prefix counts. Some internal audit
    families deliberately use broad containers (for example,
    conditional_formatting includes every worksheet and styles.xml), so a
    relationship file disappearing can otherwise be mislabelled as a lost
    conditional format.
    """
    generic = {"conditional_formatting", "doc_metadata", "sheet_metadata"}
    families: set[str] = set()
    for part in parts:
        if part.endswith(".rels"):
            continue
        for family, prefixes in ooxml_fidelity.FEATURE_PART_PREFIXES.items():
            if family in generic:
                continue
            if any(part.startswith(prefix) for prefix in prefixes):
                families.add(family)
    return sorted(families)

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_one(engine: Engine, source: Path, tier: str, workspace: Path) -> Result:
    """Round-trip one workbook and grade the result."""
    result = Result(engine=engine.name, workbook=source.name, tier=tier, status=STATUS_ERROR)

    # Work on a copy so an in-place engine cannot corrupt the corpus.
    staged_source = workspace / f"in-{source.name}"
    target = workspace / f"out-{source.name}"
    target.unlink(missing_ok=True)
    shutil.copy2(source, staged_source)

    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        try:
            engine.round_trip(staged_source, target)
        except WorkbookUnsupported as error:
            result.status = STATUS_UNSUPPORTED
            result.detail = str(error)
            result.seconds = time.perf_counter() - started
            return result
        except Exception as error:  # noqa: BLE001 - any failure is a datapoint
            result.status = STATUS_ERROR
            result.detail = f"{type(error).__name__}: {error}"
            result.seconds = time.perf_counter() - started
            return result
        finally:
            # An engine's own warnings are first-party evidence about loss.
            result.engine_warnings = sorted(
                {str(item.message).strip() for item in captured if str(item.message).strip()}
            )
    result.seconds = time.perf_counter() - started

    if not target.exists():
        result.status = STATUS_ERROR
        result.detail = "engine reported success but wrote no file"
        return result

    report = ooxml_fidelity.audit(staged_source, target)
    before, after = report["before"], report["after"]

    result.parts_before = before["part_count"]
    result.parts_after = after["part_count"]
    result.relationships_before = before["relationship_count"]
    result.relationships_after = after["relationship_count"]
    result.issue_count = report["issue_count"]
    result.issues = report["issues"]

    semantic_drift: set[str] = set()
    for issue in report["issues"]:
        kind = issue["kind"]
        result.issues_by_kind[kind] = result.issues_by_kind.get(kind, 0) + 1
        if kind == "missing_part":
            result.parts_lost += 1
            part = issue.get("part")
            if part:
                result.lost_parts.append(part)
        elif kind == "missing_relationship":
            result.relationships_lost += 1
        elif kind.endswith("_semantic_drift"):
            semantic_drift.add(kind.removesuffix("_semantic_drift"))

    result.features_lost = _feature_losses(result.lost_parts)
    result.semantic_drift = sorted(semantic_drift)
    result.status = STATUS_FAITHFUL if result.issue_count == 0 else STATUS_CHANGED
    return result


def load_manifest(corpus: Path) -> dict[str, str]:
    """Map workbook name to tier, using the generator's manifest when present."""
    manifest_path = corpus / "manifest.json"
    if not manifest_path.exists():
        return {}
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {entry["name"]: entry.get("tier", "unknown") for entry in data.get("fixtures", [])}


def run(corpus: Path, engines: list[Engine]) -> dict:
    """Run every engine across every workbook in the corpus."""
    tiers = load_manifest(corpus)
    workbooks = sorted(
        path
        for path in corpus.iterdir()
        if path.suffix.lower() in {".xlsx", ".xlsm", ".xltx", ".xltm", ".xlsb"}
    )
    if not workbooks:
        raise SystemExit(f"no workbooks found in {corpus}; run `python3 corpus.py {corpus}` first")

    results: list[Result] = []
    with tempfile.TemporaryDirectory(prefix="fidelity-") as raw_workspace:
        workspace = Path(raw_workspace)
        for engine in engines:
            for workbook in workbooks:
                results.append(
                    run_one(engine, workbook, tiers.get(workbook.name, "unknown"), workspace)
                )

    return {
        "harness": "wolfxl round-trip fidelity harness",
        "operation": "load then save, with no edits",
        "implementation": {
            name: _sha256(Path(__file__).resolve().parent / name)
            for name in ("roundtrip.py", "engines.py", "ooxml_fidelity.py", "corpus.py")
        },
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "engines": [
            {
                "name": engine.name,
                "version": engine.version,
                "notes": engine.notes,
                "settings": engine.settings,
            }
            for engine in engines
        ],
        "corpus": {
            "workbooks": [
                {
                    "name": path.name,
                    "sha256": _sha256(path),
                    "tier": tiers.get(path.name, "unknown"),
                }
                for path in workbooks
            ],
        },
        "totals": _totals(results),
        "results": [asdict(result) for result in results],
    }


def _totals(results: list[Result]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = totals.setdefault(
            result.engine,
            {
                "workbooks": 0,
                "faithful": 0,
                "changed": 0,
                "unsupported": 0,
                "error": 0,
                "parts_lost": 0,
                "relationships_lost": 0,
            },
        )
        bucket["workbooks"] += 1
        bucket[result.status] += 1
        bucket["parts_lost"] += result.parts_lost
        bucket["relationships_lost"] += result.relationships_lost
    return totals


STATUS_MARK = {
    STATUS_FAITHFUL: "kept everything",
    STATUS_CHANGED: "package changed",
    STATUS_UNSUPPORTED: "could not open",
    STATUS_ERROR: "errored",
}


def to_markdown(report: dict) -> str:
    """Render the report as a Markdown page suitable for pasting into docs."""
    lines: list[str] = []
    lines.append("# Round-trip fidelity results")
    lines.append("")
    lines.append(
        f"Operation: **{report['operation']}**. "
        f"Generated {report['generated_at_utc']} on Python "
        f"{report['environment']['python']}, {report['environment']['machine']}."
    )
    lines.append("")

    lines.append("## Engines measured")
    lines.append("")
    lines.append("| Engine | Version | Configuration | Notes |")
    lines.append("| --- | --- | --- | --- |")
    for engine in report["engines"]:
        settings = ", ".join(f"{key}={value}" for key, value in engine["settings"].items()) or "defaults"
        lines.append(
            f"| `{engine['name']}` | {engine['version']} | {settings} | {engine['notes']} |"
        )
    lines.append("")

    lines.append("## Totals")
    lines.append("")
    lines.append("| Engine | Workbooks | Kept everything | Package changed | Could not open | Parts lost | Relationships lost |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for engine, totals in report["totals"].items():
        lines.append(
            f"| `{engine}` | {totals['workbooks']} | {totals['faithful']} | {totals['changed']} "
            f"| {totals['unsupported']} | {totals['parts_lost']} | {totals['relationships_lost']} |"
        )
    lines.append("")

    lines.append("## Per workbook")
    lines.append("")
    lines.append("| Workbook | Tier | Engine | Result | Parts | Relationships | Features lost | Semantic drift |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for result in report["results"]:
        parts = f"{result['parts_before']} to {result['parts_after']}"
        rels = f"{result['relationships_before']} to {result['relationships_after']}"
        lost = ", ".join(result["features_lost"]) or "none"
        drift = ", ".join(result["semantic_drift"]) or "none"
        detail = STATUS_MARK.get(result["status"], result["status"])
        if result["status"] in {STATUS_UNSUPPORTED, STATUS_ERROR}:
            parts = rels = "n/a"
            lost = result["detail"] or "n/a"
            drift = "n/a"
        lines.append(
            f"| `{result['workbook']}` | {result['tier']} | `{result['engine']}` "
            f"| {detail} | {parts} | {rels} | {lost} | {drift} |"
        )
    lines.append("")

    warned = [result for result in report["results"] if result["engine_warnings"]]
    if warned:
        lines.append("## Warnings the engines raised themselves")
        lines.append("")
        lines.append("Emitted by the library during the save, not by this harness.")
        lines.append("")
        for result in warned:
            for message in result["engine_warnings"]:
                lines.append(f"- `{result['engine']}` on `{result['workbook']}`: {message}")
        lines.append("")

    lost_detail = [result for result in report["results"] if result["lost_parts"]]
    if lost_detail:
        lines.append("## Parts that went missing")
        lines.append("")
        for result in lost_detail:
            lines.append(f"### `{result['engine']}` on `{result['workbook']}`")
            lines.append("")
            for part in result["lost_parts"]:
                lines.append(f"- `{part}`")
            lines.append("")

    return "\n".join(lines)


def to_text(report: dict) -> str:
    """Compact console summary."""
    lines = [f"{report['operation']}  |  {report['generated_at_utc']}", ""]
    width = max(len(result["workbook"]) for result in report["results"]) + 2
    for engine in report["engines"]:
        lines.append(f"{engine['name']} {engine['version']}")
        for result in report["results"]:
            if result["engine"] != engine["name"]:
                continue
            if result["status"] in {STATUS_UNSUPPORTED, STATUS_ERROR}:
                summary = f"{STATUS_MARK[result['status']]}: {result['detail']}"
            elif result["status"] == STATUS_FAITHFUL:
                summary = "kept everything"
            else:
                signals = result["features_lost"] + result["semantic_drift"]
                families = ", ".join(dict.fromkeys(signals)) or "package wiring"
                summary = (
                    f"{result['parts_lost']} part(s) lost, "
                    f"{result['relationships_lost']} relationship(s) lost [{families}]"
                )
            lines.append(f"  {result['workbook']:<{width}} {summary}")
        totals = report["totals"][engine["name"]]
        lines.append(
            f"  -> {totals['faithful']}/{totals['workbooks']} workbooks fully preserved, "
            f"{totals['parts_lost']} parts lost overall"
        )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", type=Path, nargs="?", default=Path("corpus"))
    parser.add_argument(
        "--engine",
        action="append",
        default=None,
        metavar="NAME",
        help="builtin name or module:factory path; repeatable",
    )
    parser.add_argument("--json", type=Path, help="write the full report as JSON")
    parser.add_argument("--markdown", type=Path, nargs="?", const=Path("-"), help="write a Markdown report")
    parser.add_argument("--fail-on-change", action="store_true", help="exit nonzero on any package difference")
    args = parser.parse_args(argv)

    specs = args.engine or ["openpyxl", "wolfxl-modify"]
    engines: list[Engine] = []
    for spec in specs:
        try:
            engines.append(load_engine(spec))
        except EngineUnavailable as error:
            print(f"skipping {spec}: {error}", file=sys.stderr)
    if not engines:
        print("no engines available; install openpyxl and/or wolfxl", file=sys.stderr)
        return 2

    report = run(args.corpus, engines)

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)
    if args.markdown is not None:
        rendered = to_markdown(report)
        if str(args.markdown) == "-":
            print(rendered)
        else:
            args.markdown.write_text(rendered + "\n", encoding="utf-8")
            print(f"wrote {args.markdown}", file=sys.stderr)
    if args.markdown is None:
        print(to_text(report))

    if args.fail_on_change and any(
        totals["changed"] or totals["error"] for totals in report["totals"].values()
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
