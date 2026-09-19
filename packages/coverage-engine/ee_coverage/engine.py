"""Evidence-aware coverage: a linked test only counts if its latest result is valid *now*.

For every (requirement, applicable variant) pair, each linked test's latest non-BLOCKED execution is
classified, then the pair takes the dominant status:

    FAILED > CURRENT > STALE > INCOMPATIBLE > MISSING

- MISSING: no linked test, or no execution of a linked test on this variant
- FAILED: latest execution failed
- INCOMPATIBLE: the requirement was revised after the evidence was produced
- STALE: a linked component changed after the evidence build, or evidence is older than the age limit
- CURRENT: passing, compatible, fresh evidence
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum

from ee_domain.schemas import TestExecutionIn
from ee_domain.snapshot import ValidationSnapshot


class EvidenceStatus(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    MISSING = "MISSING"
    INCOMPATIBLE = "INCOMPATIBLE"
    FAILED = "FAILED"


_DOMINANCE = [
    EvidenceStatus.FAILED,
    EvidenceStatus.CURRENT,
    EvidenceStatus.STALE,
    EvidenceStatus.INCOMPATIBLE,
    EvidenceStatus.MISSING,
]


@dataclass(frozen=True)
class CoverageConfig:
    max_evidence_age_days: int = 35
    version: str = "coverage-1.0"


@dataclass(frozen=True)
class EvidenceRecord:
    requirement_id: str
    variant_id: str
    status: EvidenceStatus
    test_id: str | None
    execution_id: str | None
    evidence_build_id: str | None
    age_days: int | None
    reasons: list[str]


@dataclass(frozen=True)
class CoverageSummary:
    build_id: str
    requirements_total: int
    requirements_with_tests: int
    structural_coverage: float
    evidence_pairs: int
    evidence_coverage: float
    status_counts: dict[str, int]
    by_component: dict[str, dict[str, int]] = field(default_factory=dict)


def _classify(
    snap: ValidationSnapshot, rid: str, e: TestExecutionIn, cfg: CoverageConfig
) -> tuple[EvidenceStatus, int, list[str]]:
    age = (snap.as_of.release_date - e.executed_at.date()).days
    if e.verdict == "FAIL":
        return EvidenceStatus.FAILED, age, [f"latest execution {e.id} of {e.test_id} failed on {e.build_id}"]
    rev_then, rev_now = snap.requirement_revision_at(rid, e.build_id), snap.requirements[rid].revision
    if rev_then < rev_now:
        return (
            EvidenceStatus.INCOMPATIBLE,
            age,
            [f"{rid} revised r{rev_then} -> r{rev_now} after evidence {e.id}"],
        )
    ev_seq = snap.seq(e.build_id)
    reasons = [
        f"{ch.target_id} changed in {ch.build_id} after evidence build {e.build_id}"
        for ch in snap.changes
        if ch.target_type == "component"
        and ch.target_id in snap.req_components.get(rid, [])
        and snap.seq(ch.build_id) > ev_seq
    ]
    if age > cfg.max_evidence_age_days:
        reasons.append(f"evidence age {age} d exceeds {cfg.max_evidence_age_days} d")
    if reasons:
        return EvidenceStatus.STALE, age, reasons
    return EvidenceStatus.CURRENT, age, [f"passed on {e.build_id} ({age} d ago), compatible with r{rev_now}"]


def assess_evidence(snap: ValidationSnapshot, config: CoverageConfig | None = None) -> list[EvidenceRecord]:
    cfg = config or CoverageConfig()
    latest: dict[tuple[str, str], TestExecutionIn] = {}
    for e in snap.executions:  # sorted by executed_at, so later overwrites earlier
        if e.verdict != "BLOCKED":
            latest[(e.test_id, e.variant_id)] = e

    records: list[EvidenceRecord] = []
    for rid in sorted(snap.requirements):
        tests = snap.requirement_tests.get(rid, [])
        variants = sorted({v for t in tests for v in snap.test_variants.get(t, [])}) or sorted(snap.variants)
        for vid in variants:
            candidates = []
            for tid in tests:
                ex = latest.get((tid, vid))
                if ex is not None:
                    status, age, reasons = _classify(snap, rid, ex, cfg)
                    candidates.append(
                        (_DOMINANCE.index(status), -ex.executed_at.timestamp(), status, ex, age, reasons)
                    )
            if not candidates:
                reason = "no linked test" if not tests else f"no execution of linked tests on {vid}"
                records.append(
                    EvidenceRecord(rid, vid, EvidenceStatus.MISSING, None, None, None, None, [reason])
                )
                continue
            _, _, status, e, age, reasons = min(candidates, key=lambda c: (c[0], c[1], c[3].id))
            records.append(EvidenceRecord(rid, vid, status, e.test_id, e.id, e.build_id, age, reasons))
    return records


def assess_test_evidence(
    snap: ValidationSnapshot, test_id: str, variant_id: str, config: CoverageConfig | None = None
) -> list[EvidenceRecord]:
    """Evidence that one test's latest run on one variant gives each requirement it covers, as of ``snap``.

    Answers "does this test still provide valid evidence for this build and variant?" with the same rules as
    ``assess_evidence``, but for a single test instead of the best test per requirement.
    """
    cfg = config or CoverageConfig()
    latest = None
    for e in snap.executions:  # sorted by executed_at, so later overwrites earlier
        if e.test_id == test_id and e.variant_id == variant_id and e.verdict != "BLOCKED":
            latest = e
    records: list[EvidenceRecord] = []
    for rid in sorted(snap.test_requirements.get(test_id, [])):
        if latest is None:
            reason = f"{test_id} has not run on {variant_id} before {snap.build_id}"
            records.append(
                EvidenceRecord(rid, variant_id, EvidenceStatus.MISSING, test_id, None, None, None, [reason])
            )
            continue
        status, age, reasons = _classify(snap, rid, latest, cfg)
        records.append(
            EvidenceRecord(rid, variant_id, status, test_id, latest.id, latest.build_id, age, reasons)
        )
    return records


def summarize_coverage(snap: ValidationSnapshot, records: list[EvidenceRecord]) -> CoverageSummary:
    total = len(snap.requirements)
    with_tests = sum(1 for r in snap.requirements if snap.requirement_tests.get(r))
    counts = Counter(r.status.value for r in records)
    by_component: dict[str, Counter[str]] = {}
    for rec in records:
        for c in snap.req_components.get(rec.requirement_id, []):
            by_component.setdefault(c, Counter())[rec.status.value] += 1
    return CoverageSummary(
        build_id=snap.build_id,
        requirements_total=total,
        requirements_with_tests=with_tests,
        structural_coverage=round(with_tests / max(total, 1), 4),
        evidence_pairs=len(records),
        evidence_coverage=round(counts[EvidenceStatus.CURRENT.value] / max(len(records), 1), 4),
        status_counts={s.value: counts.get(s.value, 0) for s in EvidenceStatus},
        by_component={c: dict(v) for c, v in sorted(by_component.items())},
    )
