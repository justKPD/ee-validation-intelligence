"""MCP-compatible tool registry. Every call passes the policy gate before its handler runs.

``list_tools()`` returns MCP-style descriptors (``name``, ``description``, ``inputSchema``), so the same registry can be
served by an MCP server or converted into model tool definitions.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ee_coverage import EvidenceStatus, assess_test_evidence
from ee_domain.snapshot import DatasetView, build_snapshot
from ee_domain.visibility import visible_data
from ee_policies import PolicyDeniedError, PolicyGate
from ee_ranking import DecisionContext, RankingConfig, build_context, rank_engineering
from ee_risk import RiskConfig


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    permission: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]

    def descriptor(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {"permission": self.permission},
        }


class ToolUnavailableError(RuntimeError):
    """A tool could not produce a result (outage, timeout). The agent must fail safely, never guess."""


def _schema(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


BUILD = {"type": "string", "pattern": "^B\\d{3}$"}
VARIANT = {"type": "string", "pattern": "^V\\d+$"}


class ToolRegistry:
    def __init__(
        self,
        data: DatasetView,
        gate: PolicyGate,
        risk_config: RiskConfig | None = None,
        ranking_config: RankingConfig | None = None,
        faults: set[str] | None = None,
    ):
        self.data = data
        self.gate = gate
        self.faults = faults or set()
        self.risk_config = risk_config or RiskConfig()
        self.ranking_config = ranking_config or RankingConfig()
        self._contexts: dict[str, DecisionContext] = {}
        self.calls: list[dict[str, Any]] = []
        self.specs: dict[str, ToolSpec] = {s.name: s for s in self._build_specs()}

    # --- infrastructure --------------------------------------------------------------------------
    def context(self, build_id: str) -> DecisionContext:
        if build_id not in self._contexts:
            snap = build_snapshot(visible_data(self.data, build_id), build_id)
            self._contexts[build_id] = build_context(snap, self.risk_config)
        return self._contexts[build_id]

    def list_tools(self) -> list[dict[str, Any]]:
        return [s.descriptor() for s in self.specs.values()]

    def call(self, name: str, **args: Any) -> Any:
        spec = self.specs.get(name)
        permission = spec.permission if spec else f"unregistered_tool:{name}"
        try:
            self.gate.enforce(permission, name)
        except PolicyDeniedError as exc:
            self.calls.append(
                {"tool": name, "args": args, "decision": "POLICY_DENIED", "reason": exc.decision.reason}
            )
            raise
        assert spec is not None
        if name in self.faults:
            self.calls.append({"tool": name, "args": args, "decision": "ALLOWED", "error": "UNAVAILABLE"})
            raise ToolUnavailableError(name)
        result = spec.handler(**args)
        self.calls.append({"tool": name, "args": args, "decision": "ALLOWED"})
        return result

    # --- handlers --------------------------------------------------------------------------------
    def _build_changes(self, build_id: str) -> list[dict[str, Any]]:
        return [c.model_dump() for c in self.context(build_id).snapshot.current_changes]

    def _component_risk(
        self, build_id: str, component_id: str | None = None, top_n: int = 10
    ) -> list[dict[str, Any]]:
        risks = self.context(build_id).component_risk
        rows = (
            [risks[component_id]] if component_id else sorted(risks.values(), key=lambda r: -r.score)[:top_n]
        )
        return [
            {
                "component_id": r.component_id,
                "score": r.score,
                "impact": r.impact,
                "occurrence": r.occurrence,
                "detectability": r.detectability,
                "factors": r.factors,
                "flags": r.flags,
                "evidence": r.evidence,
            }
            for r in rows
        ]

    def _requirement_coverage(self, build_id: str, variant_id: str | None = None) -> dict[str, Any]:
        recs = [
            r
            for r in self.context(build_id).evidence.values()
            if variant_id is None or r.variant_id == variant_id
        ]
        counts: dict[str, int] = {s.value: 0 for s in EvidenceStatus}
        for r in recs:
            counts[r.status.value] += 1
        return {"pairs": len(recs), "status_counts": counts}

    def _evidence(self, build_id: str, requirement_id: str, variant_id: str) -> dict[str, Any]:
        rec = self.context(build_id).evidence.get((requirement_id, variant_id))
        if rec is None:
            return {"requirement_id": requirement_id, "variant_id": variant_id, "status": "UNKNOWN"}
        return {
            "requirement_id": rec.requirement_id,
            "variant_id": rec.variant_id,
            "status": rec.status.value,
            "execution_id": rec.execution_id,
            "age_days": rec.age_days,
            "reasons": rec.reasons,
        }

    def _test_evidence(self, build_id: str, test_id: str, variant_id: str | None = None) -> dict[str, Any]:
        snap = self.context(build_id).snapshot
        if test_id not in snap.tests:
            return {"test_id": test_id, "build_id": build_id, "known": False, "variants": []}
        applicable = sorted(snap.test_variants.get(test_id, []))
        asked = [variant_id] if variant_id else applicable
        out: list[dict[str, Any]] = []
        for vid in asked:
            if vid not in applicable:
                out.append({"variant_id": vid, "verdict": "NOT_APPLICABLE", "records": []})
                continue
            recs = assess_test_evidence(snap, test_id, vid)
            statuses = {r.status for r in recs}
            if statuses == {EvidenceStatus.CURRENT}:
                verdict = "VALID"
            elif statuses <= {EvidenceStatus.MISSING}:
                verdict = "NO_EVIDENCE"
            else:
                verdict = "NOT_VALID"
            out.append(
                {
                    "variant_id": vid,
                    "verdict": verdict,
                    "records": [
                        {
                            "requirement_id": r.requirement_id,
                            "status": r.status.value,
                            "execution_id": r.execution_id,
                            "evidence_build_id": r.evidence_build_id,
                            "age_days": r.age_days,
                            "reasons": r.reasons,
                            "component_ids": snap.req_components.get(r.requirement_id, []),
                        }
                        for r in recs
                    ],
                }
            )
        return {
            "test_id": test_id,
            "build_id": build_id,
            "known": True,
            "applicable_variants": applicable,
            "variants": out,
        }

    # --- read-only question handlers (the question engine answers only from these) ----------------
    def _recorded(self) -> tuple[list[Any], dict[str, Any]]:
        """All recorded executions (sorted) and defects by execution id: history, not an as-of view."""
        executions = sorted(self.data["executions"], key=lambda e: (e.executed_at, e.id))
        return executions, {d.execution_id: d for d in self.data["defects"]}

    def _test_results(
        self, test_id: str, build_id: str | None = None, variant_id: str | None = None
    ) -> dict[str, Any]:
        executions, defects = self._recorded()
        runs = []
        for e in executions:
            if e.test_id != test_id or (build_id and e.build_id != build_id):
                continue
            if variant_id and e.variant_id != variant_id:
                continue
            d = defects.get(e.id)
            runs.append(
                {
                    "execution_id": e.id,
                    "build_id": e.build_id,
                    "variant_id": e.variant_id,
                    "verdict": e.verdict,
                    "date": e.executed_at.date().isoformat(),
                    "defect_id": d.id if d else None,
                    "defect_component": d.component_id if d else None,
                    "defect_severity": d.severity if d else None,
                }
            )
        counts = Counter(r["verdict"] for r in runs)
        return {
            "test_id": test_id,
            "build_id": build_id,
            "variant_id": variant_id,
            "runs": runs,
            "verdict_counts": {v: counts.get(v, 0) for v in ("PASS", "FAIL", "BLOCKED")},
        }

    def _requirement_evidence(
        self, build_id: str, requirement_id: str, variant_id: str | None = None
    ) -> dict[str, Any]:
        ctx = self.context(build_id)
        snap = ctx.snapshot
        req = snap.requirements[requirement_id]
        keys = sorted(
            k for k in ctx.evidence if k[0] == requirement_id and (variant_id is None or k[1] == variant_id)
        )
        rows = []
        for key in keys:
            r = ctx.evidence[key]
            rows.append(
                {
                    "variant_id": r.variant_id,
                    "status": r.status.value,
                    "test_id": r.test_id,
                    "execution_id": r.execution_id,
                    "evidence_build_id": r.evidence_build_id,
                    "age_days": r.age_days,
                    "reasons": r.reasons,
                }
            )
        return {
            "requirement_id": requirement_id,
            "build_id": build_id,
            "title": req.title,
            "severity": req.severity,
            "revision": req.revision,
            "linked_tests": sorted(snap.requirement_tests.get(requirement_id, [])),
            "component_ids": snap.req_components.get(requirement_id, []),
            "variants": rows,
        }

    def _risk_explanation(self, build_id: str, component_id: str) -> dict[str, Any]:
        ctx = self.context(build_id)
        ranked = sorted(ctx.component_risk.values(), key=lambda r: (-r.score, r.component_id))
        r = ctx.component_risk[component_id]
        return {
            "component_id": component_id,
            "build_id": build_id,
            "score": r.score,
            "rank": next(i for i, x in enumerate(ranked, start=1) if x.component_id == component_id),
            "of": len(ranked),
            "contributions": sorted(r.contributions.items(), key=lambda kv: -kv[1]),
            "impact": r.impact,
            "occurrence": r.occurrence,
            "detectability": r.detectability,
            "confidence": r.confidence,
            "past_executions": r.past_executions,
            "past_defects": r.past_defects,
            "flags": r.flags,
            "changes": [
                {"id": c.id, "change_kind": c.change_kind, "magnitude": c.magnitude}
                for c in ctx.snapshot.current_changes
                if c.target_type == "component" and c.target_id == component_id
            ],
        }

    def _component_defects(self, component_id: str, build_id: str | None = None) -> dict[str, Any]:
        executions, _ = self._recorded()
        build_of = {e.id: e.build_id for e in executions}
        rows = sorted(
            (
                {
                    "defect_id": d.id,
                    "build_id": build_of.get(d.execution_id),
                    "severity": d.severity,
                    "error_code": d.error_code,
                    "title": d.title,
                }
                for d in self.data["defects"]
                if d.component_id == component_id
                and (build_id is None or build_of.get(d.execution_id) == build_id)
            ),
            key=lambda x: (x["build_id"] or "", x["defect_id"]),
        )
        return {
            "component_id": component_id,
            "build_id": build_id,
            "defects": rows,
            "by_build": dict(sorted(Counter(x["build_id"] for x in rows).items())),
            "by_severity": dict(sorted(Counter(x["severity"] for x in rows).items(), reverse=True)),
        }

    def _build_results(self, build_id: str, variant_id: str | None = None) -> dict[str, Any]:
        executions, defects = self._recorded()
        runs = [
            e
            for e in executions
            if e.build_id == build_id and (variant_id is None or e.variant_id == variant_id)
        ]
        counts = Counter(e.verdict for e in runs)
        failures = []
        for e in runs:
            if e.verdict != "FAIL":
                continue
            d = defects.get(e.id)
            failures.append(
                {
                    "test_id": e.test_id,
                    "variant_id": e.variant_id,
                    "execution_id": e.id,
                    "defect_id": d.id if d else None,
                    "defect_component": d.component_id if d else None,
                    "defect_severity": d.severity if d else None,
                }
            )
        failures.sort(key=lambda f: (-(f["defect_severity"] or 0), f["test_id"], f["variant_id"]))
        return {
            "build_id": build_id,
            "variant_id": variant_id,
            "runs": len(runs),
            "verdict_counts": {v: counts.get(v, 0) for v in ("PASS", "FAIL", "BLOCKED")},
            "failures": failures,
        }

    def _build_summary(self, build_id: str, variant_id: str | None = None) -> dict[str, Any]:
        """Headline numbers of one build: changes, evidence and risk as of its release, plus its recorded results."""
        ctx = self.context(build_id)
        recs = [r for (_, vid), r in ctx.evidence.items() if variant_id is None or vid == variant_id]
        current = sum(r.status == EvidenceStatus.CURRENT for r in recs)
        risks = sorted(ctx.component_risk.values(), key=lambda r: (-r.score, r.component_id))
        executions, defects = self._recorded()
        runs = [
            e
            for e in executions
            if e.build_id == build_id and (variant_id is None or e.variant_id == variant_id)
        ]
        verdicts = Counter(e.verdict for e in runs)
        return {
            "changes": len(ctx.snapshot.current_changes),
            "evidence_pairs": len(recs),
            "current_share": round(current / max(len(recs), 1), 4),
            "mean_risk": round(sum(r.score for r in risks) / max(len(risks), 1), 4),
            "top_component": risks[0].component_id,
            "top_score": risks[0].score,
            "runs": len(runs),
            "fail": verdicts.get("FAIL", 0),
            "blocked": verdicts.get("BLOCKED", 0),
            "defects": sum(1 for e in runs if e.id in defects),
        }

    def _compare_builds(self, build_a: str, build_b: str, variant_id: str | None = None) -> dict[str, Any]:
        a_ctx, b_ctx = self.context(build_a), self.context(build_b)
        lost = gained = 0
        for key, rb in b_ctx.evidence.items():
            if variant_id and key[1] != variant_id:
                continue
            ra = a_ctx.evidence.get(key)
            was, now = (
                ra is not None and ra.status == EvidenceStatus.CURRENT,
                rb.status == EvidenceStatus.CURRENT,
            )
            lost += was and not now
            gained += now and not was
        deltas: list[dict[str, Any]] = sorted(
            (
                {
                    "component_id": c,
                    "a": a_ctx.component_risk[c].score,
                    "b": b_ctx.component_risk[c].score,
                    "delta": round(b_ctx.component_risk[c].score - a_ctx.component_risk[c].score, 4),
                }
                for c in b_ctx.component_risk
            ),
            key=lambda d: (-d["delta"], d["component_id"]),
        )
        return {
            "build_a": build_a,
            "build_b": build_b,
            "variant_id": variant_id,
            "builds": {
                build_a: self._build_summary(build_a, variant_id),
                build_b: self._build_summary(build_b, variant_id),
            },
            "evidence_lost": lost,
            "evidence_gained": gained,
            "risk_up": [d for d in deltas if d["delta"] > 0][:3],
            "risk_down": [d for d in reversed(deltas) if d["delta"] < 0][:3],
        }

    def _risk_trend(self, build_from: str, build_to: str, component_id: str | None = None) -> dict[str, Any]:
        order = [b.id for b in sorted(self.data["builds"], key=lambda b: b.sequence)]
        span = order[order.index(build_from) : order.index(build_to) + 1]
        executions, defects = self._recorded()
        build_of = {e.id: e.build_id for e in executions}
        defects_per = Counter((d.component_id, build_of.get(d.execution_id)) for d in defects.values())
        ranked = {
            b: sorted(self.context(b).component_risk.values(), key=lambda r: (-r.score, r.component_id))
            for b in span
        }
        out: dict[str, Any] = {
            "build_from": build_from,
            "build_to": build_to,
            "component_id": component_id,
            "of": len(ranked[build_to]),
        }
        if component_id:
            out["series"] = [
                {
                    "build_id": b,
                    "score": self.context(b).component_risk[component_id].score,
                    "rank": next(
                        i for i, r in enumerate(ranked[b], start=1) if r.component_id == component_id
                    ),
                    "defects": defects_per.get((component_id, b), 0),
                }
                for b in span
            ]
            return out
        first, last = self.context(build_from).component_risk, self.context(build_to).component_risk
        deltas: list[dict[str, Any]] = sorted(
            (
                {
                    "component_id": c,
                    "a": first[c].score,
                    "b": last[c].score,
                    "delta": round(last[c].score - first[c].score, 4),
                }
                for c in last
            ),
            key=lambda d: (-d["delta"], d["component_id"]),
        )
        out.update(
            {
                "n_worse": sum(d["delta"] > 0 for d in deltas),
                "n_better": sum(d["delta"] < 0 for d in deltas),
                "worse": [d for d in deltas if d["delta"] > 0][:5],
                "better": [d for d in reversed(deltas) if d["delta"] < 0][:3],
                "riskiest": {
                    "component_id": ranked[build_to][0].component_id,
                    "score": ranked[build_to][0].score,
                },
            }
        )
        return out

    def _test_history(self, build_id: str, test_id: str) -> list[dict[str, Any]]:
        snap = self.context(build_id).snapshot
        defects = {d.execution_id: d.id for d in snap.defects}
        return [
            {
                "execution_id": e.id,
                "build_id": e.build_id,
                "variant_id": e.variant_id,
                "verdict": e.verdict,
                "defect_id": defects.get(e.id),
            }
            for e in snap.executions
            if e.test_id == test_id
        ]

    def _failure_families(self, build_id: str, component_id: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "id": f.id,
                "component_id": f.component_id,
                "occurrences": f.occurrences,
                "status": f.status,
                "title": f.representative_title,
                "defect_ids": f.defect_ids,
            }
            for f in self.context(build_id).families
            if component_id is None or f.component_id == component_id
        ]

    def _ranked_tests(
        self,
        build_id: str,
        variant_id: str | None = None,
        top_n: int = 10,
        budget_minutes: float | None = None,
        component_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        ranked = rank_engineering(self.context(build_id), self.ranking_config)
        if variant_id:
            ranked = [r for r in ranked if r.variant_id == variant_id]
        if component_ids:
            focused = [r for r in ranked if set(r.component_ids) & set(component_ids)]
            ranked = focused or ranked
        out, used = [], 0.0
        for r in ranked:
            if budget_minutes is not None and used + r.duration_min > budget_minutes:
                continue
            out.append(r)
            used += r.duration_min
            if len(out) >= top_n:
                break
        return [r.__dict__ | {"cumulative_minutes": None} for r in out]

    def _propose_plan(
        self,
        build_id: str,
        variant_id: str | None,
        top_n: int = 5,
        budget_minutes: float | None = None,
        component_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        ctx = self.context(build_id)
        need = {k for k, rec in ctx.evidence.items() if rec.status != EvidenceStatus.CURRENT}
        plan = self._ranked_tests(build_id, variant_id, top_n, budget_minutes, component_ids)
        for item in plan:
            pairs = {(r, item["variant_id"]) for r in item["requirement_ids"]}
            item["expected_coverage_gain"] = round(len(pairs & need) / max(len(need), 1), 4)
        return plan

    def _prohibited(self, **_: Any) -> Any:  # pragma: no cover - unreachable: gate denies first
        raise RuntimeError("prohibited tool handler must never execute")

    def _build_specs(self) -> list[ToolSpec]:
        s = _schema
        return [
            ToolSpec(
                "get_build_changes",
                "Component changes and requirement revisions in a build.",
                "read_requirements",
                s({"build_id": BUILD}, ["build_id"]),
                self._build_changes,
            ),
            ToolSpec(
                "get_component_risk",
                "Deterministic, decomposed component risk as of a build.",
                "read_risk",
                s(
                    {"build_id": BUILD, "component_id": {"type": "string"}, "top_n": {"type": "integer"}},
                    ["build_id"],
                ),
                self._component_risk,
            ),
            ToolSpec(
                "get_requirement_coverage",
                "Evidence status counts (CURRENT/STALE/MISSING/INCOMPATIBLE/FAILED).",
                "read_coverage",
                s({"build_id": BUILD, "variant_id": VARIANT}, ["build_id"]),
                self._requirement_coverage,
            ),
            ToolSpec(
                "get_evidence",
                "Evidence record for one requirement on one variant.",
                "read_coverage",
                s(
                    {"build_id": BUILD, "requirement_id": {"type": "string"}, "variant_id": VARIANT},
                    ["build_id", "requirement_id", "variant_id"],
                ),
                self._evidence,
            ),
            ToolSpec(
                "get_test_evidence",
                "Whether one test's latest run gives valid evidence for a build and variant, per requirement.",
                "read_coverage",
                s(
                    {"build_id": BUILD, "test_id": {"type": "string"}, "variant_id": VARIANT},
                    ["build_id", "test_id"],
                ),
                self._test_evidence,
            ),
            ToolSpec(
                "get_test_results",
                "Recorded runs of one test (optionally for a build and variant) with their defects.",
                "read_results",
                s(
                    {"test_id": {"type": "string"}, "build_id": BUILD, "variant_id": VARIANT},
                    ["test_id"],
                ),
                self._test_results,
            ),
            ToolSpec(
                "get_requirement_evidence",
                "Evidence status of one requirement per variant as of a build, with linked tests.",
                "read_coverage",
                s(
                    {"build_id": BUILD, "requirement_id": {"type": "string"}, "variant_id": VARIANT},
                    ["build_id", "requirement_id"],
                ),
                self._requirement_evidence,
            ),
            ToolSpec(
                "explain_component_risk",
                "Why a component has its risk score: contributions, rank, changes and history.",
                "explain_risk",
                s({"build_id": BUILD, "component_id": {"type": "string"}}, ["build_id", "component_id"]),
                self._risk_explanation,
            ),
            ToolSpec(
                "get_component_defects",
                "Recorded defects of one component, optionally for one build.",
                "read_failures",
                s({"component_id": {"type": "string"}, "build_id": BUILD}, ["component_id"]),
                self._component_defects,
            ),
            ToolSpec(
                "get_build_results",
                "Recorded verdict counts and failed runs of a build, optionally for one variant.",
                "read_results",
                s({"build_id": BUILD, "variant_id": VARIANT}, ["build_id"]),
                self._build_results,
            ),
            ToolSpec(
                "compare_builds",
                "Compare two builds: changes, current evidence, risk and recorded results, with biggest risk movers.",
                "read_coverage",
                s({"build_a": BUILD, "build_b": BUILD, "variant_id": VARIANT}, ["build_a", "build_b"]),
                self._compare_builds,
            ),
            ToolSpec(
                "get_risk_trend",
                "Component risk as of every build in a range: one component's history, or the biggest risers and fallers.",
                "read_risk",
                s(
                    {"build_from": BUILD, "build_to": BUILD, "component_id": {"type": "string"}},
                    ["build_from", "build_to"],
                ),
                self._risk_trend,
            ),
            ToolSpec(
                "get_test_history",
                "Past executions and linked defects of a test.",
                "read_results",
                s({"build_id": BUILD, "test_id": {"type": "string"}}, ["build_id", "test_id"]),
                self._test_history,
            ),
            ToolSpec(
                "get_failure_families",
                "Recurring failure fingerprint families.",
                "read_failures",
                s({"build_id": BUILD, "component_id": {"type": "string"}}, ["build_id"]),
                self._failure_families,
            ),
            ToolSpec(
                "get_ranked_tests",
                "Risk-based ranked (test, variant) candidates.",
                "read_risk",
                s(
                    {
                        "build_id": BUILD,
                        "variant_id": VARIANT,
                        "top_n": {"type": "integer"},
                        "budget_minutes": {"type": "number"},
                    },
                    ["build_id"],
                ),
                self._ranked_tests,
            ),
            ToolSpec(
                "propose_test_plan",
                "Propose a test plan; recommendations are stored as PROPOSED for human review.",
                "propose_test_plan",
                s(
                    {
                        "build_id": BUILD,
                        "variant_id": VARIANT,
                        "top_n": {"type": "integer"},
                        "budget_minutes": {"type": "number"},
                    },
                    ["build_id"],
                ),
                self._propose_plan,
            ),
            ToolSpec(
                "update_requirement",
                "Modify an authoritative requirement.",
                "modify_requirement",
                s({"requirement_id": {"type": "string"}}, ["requirement_id"]),
                self._prohibited,
            ),
            ToolSpec(
                "update_test_case",
                "Rewrite an authoritative test definition.",
                "modify_test_case",
                s({"test_id": {"type": "string"}}, ["test_id"]),
                self._prohibited,
            ),
            ToolSpec(
                "set_test_verdict",
                "Change a PASS/FAIL verdict.",
                "change_test_verdict",
                s({"execution_id": {"type": "string"}}, ["execution_id"]),
                self._prohibited,
            ),
            ToolSpec(
                "close_defect",
                "Close a defect.",
                "close_defect",
                s({"defect_id": {"type": "string"}}, ["defect_id"]),
                self._prohibited,
            ),
            ToolSpec(
                "approve_release",
                "Approve a software release.",
                "approve_release",
                s({"build_id": BUILD}, ["build_id"]),
                self._prohibited,
            ),
            ToolSpec(
                "approve_recommendation",
                "Approve a recommendation.",
                "approve_recommendation",
                s({"recommendation_id": {"type": "string"}}, ["recommendation_id"]),
                self._prohibited,
            ),
            ToolSpec(
                "execute_test",
                "Execute a test on a bench or vehicle.",
                "execute_test",
                s({"test_id": {"type": "string"}}, ["test_id"]),
                self._prohibited,
            ),
        ]
