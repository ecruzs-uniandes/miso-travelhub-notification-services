import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://travelhub_app:localpass@localhost:5432/travelhub_notifications?ssl=disable",
)

from app.database import Base  # noqa: E402
import app.models  # noqa: E402, F401

target_metadata = Base.metadata


# Use a service-specific version_table so we can coexist with other services
# in the same shared database (e.g. user-services in dev/prod uses default
# alembic_version on the same `travelhub` database).
VERSION_TABLE = os.getenv("ALEMBIC_VERSION_TABLE", "alembic_version_notification")


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
