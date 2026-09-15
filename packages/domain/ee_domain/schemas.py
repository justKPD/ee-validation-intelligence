"""Pydantic v2 DTOs: the file contract between generator and ETL, and API output."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Record(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ComponentIn(_Record):
    id: str
    name: str
    domain: str
    asil: Literal["QM", "A", "B", "C", "D"]
    supplier: str
    fictional: bool = True


class ComponentDependencyIn(_Record):
    upstream_id: str
    downstream_id: str
    kind: str


class SoftwareBuildIn(_Record):
    id: str
    sequence: int = Field(ge=1)
    release_date: date
    build_family: str


class VehicleVariantIn(_Record):
    id: str
    name: str
    powertrain: str
    market: str
    features: str


class RequirementIn(_Record):
    id: str
    title: str
    category: str
    severity: int = Field(ge=1, le=5)
    fmea_impact: int = Field(ge=1, le=10)
    fmea_occurrence: int = Field(ge=1, le=10)
    fmea_detectability: int = Field(ge=1, le=10)
    revision: int = Field(ge=1)
    created_build_id: str


class BuildChangeIn(_Record):
    id: str
    build_id: str
    target_type: Literal["component", "requirement"]
    target_id: str
    change_kind: str
    magnitude: float = Field(ge=0, le=1)
    new_revision: int | None = None


class TestCaseIn(_Record):
    __test__ = False
    id: str
    name: str
    test_family: str
    level: Literal["SIL", "HIL", "VEHICLE"]
    duration_min: float = Field(gt=0)
    automated: bool


class RequirementComponentIn(_Record):
    requirement_id: str
    component_id: str


class TestRequirementIn(_Record):
    __test__ = False
    test_id: str
    requirement_id: str


class TestComponentIn(_Record):
    __test__ = False
    test_id: str
    component_id: str


class TestVariantIn(_Record):
    __test__ = False
    test_id: str
    variant_id: str


class TestExecutionIn(_Record):
    __test__ = False
    id: str
    test_id: str
    build_id: str
    variant_id: str
    attempt: int = 1
    verdict: Literal["PASS", "FAIL", "BLOCKED"]
    duration_min: float = Field(gt=0)
    executed_at: datetime
    requirement_revision: int = Field(ge=1)
    selected_by: str


class DefectIn(_Record):
    id: str
    execution_id: str
    component_id: str
    severity: int = Field(ge=1, le=5)
    error_code: str
    failure_stage: str
    signal_signature: str
    status: Literal["OPEN", "RESOLVED"]
    title: str


# file name -> DTO, in FK-safe load order
DATASET_FILES: list[tuple[str, type[_Record]]] = [
    ("components", ComponentIn),
    ("component_dependencies", ComponentDependencyIn),
    ("builds", SoftwareBuildIn),
    ("variants", VehicleVariantIn),
    ("requirements", RequirementIn),
    ("build_changes", BuildChangeIn),
    ("test_cases", TestCaseIn),
    ("requirement_components", RequirementComponentIn),
    ("test_requirements", TestRequirementIn),
    ("test_components", TestComponentIn),
    ("test_variants", TestVariantIn),
    ("executions", TestExecutionIn),
    ("defects", DefectIn),
]
