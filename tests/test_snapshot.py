from __future__ import annotations

from typing import Any

import pytest
from ee_domain.snapshot import ValidationSnapshot, build_snapshot, load_snapshot
from sqlalchemy import Engine
from sqlalchemy.orm import Session


def test_unknown_build_raises(dataset: dict[str, list[Any]]) -> None:
    with pytest.raises(KeyError):
        build_snapshot(dataset, "B999")


def test_only_past_executions_are_visible(snap_b004: ValidationSnapshot) -> None:
    assert snap_b004.executions
    assert all(snap_b004.seq(e.build_id) < 4 for e in snap_b004.executions)
    assert set(snap_b004.builds) == {"B001", "B002", "B003", "B004"}


def test_first_build_has_no_history(dataset: dict[str, list[Any]]) -> None:
    snap = build_snapshot(dataset, "B001")
    assert snap.executions == [] and snap.defects == []


def test_requirements_created_later_are_hidden(
    dataset: dict[str, list[Any]], snap_b004: ValidationSnapshot
) -> None:
    later = {r.id for r in dataset["requirements"] if r.created_build_id in {"B005", "B006"}}
    assert not later & set(snap_b004.requirements)


def test_requirement_revision_recomputed_as_of(
    dataset: dict[str, list[Any]], snap_b006: ValidationSnapshot
) -> None:
    final = {r.id: r.revision for r in dataset["requirements"]}
    assert {r: q.revision for r, q in snap_b006.requirements.items()} == final
    snap_b002 = build_snapshot(dataset, "B002")
    assert all(q.revision <= final[r] for r, q in snap_b002.requirements.items())
    assert any(q.revision < final[r] for r, q in snap_b002.requirements.items())


def test_requirement_revision_at_is_monotonic(snap_b006: ValidationSnapshot) -> None:
    for rid in list(snap_b006.requirements)[:40]:
        revs = [snap_b006.requirement_revision_at(rid, b) for b in sorted(snap_b006.builds)]
        assert revs == sorted(revs)


def test_defect_status_is_as_of_not_final(snap_b004: ValidationSnapshot) -> None:
    execs = {e.id: e for e in snap_b004.executions}
    for d in snap_b004.defects:
        expected = "OPEN" if execs[d.execution_id].build_id == "B003" else "RESOLVED"
        assert d.status == expected


def test_db_snapshot_equals_file_snapshot(engine: Engine, snap_b004: ValidationSnapshot) -> None:
    with Session(engine) as s:
        db_snap = load_snapshot(s, "B004")
    assert db_snap.requirements == snap_b004.requirements
    assert [e.id for e in db_snap.executions] == [e.id for e in snap_b004.executions]
    assert db_snap.defects == snap_b004.defects
