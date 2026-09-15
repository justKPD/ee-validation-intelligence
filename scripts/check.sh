#!/usr/bin/env bash
# Runs exactly what CI runs: lint, format check, type check, tests.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff check .
uv run ruff format --check .
uv run mypy packages apps/api/ee_api data/generator/ee_generator
uv run pytest
