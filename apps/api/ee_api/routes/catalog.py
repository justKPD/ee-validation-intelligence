"""Read-only browse endpoints for authoritative records (ADR-002: no writes)."""

from __future__ import annotations

from typing import Any

from ee_domain import models as m
from ee_domain import schemas as s
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from ee_api.deps import get_session

router = APIRouter(tags=["catalog"])


class Page[T](BaseModel):
    total: int
    limit: int
    offset: int
    items: list[T]


def _page(
    session: Session, stmt: Select[Any], dto: type[BaseModel], limit: int, offset: int
) -> dict[str, Any]:
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(stmt.limit(limit).offset(offset)).all()
    return {"total": total, "limit": limit, "offset": offset, "items": [dto.model_validate(r) for r in rows]}


Limit = Query(100, ge=1, le=1000)
Offset = Query(0, ge=0)


class ComponentDetail(s.ComponentIn):
    upstream: list[str]
    downstream: list[str]
    requirement_ids: list[str]
    test_ids: list[str]
    defect_count: int


class BuildDetail(s.SoftwareBuildIn):
    changes: list[s.BuildChangeIn]
    execution_count: int


class RequirementDetail(s.RequirementIn):
    component_ids: list[str]
    test_ids: list[str]


class TestCaseDetail(s.TestCaseIn):
    requirement_ids: list[str]
    component_ids: list[str]
    variant_ids: list[str]


@router.get("/components", response_model=Page[s.ComponentIn])
def list_components(
    domain: str | None = None,
    asil: str | None = None,
    limit: int = Limit,
    offset: int = Offset,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    stmt = select(m.Component).order_by(m.Component.id)
    if domain:
        stmt = stmt.where(m.Component.domain == domain)
    if asil:
        stmt = stmt.where(m.Component.asil == asil)
    return _page(db, stmt, s.ComponentIn, limit, offset)


@router.get("/components/{component_id}", response_model=ComponentDetail)
def get_component(component_id: str, db: Session = Depends(get_session)) -> ComponentDetail:
    comp = db.get(m.Component, component_id)
    if comp is None:
        raise HTTPException(404, f"component {component_id} not found")
    dep = m.ComponentDependency
    return ComponentDetail(
        **s.ComponentIn.model_validate(comp).model_dump(),
        upstream=list(db.scalars(select(dep.upstream_id).where(dep.downstream_id == component_id))),
        downstream=list(db.scalars(select(dep.downstream_id).where(dep.upstream_id == component_id))),
        requirement_ids=list(
            db.scalars(
                select(m.RequirementComponent.requirement_id)
                .where(m.RequirementComponent.component_id == component_id)
                .order_by(m.RequirementComponent.requirement_id)
            )
        ),
        test_ids=list(
            db.scalars(
                select(m.TestComponent.test_id)
                .where(m.TestComponent.component_id == component_id)
                .order_by(m.TestComponent.test_id)
            )
        ),
        defect_count=db.scalar(
            select(func.count()).select_from(m.Defect).where(m.Defect.component_id == component_id)
        )
        or 0,
    )


@router.get("/requirements", response_model=Page[s.RequirementIn])
def list_requirements(
    component_id: str | None = None,
    category: str | None = None,
    min_severity: int | None = Query(None, ge=1, le=5),
    limit: int = Limit,
    offset: int = Offset,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    stmt = select(m.Requirement).order_by(m.Requirement.id)
    if component_id:
        stmt = stmt.join(
            m.RequirementComponent, m.RequirementComponent.requirement_id == m.Requirement.id
        ).where(m.RequirementComponent.component_id == component_id)
    if category:
        stmt = stmt.where(m.Requirement.category == category)
    if min_severity:
        stmt = stmt.where(m.Requirement.severity >= min_severity)
    return _page(db, stmt, s.RequirementIn, limit, offset)


@router.get("/requirements/{requirement_id}", response_model=RequirementDetail)
def get_requirement(requirement_id: str, db: Session = Depends(get_session)) -> RequirementDetail:
    req = db.get(m.Requirement, requirement_id)
    if req is None:
        raise HTTPException(404, f"requirement {requirement_id} not found")
    return RequirementDetail(
        **s.RequirementIn.model_validate(req).model_dump(),
        component_ids=list(
            db.scalars(
                select(m.RequirementComponent.component_id).where(
                    m.RequirementComponent.requirement_id == requirement_id
                )
            )
        ),
        test_ids=list(
            db.scalars(
                select(m.TestRequirement.test_id)
                .where(m.TestRequirement.requirement_id == requirement_id)
                .order_by(m.TestRequirement.test_id)
            )
        ),
    )


@router.get("/builds", response_model=list[s.SoftwareBuildIn])
def list_builds(db: Session = Depends(get_session)) -> list[s.SoftwareBuildIn]:
    return [
        s.SoftwareBuildIn.model_validate(b)
        for b in db.scalars(select(m.SoftwareBuild).order_by(m.SoftwareBuild.sequence))
    ]


@router.get("/builds/{build_id}", response_model=BuildDetail)
def get_build(build_id: str, db: Session = Depends(get_session)) -> BuildDetail:
    b = db.get(m.SoftwareBuild, build_id)
    if b is None:
        raise HTTPException(404, f"build {build_id} not found")
    changes = db.scalars(
        select(m.BuildChange).where(m.BuildChange.build_id == build_id).order_by(m.BuildChange.id)
    )
    return BuildDetail(
        **s.SoftwareBuildIn.model_validate(b).model_dump(),
        changes=[s.BuildChangeIn.model_validate(c) for c in changes],
        execution_count=db.scalar(
            select(func.count()).select_from(m.TestExecution).where(m.TestExecution.build_id == build_id)
        )
        or 0,
    )


@router.get("/variants", response_model=list[s.VehicleVariantIn])
def list_variants(db: Session = Depends(get_session)) -> list[s.VehicleVariantIn]:
    return [
        s.VehicleVariantIn.model_validate(v)
        for v in db.scalars(select(m.VehicleVariant).order_by(m.VehicleVariant.id))
    ]


@router.get("/tests", response_model=Page[s.TestCaseIn])
def list_tests(
    component_id: str | None = None,
    requirement_id: str | None = None,
    level: str | None = None,
    family: str | None = None,
    limit: int = Limit,
    offset: int = Offset,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    stmt = select(m.TestCase).order_by(m.TestCase.id)
    if component_id:
        stmt = stmt.join(m.TestComponent, m.TestComponent.test_id == m.TestCase.id).where(
            m.TestComponent.component_id == component_id
        )
    if requirement_id:
        stmt = stmt.join(m.TestRequirement, m.TestRequirement.test_id == m.TestCase.id).where(
            m.TestRequirement.requirement_id == requirement_id
        )
    if level:
        stmt = stmt.where(m.TestCase.level == level)
    if family:
        stmt = stmt.where(m.TestCase.test_family == family)
    return _page(db, stmt, s.TestCaseIn, limit, offset)


@router.get("/tests/{test_id}", response_model=TestCaseDetail)
def get_test(test_id: str, db: Session = Depends(get_session)) -> TestCaseDetail:
    t = db.get(m.TestCase, test_id)
    if t is None:
        raise HTTPException(404, f"test {test_id} not found")
    return TestCaseDetail(
        **s.TestCaseIn.model_validate(t).model_dump(),
        requirement_ids=list(
            db.scalars(select(m.TestRequirement.requirement_id).where(m.TestRequirement.test_id == test_id))
        ),
        component_ids=list(
            db.scalars(select(m.TestComponent.component_id).where(m.TestComponent.test_id == test_id))
        ),
        variant_ids=list(
            db.scalars(select(m.TestVariant.variant_id).where(m.TestVariant.test_id == test_id))
        ),
    )


@router.get("/executions", response_model=Page[s.TestExecutionIn])
def list_executions(
    build_id: str | None = None,
    variant_id: str | None = None,
    test_id: str | None = None,
    verdict: str | None = None,
    limit: int = Limit,
    offset: int = Offset,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    e = m.TestExecution
    stmt = select(e).order_by(e.executed_at, e.id)
    for col, val in [
        (e.build_id, build_id),
        (e.variant_id, variant_id),
        (e.test_id, test_id),
        (e.verdict, verdict),
    ]:
        if val:
            stmt = stmt.where(col == val)
    return _page(db, stmt, s.TestExecutionIn, limit, offset)


@router.get("/defects", response_model=Page[s.DefectIn])
def list_defects(
    component_id: str | None = None,
    build_id: str | None = None,
    status: str | None = None,
    min_severity: int | None = Query(None, ge=1, le=5),
    limit: int = Limit,
    offset: int = Offset,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    stmt = select(m.Defect).order_by(m.Defect.id)
    if build_id:
        stmt = stmt.join(m.TestExecution, m.TestExecution.id == m.Defect.execution_id).where(
            m.TestExecution.build_id == build_id
        )
    if component_id:
        stmt = stmt.where(m.Defect.component_id == component_id)
    if status:
        stmt = stmt.where(m.Defect.status == status)
    if min_severity:
        stmt = stmt.where(m.Defect.severity >= min_severity)
    return _page(db, stmt, s.DefectIn, limit, offset)


@router.get("/stats")
def stats(db: Session = Depends(get_session)) -> dict[str, int]:
    tables = {
        "components": m.Component,
        "requirements": m.Requirement,
        "test_cases": m.TestCase,
        "builds": m.SoftwareBuild,
        "variants": m.VehicleVariant,
        "build_changes": m.BuildChange,
        "executions": m.TestExecution,
        "defects": m.Defect,
    }
    return {k: db.scalar(select(func.count()).select_from(v)) or 0 for k, v in tables.items()}
