import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use real metadata from project models
from infrastructure.models import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_database_url():
    """Get database URL from environment variable or .env file"""
    # Try to get from environment variable
    database_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE__URL")

    # If not found, try to load from .env file
    if not database_url:
        from dotenv import load_dotenv

        load_dotenv()
        database_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE__URL")

    # Fallback to a default SQLite (async) database for development
    if not database_url:
        database_url = "sqlite+aiosqlite:///./app.db"
        print(f"Warning: DATABASE_URL not found, using default (async): {database_url}")

    return database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with AsyncEngine.

    Fix: ensure we pass a synchronous function into `connection.run_sync`.
    The previous implementation defined `do_run_migrations` as `async def`,
    which caused "coroutine was never awaited" and resulted in empty revisions.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    def do_run_migrations(connection):
        # Helpful compare options for autogenerate
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=(connection.dialect.name == "sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()

    import asyncio

    async def run():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
