from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ee_domain.snapshot import ValidationSnapshot, build_snapshot
from ee_risk import (
    FACTORS,
    RequirementWeights,
    RiskConfig,
    RiskWeights,
    assess_components,
    assess_requirements,
    load_risk_config,
)
from ee_risk.config import DEFAULT_CONFIG_PATH


def test_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1.0"):
        RiskWeights(base=0.9)
    with pytest.raises(ValueError):
        RequirementWeights(fmea_base=0.5, component_risk=0.5, revised_in_build=0.5)


def test_repository_config_loads_and_matches_defaults() -> None:
    assert DEFAULT_CONFIG_PATH.exists()
    assert load_risk_config() == RiskConfig()


def test_config_file_overrides(tmp_path: Path) -> None:
    p = tmp_path / "risk.toml"
    p.write_text(
        'version = "custom"\n[weights]\nbase = 1.0\nrecent_change = 0\nhistorical_failure = 0\n'
        "dependency = 0\nevidence_staleness = 0\nvariant_exposure = 0\n[parameters]\ndependency_propagation = 0.5\n"
    )
    cfg = load_risk_config(p)
    assert cfg.version == "custom" and cfg.weights.base == 1.0 and cfg.dependency_propagation == 0.5


def test_scores_are_deterministic(snap_b004: ValidationSnapshot) -> None:
    assert assess_components(snap_b004) == assess_components(snap_b004)


def test_decomposition_sums_to_score_and_is_bounded(snap_b006: ValidationSnapshot) -> None:
    risks = assess_components(snap_b006)
    assert len(risks) == 40
    for r in risks.values():
        assert set(r.factors) == set(FACTORS)
        assert all(0.0 <= v <= 1.0 for v in r.factors.values()), r
        assert 0.0 <= r.score <= 1.0
        assert abs(sum(r.contributions.values()) - r.score) < 1e-3


def test_only_base_weight_means_score_equals_base(snap_b004: ValidationSnapshot) -> None:
    cfg = RiskConfig(weights=RiskWeights(1.0, 0, 0, 0, 0, 0))
    for r in assess_components(snap_b004, cfg).values():
        assert r.score == pytest.approx(r.base, abs=1e-4)


def test_changed_components_get_change_signal(snap_b004: ValidationSnapshot) -> None:
    risks = assess_components(snap_b004)
    changed = {c.target_id for c in snap_b004.current_changes if c.target_type == "component"}
    revised_comps = {
        comp
        for c in snap_b004.current_changes
        if c.target_type == "requirement"
        for comp in snap_b004.req_components.get(c.target_id, [])
    }
    assert changed
    for cid, r in risks.items():
        if cid in changed:
            assert r.factors["recent_change"] > 0
            assert r.evidence and r.evidence[0].startswith("CH-")
        elif cid not in revised_comps:
            assert r.factors["recent_change"] == 0


def test_dependency_propagates_from_changed_upstream(snap_b004: ValidationSnapshot) -> None:
    risks = assess_components(snap_b004)
    changed = {c.target_id for c in snap_b004.current_changes if c.target_type == "component"}
    downstream = {d for c in changed for d in snap_b004.downstream.get(c, [])}
    assert downstream
    assert all(risks[d].factors["dependency"] > 0 for d in downstream)


def test_first_build_has_no_change_or_evidence(dataset: dict[str, list[Any]]) -> None:
    risks = assess_components(build_snapshot(dataset, "B001"))
    assert all(r.factors["recent_change"] == 0 for r in risks.values())
    assert all(r.factors["evidence_staleness"] == 1.0 for r in risks.values())
    assert all("LOW_EVIDENCE" in r.flags for r in risks.values())


def test_history_accumulates_confidence(dataset: dict[str, list[Any]]) -> None:
    early = assess_components(build_snapshot(dataset, "B002"))
    late = assess_components(build_snapshot(dataset, "B006"))
    assert sum(r.confidence for r in late.values()) > sum(r.confidence for r in early.values())


def test_requirement_risk_and_critical_flag(snap_b006: ValidationSnapshot) -> None:
    comps = assess_components(snap_b006)
    reqs = assess_requirements(snap_b006, comps)
    assert len(reqs) == len(snap_b006.requirements)
    for rid, rr in reqs.items():
        req = snap_b006.requirements[rid]
        assert rr.critical == (req.severity >= 4 or req.fmea_impact >= 8)
        assert 0 <= rr.score <= 1
    revised = [r for r in reqs.values() if r.revised_in_build]
    assert revised and all(r.score >= 0.2 for r in revised)
