from __future__ import annotations

import argparse
from pathlib import Path

from ee_domain.db import REPO_ROOT, database_url, make_engine, redacted_url
from ee_generator import generate_programme, write_programme

from ee_etl.importer import DataQualityError, load_dataset
from ee_etl.migrate import upgrade_head
from ee_etl.report import dataset_summary_markdown

SYNTHETIC = REPO_ROOT / "data" / "synthetic"
SUMMARY = REPO_ROOT / "docs" / "methodology" / "dataset-summary.md"


def _import(dataset: Path) -> None:
    engine = make_engine()
    upgrade_head(database_url())
    try:
        result = load_dataset(dataset, engine)
    except DataQualityError as exc:
        print("IMPORT REJECTED:")
        for msg in exc.messages:
            print("  -", msg)
        raise SystemExit(1) from exc
    for w in result.quality.warnings:
        print("  warning:", w)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(dataset_summary_markdown(engine), encoding="utf-8")
    print(f"Imported {sum(result.counts.values())} records into {redacted_url()}")
    print(f"Summary written to {SUMMARY}")


def import_main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Import a synthetic dataset into the canonical database")
    p.add_argument("--dataset", type=Path, default=SYNTHETIC / "dataset")
    _import(p.parse_args(argv).dataset)


def seed_main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Generate (seeded) and import in one step")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)
    dataset = write_programme(generate_programme(args.seed), SYNTHETIC)
    _import(dataset)
