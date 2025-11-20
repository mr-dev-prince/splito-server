import sys
import os
from logging.config import fileConfig

from sqlalchemy import pool
from alembic import context

# Fix PYTHONPATH so Alembic can import app/*
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.db.session import Base
import app.models.user  # import ALL models here
import app.models.group
import app.models.group_member

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


config = context.config

# Disable logging if it throws errors
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
