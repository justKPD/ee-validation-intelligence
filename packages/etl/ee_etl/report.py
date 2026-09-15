"""Dataset summary report generated from the database (not from generator memory)."""

from __future__ import annotations

from ee_domain import models as m
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session


def dataset_summary_markdown(engine: Engine) -> str:
    with Session(engine) as s:

        def count(model: type[m.Base]) -> int:
            return s.scalar(select(func.count()).select_from(model)) or 0

        lines = [
            "# Synthetic Dataset Summary",
            "",
            "> Entirely fictional synthetic data generated for an independent portfolio project.",
            "> It does not represent any BMW Group system, component or result.",
            "",
            "## Entity counts",
            "",
            "| Entity | Count |",
            "|---|---:|",
        ]
        for label, model in [
            ("Components", m.Component),
            ("Component dependencies", m.ComponentDependency),
            ("Requirements", m.Requirement),
            ("Test cases", m.TestCase),
            ("Software builds", m.SoftwareBuild),
            ("Vehicle variants", m.VehicleVariant),
            ("Build changes", m.BuildChange),
            ("Test executions", m.TestExecution),
            ("Defects", m.Defect),
        ]:
            lines.append(f"| {label} | {count(model)} |")

        n_req = count(m.Requirement)
        tested = s.scalar(select(func.count(func.distinct(m.TestRequirement.requirement_id)))) or 0
        lines += [
            "",
            "## Structural coverage",
            "",
            f"Requirements with at least one linked test: **{tested}/{n_req} "
            f"({100 * tested / max(n_req, 1):.1f}%)**",
            "",
            "## Per build",
            "",
            "| Build | Release | Changes | Executions | FAIL | BLOCKED | Defects | Exec. minutes |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for b in s.scalars(select(m.SoftwareBuild).order_by(m.SoftwareBuild.sequence)):
            ex = select(m.TestExecution).where(m.TestExecution.build_id == b.id).subquery()
            n_ex = s.scalar(select(func.count()).select_from(ex)) or 0
            n_fail = s.scalar(select(func.count()).select_from(ex).where(ex.c.verdict == "FAIL")) or 0
            n_blk = s.scalar(select(func.count()).select_from(ex).where(ex.c.verdict == "BLOCKED")) or 0
            minutes = s.scalar(select(func.sum(ex.c.duration_min))) or 0.0
            n_def = (
                s.scalar(
                    select(func.count())
                    .select_from(m.Defect)
                    .join(m.TestExecution, m.Defect.execution_id == m.TestExecution.id)
                    .where(m.TestExecution.build_id == b.id)
                )
                or 0
            )
            n_ch = (
                s.scalar(
                    select(func.count()).select_from(m.BuildChange).where(m.BuildChange.build_id == b.id)
                )
                or 0
            )
            lines.append(
                f"| {b.id} | {b.release_date} | {n_ch} | {n_ex} | {n_fail} | {n_blk} | {n_def} | "
                f"{minutes:,.0f} |"
            )

        lines += ["", "## Defects by component (top 10)", "", "| Component | Defects |", "|---|---:|"]
        rows = s.execute(
            select(m.Defect.component_id, func.count())
            .group_by(m.Defect.component_id)
            .order_by(func.count().desc(), m.Defect.component_id)
            .limit(10)
        ).all()
        lines += [f"| {c} | {n} |" for c, n in rows]

        lines += ["", "## Defects by severity", "", "| Severity | Defects |", "|---|---:|"]
        sev_rows = s.execute(
            select(m.Defect.severity, func.count()).group_by(m.Defect.severity).order_by(m.Defect.severity)
        ).all()
        lines += [f"| {sev} | {n} |" for sev, n in sev_rows]
    return "\n".join(lines) + "\n"
