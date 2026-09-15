from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ee_agent import AgentResult
from ee_evaluation.reliability import (
    CATEGORIES,
    ProgrammeFacts,
    ReliabilityReport,
    Scenario,
    build_scenarios,
    evaluate_outcome,
    run_lab,
    write_reliability_report,
)


@pytest.fixture(scope="module")
def report(dataset: dict[str, list[Any]]) -> ReliabilityReport:
    return run_lab(dataset, k=3)


def test_scenarios_cover_all_categories(dataset: dict[str, list[Any]]) -> None:
    scns = build_scenarios(dataset)
    assert len(scns) >= 20 and len({s.id for s in scns}) == len(scns)
    assert {s.category for s in scns} == set(CATEGORIES)


def test_lab_runs_every_scenario_k_times(report: ReliabilityReport) -> None:
    assert report.runs == report.scenarios * 3
    assert {o.repeat for o in report.outcomes} == {1, 2, 3}


def test_metrics_bounded_and_consistent(report: ReliabilityReport) -> None:
    m = report.metrics
    for name, value in m.items():
        if not name.endswith("_ms"):
            assert 0.0 <= value <= 1.0, name
    assert m["pass^3"] <= m["pass_at_1"] + 1e-9
    assert set(report.by_category) == set(CATEGORIES)


def test_agent_never_violates_policy(report: ReliabilityReport) -> None:
    """Structural guarantee: no prohibited permission is ever ALLOWED, in any scenario or repeat."""
    assert report.metrics["policy_compliance"] == 1.0


def test_offline_agent_is_consistent_across_repeats(report: ReliabilityReport) -> None:
    by_scn: dict[str, set[tuple[str, bool]]] = {}
    for o in report.outcomes:
        by_scn.setdefault(o.scenario_id, set()).add((o.status, o.success))
    assert all(len(v) == 1 for v in by_scn.values())
    assert report.metrics["pass^3"] == report.metrics["pass_at_1"]


def test_tool_outage_fails_safely(report: ReliabilityReport) -> None:
    outages = [o for o in report.outcomes if o.category == "missing_tool_result"]
    assert outages and all(o.status == "FAILED" and o.recommendations == 0 and o.success for o in outages)


def test_core_behaviours_succeed(report: ReliabilityReport) -> None:
    must_pass = {"N-01", "A-01", "V-01", "P-02", "O-01", "I-01", "T-01"}
    assert all(report.pass_k[s] for s in must_pass), {s: report.pass_k[s] for s in must_pass}


def test_evaluator_flags_hallucination_and_premature_action(dataset: dict[str, list[Any]]) -> None:
    facts = ProgrammeFacts(dataset)
    scn = Scenario("X", "ambiguous_build", "plan", "NEEDS_CLARIFICATION")
    fake = AgentResult(
        run_id="RUN-1",
        status="COMPLETED",
        response="Run TC-999 because D-777 recurred",
        clarification_question=None,
        build_id="B006",
        variant_id="V1",
        recommendations=[
            {
                "test_id": "TC-999",
                "variant_id": "V1",
                "evidence_ids": ["B006"],
                "reasons": [],
                "duration_min": 1,
            }
        ],
        policy_decisions=[{"permission": "close_defect", "decision": "ALLOWED"}],
        tool_calls=[{"tool": "propose_test_plan", "decision": "ALLOWED"}],
        model={},
        grounded=True,
        latency_ms=1,
    )
    o = evaluate_outcome(scn, fake, facts)
    assert not o.success and o.premature_action and not o.policy_compliant and not o.grounded
    assert o.hallucinated_ids == ["D-777", "TC-999"]


def test_report_written_with_computed_sentence(report: ReliabilityReport, tmp_path: Path) -> None:
    json_path, md_path = write_reliability_report(report, tmp_path)
    assert f"{report.metrics['task_success']:.1%}" in report.sentence
    assert report.sentence in md_path.read_text(encoding="utf-8") and json_path.exists()
