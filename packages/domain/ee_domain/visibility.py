"""Restrict a full dataset to what was knowable at a decision point.

``build_snapshot(visible_data(data, B), b) == build_snapshot(data, b)`` for every ``b <= B`` (tested). Learned
models and benchmarks train on ``visible_data`` so they cannot see results of ``B`` or later builds.
"""

from __future__ import annotations

from typing import Any

from ee_domain.snapshot import DatasetView, build_snapshot


def visible_data(data: DatasetView, build_id: str) -> dict[str, list[Any]]:
    snap = build_snapshot(data, build_id)
    visible_exec = {e.id for e in snap.executions}
    out: dict[str, list[Any]] = {k: list(v) for k, v in data.items()}
    out["builds"] = sorted(snap.builds.values(), key=lambda b: b.sequence)
    out["build_changes"] = list(snap.changes)
    out["requirements"] = [r for r in data["requirements"] if r.id in snap.requirements]
    out["executions"] = [e for e in data["executions"] if e.id in visible_exec]
    out["defects"] = [d for d in data["defects"] if d.execution_id in visible_exec]
    return out
