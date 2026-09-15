from __future__ import annotations

import json
from pathlib import Path

import pytest
from ee_evaluation.shadow import ALL_STRATEGIES, ShadowReport, run_shadow_benchmark, write_report
from ee_generator import generate_programme, write_programme


@pytest.fixture(scope="module")
def report(dataset_dir: Path) -> ShadowReport:
    gt = dataset_dir.parent / "ground_truth" / "ground_truth.json"
    return run_shadow_benchmark(dataset_dir, gt, random_repeats=5)


def test_all_decision_builds_evaluated(report: ShadowReport) -> None:
    assert [b.build_id for b in report.builds] == ["B002", "B003", "B004", "B005", "B006"]
    assert all(b.live_faults > 0 for b in report.builds)


def test_metrics_are_bounded_and_monotonic_in_k(report: ShadowReport) -> None:
    for b in report.builds:
        for s in ALL_STRATEGIES:
            prev_min, prev_def = -1.0, -1.0
            for k in report.ks:
                m = b.at_k[s][str(k)]
                for name in (
                    "critical_risk_coverage",
                    "critical_defect_recall",
                    "defect_recall",
                    "ndcg",
                    "map",
                    "coverage_gain",
                ):
                    assert m[name] is not None and 0.0 <= m[name] <= 1.0 + 1e-9, (b.build_id, s, k, name)
                assert m["minutes"] >= prev_min and m["expected_defects"] >= prev_def - 1e-9
                assert m["expected_defects"] <= b.live_faults
                prev_min, prev_def = m["minutes"], m["expected_defects"]


def test_budget_selections_respect_engineer_budget(report: ShadowReport) -> None:
    for b in report.builds:
        for s in ALL_STRATEGIES:
            assert b.at_engineer_budget[s]["minutes"] <= b.engineer_budget_minutes + 1e-6
        assert b.engineer["tests_selected"] > 0


def test_learned_model_uses_only_prior_builds(report: ShadowReport) -> None:
    seqs = ["B001", "B002", "B003", "B004", "B005", "B006"]
    for b in report.builds:
        assert b.model["trained_on_builds"] == seqs[: seqs.index(b.build_id)]


def test_sentence_is_derived_from_aggregate(report: ShadowReport) -> None:
    rb = report.aggregate["at_k"]["risk_based"]["10"]
    eng = report.aggregate["engineer"]
    budget = report.aggregate["at_engineer_budget"]["risk_based"]
    assert f"{rb['critical_defect_recall']:.1%}" in report.sentence
    assert f"{budget['critical_risk_coverage']:.1%}" in report.sentence
    assert f"{eng['critical_defect_recall']:.1%}" in report.sentence
    assert "seed 42" in report.sentence


def test_report_files_written(report: ShadowReport, tmp_path: Path) -> None:
    json_path, md_path = write_report(report, tmp_path)
    body = json.loads(json_path.read_text())
    assert body["sentence"] == report.sentence
    md = md_path.read_text(encoding="utf-8")
    assert "fictional" in md and report.sentence in md


def test_different_seed_gives_different_results(tmp_path: Path, report: ShadowReport) -> None:
    ds = write_programme(generate_programme(seed=7), tmp_path)
    other = run_shadow_benchmark(
        ds, tmp_path / "ground_truth" / "ground_truth.json", builds=["B003"], random_repeats=2
    )
    assert "seed 7" in other.sentence
    assert other.builds[0].engineer != report.builds[1].engineer


def test_findings_are_generated_and_consistent(report: ShadowReport) -> None:
    head, *losses = report.findings
    assert head.startswith("risk_based is best or within")
    compared = int(head.split(" of ")[1].split()[0])
    assert int(head.split(" on ")[1].split()[0]) == compared - len(losses)
    for line in losses:
        assert "beats risk_based" in line
