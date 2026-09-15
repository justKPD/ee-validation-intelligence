"""Default-deny policy gate. Every agent tool call is checked here before it runs (ADR-002)."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ee_domain.db import REPO_ROOT

DEFAULT_POLICY_PATH = REPO_ROOT / "config" / "agent_policy.toml"
POLICY_DENIED = "POLICY_DENIED"
AGENT_ACTOR = "ee-agent"

_PROHIBITION_REASONS = {
    "modify_requirement": "agents must not modify authoritative requirements",
    "modify_test_case": "agents must not rewrite authoritative test definitions",
    "change_test_verdict": "agents must not change PASS/FAIL verdicts",
    "close_defect": "agents must not close defects",
    "approve_release": "release approval is never delegated to an agent",
    "approve_recommendation": "only a human reviewer may approve or reject recommendations",
    "execute_test": "agents must not silently execute tests; execution follows human approval",
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class AgentPolicy:
    version: str
    permissions: dict[str, bool]
    autonomy: dict[str, str] = field(default_factory=dict)

    def allows(self, permission: str) -> bool:
        return self.permissions.get(permission, False) is True


@dataclass(frozen=True)
class PolicyDecision:
    permission: str
    tool_name: str
    actor: str
    allowed: bool
    reason: str
    policy_version: str
    at: datetime

    @property
    def decision(self) -> str:
        return "ALLOWED" if self.allowed else POLICY_DENIED


class PolicyDeniedError(PermissionError):
    def __init__(self, decision: PolicyDecision):
        super().__init__(f"{POLICY_DENIED}: {decision.reason}")
        self.decision = decision


class PolicyGate:
    def __init__(
        self,
        policy: AgentPolicy,
        sink: Callable[[PolicyDecision], None] | None = None,
        actor: str = AGENT_ACTOR,
        clock: Callable[[], datetime] = _now,
    ):
        self.policy = policy
        self.sink = sink
        self.actor = actor
        self.clock = clock
        self.decisions: list[PolicyDecision] = []

    def check(self, permission: str, tool_name: str) -> PolicyDecision:
        if self.policy.allows(permission):
            reason = f"permission '{permission}' granted by {self.policy.version}"
            allowed = True
        elif permission in self.policy.permissions:
            reason = _PROHIBITION_REASONS.get(permission, f"permission '{permission}' is prohibited")
            allowed = False
        else:
            reason = f"permission '{permission}' is not defined in {self.policy.version} (default deny)"
            allowed = False
        decision = PolicyDecision(
            permission, tool_name, self.actor, allowed, reason, self.policy.version, self.clock()
        )
        self.decisions.append(decision)
        if self.sink is not None:
            self.sink(decision)
        return decision

    def enforce(self, permission: str, tool_name: str) -> PolicyDecision:
        decision = self.check(permission, tool_name)
        if not decision.allowed:
            raise PolicyDeniedError(decision)
        return decision

    @property
    def denials(self) -> list[PolicyDecision]:
        return [d for d in self.decisions if not d.allowed]


def load_policy(path: Path | None = None) -> AgentPolicy:
    raw = tomllib.loads((path or DEFAULT_POLICY_PATH).read_text(encoding="utf-8"))
    return AgentPolicy(
        version=raw["version"],
        permissions={k: bool(v) for k, v in raw.get("permissions", {}).items()},
        autonomy=dict(raw.get("autonomy", {})),
    )
