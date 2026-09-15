"""Engines must produce identical outputs no matter what happens in future builds."""

from __future__ import annotations

from typing import Any

from ee_coverage import assess_evidence
from ee_domain.snapshot import build_snapshot
from ee_failures import fingerprint_failures
from ee_risk import assess_components, assess_requirements


def _tamper_future(data: dict[str, list[Any]], from_seq: int) -> dict[str, list[Any]]:
    seq = {b.id: b.sequence for b in data["builds"]}
    future_exec = {e.id for e in data["executions"] if seq[e.build_id] >= from_seq}
    out = dict(data)
    out["executions"] = [
        e.model_copy(update={"verdict": "FAIL"}) if e.id in future_exec else e for e in data["executions"]
    ]
    out["defects"] = [d for d in data["defects"] if d.execution_id not in future_exec]
    out["build_changes"] = [c for c in data["build_changes"] if seq[c.build_id] < from_seq] + [
        c.model_copy(update={"magnitude": 1.0}) for c in data["build_changes"] if seq[c.build_id] > from_seq
    ]
    return out


def test_future_results_cannot_change_any_engine_output(dataset: dict[str, list[Any]]) -> None:
    for build, seq in (("B003", 3), ("B004", 4), ("B005", 5)):
        clean = build_snapshot(dataset, build)
        # tamper everything from this build's own results onward, and changes of strictly later builds
        tampered_data = _tamper_future(dataset, seq)
        tampered_data["build_changes"] += [c for c in dataset["build_changes"] if c.build_id == build]
        tampered = build_snapshot(tampered_data, build)

        clean_risk, tampered_risk = assess_components(clean), assess_components(tampered)
        assert clean_risk == tampered_risk
        assert assess_requirements(clean, clean_risk) == assess_requirements(tampered, tampered_risk)
        assert assess_evidence(clean) == assess_evidence(tampered)
        assert fingerprint_failures(clean) == fingerprint_failures(tampered)


def test_stored_final_defect_status_is_ignored(dataset: dict[str, list[Any]]) -> None:
    flipped = dict(dataset)
    flipped["defects"] = [d.model_copy(update={"status": "OPEN"}) for d in dataset["defects"]]
    assert fingerprint_failures(build_snapshot(dataset, "B004")) == fingerprint_failures(
        build_snapshot(flipped, "B004")
    )
