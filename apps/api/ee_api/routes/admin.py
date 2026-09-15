"""Read-only view of model, policy and engine configuration for the admin screen (Phase 5)."""

from __future__ import annotations

import os
import tomllib
from typing import Any

from ee_domain.db import REPO_ROOT
from fastapi import APIRouter

router = APIRouter(tags=["admin"])

CONFIG_DIR = REPO_ROOT / "config"


def _toml(name: str) -> dict[str, Any] | None:
    path = CONFIG_DIR / name
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@router.get("/config")
def config() -> dict[str, Any]:
    provider = os.environ.get("EE_MODEL_PROVIDER", "offline").lower()
    return {
        "risk": _toml("risk.toml"),
        "ranking": _toml("ranking.toml"),
        "ranking_tuned": _toml("ranking.tuned.toml"),
        "policy": _toml("agent_policy.toml"),
        "model": {
            "provider": provider,
            "model": os.environ.get("EE_MODEL", "claude-opus-5")
            if provider == "anthropic"
            else "deterministic-explainer-1.0",
            "otel_exporter": os.environ.get("EE_OTEL_EXPORTER", "none"),
        },
        "editable": False,
        "note": "Configuration is version-controlled; changes go through pull requests, not the UI.",
    }
