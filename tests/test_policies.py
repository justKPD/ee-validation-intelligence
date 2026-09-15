from __future__ import annotations

from pathlib import Path

import pytest
from ee_policies import (
    AGENT_ACTOR,
    POLICY_DENIED,
    AgentPolicy,
    PolicyDecision,
    PolicyDeniedError,
    PolicyGate,
    load_policy,
)

PROHIBITED = (
    "modify_requirement",
    "modify_test_case",
    "change_test_verdict",
    "close_defect",
    "approve_release",
    "approve_recommendation",
    "execute_test",
)


def test_repository_policy_prohibits_authoritative_changes() -> None:
    policy = load_policy()
    assert policy.version == "policy-1.0"
    for p in PROHIBITED:
        assert policy.permissions[p] is False and not policy.allows(p)
    for p in ("read_requirements", "read_results", "recommend_test", "explain_risk", "request_clarification"):
        assert policy.allows(p)
    assert policy.autonomy["verdict_and_release"] == "NEVER_DELEGATED"


def test_prohibited_call_returns_policy_denied_with_specific_reason() -> None:
    gate = PolicyGate(load_policy())
    d = gate.check("change_test_verdict", "set_verdict")
    assert not d.allowed and d.decision == POLICY_DENIED
    assert "verdict" in d.reason and d.actor == AGENT_ACTOR and d.policy_version == "policy-1.0"


def test_unknown_permission_is_default_denied() -> None:
    gate = PolicyGate(AgentPolicy("p-test", {"read_tests": True}))
    d = gate.check("delete_everything", "rm")
    assert not d.allowed and "default deny" in d.reason


def test_non_boolean_true_is_not_permission() -> None:
    assert not AgentPolicy("p", {"read_tests": "yes"}).allows("read_tests")  # type: ignore[dict-item]


def test_enforce_raises_and_records_every_decision() -> None:
    seen: list[PolicyDecision] = []
    gate = PolicyGate(load_policy(), sink=seen.append)
    gate.enforce("read_risk", "get_component_risk")
    with pytest.raises(PolicyDeniedError, match=POLICY_DENIED) as exc:
        gate.enforce("close_defect", "close_defect")
    assert exc.value.decision.permission == "close_defect"
    assert [d.decision for d in seen] == ["ALLOWED", POLICY_DENIED]
    assert gate.denials == [seen[1]]


def test_policy_file_override(tmp_path: Path) -> None:
    p = tmp_path / "policy.toml"
    p.write_text('version = "strict"\n[permissions]\nread_tests = true\nrecommend_test = false\n')
    policy = load_policy(p)
    assert policy.version == "strict" and not policy.allows("recommend_test") and policy.allows("read_tests")
