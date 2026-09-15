"""Agentic-layer tables (Phases 6–8). They are NOT authoritative engineering records.

Build, variant and test ids are stored as plain strings, without foreign keys to authoritative tables, so the
append-only ledger survives dataset re-imports (ids are stable for a given seed).
"""

from __future__ import annotations

from datetime import datetime

from ee_domain.models import Base
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class AgentRun(Base):
    __tablename__ = "agent_run"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    actor: Mapped[str] = mapped_column(String(60))
    user_request: Mapped[str] = mapped_column(Text)
    build_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    variant_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(24))
    response: Mapped[str] = mapped_column(Text, default="")
    clarification_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provider: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(20))
    policy_version: Mapped[str] = mapped_column(String(20))
    engine_versions: Mapped[str] = mapped_column(Text)  # JSON object
    trace: Mapped[str] = mapped_column(Text)  # JSON list of steps and tool calls
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)


class PolicyDecisionRecord(Base):
    __tablename__ = "policy_decision"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_run.id"), nullable=True, index=True)
    at: Mapped[datetime] = mapped_column(DateTime)
    actor: Mapped[str] = mapped_column(String(60))
    tool_name: Mapped[str] = mapped_column(String(80))
    permission: Mapped[str] = mapped_column(String(60))
    decision: Mapped[str] = mapped_column(String(20), index=True)
    reason: Mapped[str] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String(20))


class Recommendation(Base):
    __tablename__ = "recommendation"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_run.id"), index=True)
    build_id: Mapped[str] = mapped_column(String(20), index=True)
    variant_id: Mapped[str] = mapped_column(String(10))
    test_id: Mapped[str] = mapped_column(String(20), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    priority_score: Mapped[float] = mapped_column(Float)
    estimated_minutes: Mapped[float] = mapped_column(Float)
    expected_coverage_gain: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), index=True)
    reasons: Mapped[str] = mapped_column(Text)  # JSON list
    evidence_ids: Mapped[str] = mapped_column(Text)  # JSON list
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class Approval(Base):
    __tablename__ = "approval"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendation.id"), index=True)
    decision: Mapped[str] = mapped_column(String(12))
    reviewer: Mapped[str] = mapped_column(String(60))
    reason: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime)


class ProvenanceRecord(Base):
    """Append-only, hash-chained ledger entry."""

    __tablename__ = "provenance_record"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_type: Mapped[str] = mapped_column(String(30), index=True)
    subject_id: Mapped[str] = mapped_column(String(40), index=True)
    at: Mapped[datetime] = mapped_column(DateTime)
    payload: Mapped[str] = mapped_column(Text)  # canonical JSON
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


AGENTIC_TABLES = [AgentRun, PolicyDecisionRecord, Recommendation, Approval, ProvenanceRecord]
