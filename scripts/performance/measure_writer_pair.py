import argparse
import subprocess
import json
import hashlib
import zipfile
import platform
import statistics
import pathlib
import os

p = argparse.ArgumentParser()
p.add_argument("before")
p.add_argument("after")
p.add_argument("output")
p.add_argument("--large", default="formulas")
p.add_argument("--rows", default="5000")
p.add_argument("--large-rows", default="50000")
p.add_argument("--sheets", default="1")
p.add_argument("--workloads", default="numeric,repeated-strings,unique-strings,formulas")
a = p.parse_args()
os.environ["WOLFXL_BENCH_SHEETS"] = a.sheets
out = pathlib.Path(a.output).resolve()
out.mkdir(parents=True, exist_ok=True)
records = []
for workload in a.workloads.split(","):
    for i, variant in enumerate(["before", "after", "after", "before"] * 2):
        binary = getattr(a, variant)
        stem = f"{workload}-{i}-{variant}"
        xlsx = out / (stem + ".xlsx")
        rss = out / (stem + ".rss")
        cmd = [
            __import__("sys").executable,
            str(pathlib.Path(__file__).with_name("time_writer.py")),
            str(rss),
            binary,
            workload,
            a.rows,
            "20",
            "7",
            str(xlsx),
        ]
        r = subprocess.run(cmd, text=True, capture_output=True, check=True)
        (out / (stem + ".txt")).write_text(r.stdout)
        with zipfile.ZipFile(xlsx) as z:
            parts = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
        samples = [
            dict(
                zip(
                    ["round", "ns", "allocations", "allocated_bytes", "output_bytes"],
                    map(int, line.split(",")[1:]),
                )
            )
            for line in r.stdout.splitlines()
            if line.startswith("sample,")
        ]
        records.append(
            dict(
                workload=workload,
                variant=variant,
                command=cmd,
                peak_rss_kib=int(rss.read_text()),
                samples=samples,
                zip_sha256=hashlib.sha256(xlsx.read_bytes()).hexdigest(),
                parts=parts,
            )
        )
        xlsx.unlink()
for variant in ["before", "after"]:
    stem = "large-" + variant
    xlsx = out / (stem + ".xlsx")
    rss = out / (stem + ".rss")
    cmd = [
        __import__("sys").executable,
        str(pathlib.Path(__file__).with_name("time_writer.py")),
        str(rss),
        getattr(a, variant),
        a.large,
        a.large_rows,
        "20",
        "1",
        str(xlsx),
    ]
    r = subprocess.run(cmd, text=True, capture_output=True, check=True)
    (out / (stem + ".txt")).write_text(r.stdout)
    with zipfile.ZipFile(xlsx) as z:
        parts = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
    records.append(
        dict(
            workload="large-" + a.large,
            variant=variant,
            command=cmd,
            peak_rss_kib=int(rss.read_text()),
            parts=parts,
            zip_sha256=hashlib.sha256(xlsx.read_bytes()).hexdigest(),
            samples=[
                dict(
                    zip(
                        ["round", "ns", "allocations", "allocated_bytes", "output_bytes"],
                        map(int, line.split(",")[1:]),
                    )
                )
                for line in r.stdout.splitlines()
                if line.startswith("sample,")
            ],
        )
    )
    xlsx.unlink()
summary = []
for workload in dict.fromkeys(r["workload"] for r in records):
    rr = [r for r in records if r["workload"] == workload]
    row = {
        "workload": workload,
        "same_parts": all(r["parts"] == rr[0]["parts"] for r in rr),
        "same_zip": all(r["zip_sha256"] == rr[0]["zip_sha256"] for r in rr),
    }
    for variant in ["before", "after"]:
        selected = [r for r in rr if r["variant"] == variant]
        samples = [s for r in selected for s in r["samples"]]
        times = sorted(s["ns"] for s in samples)
        row[variant] = {
            "median_ms": statistics.median(times) / 1e6,
            "p95_ms": times[max(0, __import__("math").ceil(len(times) * 0.95) - 1)] / 1e6,
            "allocations": statistics.median(s["allocations"] for s in samples),
            "allocated_mib": statistics.median(s["allocated_bytes"] for s in samples) / 2**20,
            "peak_rss_kib": statistics.median(r["peak_rss_kib"] for r in selected),
            "n": len(times),
            "output_bytes": samples[0]["output_bytes"],
        }
    row["speedup"] = row["before"]["median_ms"] / row["after"]["median_ms"]
    summary.append(row)
report = {
    "machine": platform.uname()._asdict(),
    "cpu": pathlib.Path("/proc/cpuinfo").read_text().split("model name", 1)[-1].splitlines()[0],
    "env": {k: v for k, v in os.environ.items() if k.startswith("WOLFXL_")},
    "binary_sha256": {
        k: hashlib.sha256(pathlib.Path(getattr(a, k)).read_bytes()).hexdigest()
        for k in ["before", "after"]
    },
    "summary": summary,
    "runs": records,
}
(out / "report.json").write_text(json.dumps(report, indent=2))
print(json.dumps(summary, indent=2))
