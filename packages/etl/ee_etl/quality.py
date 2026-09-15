"""Data-quality checks run on validated records before they touch the database."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel

SIZE_TARGETS: dict[str, tuple[int, int]] = {
    "components": (40, 40),
    "requirements": (150, 150),
    "test_cases": (250, 250),
    "builds": (6, 6),
    "variants": (4, 4),
    "executions": (1500, 3000),
    "defects": (80, 150),
}


@dataclass
class QualityReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _ids(records: Sequence[BaseModel]) -> set[str]:
    return {r.id for r in records}  # type: ignore[attr-defined]


def run_quality_checks(data: Mapping[str, Sequence[Any]], enforce_size_targets: bool = True) -> QualityReport:
    rep = QualityReport()
    comps, builds, variants = _ids(data["components"]), _ids(data["builds"]), _ids(data["variants"])
    reqs, tests, execs = _ids(data["requirements"]), _ids(data["test_cases"]), _ids(data["executions"])

    def ref(table: str, attr: str, valid: set[str]) -> None:
        bad = [getattr(r, attr) for r in data[table] if getattr(r, attr) not in valid]
        if bad:
            rep.errors.append(f"{table}.{attr}: {len(bad)} dangling references (e.g. {bad[0]})")

    for name, rows in data.items():
        keys = [getattr(r, "id", None) for r in rows]
        if keys and keys[0] is not None and len(set(keys)) != len(keys):
            rep.errors.append(f"{name}: duplicate ids")

    ref("component_dependencies", "upstream_id", comps)
    ref("component_dependencies", "downstream_id", comps)
    ref("requirements", "created_build_id", builds)
    ref("build_changes", "build_id", builds)
    ref("requirement_components", "requirement_id", reqs)
    ref("requirement_components", "component_id", comps)
    ref("test_requirements", "test_id", tests)
    ref("test_requirements", "requirement_id", reqs)
    ref("test_components", "test_id", tests)
    ref("test_components", "component_id", comps)
    ref("test_variants", "test_id", tests)
    ref("test_variants", "variant_id", variants)
    ref("executions", "test_id", tests)
    ref("executions", "build_id", builds)
    ref("executions", "variant_id", variants)
    ref("defects", "execution_id", execs)
    ref("defects", "component_id", comps)
    for ch in data["build_changes"]:
        valid = comps if ch.target_type == "component" else reqs
        if ch.target_id not in valid:
            rep.errors.append(f"build_changes: {ch.id} targets unknown {ch.target_type} {ch.target_id}")

    if any(d.upstream_id == d.downstream_id for d in data["component_dependencies"]):
        rep.errors.append("component_dependencies: self-dependency")

    applicable = {(tv.test_id, tv.variant_id) for tv in data["test_variants"]}
    release = {b.id: b.release_date for b in data["builds"]}
    exec_by_id = {e.id: e for e in data["executions"]}
    not_applicable = [e.id for e in data["executions"] if (e.test_id, e.variant_id) not in applicable]
    if not_applicable:
        rep.errors.append(f"executions: {len(not_applicable)} run on non-applicable variant")
    early = [
        e.id
        for e in data["executions"]
        if e.build_id in release
        and e.executed_at < datetime.combine(release[e.build_id], datetime.min.time())
    ]
    if early:
        rep.errors.append(f"executions: {len(early)} executed before build release")
    non_fail = [
        d.id
        for d in data["defects"]
        if d.execution_id in exec_by_id and exec_by_id[d.execution_id].verdict != "FAIL"
    ]
    if non_fail:
        rep.errors.append(f"defects: {len(non_fail)} linked to non-FAIL executions")
    if len({b.sequence for b in data["builds"]}) != len(data["builds"]):
        rep.errors.append("builds: duplicate sequence numbers")

    tested = {tr.requirement_id for tr in data["test_requirements"]}
    untested = len(reqs - tested)
    if untested:
        rep.warnings.append(f"requirements: {untested} without any linked test (structural coverage gap)")

    for name, (lo, hi) in SIZE_TARGETS.items():
        n = len(data[name])
        if not lo <= n <= hi:
            msg = f"size target: {name}={n} outside [{lo}, {hi}]"
            (rep.errors if enforce_size_targets else rep.warnings).append(msg)
    return rep
