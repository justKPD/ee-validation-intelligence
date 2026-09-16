"""Fail unless freshly generated benchmark outputs reproduce the committed seed-42 stable metrics exactly.

Usage: python scripts/verify_reproduction.py <shadow_out_dir> <reliability_out_dir>

Compares only stable, deterministic fields (no wall-clock timing). Used by CI; runnable locally.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def shadow_metrics(report: dict[str, Any]) -> dict[str, Any]:
    agg = report["aggregate"]
    return {
        "seed": report["seed"],
        "random_repeats": report["random_repeats"],
        "critical_risk_coverage_at_engineers_budget": agg["at_engineer_budget"]["risk_based"][
            "critical_risk_coverage"
        ],
        "test_minutes_saved_share": agg["at_engineer_budget"]["risk_based"]["minutes_saved_share"],
        "critical_defect_recall_at_10": {
            s: agg["at_k"][s]["10"]["critical_defect_recall"]
            for s in ("risk_based", "severity_baseline", "random_baseline")
        },
        "engineer": agg["engineer"],
        "at_k": agg["at_k"],
        "at_engineer_budget": agg["at_engineer_budget"],
        "sentence": report["sentence"],
    }


def reliability_metrics(report: dict[str, Any]) -> dict[str, Any]:
    return {"metrics": report["metrics"], "pass_k": report["pass_k"], "by_category": report["by_category"]}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    shadow_dir, reliability_dir = Path(sys.argv[1]), Path(sys.argv[2])
    checks = [
        (
            "shadow planning",
            shadow_metrics(load(ROOT / "benchmarks/shadow-planning/results/latest.json")),
            shadow_metrics(load(shadow_dir / "latest.json")),
        ),
        (
            "agent reliability",
            reliability_metrics(load(ROOT / "benchmarks/agent-reliability/results/latest.json")),
            reliability_metrics(load(reliability_dir / "latest.json")),
        ),
    ]
    failed = False
    for name, committed, fresh in checks:
        if committed == fresh:
            print(f"OK   {name}: stable metrics reproduce the committed results exactly")
            continue
        failed = True
        print(f"FAIL {name}: stable metrics differ from the committed results")
        for key in committed:
            if committed[key] != fresh.get(key):
                print(f"  {key}:\n    committed: {committed[key]}\n    fresh:     {fresh.get(key)}")
    headline = shadow_metrics(load(shadow_dir / "latest.json"))
    print(
        "headline: critical_risk_coverage@budget={} minutes_saved={} CDR@10 risk/severity/random={}/{}/{}".format(
            headline["critical_risk_coverage_at_engineers_budget"],
            headline["test_minutes_saved_share"],
            *headline["critical_defect_recall_at_10"].values(),
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
