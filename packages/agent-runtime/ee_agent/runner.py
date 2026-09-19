"""LangGraph orchestration of the Agentic Test Planner.

interpret ─┬─ refuse   (prohibited intent / injection → attempted tool is POLICY_DENIED and logged)
           ├─ clarify  (ambiguous or unknown build / variant / component / test)
           ├─ answer   (read-only evidence question about one test → grounded answer, nothing proposed)
           └─ gather → plan → explain → persist (recommendations stored as PROPOSED)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, TypedDict

from ee_domain.snapshot import DatasetView
from ee_policies import PolicyDecision, PolicyDeniedError, PolicyGate, load_policy
from ee_provenance import ProvenanceService
from ee_ranking import RankingConfig, load_ranking_config
from ee_risk import RiskConfig, load_risk_config
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from ee_agent.interpret import Interpretation, interpret_request
from ee_agent.providers import Explanation, ModelProvider, OfflineProvider
from ee_agent.tools import ToolRegistry, ToolUnavailableError

PROMPT_VERSION = "1.0"


class PlannerState(TypedDict, total=False):
    request: str
    interpretation: Interpretation
    risk: list[dict[str, Any]]
    coverage: dict[str, Any]
    changes: list[dict[str, Any]]
    plan: list[dict[str, Any]]
    explanation: Explanation
    answer: dict[str, Any]
    status: str
    response: str
    error: str


@dataclass
class AgentResult:
    run_id: str
    status: str
    response: str
    clarification_question: str | None
    build_id: str | None
    variant_id: str | None
    recommendations: list[dict[str, Any]]
    policy_decisions: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    model: dict[str, str]
    grounded: bool
    latency_ms: int
    trace: list[str] = field(default_factory=list)
    answer: dict[str, Any] | None = None  # evidence answer for ANSWERED runs


class TestPlanningAgent:
    __test__ = False

    def __init__(
        self,
        data: DatasetView,
        provider: ModelProvider | None = None,
        risk_config: RiskConfig | None = None,
        ranking_config: RankingConfig | None = None,
    ):
        self.data = data
        self.provider = provider or OfflineProvider()
        self.policy = load_policy()
        self.risk_config = risk_config or load_risk_config()
        self.ranking_config = ranking_config or load_ranking_config()
        self.builds = [b.id for b in sorted(data["builds"], key=lambda b: b.sequence)]
        self.variants = sorted(v.id for v in data["variants"])
        self.components = sorted(c.id for c in data["components"])
        self.tests = sorted(t.id for t in data["test_cases"])

    def run(
        self, request: str, session: Session, actor: str = "engineer", tool_faults: set[str] | None = None
    ) -> AgentResult:
        started = time.perf_counter()
        decisions: list[PolicyDecision] = []
        gate = PolicyGate(self.policy, sink=decisions.append)
        tools = ToolRegistry(self.data, gate, self.risk_config, self.ranking_config, tool_faults)
        trace: list[str] = []
        graph = self._graph(tools, trace)
        state: PlannerState = graph.invoke({"request": request})
        it = state["interpretation"]

        svc = ProvenanceService(session)
        explanation = state.get("explanation")
        run = svc.create_run(
            actor=actor,
            user_request=request,
            build_id=it.build_id,
            variant_id=it.variant_id,
            status=state["status"],
            response=state["response"],
            clarification_question=it.clarification if state["status"] == "NEEDS_CLARIFICATION" else None,
            model_provider=explanation.provider if explanation else self.provider.name,
            model_name=explanation.model if explanation else self.provider.model,
            prompt_version=PROMPT_VERSION,
            policy_version=self.policy.version,
            engine_versions={"risk": self.risk_config.version, "ranking": self.ranking_config.version},
            trace=[*({"step": s} for s in trace), *tools.calls],
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        for d in decisions:
            svc.record_policy_decision(d, run.id)

        recommendations = []
        if state["status"] == "COMPLETED":
            risks = {r["component_id"]: r for r in state.get("risk", [])}
            for item in state["plan"]:
                comp = max(
                    (risks[c] for c in item["component_ids"] if c in risks),
                    key=lambda r: r["score"],
                    default=None,
                )
                rec = svc.propose(
                    run_id=run.id,
                    build_id=it.build_id or "",
                    variant_id=item["variant_id"],
                    test_id=item["test_id"],
                    rank=item["rank"],
                    priority_score=item["score"],
                    estimated_minutes=item["duration_min"],
                    expected_coverage_gain=item["expected_coverage_gain"],
                    reasons=item["reasons"],
                    evidence_ids=item["evidence_ids"],
                    provenance={
                        "risk": None
                        if comp is None
                        else {
                            k: comp[k]
                            for k in ("component_id", "score", "impact", "occurrence", "detectability")
                        },
                        "signals": {
                            "changed_requirement": any("revised" in r for r in item["reasons"]),
                            "changed_component": any("changed in" in r for r in item["reasons"]),
                            "ranking_contributions": item["contributions"],
                            "critical": item["critical"],
                        },
                        "agent": {
                            "model": run.model_name,
                            "provider": run.model_provider,
                            "prompt_version": PROMPT_VERSION,
                            "policy_version": self.policy.version,
                            "risk_config": self.risk_config.version,
                            "ranking_config": self.ranking_config.version,
                        },
                        "user_request": request,
                    },
                )
                recommendations.append(
                    {
                        "recommendation_id": rec.id,
                        **{
                            k: item[k]
                            for k in (
                                "rank",
                                "test_id",
                                "variant_id",
                                "score",
                                "duration_min",
                                "expected_coverage_gain",
                                "reasons",
                                "evidence_ids",
                            )
                        },
                    }
                )

        return AgentResult(
            run_id=run.id,
            status=state["status"],
            response=state["response"],
            clarification_question=run.clarification_question,
            build_id=it.build_id,
            variant_id=it.variant_id,
            recommendations=recommendations,
            policy_decisions=[
                {"tool": d.tool_name, "permission": d.permission, "decision": d.decision, "reason": d.reason}
                for d in decisions
            ],
            tool_calls=tools.calls,
            model={"provider": run.model_provider, "name": run.model_name, "prompt_version": PROMPT_VERSION},
            grounded=explanation.grounded if explanation else True,
            latency_ms=run.latency_ms,
            trace=trace,
            answer=state.get("answer"),
        )

    def _graph(self, tools: ToolRegistry, trace: list[str]) -> Any:
        agent = self

        def interpret(state: PlannerState) -> PlannerState:
            trace.append("interpret")
            return {
                "interpretation": interpret_request(
                    state["request"], agent.builds, agent.variants, agent.components, agent.tests
                )
            }

        def route(state: PlannerState) -> str:
            return state["interpretation"].action

        def refuse(state: PlannerState) -> PlannerState:
            trace.append("refuse")
            it = state["interpretation"]
            reasons = []
            for _permission, tool in it.prohibited:
                try:
                    tools.call(tool, **{k: "REQUESTED" for k in tools.specs[tool].input_schema["required"]})
                except PolicyDeniedError as exc:
                    reasons.append(str(exc))
            if it.injection:
                gate_decision = tools.gate.check("override_policy", "policy_override")
                reasons.append(
                    f"POLICY_DENIED: {gate_decision.reason} (instruction attempted to override the policy)"
                )
            text = (
                "I can't do that. "
                + " ".join(reasons)
                + (" I can inspect evidence, explain risk and propose tests for engineer approval instead.")
            )
            return {"status": "REFUSED", "response": text}

        def clarify(state: PlannerState) -> PlannerState:
            trace.append("clarify")
            tools.gate.check("request_clarification", "ask_clarification")
            return {"status": "NEEDS_CLARIFICATION", "response": state["interpretation"].clarification or ""}

        def gather(state: PlannerState) -> PlannerState:
            trace.append("gather")
            it = state["interpretation"]
            assert it.build_id
            try:
                return {
                    "changes": tools.call("get_build_changes", build_id=it.build_id),
                    "risk": tools.call("get_component_risk", build_id=it.build_id, top_n=40),
                    "coverage": tools.call(
                        "get_requirement_coverage", build_id=it.build_id, variant_id=it.variant_id
                    ),
                }
            except ToolUnavailableError as exc:
                return _failed(str(exc))

        def _failed(tool: str) -> PlannerState:
            trace.append("fail")
            return {
                "status": "FAILED",
                "response": f"The required tool '{tool}' returned no result, so no recommendation was made. "
                "Nothing was guessed; please retry when the tool is available.",
            }

        def answer(state: PlannerState) -> PlannerState:
            trace.append("answer")
            it = state["interpretation"]
            assert it.build_id and it.test_id
            try:
                evidence = tools.call(
                    "get_test_evidence", build_id=it.build_id, test_id=it.test_id, variant_id=it.variant_id
                )
            except ToolUnavailableError as exc:
                return _failed(str(exc))
            return {"answer": evidence, "status": "ANSWERED", "response": describe_test_evidence(evidence)}

        def after(next_node: str) -> Any:
            return lambda state: END if state.get("status") == "FAILED" else next_node

        def plan(state: PlannerState) -> PlannerState:
            trace.append("plan")
            it = state["interpretation"]
            try:
                items = tools.call(
                    "propose_test_plan",
                    build_id=it.build_id,
                    variant_id=it.variant_id,
                    top_n=it.top_n,
                    budget_minutes=it.budget_minutes,
                    component_ids=it.component_ids or None,
                )
            except ToolUnavailableError as exc:
                return _failed(str(exc))
            for n, item in enumerate(items, start=1):
                item["rank"] = n
            return {"plan": items}

        def explain(state: PlannerState) -> PlannerState:
            trace.append("explain")
            it = state["interpretation"]
            facts = {
                "build_id": it.build_id,
                "scope": it.variant_id or "all variants",
                "total_minutes": sum(i["duration_min"] for i in state["plan"]),
                "coverage": state["coverage"],
                "plan": [
                    {
                        k: i[k]
                        for k in (
                            "rank",
                            "test_id",
                            "variant_id",
                            "score",
                            "duration_min",
                            "expected_coverage_gain",
                            "reasons",
                            "evidence_ids",
                        )
                    }
                    for i in state["plan"]
                ],
            }
            try:
                explanation = agent.provider.explain(facts)
            except Exception as exc:  # provider outage must not break the deterministic plan
                trace.append(f"provider_error:{type(exc).__name__}")
                explanation = OfflineProvider().explain(facts)
            return {"explanation": explanation, "status": "COMPLETED", "response": explanation.text}

        g = StateGraph(PlannerState)
        for name, fn in (
            ("interpret", interpret),
            ("refuse", refuse),
            ("clarify", clarify),
            ("answer", answer),
            ("gather", gather),
            ("plan", plan),
            ("explain", explain),
        ):
            g.add_node(name, fn)
        g.add_edge(START, "interpret")
        g.add_conditional_edges(
            "interpret",
            route,
            {"refuse": "refuse", "clarify": "clarify", "evidence": "answer", "plan": "gather"},
        )
        g.add_conditional_edges("gather", after("plan"), ["plan", END])
        g.add_conditional_edges("plan", after("explain"), ["explain", END])
        for terminal in ("refuse", "clarify", "answer", "explain"):
            g.add_edge(terminal, END)
        return g.compile()


def describe_test_evidence(ev: dict[str, Any]) -> str:
    """Plain-language answer built only from the evidence records (no model, so nothing can be invented)."""
    test, build = ev["test_id"], ev["build_id"]
    if not ev["known"]:
        return f"{test} is not linked to any requirement at {build}, so it provides no evidence there."
    rows = ev["variants"]
    valid = [r["variant_id"] for r in rows if r["verdict"] == "VALID"]
    others = [r["variant_id"] for r in rows if r["verdict"] != "VALID"]
    scope = (
        rows[0]["variant_id"]
        if len(rows) == 1
        else f"its variants ({', '.join(r['variant_id'] for r in rows)})"
    )
    if not others:
        lines = [f"Yes. {test} gives valid evidence for {build} on {scope}."]
    elif valid:
        lines = [
            f"Partly. {test} gives valid evidence for {build} on {', '.join(valid)}, but not on {', '.join(others)}."
        ]
    else:
        lines = [f"No. {test} does not give valid evidence for {build} on {scope}."]
    for r in rows:
        v, recs = r["variant_id"], r["records"]
        if r["verdict"] == "NOT_APPLICABLE":
            lines.append(
                f"{v}: not applicable, {test} is only defined for {', '.join(ev['applicable_variants'])}."
            )
        elif r["verdict"] == "NO_EVIDENCE":
            lines.append(f"{v}: {test} has not run on {v} before {build}, so there is no evidence.")
        else:
            first = recs[0]
            run = f"latest run {first['execution_id']} on {first['evidence_build_id']} ({first['age_days']} d before {build})"
            if r["verdict"] == "VALID":
                reqs = ", ".join(x["requirement_id"] for x in recs)
                lines.append(
                    f"{v}: CURRENT, {run}, passed and compatible with the current revision of {reqs}."
                )
            else:
                why = "; ".join(
                    f"{x['requirement_id']} is {x['status']}: {', '.join(x['reasons'])}" for x in recs
                )
                lines.append(f"{v}: {run}. {why}.")
    rerun = [r["variant_id"] for r in rows if r["verdict"] in ("NOT_VALID", "NO_EVIDENCE")]
    if rerun:
        lines.append(f"To restore current evidence, re-run {test} on {', '.join(rerun)} for {build}.")
    lines.append("This is a read-only answer; nothing was changed or proposed.")
    return "\n".join(lines)
