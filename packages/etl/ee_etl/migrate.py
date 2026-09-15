from __future__ import annotations

from alembic import command
from alembic.config import Config
from ee_domain.db import REPO_ROOT


def alembic_config(url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def upgrade_head(url: str) -> None:
    command.upgrade(alembic_config(url), "head")
