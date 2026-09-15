"""Validation intelligence endpoints (Phase 2): risk, evidence coverage, failure families, as of a build."""

from __future__ import annotations

from ee_coverage import (
    CoverageConfig,
    CoverageSummary,
    EvidenceRecord,
    EvidenceStatus,
    assess_evidence,
    summarize_coverage,
)
from ee_domain.snapshot import ValidationSnapshot, load_snapshot
from ee_failures import FailureFamily, fingerprint_failures
from ee_risk import ComponentRisk, RequirementRisk, assess_components, assess_requirements, load_risk_config
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ee_api.deps import get_session

router = APIRouter(tags=["intelligence"])


def snapshot_for(build_id: str, request: Request, db: Session = Depends(get_session)) -> ValidationSnapshot:
    cache: dict[str, ValidationSnapshot] = request.app.state.snapshots
    if build_id not in cache:
        try:
            cache[build_id] = load_snapshot(db, build_id)
        except KeyError as exc:
            raise HTTPException(404, f"build {build_id} not found") from exc
    return cache[build_id]


def _component_risks(snap: ValidationSnapshot) -> dict[str, ComponentRisk]:
    return assess_components(snap, load_risk_config())


@router.get("/builds/{build_id}/risk/components", response_model=list[ComponentRisk])
def component_risk(snap: ValidationSnapshot = Depends(snapshot_for)) -> list[ComponentRisk]:
    return sorted(_component_risks(snap).values(), key=lambda r: (-r.score, r.component_id))


@router.get("/builds/{build_id}/risk/components/{component_id}", response_model=ComponentRisk)
def component_risk_detail(
    component_id: str, snap: ValidationSnapshot = Depends(snapshot_for)
) -> ComponentRisk:
    risks = _component_risks(snap)
    if component_id not in risks:
        raise HTTPException(404, f"component {component_id} not found")
    return risks[component_id]


@router.get("/builds/{build_id}/risk/requirements", response_model=list[RequirementRisk])
def requirement_risk(
    critical_only: bool = False, snap: ValidationSnapshot = Depends(snapshot_for)
) -> list[RequirementRisk]:
    cfg = load_risk_config()
    reqs = assess_requirements(snap, assess_components(snap, cfg), cfg).values()
    return sorted(
        (r for r in reqs if r.critical or not critical_only), key=lambda r: (-r.score, r.requirement_id)
    )


@router.get("/builds/{build_id}/coverage", response_model=CoverageSummary)
def coverage_summary(snap: ValidationSnapshot = Depends(snapshot_for)) -> CoverageSummary:
    cfg = CoverageConfig(max_evidence_age_days=load_risk_config().max_evidence_age_days)
    return summarize_coverage(snap, assess_evidence(snap, cfg))


@router.get("/builds/{build_id}/evidence", response_model=list[EvidenceRecord])
def evidence(
    status: EvidenceStatus | None = None,
    variant_id: str | None = None,
    requirement_id: str | None = None,
    component_id: str | None = None,
    snap: ValidationSnapshot = Depends(snapshot_for),
) -> list[EvidenceRecord]:
    cfg = CoverageConfig(max_evidence_age_days=load_risk_config().max_evidence_age_days)
    records = assess_evidence(snap, cfg)
    return [
        r
        for r in records
        if (status is None or r.status == status)
        and (variant_id is None or r.variant_id == variant_id)
        and (requirement_id is None or r.requirement_id == requirement_id)
        and (component_id is None or component_id in snap.req_components.get(r.requirement_id, []))
    ]


@router.get("/builds/{build_id}/failure-families", response_model=list[FailureFamily])
def failure_families(
    component_id: str | None = None,
    recurring_only: bool = False,
    snap: ValidationSnapshot = Depends(snapshot_for),
) -> list[FailureFamily]:
    return [
        f
        for f in fingerprint_failures(snap)
        if (component_id is None or f.component_id == component_id) and (f.recurring or not recurring_only)
    ]
