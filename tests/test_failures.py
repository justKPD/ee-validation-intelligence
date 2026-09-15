from __future__ import annotations

from ee_domain.snapshot import ValidationSnapshot
from ee_failures import fingerprint_failures, unlinked_failures


def test_every_defect_in_exactly_one_family(snap_b006: ValidationSnapshot) -> None:
    fams = fingerprint_failures(snap_b006)
    ids = [d for f in fams for d in f.defect_ids]
    assert sorted(ids) == sorted(d.id for d in snap_b006.defects)
    assert sum(f.occurrences for f in fams) == len(snap_b006.defects)


def test_family_ids_are_sequential_and_deterministic(snap_b006: ValidationSnapshot) -> None:
    fams = fingerprint_failures(snap_b006)
    assert [f.id for f in fams] == [f"FF-{i:03d}" for i in range(1, len(fams) + 1)]
    assert fams == fingerprint_failures(snap_b006)


def test_recurring_families_exist(snap_b006: ValidationSnapshot) -> None:
    fams = fingerprint_failures(snap_b006)
    assert any(f.recurring for f in fams)
    assert all(f.recurring == (f.occurrences >= 2) for f in fams)


def test_family_ids_stable_across_builds(
    snap_b004: ValidationSnapshot, snap_b006: ValidationSnapshot
) -> None:
    later = {f.id: f.fingerprint for f in fingerprint_failures(snap_b006)}
    for f in fingerprint_failures(snap_b004):
        assert later[f.id] == f.fingerprint


def test_open_status_only_for_previous_build(snap_b006: ValidationSnapshot) -> None:
    for f in fingerprint_failures(snap_b006):
        if f.status == "OPEN":
            assert f.last_seen_build == "B005"
        assert f.first_seen_build in f.build_ids and f.last_seen_build in f.build_ids


def test_fingerprint_fields_match_defects(snap_b006: ValidationSnapshot) -> None:
    defects = {d.id: d for d in snap_b006.defects}
    for f in fingerprint_failures(snap_b006):
        for did in f.defect_ids:
            d = defects[did]
            assert (d.component_id, d.error_code, d.failure_stage) == (
                f.component_id,
                f.error_code,
                f.failure_stage,
            )


def test_unlinked_failures_are_fail_without_defect(snap_b006: ValidationSnapshot) -> None:
    linked = {d.execution_id for d in snap_b006.defects}
    execs = {e.id: e for e in snap_b006.executions}
    unlinked = unlinked_failures(snap_b006)
    assert unlinked
    assert all(execs[e].verdict == "FAIL" and e not in linked for e in unlinked)
