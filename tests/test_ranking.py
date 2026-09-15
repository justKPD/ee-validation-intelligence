from __future__ import annotations

from pathlib import Path
from statistics import fmean
from typing import Any

import pytest
from ee_domain.snapshot import ValidationSnapshot, build_snapshot
from ee_domain.visibility import visible_data
from ee_ranking import (
    DecisionContext,
    EngineeringWeights,
    RankingConfig,
    build_context,
    load_ranking_config,
    rank_engineering,
    rank_hybrid,
    rank_random,
    rank_severity,
    train_defect_model,
)
from ee_ranking.config import DEFAULT_CONFIG_PATH


@pytest.fixture(scope="module")
def ctx(snap_b004: ValidationSnapshot) -> DecisionContext:
    return build_context(snap_b004)


def test_config_validation_and_file() -> None:
    with pytest.raises(ValueError):
        EngineeringWeights(risk_exposure=0.9)
    with pytest.raises(ValueError):
        RankingConfig(hybrid_engineering=0.5, hybrid_learned=0.1)
    assert DEFAULT_CONFIG_PATH.exists() and load_ranking_config() == RankingConfig()


def test_candidates_cover_all_applicable_pairs(ctx: DecisionContext) -> None:
    snap = ctx.snapshot
    expected = {(t, v) for t in snap.tests for v in snap.test_variants.get(t, [])}
    assert {c.key for c in ctx.candidates} == expected
    for c in ctx.candidates:
        for name in (
            "risk_exposure",
            "uncovered",
            "change_relevance",
            "historical_failure",
            "dependency",
            "stale_evidence",
        ):
            assert 0.0 <= getattr(c, name) <= 1.0, (name, c)
        assert snap.build_id in c.evidence_ids


def test_engineering_ranking_is_deterministic_and_complete(ctx: DecisionContext) -> None:
    ranked = rank_engineering(ctx)
    assert ranked == rank_engineering(ctx)
    assert [r.rank for r in ranked] == list(range(1, len(ctx.candidates) + 1))
    assert len({(r.test_id, r.variant_id) for r in ranked}) == len(ranked)
    minutes = [r.cumulative_minutes for r in ranked]
    assert minutes == sorted(minutes)
    assert all(r.reasons and r.evidence_ids for r in ranked[:20])


def test_limit_returns_prefix(ctx: DecisionContext) -> None:
    assert rank_engineering(ctx, limit=15) == rank_engineering(ctx)[:15]


def test_duplicate_penalty_applies_after_coverage(ctx: DecisionContext) -> None:
    ranked = rank_engineering(ctx)
    assert ranked[0].duplicate_penalty == 0.0
    assert any(r.duplicate_penalty > 0 for r in ranked)


def test_changed_work_is_prioritised(ctx: DecisionContext) -> None:
    ranked = rank_engineering(ctx)
    changed = [r.rank for r in ranked if any("changed in" in x or "revised" in x for x in r.reasons)]
    untouched = [r.rank for r in ranked if not any("changed in" in x or "revised" in x for x in r.reasons)]
    assert changed and untouched and fmean(changed) < fmean(untouched)


def test_severity_baseline_order(ctx: DecisionContext) -> None:
    ranked = rank_severity(ctx)
    sev = [max(ctx.snapshot.requirements[r].severity for r in x.requirement_ids) for x in ranked]
    assert sev == sorted(sev, reverse=True)


def test_random_baseline_seeded(ctx: DecisionContext) -> None:
    assert rank_random(ctx, 3) == rank_random(ctx, 3)
    assert [r.test_id for r in rank_random(ctx, 3)] != [r.test_id for r in rank_random(ctx, 4)]


def test_visible_data_reproduces_past_snapshots(dataset: dict[str, list[Any]]) -> None:
    visible = visible_data(dataset, "B004")
    for b in ("B001", "B002", "B003", "B004"):
        assert build_snapshot(visible, b) == build_snapshot(dataset, b)
    assert all(e.build_id in {"B001", "B002", "B003"} for e in visible["executions"])


def test_learned_model_trains_only_on_past_builds(
    dataset: dict[str, list[Any]], ctx: DecisionContext
) -> None:
    model = train_defect_model(dataset, "B004")
    past = [e for e in dataset["executions"] if e.build_id in {"B001", "B002", "B003"}]
    assert model.trained and model.trained_on_builds == ["B001", "B002", "B003"]
    assert model.n_samples == len(past)
    probs = model.predict(ctx)
    assert set(probs) == {c.key for c in ctx.candidates}
    assert all(0.0 <= p <= 1.0 for p in probs.values())


def test_untrainable_model_falls_back_to_prior(dataset: dict[str, list[Any]]) -> None:
    model = train_defect_model(dataset, "B002", RankingConfig(min_positive_labels=10_000))
    assert not model.trained and 0 < model.prior < 1


def test_hybrid_ranking_has_learned_contribution(dataset: dict[str, list[Any]], ctx: DecisionContext) -> None:
    ranked = rank_hybrid(ctx, train_defect_model(dataset, "B004"))
    assert ranked[0].learned_probability is not None
    assert "learned_defect_probability" in ranked[0].contributions


def test_rankings_ignore_future_data(dataset: dict[str, list[Any]]) -> None:
    seq = {b.id: b.sequence for b in dataset["builds"]}
    future = {e.id for e in dataset["executions"] if seq[e.build_id] >= 4}
    tampered = dict(dataset)
    tampered["executions"] = [
        e.model_copy(update={"verdict": "FAIL"}) if e.id in future else e for e in dataset["executions"]
    ]
    tampered["defects"] = [d for d in dataset["defects"] if d.execution_id not in future]
    clean_ctx = build_context(build_snapshot(dataset, "B004"))
    dirty_ctx = build_context(build_snapshot(tampered, "B004"))
    assert rank_engineering(clean_ctx) == rank_engineering(dirty_ctx)
    assert rank_hybrid(clean_ctx, train_defect_model(dataset, "B004")) == rank_hybrid(
        dirty_ctx, train_defect_model(tampered, "B004")
    )


def test_ranking_package_never_reads_ground_truth() -> None:
    import ee_ranking

    src = Path(ee_ranking.__file__).parent
    for py in src.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "ground_truth" not in text and "ee_evaluation" not in text, py.name
