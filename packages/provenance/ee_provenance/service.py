"""Recommendation lifecycle, human approval and hash-chained provenance ledger.

Lifecycle: ``PROPOSED → APPROVED | REJECTED``, then ``APPROVED → EXECUTED``. Only humans decide; the agent actor is
refused here as well as by the policy gate. Every state change appends a ledger entry whose hash covers the previous
entry, so any later modification of stored history is detectable by ``verify_chain``.

The service flushes but never commits; the caller owns the transaction.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ee_policies import AGENT_ACTOR, PolicyDecision
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ee_provenance.models import AgentRun, Approval, PolicyDecisionRecord, ProvenanceRecord, Recommendation

GENESIS_HASH = "0" * 64
TRANSITIONS: dict[str, set[str]] = {"PROPOSED": {"APPROVED", "REJECTED"}, "APPROVED": {"EXECUTED"}}


class LifecycleError(ValueError):
    pass


class NotFoundError(KeyError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def entry_hash(prev_hash: str, entry_type: str, subject_id: str, at: datetime, payload: str) -> str:
    return hashlib.sha256(
        f"{prev_hash}|{entry_type}|{subject_id}|{at.isoformat()}|{payload}".encode()
    ).hexdigest()


class ProvenanceService:
    def __init__(self, session: Session, clock: Callable[[], datetime] = _now):
        self.session = session
        self.clock = clock

    # --- ids / ledger -----------------------------------------------------------------------------
    def _next_id(self, model: type[AgentRun] | type[Recommendation], prefix: str) -> str:
        n = (self.session.scalar(select(func.count()).select_from(model)) or 0) + 1
        return f"{prefix}-{n:04d}"

    def _append(self, entry_type: str, subject_id: str, payload: dict[str, Any]) -> ProvenanceRecord:
        last = self.session.scalars(
            select(ProvenanceRecord).order_by(ProvenanceRecord.seq.desc()).limit(1)
        ).first()
        prev = last.hash if last else GENESIS_HASH
        at = self.clock()
        body = canonical(payload)
        rec = ProvenanceRecord(
            entry_type=entry_type,
            subject_id=subject_id,
            at=at,
            payload=body,
            prev_hash=prev,
            hash=entry_hash(prev, entry_type, subject_id, at, body),
        )
        self.session.add(rec)
        self.session.flush()
        return rec

    def verify_chain(self) -> tuple[bool, int | None]:
        prev = GENESIS_HASH
        for rec in self.session.scalars(select(ProvenanceRecord).order_by(ProvenanceRecord.seq)):
            expected = entry_hash(prev, rec.entry_type, rec.subject_id, rec.at, rec.payload)
            if rec.prev_hash != prev or rec.hash != expected:
                return False, rec.seq
            prev = rec.hash
        return True, None

    def ledger(
        self, limit: int = 100, offset: int = 0, entry_type: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(ProvenanceRecord).order_by(ProvenanceRecord.seq.desc())
        if entry_type:
            stmt = stmt.where(ProvenanceRecord.entry_type == entry_type)
        return [
            {
                "seq": r.seq,
                "entry_type": r.entry_type,
                "subject_id": r.subject_id,
                "at": r.at.isoformat(),
                "payload": json.loads(r.payload),
                "prev_hash": r.prev_hash,
                "hash": r.hash,
            }
            for r in self.session.scalars(stmt.limit(limit).offset(offset))
        ]

    # --- agent runs and policy -----------------------------------------------------------------------
    def create_run(
        self,
        *,
        actor: str,
        user_request: str,
        build_id: str | None,
        variant_id: str | None,
        status: str,
        response: str,
        clarification_question: str | None,
        model_provider: str,
        model_name: str,
        prompt_version: str,
        policy_version: str,
        engine_versions: dict[str, str],
        trace: list[dict[str, Any]],
        latency_ms: int,
    ) -> AgentRun:
        run = AgentRun(
            id=self._next_id(AgentRun, "RUN"),
            created_at=self.clock(),
            actor=actor,
            user_request=user_request,
            build_id=build_id,
            variant_id=variant_id,
            status=status,
            response=response,
            clarification_question=clarification_question,
            model_provider=model_provider,
            model_name=model_name,
            prompt_version=prompt_version,
            policy_version=policy_version,
            engine_versions=canonical(engine_versions),
            trace=json.dumps(trace, default=str),
            latency_ms=latency_ms,
        )
        self.session.add(run)
        self.session.flush()
        self._append(
            "AGENT_RUN",
            run.id,
            {
                "status": status,
                "actor": actor,
                "user_request": user_request,
                "build_id": build_id,
                "variant_id": variant_id,
                "model": {"provider": model_provider, "name": model_name, "prompt_version": prompt_version},
                "policy_version": policy_version,
                "engine_versions": engine_versions,
            },
        )
        return run

    def record_policy_decision(self, decision: PolicyDecision, run_id: str | None) -> PolicyDecisionRecord:
        rec = PolicyDecisionRecord(
            run_id=run_id,
            at=decision.at,
            actor=decision.actor,
            tool_name=decision.tool_name,
            permission=decision.permission,
            decision=decision.decision,
            reason=decision.reason,
            policy_version=decision.policy_version,
        )
        self.session.add(rec)
        self.session.flush()
        if not decision.allowed:
            self._append(
                "POLICY_DENIED",
                run_id or "NO-RUN",
                {
                    "tool": decision.tool_name,
                    "permission": decision.permission,
                    "actor": decision.actor,
                    "reason": decision.reason,
                    "policy_version": decision.policy_version,
                },
            )
        return rec

    # --- recommendations ------------------------------------------------------------------------------
    def propose(
        self,
        *,
        run_id: str,
        build_id: str,
        variant_id: str,
        test_id: str,
        rank: int,
        priority_score: float,
        estimated_minutes: float,
        expected_coverage_gain: float,
        reasons: list[str],
        evidence_ids: list[str],
        provenance: dict[str, Any],
    ) -> Recommendation:
        if not evidence_ids:
            raise LifecycleError("a recommendation must reference evidence")
        now = self.clock()
        rec = Recommendation(
            id=self._next_id(Recommendation, "REC"),
            run_id=run_id,
            build_id=build_id,
            variant_id=variant_id,
            test_id=test_id,
            rank=rank,
            priority_score=priority_score,
            estimated_minutes=estimated_minutes,
            expected_coverage_gain=expected_coverage_gain,
            status="PROPOSED",
            reasons=json.dumps(reasons),
            evidence_ids=json.dumps(evidence_ids),
            created_at=now,
            updated_at=now,
        )
        self.session.add(rec)
        self.session.flush()
        payload = {
            "recommendation_id": rec.id,
            "run_id": run_id,
            "build": build_id,
            "variant": variant_id,
            "test_case": test_id,
            "rank": rank,
            "priority_score": priority_score,
            "estimated_minutes": estimated_minutes,
            "expected_coverage_gain": expected_coverage_gain,
            "reasons": reasons,
            "sources": evidence_ids,
            **provenance,
            "decision": {"status": "PROPOSED"},
        }
        self._append("RECOMMENDATION_PROPOSED", rec.id, payload)
        return rec

    def get_recommendation(self, recommendation_id: str) -> Recommendation:
        rec = self.session.get(Recommendation, recommendation_id)
        if rec is None:
            raise NotFoundError(recommendation_id)
        return rec

    def decide(
        self,
        recommendation_id: str,
        decision: str,
        reviewer: str,
        reason: str = "",
        execution_reference: str | None = None,
    ) -> Recommendation:
        rec = self.get_recommendation(recommendation_id)
        reviewer = reviewer.strip()
        if not reviewer:
            raise LifecycleError("a reviewer is required")
        if reviewer == AGENT_ACTOR:
            raise LifecycleError("POLICY_DENIED: the agent cannot decide on its own recommendations")
        if decision not in TRANSITIONS.get(rec.status, set()):
            raise LifecycleError(f"invalid transition {rec.status} -> {decision}")
        if decision == "REJECTED" and not reason.strip():
            raise LifecycleError("a reason is required to reject a recommendation")
        previous, rec.status, rec.updated_at = rec.status, decision, self.clock()
        self.session.add(
            Approval(
                recommendation_id=rec.id,
                decision=decision,
                reviewer=reviewer,
                reason=reason,
                at=rec.updated_at,
            )
        )
        self.session.flush()
        self._append(
            f"RECOMMENDATION_{decision}",
            rec.id,
            {
                "recommendation_id": rec.id,
                "from": previous,
                "to": decision,
                "reviewer": reviewer,
                "reason": reason,
                "execution_reference": execution_reference,
            },
        )
        return rec

    def record_for(self, recommendation_id: str) -> dict[str, Any]:
        rec = self.get_recommendation(recommendation_id)
        entries = self.session.scalars(
            select(ProvenanceRecord)
            .where(ProvenanceRecord.subject_id == recommendation_id)
            .order_by(ProvenanceRecord.seq)
        ).all()
        proposed = next(json.loads(e.payload) for e in entries if e.entry_type == "RECOMMENDATION_PROPOSED")
        decisions = self.session.scalars(
            select(Approval).where(Approval.recommendation_id == recommendation_id).order_by(Approval.id)
        ).all()
        proposed["decision"] = {
            "status": rec.status,
            "history": [
                {"decision": a.decision, "reviewer": a.reviewer, "reason": a.reason, "at": a.at.isoformat()}
                for a in decisions
            ],
        }
        proposed["ledger"] = [{"seq": e.seq, "entry_type": e.entry_type, "hash": e.hash} for e in entries]
        return proposed
