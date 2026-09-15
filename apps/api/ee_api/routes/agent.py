"""Agentic Test Planner, recommendation lifecycle, provenance ledger and policy (Phases 6–8).

These are the only write endpoints. They write the agentic layer (runs, recommendations, approvals, ledger),
never authoritative engineering records (ADR-002).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from ee_agent import TestPlanningAgent, provider_from_env
from ee_domain.snapshot import load_dataset_view
from ee_policies import load_policy
from ee_provenance import LifecycleError, NotFoundError, ProvenanceService
from ee_provenance.models import AgentRun, PolicyDecisionRecord, Recommendation
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ee_api.deps import get_session

router = APIRouter(tags=["agent"])


class PlanRequest(BaseModel):
    request: str = Field(min_length=3, max_length=2000)
    actor: str = Field("engineer", min_length=1, max_length=60)


class DecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "EXECUTED"]
    reviewer: str = Field(min_length=1, max_length=60)
    reason: str = ""
    execution_reference: str | None = None


def agent_for(request: Request, db: Session = Depends(get_session)) -> TestPlanningAgent:
    if request.app.state.agent is None:
        if request.app.state.dataset_view is None:
            request.app.state.dataset_view = load_dataset_view(db)
        request.app.state.agent = TestPlanningAgent(request.app.state.dataset_view, provider_from_env())
    agent: TestPlanningAgent = request.app.state.agent
    return agent


def _run_out(run: AgentRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "created_at": run.created_at.isoformat(),
        "actor": run.actor,
        "user_request": run.user_request,
        "build_id": run.build_id,
        "variant_id": run.variant_id,
        "status": run.status,
        "response": run.response,
        "clarification_question": run.clarification_question,
        "model": {
            "provider": run.model_provider,
            "name": run.model_name,
            "prompt_version": run.prompt_version,
        },
        "policy_version": run.policy_version,
        "latency_ms": run.latency_ms,
        "trace": json.loads(run.trace),
    }


def _rec_out(rec: Recommendation) -> dict[str, Any]:
    return {
        "id": rec.id,
        "run_id": rec.run_id,
        "build_id": rec.build_id,
        "variant_id": rec.variant_id,
        "test_id": rec.test_id,
        "rank": rec.rank,
        "priority_score": rec.priority_score,
        "estimated_minutes": rec.estimated_minutes,
        "expected_coverage_gain": rec.expected_coverage_gain,
        "status": rec.status,
        "reasons": json.loads(rec.reasons),
        "evidence_ids": json.loads(rec.evidence_ids),
        "created_at": rec.created_at.isoformat(),
        "updated_at": rec.updated_at.isoformat(),
    }


@router.post("/agent/plan")
def plan(
    body: PlanRequest, agent: TestPlanningAgent = Depends(agent_for), db: Session = Depends(get_session)
) -> dict[str, Any]:
    result = agent.run(body.request, db, actor=body.actor)
    db.commit()
    return result.__dict__


@router.get("/agent/runs")
def runs(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [
        _run_out(r)
        for r in db.scalars(
            select(AgentRun).order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).limit(limit)
        )
    ]


@router.get("/agent/runs/{run_id}")
def run_detail(run_id: str, db: Session = Depends(get_session)) -> dict[str, Any]:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(404, f"run {run_id} not found")
    out = _run_out(run)
    out["recommendations"] = [
        _rec_out(r)
        for r in db.scalars(
            select(Recommendation).where(Recommendation.run_id == run_id).order_by(Recommendation.rank)
        )
    ]
    return out


@router.get("/agent/tools")
def agent_tools(agent: TestPlanningAgent = Depends(agent_for)) -> list[dict[str, Any]]:
    from ee_agent import ToolRegistry
    from ee_policies import PolicyGate

    return ToolRegistry(agent.data, PolicyGate(agent.policy)).list_tools()


@router.get("/recommendations")
def recommendations(
    status: str | None = None,
    build_id: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(Recommendation).order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
    if status:
        stmt = stmt.where(Recommendation.status == status)
    if build_id:
        stmt = stmt.where(Recommendation.build_id == build_id)
    return [_rec_out(r) for r in db.scalars(stmt.limit(limit))]


@router.get("/recommendations/{recommendation_id}")
def recommendation_record(recommendation_id: str, db: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        return ProvenanceService(db).record_for(recommendation_id)
    except NotFoundError as exc:
        raise HTTPException(404, f"recommendation {recommendation_id} not found") from exc


@router.post("/recommendations/{recommendation_id}/decision")
def decide(
    recommendation_id: str, body: DecisionRequest, db: Session = Depends(get_session)
) -> dict[str, Any]:
    svc = ProvenanceService(db)
    try:
        rec = svc.decide(
            recommendation_id, body.decision, body.reviewer, body.reason, body.execution_reference
        )
    except NotFoundError as exc:
        raise HTTPException(404, f"recommendation {recommendation_id} not found") from exc
    except LifecycleError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    return _rec_out(rec)


@router.get("/provenance/ledger")
def ledger(
    entry_type: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return ProvenanceService(db).ledger(limit, offset, entry_type)


@router.get("/provenance/verify")
def verify(db: Session = Depends(get_session)) -> dict[str, Any]:
    ok, broken_at = ProvenanceService(db).verify_chain()
    return {"valid": ok, "broken_at_seq": broken_at}


@router.get("/policy")
def policy() -> dict[str, Any]:
    p = load_policy()
    return {"version": p.version, "permissions": p.permissions, "autonomy": p.autonomy}


@router.get("/policy/decisions")
def policy_decisions(
    decision: str | None = None, limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    stmt = select(PolicyDecisionRecord).order_by(PolicyDecisionRecord.id.desc())
    if decision:
        stmt = stmt.where(PolicyDecisionRecord.decision == decision)
    return [
        {
            "id": d.id,
            "run_id": d.run_id,
            "at": d.at.isoformat(),
            "actor": d.actor,
            "tool": d.tool_name,
            "permission": d.permission,
            "decision": d.decision,
            "reason": d.reason,
            "policy_version": d.policy_version,
        }
        for d in db.scalars(stmt.limit(limit))
    ]
