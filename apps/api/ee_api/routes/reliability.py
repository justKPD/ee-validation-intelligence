"""Agent Reliability Lab and adversarial testing results (Phases 9–10). Read-only."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["reliability"])


def _load(request: Request, name: str, hint: str) -> dict[str, Any]:
    path = request.app.state.reliability_dir / name
    if not path.exists():
        raise HTTPException(404, f"{name} not found; run `uv run {hint}`")
    return dict(json.loads(path.read_text(encoding="utf-8")))


@router.get("/benchmarks/reliability")
def reliability(request: Request) -> dict[str, Any]:
    return _load(request, "latest.json", "ee-reliability")


@router.get("/benchmarks/adversarial")
def adversarial(request: Request) -> dict[str, Any]:
    return _load(request, "adversarial.json", "ee-adversarial")
