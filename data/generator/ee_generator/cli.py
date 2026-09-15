from __future__ import annotations

import argparse
from pathlib import Path

from ee_generator.generator import generate_programme, write_programme

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "synthetic"


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Generate a fictional synthetic E/E validation programme")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    prog = generate_programme(args.seed)
    path = write_programme(prog, args.out)
    print(f"Generated seed={args.seed} into {path}")
    for k, v in prog.counts.items():
        print(f"  {k:24s} {v}")


if __name__ == "__main__":
    main()
