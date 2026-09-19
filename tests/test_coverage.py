from __future__ import annotations

from typing import Any

from ee_coverage import (
    CoverageConfig,
    EvidenceStatus,
    assess_evidence,
    assess_test_evidence,
    summarize_coverage,
)
from ee_domain.snapshot import ValidationSnapshot, build_snapshot


def test_every_record_has_reasons_and_valid_status(snap_b006: ValidationSnapshot) -> None:
    records = assess_evidence(snap_b006)
    assert records
    assert all(r.reasons for r in records)
    assert {r.status for r in records} <= set(EvidenceStatus)
    assert len({(r.requirement_id, r.variant_id) for r in records}) == len(records)


def test_all_statuses_occur_on_realistic_build(snap_b006: ValidationSnapshot) -> None:
    statuses = {r.status for r in assess_evidence(snap_b006)}
    assert statuses == set(EvidenceStatus)


def test_first_build_is_all_missing(dataset: dict[str, list[Any]]) -> None:
    records = assess_evidence(build_snapshot(dataset, "B001"))
    assert {r.status for r in records} == {EvidenceStatus.MISSING}


def test_untested_requirements_are_missing(snap_b006: ValidationSnapshot) -> None:
    untested = {r for r in snap_b006.requirements if not snap_b006.requirement_tests.get(r)}
    assert untested
    for rec in assess_evidence(snap_b006):
        if rec.requirement_id in untested:
            assert rec.status == EvidenceStatus.MISSING and rec.reasons == ["no linked test"]


def test_component_changed_in_build_invalidates_current(snap_b006: ValidationSnapshot) -> None:
    changed = {c.target_id for c in snap_b006.current_changes if c.target_type == "component"}
    for rec in assess_evidence(snap_b006):
        if set(snap_b006.req_components.get(rec.requirement_id, [])) & changed:
            assert rec.status != EvidenceStatus.CURRENT


def test_requirement_revised_in_build_is_never_current_or_stale(snap_b006: ValidationSnapshot) -> None:
    revised = {c.target_id for c in snap_b006.current_changes if c.target_type == "requirement"}
    recs = [r for r in assess_evidence(snap_b006) if r.requirement_id in revised]
    assert recs
    assert all(
        r.status in {EvidenceStatus.INCOMPATIBLE, EvidenceStatus.FAILED, EvidenceStatus.MISSING} for r in recs
    )


def test_current_evidence_is_fresh_passing(snap_b006: ValidationSnapshot) -> None:
    execs = {e.id: e for e in snap_b006.executions}
    for rec in assess_evidence(snap_b006):
        if rec.status == EvidenceStatus.CURRENT:
            assert rec.execution_id is not None and rec.age_days is not None
            assert execs[rec.execution_id].verdict == "PASS" and rec.age_days <= 35


def test_zero_age_limit_removes_all_current(snap_b006: ValidationSnapshot) -> None:
    recs = assess_evidence(snap_b006, CoverageConfig(max_evidence_age_days=0))
    assert EvidenceStatus.CURRENT not in {r.status for r in recs}


def test_summary_is_consistent(snap_b006: ValidationSnapshot) -> None:
    recs = assess_evidence(snap_b006)
    summary = summarize_coverage(snap_b006, recs)
    assert sum(summary.status_counts.values()) == summary.evidence_pairs == len(recs)
    assert 0 < summary.evidence_coverage < summary.structural_coverage <= 1
    assert summary.requirements_with_tests < summary.requirements_total
    assert set(summary.by_component) <= set(snap_b006.components)


def test_single_test_evidence_uses_the_same_rules(dataset: dict[str, list[Any]]) -> None:
    snap = build_snapshot(dataset, "B006")
    recs = assess_test_evidence(snap, "TC-186", "V2")
    assert recs and all(r.test_id == "TC-186" and r.variant_id == "V2" for r in recs)
    assert {r.requirement_id for r in recs} == set(snap.test_requirements["TC-186"])
    never_ran = assess_test_evidence(snap, "TC-186", "V3")
    assert all(r.status.value == "MISSING" and r.execution_id is None for r in never_ran)
