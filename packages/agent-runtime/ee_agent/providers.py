"""Provider-agnostic model adapter. The model only writes the explanation text from structured facts that the
deterministic engines already computed. It never chooses tests, computes risk, or calls authoritative tools.

- ``OfflineProvider`` (default): deterministic template. No network access and no cost, so it is reproducible for tests and Pass^k.
- ``AnthropicProvider``: used when ``EE_MODEL_PROVIDER=anthropic``. Model output is grounding-checked: any
  referenced id not present in the facts discards the text and falls back to the offline explanation.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

ID_PATTERN = re.compile(r"\b(?:TC-\d{3}|R-\d{3}|D-\d{3}|EX-\d{5}|CH-\d{4}|FF-\d{3}|ECU-[A-Z0-9_]+|B\d{3})\b")


@dataclass(frozen=True)
class Explanation:
    text: str
    provider: str
    model: str
    grounded: bool
    fallback_used: bool = False


class ModelProvider(Protocol):
    name: str
    model: str

    def explain(self, facts: dict[str, Any]) -> Explanation: ...


def referenced_ids(text: str) -> set[str]:
    return set(ID_PATTERN.findall(text))


def known_ids(facts: dict[str, Any]) -> set[str]:
    return referenced_ids(json.dumps(facts))


class OfflineProvider:
    name = "offline"
    model = "deterministic-explainer-1.0"

    def explain(self, facts: dict[str, Any]) -> Explanation:
        lines = [
            f"Validation plan for {facts['build_id']} ({facts['scope']}): {len(facts['plan'])} recommended test(s), "
            f"{facts['total_minutes']:.0f} min estimated."
        ]
        for item in facts["plan"]:
            lines.append(
                f"{item['rank']}. {item['test_id']} on {item['variant_id']} - priority {item['score']:.3f}, "
                f"{item['duration_min']:.0f} min, coverage gain +{item['expected_coverage_gain']:.1%}."
            )
            lines += [f"   - {r}" for r in item["reasons"][:4]]
        lines.append("All recommendations are PROPOSED and require an engineer's approval before execution.")
        return Explanation("\n".join(lines), self.name, self.model, grounded=True)


SYSTEM_PROMPT = (
    "You explain E/E validation test recommendations to automotive test engineers. The facts JSON was computed by "
    "deterministic engines and is authoritative. Explain why each recommended test is ranked where it is, citing only "
    "identifiers that appear in the facts. Do not invent tests, requirements, defects or numbers. Do not change the "
    "ranking. Note that recommendations await engineer approval. Plain text, concise."
)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str = "claude-opus-5", client: Any | None = None):
        self.model = model
        self._client = client
        self._offline = OfflineProvider()

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def explain(self, facts: dict[str, Any]) -> Explanation:
        response = self._get_client().beta.messages.create(
            model=self.model,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(facts, sort_keys=True)}],
        )
        offline = self._offline.explain(facts)
        if response.stop_reason == "refusal":
            return Explanation(offline.text, self.name, self.model, grounded=True, fallback_used=True)
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text or not referenced_ids(text) <= known_ids(facts):
            return Explanation(offline.text, self.name, self.model, grounded=False, fallback_used=True)
        return Explanation(text, self.name, getattr(response, "model", self.model), grounded=True)


def provider_from_env() -> ModelProvider:
    if os.environ.get("EE_MODEL_PROVIDER", "offline").lower() == "anthropic":
        return AnthropicProvider(os.environ.get("EE_MODEL", "claude-opus-5"))
    return OfflineProvider()
