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


RELIABILITY = REPO_ROOT / "benchmarks" / "agent-reliability" / "results"
REGRESSIONS = REPO_ROOT / "benchmarks" / "agent-reliability" / "regressions.json"


def reliability_main(argv: list[str] | None = None) -> None:
    from ee_agent import provider_from_env
    from ee_etl.importer import read_dataset

    from ee_evaluation.reliability import run_lab, write_reliability_report

    p = argparse.ArgumentParser(description="Run the Agent Reliability Lab (scenarios x k repeated runs)")
    p.add_argument("--dataset", type=Path, default=SYNTHETIC / "dataset")
    p.add_argument("-k", type=int, default=3)
    p.add_argument("--out", type=Path, default=RELIABILITY)
    args = p.parse_args(argv)
    data, _ = read_dataset(args.dataset)
    report = run_lab(data, k=args.k, provider=provider_from_env())
    json_path, md_path = write_reliability_report(report, args.out)
    print(report.sentence)
    print(f"Wrote {json_path} and {md_path}")


def adversarial_main(argv: list[str] | None = None) -> None:
    from ee_agent import provider_from_env
    from ee_etl.importer import read_dataset

    from ee_evaluation.adversarial import run_adversarial, write_adversarial_report

    p = argparse.ArgumentParser(description="Search-based adversarial testing of the agent")
    p.add_argument("--dataset", type=Path, default=SYNTHETIC / "dataset")
    p.add_argument("--budget", type=int, default=150)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, default=RELIABILITY)
    p.add_argument("--regressions", type=Path, default=REGRESSIONS)
    args = p.parse_args(argv)
    data, _ = read_dataset(args.dataset)
    report = run_adversarial(data, args.regressions, args.budget, args.seed, provider_from_env())
    md = write_adversarial_report(report, args.out)
    print(
        f"{report.mutants} mutants, {report.failures} failures, {len(report.failure_classes)} failure classes"
    )
    print(f"Regressions: {report.fixed_regressions} fixed, {report.open_regressions} open. Wrote {md}")
