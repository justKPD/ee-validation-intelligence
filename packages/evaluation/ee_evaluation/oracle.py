"""Counterfactual scoring oracle built from the generator's hidden ground truth.

Given any selection of (test, variant) pairs for a build, the oracle computes the *expected* number of hidden
live faults detected: ``P(detect f) = 1 − Π (1 − sensitivity_t)`` over selected pairs whose test touches the
fault's component on an in-scope variant. This lets strategies be compared on tests engineers never ran.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ee_domain.snapshot import DatasetView

Key = tuple[str, str]


@dataclass(frozen=True)
class HiddenFault:
    id: str
    component_id: str
    severity: int
    variant_scope: frozenset[str]
    live_builds: frozenset[str]

    @property
    def critical(self) -> bool:
        return self.severity >= 4


class Oracle:
    def __init__(
        self,
        faults: Sequence[HiddenFault],
        test_sensitivity: dict[str, float],
        test_components: dict[str, frozenset[str]],
    ):
        self.faults = list(faults)
        self.test_sensitivity = test_sensitivity
        self.test_components = test_components

    def live_faults(self, build_id: str) -> list[HiddenFault]:
        return [f for f in self.faults if build_id in f.live_builds]

    def exposure_index(
        self, build_id: str, keys: Sequence[Key]
    ) -> tuple[list[HiddenFault], dict[Key, list[tuple[int, float]]]]:
        """For each pair, the live faults (by index) it can detect and its detection probability."""
        faults = self.live_faults(build_id)
        by_comp: dict[str, list[int]] = {}
        for i, f in enumerate(faults):
            by_comp.setdefault(f.component_id, []).append(i)
        index: dict[Key, list[tuple[int, float]]] = {}
        for test_id, variant_id in keys:
            sens = self.test_sensitivity.get(test_id, 0.0)
            hits = [
                (i, sens)
                for comp in sorted(self.test_components.get(test_id, frozenset()))
                for i in by_comp.get(comp, [])
                if variant_id in faults[i].variant_scope
            ]
            if hits:
                index[(test_id, variant_id)] = hits
        return faults, index


def load_oracle(ground_truth_path: Path, data: DatasetView) -> Oracle:
    gt = json.loads(ground_truth_path.read_text())
    faults = [
        HiddenFault(
            id=f["id"],
            component_id=f["component_id"],
            severity=int(f["severity"]),
            variant_scope=frozenset(f["variant_scope"]),
            live_builds=frozenset(f.get("live_builds", [])),
        )
        for f in gt["faults"]
    ]
    if faults and not any(f.live_builds for f in faults):
        raise ValueError(
            "ground truth has no fault live_builds; regenerate the dataset with generator >= 1.1.0"
        )
    comps: dict[str, set[str]] = {}
    for tc in data["test_components"]:
        comps.setdefault(tc.test_id, set()).add(tc.component_id)
    return Oracle(faults, dict(gt["test_sensitivity"]), {t: frozenset(c) for t, c in comps.items()})
