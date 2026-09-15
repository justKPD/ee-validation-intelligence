"""Deterministic failure fingerprints.

Fingerprint key: ``component | test family | error code | failure stage``. Build family, variants and
signal signatures are attributes of a family, not part of its key, so one fault recurring across
builds and variants stays one family.

Family ids are assigned by first occurrence time, so they stay stable as later builds add families.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ee_domain.schemas import DefectIn, TestExecutionIn
from ee_domain.snapshot import ValidationSnapshot


@dataclass(frozen=True)
class FailureFamily:
    id: str
    fingerprint: str
    component_id: str
    test_family: str
    error_code: str
    failure_stage: str
    occurrences: int
    defect_ids: list[str]
    execution_ids: list[str]
    build_ids: list[str]
    variant_ids: list[str]
    signal_signatures: list[str]
    representative_title: str
    first_seen_build: str
    last_seen_build: str
    max_severity: int
    status: str
    recurring: bool


def fingerprint_failures(snap: ValidationSnapshot) -> list[FailureFamily]:
    execs = {e.id: e for e in snap.executions}
    groups: dict[str, list[tuple[DefectIn, TestExecutionIn]]] = {}
    for d in snap.defects:
        e = execs[d.execution_id]
        family = snap.tests[e.test_id].test_family
        key = f"{d.component_id}|{family}|{d.error_code}|{d.failure_stage}"
        groups.setdefault(key, []).append((d, e))

    ordered = sorted(groups.items(), key=lambda kv: (min(e.executed_at for _, e in kv[1]), kv[0]))
    families = []
    for n, (key, items) in enumerate(ordered, start=1):
        items.sort(key=lambda de: (de[1].executed_at, de[0].id))
        component, test_family, code, stage = key.split("|")
        builds = sorted({e.build_id for _, e in items}, key=snap.seq)
        titles = Counter(d.title for d, _ in items)
        families.append(
            FailureFamily(
                id=f"FF-{n:03d}",
                fingerprint=key,
                component_id=component,
                test_family=test_family,
                error_code=code,
                failure_stage=stage,
                occurrences=len(items),
                defect_ids=[d.id for d, _ in items],
                execution_ids=[e.id for _, e in items],
                build_ids=builds,
                variant_ids=sorted({e.variant_id for _, e in items}),
                signal_signatures=sorted({d.signal_signature for d, _ in items}),
                representative_title=min(titles, key=lambda t: (-titles[t], t)),
                first_seen_build=builds[0],
                last_seen_build=builds[-1],
                max_severity=max(d.severity for d, _ in items),
                status="OPEN" if any(d.status == "OPEN" for d, _ in items) else "RESOLVED",
                recurring=len(items) >= 2,
            )
        )
    return families


def unlinked_failures(snap: ValidationSnapshot) -> list[str]:
    """FAIL executions without a defect: flaky or not-yet-triaged candidates."""
    linked = {d.execution_id for d in snap.defects}
    return [e.id for e in snap.executions if e.verdict == "FAIL" and e.id not in linked]
