"""Generator-independent import: files -> Pydantic validation -> DQ -> single transaction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ee_domain import models
from ee_domain.schemas import DATASET_FILES
from ee_domain.telemetry import tracer
from pydantic import ValidationError
from sqlalchemy import Engine, delete, insert
from sqlalchemy.orm import Session

from ee_etl.quality import QualityReport, run_quality_checks

_MODEL_BY_FILE = dict(
    zip([f for f, _ in DATASET_FILES], models.AUTHORITATIVE_TABLES_IN_LOAD_ORDER, strict=True)
)


class DataQualityError(Exception):
    def __init__(self, messages: list[str]):
        super().__init__("; ".join(messages))
        self.messages = messages


@dataclass
class ImportResult:
    manifest: dict[str, Any]
    counts: dict[str, int]
    quality: QualityReport


def read_dataset(
    dataset_dir: Path, verify_checksums: bool = True
) -> tuple[dict[str, list[Any]], dict[str, Any]]:
    manifest_path = dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    data: dict[str, list[Any]] = {}
    errors: list[str] = []
    for name, dto in DATASET_FILES:
        raw = (dataset_dir / f"{name}.json").read_bytes()
        expected = manifest.get("sha256", {}).get(name)
        if verify_checksums and expected and hashlib.sha256(raw).hexdigest() != expected:
            errors.append(f"{name}: checksum mismatch with manifest")
        rows = []
        for i, obj in enumerate(json.loads(raw)):
            try:
                rows.append(dto.model_validate(obj))
            except ValidationError as exc:
                errors.append(f"{name}[{i}]: {exc.errors()[0]['loc']} {exc.errors()[0]['msg']}")
        data[name] = rows
    if errors:
        raise DataQualityError(errors)
    return data, manifest


def load_dataset(dataset_dir: Path, engine: Engine, enforce_size_targets: bool = True) -> ImportResult:
    with tracer("ee_etl").start_as_current_span("etl.load_dataset"):
        data, manifest = read_dataset(dataset_dir)
        quality = run_quality_checks(data, enforce_size_targets=enforce_size_targets)
        if not quality.ok:
            raise DataQualityError(quality.errors)
        with Session(engine) as session, session.begin():
            for model in reversed(models.AUTHORITATIVE_TABLES_IN_LOAD_ORDER):
                session.execute(delete(model))
            for name, _ in DATASET_FILES:
                rows = [r.model_dump() for r in data[name]]
                if rows:
                    session.execute(insert(_MODEL_BY_FILE[name]), rows)
        return ImportResult(manifest=manifest, counts={k: len(v) for k, v in data.items()}, quality=quality)
