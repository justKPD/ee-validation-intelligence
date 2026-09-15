"""Candidate (test, variant) features derived from the deterministic engines, as of a build."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ee_coverage import CoverageConfig, EvidenceRecord, EvidenceStatus, assess_evidence
from ee_domain.schemas import BuildChangeIn
from ee_domain.snapshot import ValidationSnapshot
from ee_failures import FailureFamily, fingerprint_failures
from ee_risk import ComponentRisk, RequirementRisk, RiskConfig, assess_components, assess_requirements

FEATURE_NAMES = (
    "risk_exposure",
    "uncovered",
    "change_relevance",
    "historical_failure",
    "dependency",
    "stale_evidence",
    "critical",
    "failed_evidence",
    "open_failure_family",
    "max_severity",
    "duration",
)


@dataclass(frozen=True)
class CandidateFeatures:
    test_id: str
    variant_id: str
    duration_min: float
    requirement_ids: tuple[str, ...]
    component_ids: tuple[str, ...]
    max_severity: int
    critical: bool
    risk_exposure: float
    uncovered: float
    failed_evidence: bool
    change_relevance: float
    historical_failure: float
    dependency: float
    stale_evidence: float
    open_failure_family: bool
    reasons: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str]:
        return (self.test_id, self.variant_id)

    def vector(self, max_duration: float) -> list[float]:
        return [
            self.risk_exposure,
            self.uncovered,
            self.change_relevance,
            self.historical_failure,
            self.dependency,
            self.stale_evidence,
            float(self.critical),
            float(self.failed_evidence),
            float(self.open_failure_family),
            self.max_severity / 5,
            self.duration_min / max(max_duration, 1e-9),
        ]


@dataclass(frozen=True)
class DecisionContext:
    snapshot: ValidationSnapshot
    component_risk: dict[str, ComponentRisk]
    requirement_risk: dict[str, RequirementRisk]
    evidence: dict[tuple[str, str], EvidenceRecord]
    families: list[FailureFamily]
    candidates: list[CandidateFeatures]

    @property
    def build_id(self) -> str:
        return self.snapshot.build_id

    @property
    def max_duration(self) -> float:
        return max((c.duration_min for c in self.candidates), default=1.0)


def build_context(
    snap: ValidationSnapshot,
    risk_config: RiskConfig | None = None,
    coverage_config: CoverageConfig | None = None,
) -> DecisionContext:
    rcfg = risk_config or RiskConfig()
    ccfg = coverage_config or CoverageConfig(max_evidence_age_days=rcfg.max_evidence_age_days)
    comp_risk = assess_components(snap, rcfg)
    req_risk = assess_requirements(snap, comp_risk, rcfg)
    evidence = {(r.requirement_id, r.variant_id): r for r in assess_evidence(snap, ccfg)}
    families = fingerprint_failures(snap)

    open_families: dict[str, list[str]] = {}
    for f in families:
        if f.status == "OPEN":
            open_families.setdefault(f.component_id, []).append(f.id)
    exec_by_id = {e.id: e for e in snap.executions}
    runs: Counter[str] = Counter()
    last_seq: dict[tuple[str, str], int] = {}
    for e in snap.executions:
        runs[e.test_id] += 1
        key = (e.test_id, e.variant_id)
        last_seq[key] = max(last_seq.get(key, 0), snap.seq(e.build_id))
    defects_by_test: dict[str, list[str]] = {}
    for d in snap.defects:
        defects_by_test.setdefault(exec_by_id[d.execution_id].test_id, []).append(d.id)
    revised: dict[str, BuildChangeIn] = {
        ch.target_id: ch for ch in snap.current_changes if ch.target_type == "requirement"
    }
    comp_changes: dict[str, BuildChangeIn] = {
        ch.target_id: ch for ch in snap.current_changes if ch.target_type == "component"
    }

    candidates: list[CandidateFeatures] = []
    for tid in sorted(snap.tests):
        test = snap.tests[tid]
        reqs = snap.test_requirements[tid]
        comps = snap.test_components.get(tid, [])
        rrisks = [req_risk[r] for r in reqs]
        n_def = len(defects_by_test.get(tid, []))
        historical = min(1.0, ((n_def + 0.5) / (runs[tid] + 5)) / 0.3)
        change = max((comp_risk[c].factors["recent_change"] for c in comps), default=0.0)
        dependency = max((comp_risk[c].factors["dependency"] for c in comps), default=0.0)
        fams = sorted({f for c in comps for f in open_families.get(c, [])})
        for vid in snap.test_variants.get(tid, []):
            recs = [evidence[(r, vid)] for r in reqs if (r, vid) in evidence]
            non_current = [x for x in recs if x.status != EvidenceStatus.CURRENT]
            last = last_seq.get((tid, vid))
            if last is None or snap.sequence == 1:
                stale = 1.0
            else:
                stale = (snap.sequence - 1 - last) / (snap.sequence - 1)

            reasons = [
                f"requirement {r} revised to r{snap.requirements[r].revision} in {snap.build_id}"
                for r in reqs
                if r in revised
            ]
            reasons += [
                f"{c} changed in {snap.build_id} ({comp_changes[c].change_kind}, magnitude {comp_changes[c].magnitude:.2f})"
                for c in comps
                if c in comp_changes
            ]
            reasons += [f"{x.requirement_id} evidence on {vid} is {x.status.value}" for x in non_current]
            if n_def:
                reasons.append(f"test revealed {n_def} defect(s) in earlier builds")
            reasons += [f"related failure family {f} is unresolved" for f in fams]
            crit = [x.requirement_id for x in rrisks if x.critical]
            if crit:
                reasons.append("covers critical requirement(s) " + ", ".join(crit))

            evidence_ids = (
                {snap.build_id, *reqs}
                | {comp_changes[c].id for c in comps if c in comp_changes}
                | {revised[r].id for r in reqs if r in revised}
                | set(defects_by_test.get(tid, [])[-3:])
                | {x.execution_id for x in recs if x.execution_id}
            )
            candidates.append(
                CandidateFeatures(
                    test_id=tid,
                    variant_id=vid,
                    duration_min=test.duration_min,
                    requirement_ids=tuple(reqs),
                    component_ids=tuple(comps),
                    max_severity=max(snap.requirements[r].severity for r in reqs),
                    critical=bool(crit),
                    risk_exposure=max(x.score for x in rrisks),
                    uncovered=len(non_current) / len(recs) if recs else 1.0,
                    failed_evidence=any(x.status == EvidenceStatus.FAILED for x in recs),
                    change_relevance=change,
                    historical_failure=round(historical, 4),
                    dependency=dependency,
                    stale_evidence=round(stale, 4),
                    open_failure_family=bool(fams),
                    reasons=tuple(reasons),
                    evidence_ids=tuple(sorted(evidence_ids)),
                )
            )
    return DecisionContext(snap, comp_risk, req_risk, evidence, families, candidates)
