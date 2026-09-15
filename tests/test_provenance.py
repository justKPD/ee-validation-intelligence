from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from ee_domain.db import make_engine
from ee_domain.models import Base
from ee_policies import AGENT_ACTOR, PolicyGate, load_policy
from ee_provenance import LifecycleError, NotFoundError, ProvenanceService
from ee_provenance.models import ProvenanceRecord
from sqlalchemy import update
from sqlalchemy.orm import Session


@pytest.fixture()
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'prov.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _clock() -> Iterator[datetime]:
    t = datetime(2026, 9, 15, 12, 0, 0)
    while True:
        t += timedelta(seconds=1)
        yield t


@pytest.fixture()
def svc(session: Session) -> ProvenanceService:
    ticks = _clock()
    return ProvenanceService(session, clock=lambda: next(ticks))


def _run(svc: ProvenanceService) -> str:
    return svc.create_run(
        actor="engineer_12",
        user_request="What should we validate first for B006 on V3?",
        build_id="B006",
        variant_id="V3",
        status="COMPLETED",
        response="ok",
        clarification_question=None,
        model_provider="offline",
        model_name="deterministic-planner",
        prompt_version="1.0",
        policy_version="policy-1.0",
        engine_versions={"risk": "risk-1.0"},
        trace=[{"tool": "get_ranked_tests"}],
        latency_ms=12,
    ).id


def _propose(svc: ProvenanceService, run_id: str, test_id: str = "TC-147") -> str:
    return svc.propose(
        run_id=run_id,
        build_id="B006",
        variant_id="V3",
        test_id=test_id,
        rank=1,
        priority_score=0.873,
        estimated_minutes=8.0,
        expected_coverage_gain=0.074,
        reasons=["High-risk requirement R-044 changed"],
        evidence_ids=["R-044", "B006", "D-104", "EX-00920"],
        provenance={
            "risk": {"score": 0.873},
            "agent": {"model": "deterministic-planner", "prompt_version": "1.0"},
        },
    ).id


def test_full_lifecycle_and_record(svc: ProvenanceService) -> None:
    rec_id = _propose(svc, _run(svc))
    assert rec_id == "REC-0001" and svc.get_recommendation(rec_id).status == "PROPOSED"
    svc.decide(rec_id, "APPROVED", "engineer_12", "matches change impact")
    svc.decide(rec_id, "EXECUTED", "engineer_12", execution_reference="HIL-bench-3 run 77")
    record = svc.record_for(rec_id)
    assert record["test_case"] == "TC-147" and record["sources"] == ["R-044", "B006", "D-104", "EX-00920"]
    assert record["decision"]["status"] == "EXECUTED"
    assert [h["decision"] for h in record["decision"]["history"]] == ["APPROVED", "EXECUTED"]
    assert [e["entry_type"] for e in record["ledger"]] == [
        "RECOMMENDATION_PROPOSED",
        "RECOMMENDATION_APPROVED",
        "RECOMMENDATION_EXECUTED",
    ]
    assert record["agent"]["prompt_version"] == "1.0"


@pytest.mark.parametrize(
    ("steps", "bad"),
    [
        ((), "EXECUTED"),
        (("REJECTED",), "APPROVED"),
        (("APPROVED",), "REJECTED"),
        (("APPROVED", "EXECUTED"), "APPROVED"),
    ],
)
def test_invalid_transitions_rejected(svc: ProvenanceService, steps: tuple[str, ...], bad: str) -> None:
    rec_id = _propose(svc, _run(svc))
    for s in steps:
        svc.decide(rec_id, s, "engineer_1", "reason")
    with pytest.raises(LifecycleError, match="invalid transition"):
        svc.decide(rec_id, bad, "engineer_1", "reason")


def test_rejection_requires_reason_and_reviewer(svc: ProvenanceService) -> None:
    rec_id = _propose(svc, _run(svc))
    with pytest.raises(LifecycleError, match="reason"):
        svc.decide(rec_id, "REJECTED", "engineer_1", "  ")
    with pytest.raises(LifecycleError, match="reviewer"):
        svc.decide(rec_id, "APPROVED", " ")


def test_agent_cannot_approve_its_own_recommendation(svc: ProvenanceService) -> None:
    rec_id = _propose(svc, _run(svc))
    with pytest.raises(LifecycleError, match="POLICY_DENIED"):
        svc.decide(rec_id, "APPROVED", AGENT_ACTOR)


def test_recommendation_without_evidence_is_refused(svc: ProvenanceService) -> None:
    run_id = _run(svc)
    with pytest.raises(LifecycleError, match="evidence"):
        svc.propose(
            run_id=run_id,
            build_id="B006",
            variant_id="V3",
            test_id="TC-1",
            rank=1,
            priority_score=0.5,
            estimated_minutes=1,
            expected_coverage_gain=0,
            reasons=["x"],
            evidence_ids=[],
            provenance={},
        )


def test_unknown_recommendation(svc: ProvenanceService) -> None:
    with pytest.raises(NotFoundError):
        svc.decide("REC-9999", "APPROVED", "engineer_1")


def test_policy_denials_are_persisted_and_ledgered(svc: ProvenanceService) -> None:
    run_id = _run(svc)
    gate = PolicyGate(load_policy(), sink=lambda d: svc.record_policy_decision(d, run_id))
    gate.check("read_results", "get_test_history")
    gate.check("change_test_verdict", "set_verdict")
    denied = svc.ledger(entry_type="POLICY_DENIED")
    assert len(denied) == 1 and denied[0]["payload"]["permission"] == "change_test_verdict"
    assert denied[0]["subject_id"] == run_id


def test_hash_chain_verifies_and_detects_tampering(svc: ProvenanceService, session: Session) -> None:
    rec_id = _propose(svc, _run(svc))
    svc.decide(rec_id, "REJECTED", "engineer_2", "not relevant for V3")
    assert svc.verify_chain() == (True, None)
    entries = svc.ledger()
    assert entries[0]["prev_hash"] == entries[1]["hash"]
    session.execute(
        update(ProvenanceRecord).where(ProvenanceRecord.seq == 2).values(payload='{"test_case":"TC-999"}')
    )
    ok, broken_at = svc.verify_chain()
    assert not ok and broken_at == 2
