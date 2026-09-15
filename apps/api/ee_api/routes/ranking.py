"""Test ranking (Phase 3) and shadow benchmark results (Phase 4). Read-only."""

from __future__ import annotations

import json
from typing import Any, Literal

from ee_domain.snapshot import ValidationSnapshot, load_dataset_view
from ee_ranking import (
    DecisionContext,
    RankedTest,
    build_context,
    load_ranking_config,
    rank_engineering,
    rank_hybrid,
    rank_random,
    rank_severity,
    train_defect_model,
)
from ee_risk import load_risk_config
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ee_api.deps import get_session
from ee_api.routes.intelligence import snapshot_for

router = APIRouter(tags=["ranking"])

Strategy = Literal["risk_based", "hybrid", "severity_baseline", "random_baseline"]


def context_for(request: Request, snap: ValidationSnapshot = Depends(snapshot_for)) -> DecisionContext:
    cache: dict[str, DecisionContext] = request.app.state.contexts
    if snap.build_id not in cache:
        cache[snap.build_id] = build_context(snap, load_risk_config())
    return cache[snap.build_id]


def full_ranking(
    request: Request, db: Session, ctx: DecisionContext, strategy: str, seed: int
) -> list[RankedTest]:
    key = (ctx.build_id, strategy, seed)
    cache: dict[tuple[str, str, int], list[RankedTest]] = request.app.state.rankings
    if key not in cache:
        cfg = load_ranking_config()
        if strategy == "risk_based":
            cache[key] = rank_engineering(ctx, cfg)
        elif strategy == "hybrid":
            if request.app.state.dataset_view is None:
                request.app.state.dataset_view = load_dataset_view(db)
            model = train_defect_model(
                request.app.state.dataset_view, ctx.build_id, cfg, None, load_risk_config()
            )
            request.app.state.models[ctx.build_id] = model.info()
            cache[key] = rank_hybrid(ctx, model, cfg)
        elif strategy == "severity_baseline":
            cache[key] = rank_severity(ctx)
        else:
            cache[key] = rank_random(ctx, seed)
    return cache[key]


@router.get("/builds/{build_id}/ranking", response_model=list[RankedTest])
def ranking(
    request: Request,
    strategy: Strategy = "risk_based",
    limit: int = Query(20, ge=1, le=1000),
    variant_id: str | None = None,
    budget_minutes: float | None = Query(None, gt=0),
    seed: int = 0,
    ctx: DecisionContext = Depends(context_for),
    db: Session = Depends(get_session),
) -> list[RankedTest]:
    ranked = full_ranking(request, db, ctx, strategy, seed)
    if variant_id:
        ranked = [r for r in ranked if r.variant_id == variant_id]
    if budget_minutes is not None:
        selected, used = [], 0.0
        for r in ranked:
            if used + r.duration_min <= budget_minutes:
                selected.append(r)
                used += r.duration_min
        ranked = selected
    return ranked[:limit]


@router.get("/builds/{build_id}/ranking/model")
def ranking_model(
    request: Request, ctx: DecisionContext = Depends(context_for), db: Session = Depends(get_session)
) -> dict[str, Any]:
    full_ranking(request, db, ctx, "hybrid", 0)
    return dict(request.app.state.models[ctx.build_id])


@router.get("/benchmarks/shadow")
def shadow_benchmark(request: Request) -> dict[str, Any]:
    path = request.app.state.benchmark_dir / "latest.json"
    if not path.exists():
        raise HTTPException(404, "shadow benchmark has not been run; run `uv run ee-shadow`")
    return dict(json.loads(path.read_text(encoding="utf-8")))
