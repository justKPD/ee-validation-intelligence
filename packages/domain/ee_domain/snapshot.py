"""Leakage-safe, immutable view of the validation programme *as of* a software build.

Decision point semantics for build ``B`` (sequence ``n``):

- builds, requirements and changes with sequence ``<= n`` are visible (the changes of ``B`` are known when
  ``B`` is released);
- executions and defects are visible only from builds with sequence ``< n`` (``B`` has not been tested yet);
- requirement revisions are recomputed as of ``B`` from the change history;
- defect status is recomputed: defects found on the immediately preceding build are ``OPEN`` at the
  decision point, older ones are ``RESOLVED``. The stored (final) status is never used.

Every engine consumes this object only, so no engine can see future results.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ee_domain import models as m
from ee_domain import schemas as s

DatasetView = Mapping[str, Sequence[Any]]


@dataclass(frozen=True)
class ValidationSnapshot:
    as_of: s.SoftwareBuildIn
    builds: dict[str, s.SoftwareBuildIn]
    components: dict[str, s.ComponentIn]
    dependencies: list[s.ComponentDependencyIn]
    variants: dict[str, s.VehicleVariantIn]
    requirements: dict[str, s.RequirementIn]
    tests: dict[str, s.TestCaseIn]
    changes: list[s.BuildChangeIn]
    executions: list[s.TestExecutionIn]
    defects: list[s.DefectIn]
    req_components: dict[str, list[str]]
    test_requirements: dict[str, list[str]]
    test_components: dict[str, list[str]]
    test_variants: dict[str, list[str]]
    requirement_revision_sequences: dict[str, list[int]]

    @property
    def build_id(self) -> str:
        return self.as_of.id

    @property
    def sequence(self) -> int:
        return self.as_of.sequence

    def seq(self, build_id: str) -> int:
        return self.builds[build_id].sequence

    def requirement_revision_at(self, requirement_id: str, build_id: str) -> int:
        return 1 + bisect_right(
            self.requirement_revision_sequences.get(requirement_id, []), self.seq(build_id)
        )

    @cached_property
    def current_changes(self) -> list[s.BuildChangeIn]:
        return [c for c in self.changes if c.build_id == self.as_of.id]

    @cached_property
    def component_requirements(self) -> dict[str, list[str]]:
        return _invert(self.req_components)

    @cached_property
    def component_tests(self) -> dict[str, list[str]]:
        return _invert(self.test_components)

    @cached_property
    def requirement_tests(self) -> dict[str, list[str]]:
        return _invert(self.test_requirements)

    @cached_property
    def upstream(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = defaultdict(list)
        for d in self.dependencies:
            out[d.downstream_id].append(d.upstream_id)
        return {k: sorted(v) for k, v in out.items()}

    @cached_property
    def downstream(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = defaultdict(list)
        for d in self.dependencies:
            out[d.upstream_id].append(d.downstream_id)
        return {k: sorted(v) for k, v in out.items()}


def _invert(mapping: Mapping[str, Sequence[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for k, vs in mapping.items():
        for v in vs:
            out[v].append(k)
    return {k: sorted(v) for k, v in out.items()}


def _group(
    rows: Sequence[Any], key: str, val: str, keep: Callable[[str, str], bool] = lambda _k, _v: True
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        k, v = getattr(r, key), getattr(r, val)
        if keep(k, v):
            out[k].append(v)
    return {k: sorted(v) for k, v in out.items()}


def build_snapshot(data: DatasetView, build_id: str) -> ValidationSnapshot:
    all_builds = {b.id: b for b in data["builds"]}
    if build_id not in all_builds:
        raise KeyError(f"unknown build {build_id}")
    as_of = all_builds[build_id]
    n = as_of.sequence
    builds = {k: b for k, b in all_builds.items() if b.sequence <= n}

    changes = sorted((c for c in data["build_changes"] if c.build_id in builds), key=lambda c: c.id)
    rev_seqs: dict[str, list[int]] = defaultdict(list)
    for c in changes:
        if c.target_type == "requirement":
            rev_seqs[c.target_id].append(builds[c.build_id].sequence)
    rev_seqs = {k: sorted(v) for k, v in rev_seqs.items()}

    requirements = {
        r.id: r.model_copy(update={"revision": 1 + len(rev_seqs.get(r.id, []))})
        for r in data["requirements"]
        if r.created_build_id in builds
    }
    test_requirements = _group(
        data["test_requirements"], "test_id", "requirement_id", lambda _t, r: r in requirements
    )
    tests = {t.id: t for t in data["test_cases"] if test_requirements.get(t.id)}

    executions = sorted(
        (
            e
            for e in data["executions"]
            if e.build_id in builds and builds[e.build_id].sequence < n and e.test_id in tests
        ),
        key=lambda e: (e.executed_at, e.id),
    )
    visible = {e.id: e for e in executions}
    defects = []
    for d in sorted(data["defects"], key=lambda d: d.id):
        e = visible.get(d.execution_id)
        if e is not None:
            status = "OPEN" if builds[e.build_id].sequence == n - 1 else "RESOLVED"
            defects.append(d.model_copy(update={"status": status}))

    return ValidationSnapshot(
        as_of=as_of,
        builds=builds,
        components={c.id: c for c in data["components"]},
        dependencies=list(data["component_dependencies"]),
        variants={v.id: v for v in data["variants"]},
        requirements=requirements,
        tests=tests,
        changes=changes,
        executions=executions,
        defects=defects,
        req_components=_group(
            data["requirement_components"], "requirement_id", "component_id", lambda r, _c: r in requirements
        ),
        test_requirements=test_requirements,
        test_components=_group(data["test_components"], "test_id", "component_id", lambda t, _c: t in tests),
        test_variants=_group(data["test_variants"], "test_id", "variant_id", lambda t, _v: t in tests),
        requirement_revision_sequences=rev_seqs,
    )


def load_dataset_view(session: Session) -> dict[str, list[Any]]:
    view: dict[str, list[Any]] = {}
    for (name, dto), model in zip(s.DATASET_FILES, m.AUTHORITATIVE_TABLES_IN_LOAD_ORDER, strict=True):
        view[name] = [dto.model_validate(row) for row in session.scalars(select(model))]
    return view


def load_snapshot(session: Session, build_id: str) -> ValidationSnapshot:
    return build_snapshot(load_dataset_view(session), build_id)
