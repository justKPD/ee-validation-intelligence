from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ee_evaluation.calibration import (
    CalibrationReport,
    bootstrap_ci,
    candidate_configs,
    expected_calibration_error,
    override_analysis,
    prediction_quality,
    reliability_curve,
    run_calibration,
    write_calibration_report,
)
from ee_ranking import RankingConfig


def test_ece_known_values() -> None:
    assert expected_calibration_error([0.25, 0.25, 0.25, 0.25], [1, 0, 0, 0]) == 0.0
    assert expected_calibration_error([0.9, 0.9], [0, 0]) == pytest.approx(0.9)
    curve = reliability_curve([0.05, 0.15, 0.95, 1.0], [0, 0, 1, 1])
    assert sum(c["count"] for c in curve) == 4 and curve[-1]["observed_rate"] == 1.0


def test_bootstrap_ci_is_deterministic_and_ordered() -> None:
    a, b = bootstrap_ci([0.1, -0.2, 0.3, 0.05, 0.0]), bootstrap_ci([0.1, -0.2, 0.3, 0.05, 0.0])
    assert a == b and a["ci_low"] <= a["mean"] <= a["ci_high"] and a["n"] == 5
    assert bootstrap_ci([0.5, 0.5, 0.5]) == {"mean": 0.5, "ci_low": 0.5, "ci_high": 0.5, "n": 3}


def test_candidate_grid_is_valid_and_unique() -> None:
    cands = candidate_configs(RankingConfig())
    assert len(cands) == 12 and len({n for n, _ in cands}) == 12
    assert all(isinstance(c, RankingConfig) for _, c in cands)


def test_prediction_quality_uses_only_observed_executions(dataset: dict[str, list[Any]]) -> None:
    q = prediction_quality(dataset, builds=["B004", "B005"])
    n = sum(1 for e in dataset["executions"] if e.build_id in {"B004", "B005"})
    scores = {s["name"]: s for s in q["scores"]}
    assert scores["learned_probability"]["n"] == n
    for s in scores.values():
        assert s["auroc"] is None or 0.0 <= s["auroc"] <= 1.0
    assert 0 <= scores["learned_probability"]["brier"] <= 1 and 0 <= scores["learned_probability"]["ece"] <= 1


def test_override_analysis_is_consistent(dataset_dir: Path) -> None:
    gt = dataset_dir.parent / "ground_truth" / "ground_truth.json"
    o = override_analysis(dataset_dir, gt, builds=["B004"])
    b = o["builds"][0]
    assert 0 <= b["jaccard"] <= 1 and 0 <= b["override_share"] <= 1
    assert b["expected_defects_engineer_only"] + b["expected_defects_shared"] >= 0
    assert b["expected_defects_ranker_only"] <= b["live_faults"]


@pytest.fixture(scope="module")
def small_report(dataset_dir: Path) -> CalibrationReport:
    gt = dataset_dir.parent / "ground_truth" / "ground_truth.json"
    configs = candidate_configs(RankingConfig())[:2]
    return run_calibration(
        dataset_dir, gt, dev_seeds=[7], configs=configs, builds=["B003", "B004"], random_repeats=1
    )


def test_tuning_never_uses_heldout_seed(small_report: CalibrationReport) -> None:
    assert small_report.heldout_seed == 42 and 42 not in small_report.tuning["dev_seeds"]
    assert small_report.tuning["best"] in small_report.tuning["objective_by_config"]


def test_report_sentence_and_files(small_report: CalibrationReport, tmp_path: Path) -> None:
    assert f"seed {small_report.heldout_seed}" in small_report.sentence
    assert small_report.findings
    tuned_path = tmp_path / "ranking.tuned.toml"
    md = write_calibration_report(small_report, tmp_path, tuned_path, RankingConfig())
    assert small_report.sentence in md.read_text(encoding="utf-8")
    assert tuned_path.exists() == small_report.tuned_improves_heldout
