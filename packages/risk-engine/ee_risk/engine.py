"""Deterministic risk engine. No LLM involvement; every score is a documented weighted sum.

Component factors (all in [0, 1]):

- ``base``: mean FMEA impact x occurrence x detectability / 1000 over the component's requirements
- ``recent_change``: largest change magnitude in the as-of build (requirement revisions count too)
- ``historical_failure``: Beta-smoothed defect rate over past executions, saturated
- ``dependency``: largest recent change among upstream components, attenuated
- ``evidence_staleness``: share of the component's (test, variant) pairs not executed on the previous build
- ``variant_exposure``: share of vehicle variants the component's tests apply to
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from ee_domain.schemas import RequirementIn
from ee_domain.snapshot import ValidationSnapshot

from ee_risk.config import RiskConfig

FACTORS = (
    "base",
    "recent_change",
    "historical_failure",
    "dependency",
    "evidence_staleness",
    "variant_exposure",
)


@dataclass(frozen=True)
class ComponentRisk:
    component_id: str
    build_id: str
    score: float
    base: float
    impact: float
    occurrence: float
    detectability: float
    factors: dict[str, float]
    contributions: dict[str, float]
    confidence: float
    past_executions: int
    past_defects: int
    flags: list[str]
    evidence: list[str]
    config_version: str


@dataclass(frozen=True)
class RequirementRisk:
    requirement_id: str
    build_id: str
    score: float
    fmea_base: float
    component_risk: float
    revised_in_build: bool
    critical: bool
    component_ids: list[str]


def is_critical(req: RequirementIn) -> bool:
    """Critical = high severity or high FMEA impact. Used by benchmarks for critical-risk coverage."""
    return req.severity >= 4 or req.fmea_impact >= 8


def _r(x: float) -> float:
    return round(x, 4)


def _fmea_base(req: RequirementIn) -> float:
    return req.fmea_impact * req.fmea_occurrence * req.fmea_detectability / 1000


def _recent_change(snap: ValidationSnapshot, cfg: RiskConfig) -> dict[str, float]:
    change: dict[str, float] = {c: 0.0 for c in snap.components}
    for ch in snap.current_changes:
        if ch.target_type == "component" and ch.target_id in change:
            change[ch.target_id] = max(change[ch.target_id], ch.magnitude)
        elif ch.target_type == "requirement":
            for c in snap.req_components.get(ch.target_id, []):
                change[c] = max(change[c], cfg.requirement_revision_change_signal)
    return change


def assess_components(snap: ValidationSnapshot, config: RiskConfig | None = None) -> dict[str, ComponentRisk]:
    cfg = config or RiskConfig()
    w = cfg.weights
    change = _recent_change(snap, cfg)

    runs: dict[str, int] = {c: 0 for c in snap.components}
    ran_prev: dict[str, set[tuple[str, str]]] = {c: set() for c in snap.components}
    for e in snap.executions:
        for c in snap.test_components.get(e.test_id, []):
            runs[c] += 1
            if snap.seq(e.build_id) == snap.sequence - 1:
                ran_prev[c].add((e.test_id, e.variant_id))
    defects_of: dict[str, list[str]] = {c: [] for c in snap.components}
    for d in snap.defects:
        defects_of[d.component_id].append(d.id)

    n_variants = max(len(snap.variants), 1)
    out: dict[str, ComponentRisk] = {}
    for cid in sorted(snap.components):
        reqs = [snap.requirements[r] for r in snap.component_requirements.get(cid, [])]
        tests = snap.component_tests.get(cid, [])
        pairs = {(t, v) for t in tests for v in snap.test_variants.get(t, [])}

        impact = fmean(r.fmea_impact for r in reqs) / 10 if reqs else 0.0
        occurrence = fmean(r.fmea_occurrence for r in reqs) / 10 if reqs else 0.0
        detectability = fmean(r.fmea_detectability for r in reqs) / 10 if reqs else 0.0
        base = fmean(_fmea_base(r) for r in reqs) if reqs else 0.0

        n_fail = len(defects_of[cid])
        rate = (n_fail + cfg.failure_prior_alpha) / (
            runs[cid] + cfg.failure_prior_alpha + cfg.failure_prior_beta
        )
        historical = min(1.0, rate / cfg.failure_rate_saturation)
        dependency = cfg.dependency_propagation * max(
            (change[u] for u in snap.upstream.get(cid, [])), default=0.0
        )
        no_history = snap.sequence == 1 or not pairs
        staleness = 1.0 if no_history else 1.0 - len(ran_prev[cid] & pairs) / len(pairs)
        exposure = len({v for _, v in pairs}) / n_variants

        factors = {
            "base": base,
            "recent_change": change[cid],
            "historical_failure": historical,
            "dependency": dependency,
            "evidence_staleness": staleness,
            "variant_exposure": exposure,
        }
        contributions = {k: getattr(w, k) * v for k, v in factors.items()}
        confidence = runs[cid] / (runs[cid] + cfg.confidence_half_evidence)
        flags = []
        if confidence < 0.3:
            flags.append("LOW_EVIDENCE")
        if confidence >= 0.5 and abs(occurrence - historical) > cfg.disagreement_threshold:
            flags.append("FMEA_HISTORY_DISAGREEMENT")
        evidence = [ch.id for ch in snap.current_changes if ch.target_id == cid] + sorted(defects_of[cid])[
            -5:
        ]
        out[cid] = ComponentRisk(
            component_id=cid,
            build_id=snap.build_id,
            score=_r(sum(contributions.values())),
            base=_r(base),
            impact=_r(impact),
            occurrence=_r(occurrence),
            detectability=_r(detectability),
            factors={k: _r(v) for k, v in factors.items()},
            contributions={k: _r(v) for k, v in contributions.items()},
            confidence=_r(confidence),
            past_executions=runs[cid],
            past_defects=n_fail,
            flags=flags,
            evidence=evidence,
            config_version=cfg.version,
        )
    return out


def assess_requirements(
    snap: ValidationSnapshot, component_risks: dict[str, ComponentRisk], config: RiskConfig | None = None
) -> dict[str, RequirementRisk]:
    cfg = config or RiskConfig()
    rw = cfg.requirement_weights
    revised = {ch.target_id for ch in snap.current_changes if ch.target_type == "requirement"}
    out: dict[str, RequirementRisk] = {}
    for rid in sorted(snap.requirements):
        req = snap.requirements[rid]
        comps = snap.req_components.get(rid, [])
        comp_risk = max((component_risks[c].score for c in comps), default=0.0)
        base = _fmea_base(req)
        is_rev = rid in revised
        score = rw.fmea_base * base + rw.component_risk * comp_risk + rw.revised_in_build * float(is_rev)
        out[rid] = RequirementRisk(
            requirement_id=rid,
            build_id=snap.build_id,
            score=_r(score),
            fmea_base=_r(base),
            component_risk=_r(comp_risk),
            revised_in_build=is_rev,
            critical=is_critical(req),
            component_ids=comps,
        )
    return out
