from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from jobradar.adapters.persistence.db import CONNECT_TIMEOUT_SECONDS
from jobradar.adapters.persistence.models import Base
from jobradar.config import get_settings

config = context.config

# Use the [loggers] sections of alembic.ini for Alembic's console output.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate compares the database against this metadata, so it only sees
# tables whose model classes have been imported; models/__init__.py imports
# every one of them.
target_metadata = Base.metadata

# Same source as the app: real environment variables first, then .env.
database_url = str(get_settings().database_url)


# Offline mode (alembic upgrade head --sql): prints the SQL without connecting.
def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# Online mode (the default): connects and applies the migrations.
def run_migrations_online() -> None:
    # NullPool: a one-shot process has no use for a connection pool.
    connectable = create_engine(
        database_url,
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Server defaults are not compared unless asked, so autogenerate
            # and alembic check would miss a default that differs. Neither
            # compares a check constraint's condition nor a partial index's
            # WHERE; tests/integration/test_migrations.py covers those.
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
