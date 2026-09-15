from __future__ import annotations

import argparse
from pathlib import Path

from ee_domain.db import REPO_ROOT

from ee_evaluation.shadow import run_shadow_benchmark, write_report

SYNTHETIC = REPO_ROOT / "data" / "synthetic"
RESULTS = REPO_ROOT / "benchmarks" / "shadow-planning" / "results"


def shadow_main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Run the Shadow Test Planning benchmark")
    p.add_argument("--dataset", type=Path, default=SYNTHETIC / "dataset")
    p.add_argument("--ground-truth", type=Path, default=SYNTHETIC / "ground_truth" / "ground_truth.json")
    p.add_argument("--out", type=Path, default=RESULTS)
    p.add_argument("--random-repeats", type=int, default=20)
    args = p.parse_args(argv)
    report = run_shadow_benchmark(args.dataset, args.ground_truth, random_repeats=args.random_repeats)
    json_path, md_path = write_report(report, args.out)
    print(report.sentence)
    print(f"Wrote {json_path} and {md_path}")
