"""
Alembic Environment Configuration
Database migration environment setup (SYNC for Alembic)
"""

import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import settings and Base
from app.core.config import settings
from app.core.database import Base

# Import ALL models for autogenerate
from app.models import (
    lead,
    campaign,
    user,
    scraping_job,
    email_log,
    audit_log,
    webhook_delivery
)

# Alembic Config
config = context.config

# Logging config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set DB URL (SYNC)
config.set_main_option(
    "sqlalchemy.url",
    settings.get_database_url_sync()
)

# Metadata for autogenerate
target_metadata = Base.metadata


# ---------------------------
# OFFLINE MODE
# ---------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------
# ONLINE MODE (SYNC ENGINE)
# ---------------------------
def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = create_engine(
        settings.get_database_url_sync(),
        poolclass=pool.NullPool,
        pool_pre_ping=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------
# ENTRY POINT
# ---------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()