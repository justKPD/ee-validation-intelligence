"""SQLAlchemy 2 ORM models for authoritative validation records.

Later-phase tables (recommendations, approvals, agent runs, provenance) live in
their own modules and are added by dedicated migrations.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Component(Base):
    __tablename__ = "component"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(40))
    asil: Mapped[str] = mapped_column(String(8))
    supplier: Mapped[str] = mapped_column(String(80))
    fictional: Mapped[bool] = mapped_column(Boolean, default=True)


class ComponentDependency(Base):
    __tablename__ = "component_dependency"
    upstream_id: Mapped[str] = mapped_column(ForeignKey("component.id"), primary_key=True)
    downstream_id: Mapped[str] = mapped_column(ForeignKey("component.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))


class SoftwareBuild(Base):
    __tablename__ = "software_build"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, unique=True)
    release_date: Mapped[date] = mapped_column(Date)
    build_family: Mapped[str] = mapped_column(String(20))


class VehicleVariant(Base):
    __tablename__ = "vehicle_variant"
    id: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    powertrain: Mapped[str] = mapped_column(String(20))
    market: Mapped[str] = mapped_column(String(20))
    features: Mapped[str] = mapped_column(Text)  # comma separated feature flags


class Requirement(Base):
    __tablename__ = "requirement"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30))
    severity: Mapped[int] = mapped_column(Integer)
    fmea_impact: Mapped[int] = mapped_column(Integer)
    fmea_occurrence: Mapped[int] = mapped_column(Integer)
    fmea_detectability: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    created_build_id: Mapped[str] = mapped_column(ForeignKey("software_build.id"))


class BuildChange(Base):
    __tablename__ = "build_change"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    build_id: Mapped[str] = mapped_column(ForeignKey("software_build.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(12))  # component | requirement
    target_id: Mapped[str] = mapped_column(String(40), index=True)
    change_kind: Mapped[str] = mapped_column(String(30))
    magnitude: Mapped[float] = mapped_column(Float)
    new_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TestCase(Base):
    __tablename__ = "test_case"
    __test__ = False
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    test_family: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(10))
    duration_min: Mapped[float] = mapped_column(Float)
    automated: Mapped[bool] = mapped_column(Boolean)


class RequirementComponent(Base):
    __tablename__ = "requirement_component"
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirement.id"), primary_key=True)
    component_id: Mapped[str] = mapped_column(ForeignKey("component.id"), primary_key=True)


class TestRequirement(Base):
    __tablename__ = "test_requirement"
    __test__ = False
    test_id: Mapped[str] = mapped_column(ForeignKey("test_case.id"), primary_key=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirement.id"), primary_key=True)


class TestComponent(Base):
    __tablename__ = "test_component"
    __test__ = False
    test_id: Mapped[str] = mapped_column(ForeignKey("test_case.id"), primary_key=True)
    component_id: Mapped[str] = mapped_column(ForeignKey("component.id"), primary_key=True)


class TestVariant(Base):
    __tablename__ = "test_variant"
    __test__ = False
    test_id: Mapped[str] = mapped_column(ForeignKey("test_case.id"), primary_key=True)
    variant_id: Mapped[str] = mapped_column(ForeignKey("vehicle_variant.id"), primary_key=True)


class TestExecution(Base):
    __tablename__ = "test_execution"
    __test__ = False
    __table_args__ = (UniqueConstraint("test_id", "build_id", "variant_id", "attempt"),)
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("test_case.id"), index=True)
    build_id: Mapped[str] = mapped_column(ForeignKey("software_build.id"), index=True)
    variant_id: Mapped[str] = mapped_column(ForeignKey("vehicle_variant.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    verdict: Mapped[str] = mapped_column(String(10))
    duration_min: Mapped[float] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(DateTime)
    requirement_revision: Mapped[int] = mapped_column(Integer)
    selected_by: Mapped[str] = mapped_column(String(30))


class Defect(Base):
    __tablename__ = "defect"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("test_execution.id"), index=True)
    component_id: Mapped[str] = mapped_column(ForeignKey("component.id"), index=True)
    severity: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str] = mapped_column(String(20))
    failure_stage: Mapped[str] = mapped_column(String(30))
    signal_signature: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(12))
    title: Mapped[str] = mapped_column(String(200))


AUTHORITATIVE_TABLES_IN_LOAD_ORDER: list[type[Base]] = [
    Component,
    ComponentDependency,
    SoftwareBuild,
    VehicleVariant,
    Requirement,
    BuildChange,
    TestCase,
    RequirementComponent,
    TestRequirement,
    TestComponent,
    TestVariant,
    TestExecution,
    Defect,
]
