"""MCP-compatible tool registry. Every call passes the policy gate before its handler runs.

``list_tools()`` returns MCP-style descriptors (``name``, ``description``, ``inputSchema``), so the same registry can be
served by an MCP server or converted into model tool definitions.
"""

from __future__ import annotations

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
