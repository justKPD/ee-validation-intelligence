from __future__ import annotations

import os

import ee_provenance.models  # noqa: F401  (registers agentic-layer tables on Base.metadata)
from alembic import context
from ee_domain.models import Base
from sqlalchemy import engine_from_config, pool

config = context.config
if os.environ.get("EE_DATABASE_URL") and not config.attributes.get("url_locked"):
    config.set_main_option("sqlalchemy.url", os.environ["EE_DATABASE_URL"])

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
