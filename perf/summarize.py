"""Collect the JMeter dashboard statistics of several scenario runs into one table.

    .venv/bin/python perf/summarize.py <out_root> [scenario ...]

Reads <out_root>/<scenario>/dashboard/statistics.json (written by `jmeter -e -o`) and
prints a Markdown table; also writes <out_root>/summary.csv and summary.json.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

FIELDS = (
    ("samples", "sampleCount"),
    ("errors", "errorCount"),
    ("error_pct", "errorPct"),
    ("mean_ms", "meanResTime"),
    ("median_ms", "medianResTime"),
    ("p90_ms", "pct1ResTime"),
    ("p95_ms", "pct2ResTime"),
    ("p99_ms", "pct3ResTime"),
    ("max_ms", "maxResTime"),
    ("throughput_per_s", "throughput"),
)


def load(out_root: Path, scenario: str) -> list[dict]:
    stats = json.loads((out_root / scenario / "dashboard" / "statistics.json").read_text())
    meta = dict(
        part.split("=", 1)
        for line in (out_root / scenario / "meta.txt").read_text().split("\n")
        for part in line.split()
        if "=" in part
    )
    rows = []
    for label, s in stats.items():
        row = {"scenario": scenario, "label": label, "users": meta.get("users"),
               "backends": meta.get("backends"), "via_proxy": meta.get("via_proxy")}
        for name, key in FIELDS:
            value = s.get(key)
            row[name] = round(value, 2) if isinstance(value, float) else value
        rows.append(row)
    return rows


def main() -> None:
    out_root = Path(sys.argv[1])
    scenarios = sys.argv[2:] or sorted(p.name for p in out_root.iterdir() if (p / "dashboard").is_dir())
    rows = [r for s in scenarios for r in load(out_root, s)]
    if not rows:
        sys.exit("no dashboards found")
    with open(out_root / "summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out_root / "summary.json").write_text(json.dumps(rows, indent=2))

    cols = ["scenario", "label", "users", "samples", "error_pct", "mean_ms", "median_ms",
            "p95_ms", "p99_ms", "throughput_per_s"]
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in rows:
        print("| " + " | ".join(str(r[c]) for c in cols) + " |")


if __name__ == "__main__":
    main()
