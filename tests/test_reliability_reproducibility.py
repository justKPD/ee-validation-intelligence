from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ee_evaluation.reliability import build_scenarios, run_lab, write_reliability_report


def test_committed_reliability_results_exclude_wall_clock_timing(
    dataset: dict[str, list[Any]], tmp_path: Path
) -> None:
    scenarios = build_scenarios(dataset)[:3]
    first = run_lab(dataset, k=2, scenarios=scenarios)
    second = run_lab(dataset, k=2, scenarios=scenarios)
    a, b = tmp_path / "a", tmp_path / "b"
    write_reliability_report(first, a)
    write_reliability_report(second, b)

    stable = (a / "latest.json").read_text(encoding="utf-8")
    assert "latency" not in stable
    assert stable == (b / "latest.json").read_text(encoding="utf-8")  # byte-identical across runs
    assert (a / "latest.md").read_text(encoding="utf-8") == (b / "latest.md").read_text(encoding="utf-8")

    diagnostics = json.loads((a / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["non_deterministic"] is True and len(diagnostics["runs"]) == 6
